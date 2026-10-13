#!/usr/bin/env python3
"""Render scenes one file at a time, cache by content hash, and extract review frames.

  render.py hook squares            # final 1080p30 renders of these scene ids (workspace/scenes/<id>.py)
  render.py hook --preview          # fast 480p15 preview for checking frames (≈2-3x faster); --draft = same
  render.py --all -j 4              # final renders of every scene in plan.json that changed, 4 at a time
  render.py --stings                # brand intro/outro → workspace/renders/_intro.mp4, _outro.mp4
  render.py --probe 42.5            # what is on screen at 42.5 s of out/video.mp4 (for refine)

Per scene it writes:
  renders/<id>.mp4 + renders/<id>.json   (hash, duration, quality); previews go to previews/ instead,
  renders/<id>.cues.json                 sound-effect cues the scene logged (mixed by stitch.py)
                                         so a preview never replaces a final render
  frames/<id>_1.jpg … and frames/<id>_sheet.jpg   (look at the sheet! from the latest render, either kind)
  logs/<id>.render.log                   (full manim output; on failure the traceback is printed)
  logs/<id>.layout.json                  (written by WaitwhatScene: overlapping / off-frame text)

A scene is skipped when its code, shared code, style lib and narration timing are unchanged, so a
refine re-renders only what it touched. Exit code 1 if any scene failed.

Narration timing: while `ww tts` is still voicing a scene (workspace/audio/<id>.pending), rendering
that scene waits for its audio (up to --wait-audio seconds), so scene code can be written in
parallel with the voice. Without audio the lib estimates timings from the plan's narration (fine
for a preview, never for a final render: the result carries a warning).
-j defaults to WAITWHAT_RENDER_JOBS, else max(2, cores - 2).
Stdlib only; it finds manim in the plugin's .venv.
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "skills" / "manim-scenes" / "lib"
VENV_BIN = ROOT / ".venv" / "bin"
QUALITY = {"h": "-qh", "m": "-qm", "l": "-ql"}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def toolchain_env(ws: Path, scene_id: str | None = None) -> dict:
    env = dict(os.environ)
    path = [str(VENV_BIN)]
    texbin = ROOT / ".venv" / "texbin"
    if texbin.exists():
        path.append(texbin.read_text().strip())
    env["PATH"] = os.pathsep.join(path + [env.get("PATH", "")])
    env["PYTHONPATH"] = os.pathsep.join([str(LIB), str(ws / "scenes"), env.get("PYTHONPATH", "")])
    env["WAITWHAT_ROOT"] = str(ROOT)
    env["WAITWHAT_WORKSPACE"] = str(ws)
    env.setdefault("PYTHONWARNINGS", "ignore::SyntaxWarning")
    if scene_id:
        env["WAITWHAT_SCENE_ID"] = scene_id
    return env


def ensure_toolchain():
    if not (VENV_BIN / "manim").exists():
        print("render: toolchain missing → running setup.sh", file=sys.stderr)
        subprocess.run([str(ROOT / "scripts" / "setup.sh")], check=True)


def scene_class(path: Path) -> str:
    tree = ast.parse(path.read_text())
    names = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = [getattr(b, "id", getattr(b, "attr", "")) for b in node.bases]
            if any("Scene" in b or b in ("WaitwhatIntro", "WaitwhatOutro") for b in bases):
                names.append(node.name)
    if not names:
        raise SystemExit(f"render: no Scene subclass in {path}")
    return names[-1]


def content_hash(ws: Path, sid: str, quality: str, fps: int) -> str:
    """Hash of everything that can change this scene's pixels.

    The plan only contributes this scene's entry and the palette colours its code mentions, so
    adding a concept colour or editing another scene doesn't force a re-render.
    """
    h = hashlib.sha256()
    h.update(f"{quality}{fps}".encode())
    code_files = [ws / "scenes" / f"{sid}.py", *sorted((ws / "scenes").glob("shared*.py"))]
    code_text = ""
    for p in [*code_files, *sorted(LIB.glob("*.py")), ws / "audio" / f"{sid}.json"]:
        if p.exists():
            data = p.read_bytes()
            h.update(data)
            if p in code_files:
                code_text += data.decode(errors="ignore")
    plan_f = ws / "plan.json"
    if plan_f.exists():
        try:
            plan = json.loads(plan_f.read_text())
            pal = {k: v for k, v in (plan.get("palette") or {}).items()
                   if f'"{k}"' in code_text or f"'{k}'" in code_text}
            entry = [s for s in plan.get("scenes", []) if s.get("id") == sid]
            # the theme repaints every pixel; the title seeds its background texture
            look = [plan.get("theme"), plan.get("title") if plan.get("theme") else None,
                    os.environ.get("WAITWHAT_THEME")]
            h.update(json.dumps([pal, entry, look], sort_keys=True).encode())
        except Exception:
            h.update(plan_f.read_bytes())
    return h.hexdigest()[:16]


def ffprobe_duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def extract_frames(ws: Path, sid: str, mp4: Path, n: int, extra: list[float] | None = None) -> tuple[list[str], str]:
    """Review frames (≤960 px wide) and a vertical contact sheet."""
    fdir = ws / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    for old in fdir.glob(f"{sid}_*.jpg"):
        old.unlink()
    dur = ffprobe_duration(mp4)
    times = [dur * f for f in ([0.5] if n == 1 else [0.12 + 0.76 * i / (n - 1) for i in range(n)])]
    times = sorted(set(round(t, 2) for t in times + (extra or []) if 0 <= t < dur))
    frames = []
    for i, t in enumerate(times, start=1):
        out = fdir / f"{sid}_{i}.jpg"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(mp4),
                        "-frames:v", "1", "-vf", "scale='min(960,iw)':-2", "-q:v", "3", str(out)], check=False)
        if out.exists():
            frames.append(str(out))
    sheet = fdir / f"{sid}_sheet.jpg"
    if frames:
        ins = sum([["-i", f] for f in frames], [])
        # label each tile with its timestamp is not possible without drawtext everywhere; order = time
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex",
                        f"{''.join(f'[{i}]pad=iw:ih+8:0:0:0x333333[p{i}];' for i in range(len(frames)))}"
                        f"{''.join(f'[p{i}]' for i in range(len(frames)))}vstack=inputs={len(frames)}"
                        if len(frames) > 1 else "null", "-q:v", "3", str(sheet)], check=False)
    return frames, str(sheet)


def default_jobs() -> int:
    try:
        n = int(os.environ.get("WAITWHAT_RENDER_JOBS", "") or 0)
    except ValueError:
        n = 0
    return n if n > 0 else max(2, (os.cpu_count() or 4) - 2)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return pid > 0


def wait_for_audio(ws: Path, sid: str, timeout: float) -> float:
    """Wait while `ww tts` is voicing this scene (audio/<id>.pending holds a live pid). → seconds waited."""
    m = ws / "audio" / f"{sid}.pending"
    t0 = time.time()
    said = False
    while m.exists() and time.time() - t0 < timeout:
        try:
            if not _pid_alive(int(m.read_text().strip() or 0)):
                break
        except (ValueError, OSError):
            break
        if not said:
            print(f"render: waiting for the narration audio of '{sid}' (ww tts is voicing it)…", file=sys.stderr, flush=True)
            said = True
        time.sleep(0.5)
    return round(time.time() - t0, 1)


_TAGS = re.compile(r"<\s*(bookmark|break)\b[^>]*/\s*>", re.I)


def audio_note(ws: Path, sid: str) -> str | None:
    """A warning when the scene's narration timing is missing or older than its narration."""
    try:
        plan = json.loads((ws / "plan.json").read_text())
        sc = next((x for x in plan.get("scenes", []) if x.get("id") == sid), None)
    except Exception:
        return None
    if sc is None or not (sc.get("narration") or "").strip():
        return None
    af = ws / "audio" / f"{sid}.json"
    if not af.exists():
        return "no narration audio yet: timing is ESTIMATED from the plan. Run `ww tts`, then re-render before the final cut"
    try:
        said = json.loads(af.read_text()).get("text", "")
    except Exception:
        return "unreadable narration timing file"
    want = re.sub(r"\s+", " ", _TAGS.sub(" ", sc["narration"])).strip()
    if said and said != want:
        return "the narration in plan.json changed since this audio was voiced: run `ww tts --scene " + sid + "`"
    return None


