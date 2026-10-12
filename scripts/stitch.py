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
under the voice with sidechaincompress; optional soft whooshes on hard cuts and a pencil scribble
under the stings; then loudnorm. Run it with the plugin venv (numpy), e.g. via scripts/ww stitch.
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
            sfx_dir = ROOT / ".cache" / "sfx"
            if not (sfx_dir / "whoosh.wav").exists():
                run([sys.executable, str(ROOT / "scripts" / "music.py"), "sfx", "-o", str(sfx_dir)])
            whoosh, scribble = read_wav(sfx_dir / "whoosh.wav"), read_wav(sfx_dir / "scribble.wav")
            for k, s in enumerate(segs):
                if s["id"] == "_intro":
                    place(fx, scribble, s["start"] + 0.62, -20)
                elif s["id"] == "_outro":
                    place(fx, scribble, s["start"] + 0.45, -22)
                    if k > 0:
                        place(fx, whoosh, max(0, s["start"] - 0.35), -26)
                elif k > 0 and s.get("transition", "cut") == "cut":
                    place(fx, whoosh, max(0, s["start"] - 0.35), -26)
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
        if bed:
            ins += ["-i", str(bed)]
            fc = (f"[0:a]asplit=2[n1][n2];"
                  f"[2:a]volume={snd['music_db']}dB[m];"
                  f"[m][n2]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=450:makeup=1[md];"
                  f"[n1][md][1:a]amix=inputs=3:normalize=0:duration=first,"
                  f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample={SR}[out]")
        else:
            fc = f"[0:a][1:a]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11,aresample={SR}[out]"
        run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", fc, "-map", "[out]",
             "-t", f"{vtotal:.3f}", str(mix)])

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
