#!/usr/bin/env python3
"""Render scenes one file at a time, cache by content hash, and extract review frames.

  render.py hook squares            # render these scene ids (workspace/scenes/<id>.py)
  render.py --all -j 3              # every scene in plan.json that changed, 3 at a time
  render.py hook --draft            # 480p for a fast look; final renders are 1080p30
  render.py --stings                # brand intro/outro → workspace/renders/_intro.mp4, _outro.mp4
  render.py --probe 42.5            # what is on screen at 42.5 s of out/video.mp4 (for refine)

Per scene it writes:
  renders/<id>.mp4 + renders/<id>.json   (hash, duration, quality)
  frames/<id>_1.jpg … and frames/<id>_sheet.jpg   (look at the sheet!)
  logs/<id>.render.log                   (full manim output; on failure the traceback is printed)
  logs/<id>.layout.json                  (written by WaitwhatScene: overlapping / off-frame text)

A scene is skipped when its code, shared code, style lib and narration timing are unchanged, so a
refine re-renders only what it touched. Exit code 1 if any scene failed.
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
    for p in [*code_files, LIB / "waitwhat_style.py", ws / "audio" / f"{sid}.json"]:
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
            h.update(json.dumps([pal, entry], sort_keys=True).encode())
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
                        "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "3", str(out)], check=False)
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


def summarize_failure(log: str) -> str:
    text = ANSI.sub("", log)
    lines = [re.sub(r"[│╭╮╰╯─━┃]+", " ", l).rstrip() for l in text.splitlines()]
    lines = [l for l in lines if l.strip()]
    idx = max((i for i, l in enumerate(lines) if "Traceback" in l), default=max(0, len(lines) - 40))
    tail = lines[idx:][-45:]
    return "\n".join(tail)


def render_one(ws: Path, sid: str, quality: str, fps: int, force: bool, nframes: int) -> dict:
    src = ws / "scenes" / f"{sid}.py"
    if not src.exists():
        return {"id": sid, "ok": False, "error": f"missing {src}"}
    h = content_hash(ws, sid, quality, fps)
    meta_f, mp4_out = ws / "renders" / f"{sid}.json", ws / "renders" / f"{sid}.mp4"
    if not force and meta_f.exists() and mp4_out.exists():
        try:
            if json.loads(meta_f.read_text()).get("hash") == h:
                return {"id": sid, "ok": True, "skipped": True, "duration": ffprobe_duration(mp4_out)}
        except Exception:
            pass
    cls = scene_class(src)
    media = ws / ".media" / sid
    shutil.rmtree(media, ignore_errors=True)
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
    (ws / "renders").mkdir(parents=True, exist_ok=True)
    shutil.copy2(produced[-1], mp4_out)
    shutil.rmtree(media, ignore_errors=True)
    dur = ffprobe_duration(mp4_out)
    meta_f.write_text(json.dumps({"hash": h, "duration": dur, "quality": quality, "fps": fps,
                                  "class": cls, "rendered_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))
    res = {"id": sid, "ok": True, "seconds": round(time.time() - t0, 1), "duration": round(dur, 2)}
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
    if nframes:
        frames, sheet = extract_frames(ws, sid, mp4_out, nframes)
        res["sheet"] = sheet
    return res


def render_stings(ws: Path) -> dict:
    src = (LIB / "waitwhat_style.py").read_bytes()
    key = hashlib.sha256(src).hexdigest()[:12]
    cache = ROOT / ".cache" / "stings" / key
    if not (cache / "Intro.mp4").exists() or not (cache / "Outro.mp4").exists():
        cache.mkdir(parents=True, exist_ok=True)
        f = cache / "sting.py"
        f.write_text("from waitwhat_style import *\n\nclass Intro(WaitwhatIntro):\n    pass\n\n"
                     "class Outro(WaitwhatOutro):\n    pass\n")
        proc = subprocess.run([str(VENV_BIN / "manim"), "render", "-qh", "--fps", "30", "--disable_caching",
                               "--media_dir", str(cache / "media"), str(f), "Intro", "Outro"],
                              cwd=cache, env=toolchain_env(ws), capture_output=True, text=True)
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
    ap.add_argument("--draft", action="store_true", help="480p (quality l)")
    ap.add_argument("--quality", choices=list(QUALITY), default="h")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--frames", type=int, default=3, help="review frames per scene (0 = none)")
    ap.add_argument("-j", "--jobs", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
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
    quality = "l" if a.draft else a.quality
    failed = False
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        futs = {pool.submit(render_one, ws, sid, quality, a.fps, a.force, a.frames): sid for sid in ids}
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