def summarize_failure(log: str) -> str:
    text = ANSI.sub("", log)
    lines = [re.sub(r"[│╭╮╰╯─━┃]+", " ", l).rstrip() for l in text.splitlines()]
    lines = [l for l in lines if l.strip()]
    idx = max((i for i, l in enumerate(lines) if "Traceback" in l), default=max(0, len(lines) - 40))
    tail = lines[idx:][-45:]
    return "\n".join(tail)


def render_one(ws: Path, sid: str, quality: str, fps: int, force: bool, nframes: int,
               preview: bool = False, wait_audio: float = 600) -> dict:
    src = ws / "scenes" / f"{sid}.py"
    if not src.exists():
        return {"id": sid, "ok": False, "error": f"missing {src}"}
    waited = wait_for_audio(ws, sid, wait_audio) if wait_audio > 0 else 0.0
    note = audio_note(ws, sid)
    h = content_hash(ws, sid, quality, fps)
    out_dir = ws / ("previews" if preview else "renders")
    meta_f, mp4_out = out_dir / f"{sid}.json", out_dir / f"{sid}.mp4"
    if not force and meta_f.exists() and mp4_out.exists():
        try:
            if json.loads(meta_f.read_text()).get("hash") == h:
                res = {"id": sid, "ok": True, "skipped": True, "duration": ffprobe_duration(mp4_out)}
                if preview:
                    res["preview"] = True
                if note:
                    res["warning"] = note
                return res
        except Exception:
            pass
    cls = scene_class(src)
    media = ws / ".media" / sid
    shutil.rmtree(media, ignore_errors=True)
    (ws / "logs" / f"{sid}.cues.json").unlink(missing_ok=True)
    cmd = [str(VENV_BIN / "manim"), "render", QUALITY[quality], "--fps", str(fps), "--disable_caching",
           "--media_dir", str(media), "-o", sid, str(src), cls]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ws, env=toolchain_env(ws, sid), capture_output=True, text=True)
    (ws / "logs").mkdir(parents=True, exist_ok=True)
    log = proc.stdout + "\n" + proc.stderr
    (ws / "logs" / f"{sid}.render.log").write_text(ANSI.sub("", log))
    produced = sorted(media.glob(f"videos/**/{sid}.mp4"), key=lambda p: p.stat().st_mtime)
    if proc.returncode != 0 or not produced:
        err = summarize_failure(log)
        tex_logs = sorted(media.glob("Tex/*.log"), key=lambda p: p.stat().st_mtime)
        if "latex error" in log.lower() and tex_logs:
            lines = tex_logs[-1].read_text(errors="ignore").splitlines()
            bang = [i for i, l in enumerate(lines) if l.startswith("!")]
            if bang:
                err += "\n\nLaTeX says:\n" + "\n".join(lines[bang[0]:bang[0] + 4])
        return {"id": sid, "ok": False, "seconds": round(time.time() - t0, 1), "error": err}
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(produced[-1], mp4_out)
    cues_src, cues_out = ws / "logs" / f"{sid}.cues.json", out_dir / f"{sid}.cues.json"
    if cues_src.exists():  # sound-effect cues logged by the scene, mixed by stitch.py
        shutil.copy2(cues_src, cues_out)
    else:
        cues_out.unlink(missing_ok=True)
    shutil.rmtree(media, ignore_errors=True)
    dur = ffprobe_duration(mp4_out)
    meta_f.write_text(json.dumps({"hash": h, "duration": dur, "quality": quality, "fps": fps,
                                  "class": cls, "rendered_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))
    res = {"id": sid, "ok": True, "seconds": round(time.time() - t0, 1), "duration": round(dur, 2)}
    if preview:
        res["preview"] = True
    if waited >= 1:
        res["waited_for_audio"] = waited
    lay = ws / "logs" / f"{sid}.layout.json"
    if lay.exists():
        try:
            L = json.loads(lay.read_text())
            res["layout_issues"] = L.get("issues", [])[:8]
            if L.get("missing_marks"):
                res["missing_marks"] = L["missing_marks"]
            if L.get("narration_end") and dur + 0.05 < L["narration_end"]:
                res["warning"] = f"video ({dur:.1f}s) is shorter than its narration ({L['narration_end']:.1f}s); call self.finish()"
        except Exception:
            pass
    try:
        res["sfx_cues"] = len(json.loads(cues_out.read_text())["cues"]) if cues_out.exists() else 0
    except Exception:
        pass
    if note:
        res["warning"] = f"{res['warning']}; {note}" if res.get("warning") else note
    if nframes:
        frames, sheet = extract_frames(ws, sid, mp4_out, nframes)
        res["sheet"] = sheet
    return res


def render_stings(ws: Path) -> dict:
    src = (LIB / "waitwhat_style.py").read_bytes()
    key = hashlib.sha256(src).hexdigest()[:12]
    env = toolchain_env(ws)
    env["WAITWHAT_THEME"] = "classic"  # the brand stings are always on black
    cache = ROOT / ".cache" / "stings" / key
    if not (cache / "Intro.mp4").exists() or not (cache / "Outro.mp4").exists():
        cache.mkdir(parents=True, exist_ok=True)
        f = cache / "sting.py"
        f.write_text("from waitwhat_style import *\n\nclass Intro(WaitwhatIntro):\n    pass\n\n"
                     "class Outro(WaitwhatOutro):\n    pass\n")
        proc = subprocess.run([str(VENV_BIN / "manim"), "render", "-qh", "--fps", "30", "--disable_caching",
                               "--media_dir", str(cache / "media"), str(f), "Intro", "Outro"],
                              cwd=cache, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            return {"ok": False, "error": summarize_failure(proc.stdout + proc.stderr)}
        for name in ("Intro", "Outro"):
            shutil.copy2(next(cache.glob(f"media/videos/**/{name}.mp4")), cache / f"{name}.mp4")
        shutil.rmtree(cache / "media", ignore_errors=True)
    (ws / "renders").mkdir(parents=True, exist_ok=True)
    shutil.copy2(cache / "Intro.mp4", ws / "renders" / "_intro.mp4")
    shutil.copy2(cache / "Outro.mp4", ws / "renders" / "_outro.mp4")
    return {"ok": True, "intro": str(ws / "renders" / "_intro.mp4"), "outro": str(ws / "renders" / "_outro.mp4")}


def probe(ws: Path, at: float) -> dict:
    tl_f = ws / "timeline.json"
    if not tl_f.exists():
        raise SystemExit("render: workspace/timeline.json missing (it is written by stitch.py)")
    tl = json.loads(tl_f.read_text())
    seg = next((s for s in tl["segments"] if s["start"] <= at < s["start"] + s["duration"]), tl["segments"][-1])
    if not seg.get("id") or seg["id"].startswith("_"):
        return {"at": at, "segment": seg, "note": "this moment is in the intro/outro sting"}
    local = at - seg["start"]
    sid = seg["id"]
    env = toolchain_env(ws, sid)
    env["WAITWHAT_PROBE_T"] = f"{local:.3f}"
    src = ws / "scenes" / f"{sid}.py"
    out = ws / "logs" / f"{sid}.probe.json"
    out.unlink(missing_ok=True)
    subprocess.run([str(VENV_BIN / "manim"), "render", "-ql", "--dry_run", "--disable_caching", str(src),
                    scene_class(src)], cwd=ws, env=env, capture_output=True, text=True)
    said = []
    af = ws / "audio" / f"{sid}.json"
    if af.exists():
        A = json.loads(af.read_text())
        t_audio = local - A.get("lead_in", 0.35)
        said = [w["w"] for w in A.get("words", []) if t_audio - 4.0 <= w["start"] <= t_audio + 1.5]
    res = {"at": at, "scene": sid, "scene_index": seg.get("index"), "local_t": round(local, 2),
           "narration_near": " ".join(said)}
    if out.exists():
        res["on_screen"] = json.loads(out.read_text())["mobjects"]
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--ws", default="workspace")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--preview", "--draft", dest="preview", action="store_true",
                    help="fast 480p15 preview into previews/ (frames + sheet as usual); final renders stay 1080p30")
    ap.add_argument("--quality", choices=list(QUALITY), default="h")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--frames", type=int, default=3, help="review frames per scene (0 = none)")
    ap.add_argument("-j", "--jobs", type=int, default=default_jobs(),
                    help="scenes rendered in parallel (default WAITWHAT_RENDER_JOBS, else max(2, cores-2))")
    ap.add_argument("--wait-audio", type=float, default=600, metavar="SECONDS",
                    help="max wait for a scene's audio while ww tts voices it (0 = don't wait)")
    ap.add_argument("--stings", action="store_true")
    ap.add_argument("--probe", type=float, metavar="SECONDS")
    a = ap.parse_args()
    ws = Path(a.ws).resolve()
    ensure_toolchain()

    if a.probe is not None:
        print(json.dumps(probe(ws, a.probe), indent=1))
        return
    if a.stings:
        print(json.dumps(render_stings(ws)))
        if not a.ids and not a.all:
            return
    ids = list(a.ids)
    if a.all:
        plan = json.loads((ws / "plan.json").read_text())
        ids = [s["id"] for s in plan.get("scenes", [])]
    if not ids:
        ap.error("give scene ids, --all, --stings or --probe")
    quality = "l" if a.preview else a.quality
    fps = 15 if a.preview and a.fps == 30 else a.fps
    failed = False
    with cf.ThreadPoolExecutor(max_workers=max(1, min(a.jobs, len(ids)))) as pool:
        futs = {pool.submit(render_one, ws, sid, quality, fps, a.force, a.frames, a.preview, a.wait_audio): sid
                for sid in ids}
        for fut in cf.as_completed(futs):
            r = fut.result()
            failed |= not r["ok"]
            if r["ok"]:
                print(json.dumps(r))
            else:
                print(f"\n✗ {r['id']} FAILED\n{r.get('error', '')}\n", file=sys.stderr)
                print(json.dumps({"id": r["id"], "ok": False}))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
