#!/usr/bin/env python3
"""Assemble the final video and the job outputs required by the contract.

  stitch.py                      # run from the job dir
  stitch.py --job DIR --no-intro --music curious

Reads workspace/plan.json, renders/<id>.mp4, audio/<id>.{wav,json}; writes
  out/video.mp4        1920x1080 30 fps, h264 + aac, loudness-normalised (-16 LUFS, -1.5 dBTP)
  out/thumbnail.jpg    1280x720 (workspace/thumbnail.png if the agent made one, else a chosen frame)
  out/manifest.json    {title, scenes:[{index,title,narration,start,duration}]}
  workspace/timeline.json   segment start/duration per scene id (used by refine and render --probe)

Audio: narration placed at each scene's start + lead_in; a music bed (procedural, or a file) ducked
under the voice with sidechaincompress; sound effects (see below) on their own bus, also ducked
under the voice; then loudnorm. Run it with the plugin venv (numpy), e.g. via scripts/ww stitch.

Sound effects come from the curated library in assets/sfx (library.json: several takes per sound,
loudness-matched, with the onset of each take). The cues are the ones each scene logged against
its own clock (renders/<id>.cues.json: appear → pop, write → pencil/chalk/marker, erase → eraser,
plus explicit ones like coin or chime), plus a whoosh on hard cuts and chalk under the intro sting.
Each cue lands its take's onset on the event; takes rotate (never the same take twice in a row)
with a little pitch and level variation; automatic cues are thinned so the track never gets busy
(automatic cues: none within 0.6 s of another cue, at most one other within 1.25 s and two within
2.5 s, textures never overlap; chosen cues: at most 6 within 1.25 s). What was
placed and dropped is logged to workspace/logs/sfx.json.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
W, H, FPS = 1920, 1080, 30
TAG = re.compile(r"<\s*(bookmark|break)\b[^>]*/\s*>", re.I)


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"stitch: command failed:\n{' '.join(cmd)}\n{p.stderr[-2500:]}")


def ffprobe(p: Path, entries: str = "format=duration") -> str:
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "default=nw=1:nk=1", str(p)],
                          capture_output=True, text=True).stdout.strip()


def duration(p: Path) -> float:
    try:
        return float(ffprobe(p).splitlines()[0])
    except (ValueError, IndexError):
        return 0.0


def read_wav(p: Path) -> np.ndarray:
    """→ float stereo at SR (resampled with ffmpeg if needed)."""
    with wave.open(str(p)) as w:
        ok = w.getframerate() == SR and w.getsampwidth() == 2
        if ok:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
            x = x.reshape(-1, w.getnchannels())
    if not ok:
        with tempfile.TemporaryDirectory() as td:
            q = Path(td) / "r.wav"
            run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(p), "-ar", str(SR), "-sample_fmt", "s16", str(q)])
            return read_wav(q)
    return np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x[:, :2]


def write_wav(p: Path, x: np.ndarray) -> None:
    """Writes stereo s16 in chunks, so an hour-long track never needs extra full-size copies."""
    step = SR * 30
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        for i in range(0, len(x), step):
            c = np.clip(x[i:i + step], -1, 1)
            if c.shape[1] == 1:
                c = np.repeat(c, 2, axis=1)
            w.writeframes((c * 32767).astype("<i2").tobytes())


def place(track: np.ndarray, clip: np.ndarray, at: float, gain_db: float = 0.0) -> None:
    i = int(round(at * SR))
    if i >= len(track):
        return
    n = min(len(clip), len(track) - i)
    if track.shape[1] == 1 and clip.shape[1] != 1:
        clip = clip[:n].mean(axis=1, keepdims=True)
    track[i:i + n] += clip[:n] * (10 ** (gain_db / 20))


class SfxLibrary:
    """assets/sfx/library.json + decoded takes (mono float32 at SR), loaded lazily."""

    def __init__(self, root: Path):
        self.dir = root / "assets" / "sfx"
        f = self.dir / "library.json"
        self.sounds = json.loads(f.read_text()).get("sounds", {}) if f.exists() else {}
        self._audio: dict[str, np.ndarray] = {}
        self._last: dict[str, int] = {}

    def __bool__(self) -> bool:
        return bool(self.sounds)

    def audio(self, file: str) -> np.ndarray:
        if file not in self._audio:
            self._audio[file] = read_wav(self.dir / file)[:, :1]
        return self._audio[file]

    def pick(self, name: str, rng: np.random.Generator) -> dict | None:
        """A take of `name`, never the same one twice in a row."""
        snd = self.sounds.get(name)
        if not snd:
            return None
        n = len(snd["takes"])
        choices = [i for i in range(n) if i != self._last.get(name)] or list(range(n))
        i = int(rng.choice(choices))
        self._last[name] = i
        return snd["takes"][i]


def fit_texture(x: np.ndarray, target: float) -> np.ndarray:
    """Trim (with a fade) or loop (with crossfades) a texture take to `target` seconds."""
    n = int(target * SR)
    xf = int(0.05 * SR)
    if len(x) >= n:
        y = x[:n].copy()
    else:
        y = x.copy()
        while len(y) < n:
            fade = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
            head = y[-xf:] * (1 - fade) + x[:xf] * fade
            y = np.concatenate([y[:-xf], head, x[xf:]])
        y = y[:n]
    fo = min(int(0.08 * SR), len(y) // 3)
    if fo > 0:
        y[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    return y


def varispeed(x: np.ndarray, r: float) -> np.ndarray:
    """Resample by r (r > 1 = higher and shorter): a little natural variation between repeats."""
    if abs(r - 1) < 1e-3 or len(x) < 4:
        return x
    idx = np.arange(0, len(x) - 1, r)
    return np.interp(idx, np.arange(len(x)), x[:, 0]).astype(np.float32)[:, None]


def thin_cues(cues: list[dict]) -> tuple[list[dict], list[dict]]:
    """Density limit. Structural cues (cut whooshes) and explicit cues win over automatic ones;
    automatic cues need 0.6 s of space around them, at most one other cue within 1.25 s and two
    within 2.5 s, and
    textures (writing, typing, erasing) never overlap each other. Even chosen cues are capped
    (0.18 s between repeats of one sound, at most 6 within 1.25 s)."""
    kept: list[dict] = []
    dropped: list[dict] = []
    for c in sorted(cues, key=lambda c: (-c["prio"], c["at"])):
        auto = c["prio"] <= 1
        why = None
        for k in kept:
            g = 0.6 if auto or k["prio"] <= 1 else (0.18 if k["name"] == c["name"] else 0.1)
            if abs(k["at"] - c["at"]) < g:
                why = f"too close to {k['name']}"
                break
            if auto and c.get("dur") and k.get("dur") and k["at"] < c["at"] + c["dur"] and c["at"] < k["at"] + k["dur"]:
                why = f"overlaps {k['name']}"
                break
        near = sum(1 for k in kept if abs(k["at"] - c["at"]) < 1.25)
        wide = sum(1 for k in kept if abs(k["at"] - c["at"]) < 2.5)
        if not why and ((near >= 2 or wide >= 3) if auto else near >= 6):
            why = "busy"
        if why:
            dropped.append({**c, "why": why})
        else:
            kept.append(c)
    return sorted(kept, key=lambda c: c["at"]), sorted(dropped, key=lambda c: c["at"])


def build_sfx(segs: list[dict], ws: Path, snd: dict, n: int, title: str) -> np.ndarray:
    """The sound-effects bus (mono) for the whole video, from the scenes' cue files."""
    fx = np.zeros((n, 1), np.float32)
    lib = SfxLibrary(ROOT)
    cues: list[dict] = []
    for k, s in enumerate(segs):
        if s["id"] == "_intro":
            cues.append({"at": s["start"] + 0.05, "name": "chalk", "gain": -3.0, "dur": 1.1, "prio": 3, "scene": "_intro"})
            continue
        if k > 0 and (s["id"] == "_outro" or s.get("transition", "cut") == "cut"):
            cues.append({"at": s["start"], "name": "whoosh", "gain": -1.0, "prio": 3, "scene": s["id"]})
        if s["id"].startswith("_"):
            continue
        f = ws / "renders" / f"{s['id']}.cues.json"
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        for c in data.get("cues", []):
            if c.get("auto") and not snd.get("sfx_auto", True):
                continue
            t = float(c.get("t", 0))
            if t > s["duration"] + 0.05:
                continue
            cues.append({"at": round(s["start"] + t, 3), "name": c.get("name"), "gain": float(c.get("gain", 0)),
                         "dur": c.get("dur"), "prio": 1 if c.get("auto") else 2, "scene": s["id"],
                         "kind": c.get("kind")})
    kept, dropped = thin_cues(cues)
    rng = np.random.default_rng(sum(map(ord, title)) % 100000)
    placed = []
    if lib:
        base_db = float(snd.get("sfx_db", 0.0))
        for c in kept:
            meta = lib.sounds.get(c["name"])
            take = lib.pick(c["name"], rng)
            if not take:
                dropped.append({**c, "why": "not in the library"})
                continue
            x = lib.audio(take["file"])
            r = float(rng.uniform(0.96, 1.04))
            x = varispeed(x, r)
            onset = float(take.get("onset", 0)) / r
            if meta["kind"] == "texture":
                x = fit_texture(x, min(3.0, max(0.25, float(c.get("dur") or len(x) / SR))))
                onset = 0.0
            gain = float(meta.get("gain_db", -16)) + c["gain"] + base_db + float(rng.uniform(-1, 1))
            at = max(0.0, c["at"] - onset)
            place(fx, x, at, gain)
            placed.append({"at": c["at"], "name": c["name"], "take": take["file"], "gain_db": round(gain, 1),
                           "scene": c["scene"], **({"dur": c["dur"]} if c.get("dur") else {}),
                           **({"auto": True} if c["prio"] == 1 else {})})
    else:  # no library: the old procedural whoosh on cuts and scribble under the intro
        sfx_dir = ROOT / ".cache" / "sfx"
        if not (sfx_dir / "whoosh.wav").exists():
            run([sys.executable, str(ROOT / "scripts" / "music.py"), "sfx", "-o", str(sfx_dir)])
        whoosh, scribble = read_wav(sfx_dir / "whoosh.wav"), read_wav(sfx_dir / "scribble.wav")
        for c in kept:
            if c["name"] == "whoosh":
                place(fx, whoosh, max(0, c["at"] - 0.35), -26)
            elif c["scene"] == "_intro":
                place(fx, scribble, c["at"] + 0.57, -20)
    (ws / "logs").mkdir(parents=True, exist_ok=True)
    (ws / "logs" / "sfx.json").write_text(json.dumps({"placed": placed, "dropped": dropped}, indent=1))
    return fx


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub(" ", text or "")).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job", default=".")
    ap.add_argument("--music", help="mood (calm|curious|bright|focus), a file path, or 'none'")
    ap.add_argument("--music-db", type=float, help="bed level before ducking (default -17 dB)")
    ap.add_argument("--no-intro", action="store_true")
    ap.add_argument("--no-outro", action="store_true")
    ap.add_argument("--no-sfx", action="store_true")
    ap.add_argument("--stems", metavar="DIR", help="also save the narration, effects and music stems here (for checking the mix)")
    a = ap.parse_args()

    job = Path(a.job).resolve()
    ws, out = job / "workspace", job / "out"
    out.mkdir(parents=True, exist_ok=True)
    plan = json.loads((ws / "plan.json").read_text())
    snd = {"music": "calm", "music_db": -17.0, "sfx": True, "intro": True, "outro": True, **(plan.get("sound") or {})}
    if a.music:
        snd["music"] = a.music
    if a.music_db is not None:
        snd["music_db"] = a.music_db
    if a.no_intro:
        snd["intro"] = False
    if a.no_outro:
        snd["outro"] = False
    if a.no_sfx:
        snd["sfx"] = False

    # ------------------------------------------------------------------ segments
    if snd["intro"] or snd["outro"]:  # cached by style-lib hash, so this is a copy unless the lib changed
        subprocess.run([sys.executable, str(ROOT / "scripts" / "render.py"), "--ws", str(ws), "--stings"],
                       check=True, stdout=subprocess.DEVNULL)
    segs = []
    if snd["intro"]:
        segs.append({"id": "_intro", "video": ws / "renders" / "_intro.mp4"})
    missing = []
    for i, sc in enumerate(plan["scenes"], start=1):
        v = ws / "renders" / f"{sc['id']}.mp4"
        if not v.exists():
            missing.append(sc["id"])
        segs.append({"id": sc["id"], "index": i, "title": sc.get("title", f"Scene {i}"), "video": v,
                     "audio": ws / "audio" / f"{sc['id']}.wav", "timing": ws / "audio" / f"{sc['id']}.json",
                     "transition": sc.get("transition", "cut"), "narration": plain(sc.get("narration", ""))})
    if missing:
        sys.exit(f"stitch: not rendered yet: {', '.join(missing)} (run render.py)")
    if snd["outro"]:
        segs.append({"id": "_outro", "video": ws / "renders" / "_outro.mp4"})

    t = 0.0
    for s in segs:
        dv = duration(s["video"])
        lead, da = 0.0, 0.0
        if s.get("timing") and s["timing"].exists():
            T = json.loads(s["timing"].read_text())
            lead, da = float(T.get("lead_in", 0.35)), float(T.get("duration", 0))
        s["lead_in"], s["speech"] = lead, da
        s["duration"] = round(max(dv, lead + da + 0.3 if da else dv), 3)
        s["pad"] = max(0.0, s["duration"] - dv)
        s["start"] = round(t, 3)
        t += s["duration"]

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # -------------------------------------------------------------- video
        def encode(k: int, s: dict) -> str:
            seg = tmp / f"seg{k:04d}.mp4"
            vf = (f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
                  f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p")
            if s["pad"] > 0.01:
                vf += f",tpad=stop_mode=clone:stop_duration={s['pad'] + 0.1:.3f}"
            run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(s["video"]), "-vf", vf, "-t", f"{s['duration']:.3f}",
                 "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-r", str(FPS),
                 "-video_track_timescale", "15360", str(seg)])
            return f"file '{seg}'"

        # Segments are independent: encode a few at once (long videos have dozens).
        workers = max(1, min(4, (os.cpu_count() or 2) // 2))
        with cf.ThreadPoolExecutor(max_workers=workers) as pool:
            lst = list(pool.map(lambda ks: encode(*ks), enumerate(segs)))
        (tmp / "list.txt").write_text("\n".join(lst))
        video = tmp / "video.mp4"
        run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
             "-c", "copy", str(video)])
        vtotal = duration(video)

        # -------------------------------------------------------------- narration + sfx tracks
        n = int((vtotal + 0.5) * SR)
        # Mono in memory (narration is mono, the sfx are centred); written out as stereo.
        narr = np.zeros((n, 1), np.float32)
        fx = np.zeros((n, 1), np.float32)
        for s in segs:
            if s.get("audio") and s["audio"].exists():
                place(narr, read_wav(s["audio"]), s["start"] + s["lead_in"])
        if snd["sfx"]:
            fx = build_sfx(segs, ws, snd, n, plan.get("title", "waitwhat"))
        write_wav(tmp / "narr.wav", narr)
        write_wav(tmp / "fx.wav", fx)

        # -------------------------------------------------------------- music bed
        music = str(snd.get("music") or "none")
        bed = None
        if music != "none":
            if Path(music).expanduser().exists():
                bed = tmp / "bed.wav"
                run(["ffmpeg", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", str(Path(music).expanduser()),
                     "-t", f"{vtotal + 0.5:.3f}", "-ar", str(SR), "-ac", "2",
                     "-af", f"afade=t=in:d=2,afade=t=out:st={max(0, vtotal - 3):.3f}:d=3", str(bed)])
            else:
                bed = tmp / "bed.wav"
                seed = sum(map(ord, plan.get("title", "waitwhat"))) % 1000
                run([sys.executable, str(ROOT / "scripts" / "music.py"), "bed", "--mood", music,
                     "--seconds", f"{vtotal + 0.5:.3f}", "--seed", str(seed), "-o", str(bed)])

        # -------------------------------------------------------------- mix + loudness
        mix = tmp / "mix.wav"
        ins = ["-i", str(tmp / "narr.wav"), "-i", str(tmp / "fx.wav")]
        # The effects bus is ducked under the voice too (gently: ~3-6 dB while someone speaks), and
        # kept out of the music's sidechain so a whoosh never pumps the bed.
        fx_duck = "sidechaincompress=threshold=0.04:ratio=3:attack=5:release=250:makeup=1"
        if bed:
            ins += ["-i", str(bed)]
            fc = (f"[0:a]asplit=3[n1][n2][n3];"
                  f"[2:a]volume={snd['music_db']}dB[m];"
                  f"[m][n2]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=450:makeup=1[md];"
                  f"[1:a][n3]{fx_duck}[fd];"
                  f"[n1][md][fd]amix=inputs=3:normalize=0:duration=first,"
                  f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample={SR}[out]")
        else:
            fc = (f"[0:a]asplit=2[n1][n3];[1:a][n3]{fx_duck}[fd];"
                  f"[n1][fd]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11,aresample={SR}[out]")
        run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", fc, "-map", "[out]",
             "-t", f"{vtotal:.3f}", str(mix)])

        if a.stems:
            sd = Path(a.stems)
            sd.mkdir(parents=True, exist_ok=True)
            for name in ("narr.wav", "fx.wav", "bed.wav", "mix.wav"):
                if (tmp / name).exists():
                    shutil.copy2(tmp / name, sd / name)

        final = out / "video.mp4"
        run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-i", str(mix), "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart",
             "-shortest", str(final)])

    # ------------------------------------------------------------------ thumbnail
    thumb = out / "thumbnail.jpg"
    custom = ws / "thumbnail.png"
    scenes = [s for s in segs if not s["id"].startswith("_")]
    if custom.exists():
        run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(custom), "-vf", "scale=1280:720", "-q:v", "2", str(thumb)])
    else:
        tp = plan.get("thumbnail") or {}
        pick = next((s for s in scenes if s["id"] == tp.get("scene")), None)
        if pick is None:
            pick = scenes[min(len(scenes) - 1, max(0, len(scenes) // 2))]
        at = pick["start"] + float(tp.get("t", pick["duration"] * 0.8))
        run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{at:.2f}", "-i", str(out / "video.mp4"),
             "-frames:v", "1", "-vf", "scale=1280:720", "-q:v", "2", str(thumb)])

    # ------------------------------------------------------------------ manifest + timeline
    manifest = {"title": plan.get("title", "waitwhat"),
                "scenes": [{"index": s["index"], "title": s["title"], "narration": s["narration"],
                            "start": s["start"], "duration": s["duration"]} for s in scenes]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    timeline = {"total": round(duration(out / "video.mp4"), 3),
                "segments": [{k: (str(v) if isinstance(v, Path) else v) for k, v in s.items()
                              if k in ("id", "index", "title", "start", "duration", "lead_in", "speech", "transition")}
                             for s in segs]}
    (ws / "timeline.json").write_text(json.dumps(timeline, indent=1))
    shutil.rmtree(ws / ".media", ignore_errors=True)  # render scratch; keeps the archived workspace small

    v = ffprobe(out / "video.mp4", "stream=codec_name,width,height")
    print(json.dumps({"ok": True, "video": str(out / "video.mp4"), "duration": timeline["total"],
                      "streams": v.split(), "thumbnail": str(thumb), "manifest": str(out / "manifest.json")}))


if __name__ == "__main__":
    main()
