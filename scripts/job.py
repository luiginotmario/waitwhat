#!/usr/bin/env python3
"""Create and validate job dirs that follow the waitwhat job I/O contract.

  job.py new "Why is the sky blue?" [--attach a.pdf ...] [--aspect 9:16] [--base ./waitwhat-videos]
        → ./waitwhat-videos/why-is-the-sky-blue/   (prints the path)
  job.py refine ./waitwhat-videos/why-is-the-sky-blue "wait, what is scattering?" --at 42.5 [--frame f.png]
        → ./waitwhat-videos/why-is-the-sky-blue-v2/  with the previous workspace copied in
  job.py check [JOB]      → validates out/ against the contract (exit 1 on problems)
  job.py brief <id>       → a scene builder's brief (its plan entry, neighbours, the arc)
  job.py narrate <id> [--text T | --file F | stdin] [--no-voice]
                          → set one scene's narration in plan.json (locked: parallel builders) and voice it
  job.py script           → the whole narration in order, for a read-through

The worker creates job dirs itself; these commands make local Claude Code use behave the same way.
Stdlib only.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import tempfile
import mimetypes
import re
import shutil
import subprocess
import sys
from pathlib import Path


def slugify(text: str, n: int = 48) -> str:
    s = re.sub(r"https?://(www\.)?", "", text.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:n].rstrip("-") or "video")


def make_dirs(job: Path) -> None:
    for d in ("inputs", "workspace", "out", ".waitwhat"):
        (job / d).mkdir(parents=True, exist_ok=True)


def cmd_new(a) -> None:
    base = Path(a.base).resolve()
    slug = a.slug or slugify(a.prompt)
    job = base / slug
    k = 2
    while job.exists() and any(job.iterdir()):
        job = base / f"{slug}-{k}"; k += 1
    make_dirs(job)
    atts = []
    for f in a.attach or []:
        src = Path(f).expanduser().resolve()
        dst = job / "inputs" / src.name
        shutil.copy2(src, dst)
        atts.append({"path": str(dst.relative_to(job)), "name": src.name,
                     "mime": mimetypes.guess_type(src.name)[0] or "application/octet-stream"})
    req = {"prompt": a.prompt, "attachments": atts}
    if getattr(a, "aspect", None):
        req["aspect"] = a.aspect
    (job / "request.json").write_text(json.dumps(req, indent=1))
    print(job)


def cmd_refine(a) -> None:
    prev = Path(a.job).resolve()
    if not (prev / "workspace" / "plan.json").exists():
        sys.exit(f"job: {prev} has no workspace/plan.json to refine")
    m = re.match(r"(.*)-v(\d+)$", prev.name)
    stem, ver = (m.group(1), int(m.group(2)) + 1) if m else (prev.name, 2)
    job = prev.parent / f"{stem}-v{ver}"
    while job.exists():
        ver += 1; job = prev.parent / f"{stem}-v{ver}"
    make_dirs(job)
    shutil.copytree(prev / "workspace", job / "workspace", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".media"))
    if (prev / "out" / "manifest.json").exists():
        shutil.copy2(prev / "out" / "manifest.json", job / "inputs" / "previous_manifest.json")
    frame_rel = None
    if a.frame:
        src = Path(a.frame).expanduser().resolve()
        dst = job / "inputs" / f"refine_frame{src.suffix or '.png'}"
        shutil.copy2(src, dst)
        frame_rel = str(dst.relative_to(job))
    elif (prev / "out" / "video.mp4").exists():
        dst = job / "inputs" / "refine_frame.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{a.at:.2f}", "-i",
                        str(prev / "out" / "video.mp4"), "-frames:v", "1", str(dst)], check=False)
        frame_rel = str(dst.relative_to(job)) if dst.exists() else None
    req = json.loads((prev / "request.json").read_text()) if (prev / "request.json").exists() else {}
    req["refine"] = {"text": a.text, "at_seconds": a.at, "frame_path": frame_rel}
    (job / "request.json").write_text(json.dumps(req, indent=1))
    print(job)


def _aspect_size(job: Path) -> tuple[int, int]:
    """(width, height) the video must have: 1920x1080, or 1080x1920 for a 9:16 video (scripts/aspect.py)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import aspect
    return aspect.SIZE[aspect.aspect_of(job / "workspace")]


def cmd_check(a) -> None:
    job = Path(a.job).resolve()
    problems = []
    v = job / "out" / "video.mp4"
    if not v.exists():
        problems.append("out/video.mp4 missing")
    else:
        info = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                               "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", str(v)],
                              capture_output=True, text=True)
        data = json.loads(info.stdout or "{}")
        streams = data.get("streams", [])
        vs = [s for s in streams if s.get("codec_type") == "video"]
        aus = [s for s in streams if s.get("codec_type") == "audio"]
        if not vs or vs[0].get("codec_name") != "h264":
            problems.append("video stream is not h264")
        elif (vs[0].get("width"), vs[0].get("height")) != _aspect_size(job):
            w, h = _aspect_size(job)
            problems.append(f"video is {vs[0].get('width')}x{vs[0].get('height')}, expected {w}x{h}")
        if not aus or aus[0].get("codec_name") != "aac":
            problems.append("audio stream is not aac")
    if not (job / "out" / "thumbnail.jpg").exists():
        problems.append("out/thumbnail.jpg missing")
    mf = job / "out" / "manifest.json"
    if not mf.exists():
        problems.append("out/manifest.json missing")
    else:
        m = json.loads(mf.read_text())
        if not m.get("title"):
            problems.append("manifest.title empty")
        for s in m.get("scenes", []):
            for k in ("index", "title", "narration", "start", "duration"):
                if k not in s:
                    problems.append(f"manifest scene {s.get('index')} missing '{k}'")
        if not m.get("scenes"):
            problems.append("manifest.scenes empty")
    pf = job / ".waitwhat" / "progress.json"
    if pf.exists() and json.loads(pf.read_text()).get("stage") != "done":
        problems.append("progress stage is not 'done' yet")
    if problems:
        print("✗ contract check failed:\n  - " + "\n  - ".join(problems))
        sys.exit(1)
    print(f"✓ {job} satisfies the job contract")


@contextlib.contextmanager
def plan_lock(ws: Path):
    """Exclusive lock for a read-modify-write of plan.json (scene builders narrate in parallel)."""
    with open(ws / ".plan.lock", "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def save_plan(ws: Path, plan: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=ws, prefix=".plan.", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(plan, f, indent=1, ensure_ascii=False)
    os.replace(tmp, ws / "plan.json")  # atomic: tts/render/progress never read half a file


def cmd_narrate(a) -> None:
    """One scene's narration → plan.json (under the lock, atomically), then `tts.py --scene <id>`."""
    job = Path(a.job).resolve()
    ws = job / "workspace"
    text = a.text if a.text is not None else (Path(a.file).read_text() if a.file else sys.stdin.read())
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text).strip()
    if not text:
        sys.exit("narrate: empty narration")
    with plan_lock(ws):
        plan = json.loads((ws / "plan.json").read_text())
        hit = next((s for s in plan.get("scenes", []) if s.get("id") == a.id), None)
        if hit is None:
            sys.exit(f"narrate: no scene '{a.id}' in plan.json")
        hit["narration"] = text
        save_plan(ws, plan)
    words = len(re.sub(r"<[^>]+>", " ", text).split())
    print(f"narrate: {a.id}: {words} words (~{words / 3.2:.0f} s at 190 wpm)"
          + (f", target {hit['seconds']} s" if hit.get("seconds") else ""), flush=True)
    if a.no_voice:
        return
    tts = Path(__file__).resolve().parent / "tts.py"
    sys.exit(subprocess.run([sys.executable, str(tts), "--ws", str(ws), "--scene", a.id]).returncode)


def cmd_script(a) -> None:
    """The narration in plan order (markup kept, so bookmarks are visible), with voiced lengths."""
    ws = Path(a.job).resolve() / "workspace"
    plan = json.loads((ws / "plan.json").read_text())
    total_w, total_s = 0, 0.0
    for k, sc in enumerate(plan.get("scenes", []), start=1):
        nar = sc.get("narration") or ""
        words = len(re.sub(r"<[^>]+>", " ", nar).split())
        total_w += words
        dur = ""
        af = ws / "audio" / f"{sc.get('id')}.json"
        if af.exists():
            try:
                d = float(json.loads(af.read_text()).get("duration", 0))
                total_s += d
                dur = f", voiced {d:.1f} s"
            except Exception:
                pass
        print(f"[{k}] {sc.get('id')} ({sc.get('energy', 'medium')}, {words} words{dur}): {nar or '(no narration yet)'}\n")
    tgt = plan.get("duration_target")
    print(f"total: {total_w} words, {total_s:.0f} s voiced" + (f" (target {tgt} s)" if tgt else ""))


def cmd_brief(a) -> None:
    """A scene builder's brief: its plan.json entry, the neighbours' handoff details, theme and palette."""
    job = Path(a.job).resolve()
    plan = json.loads((job / "workspace" / "plan.json").read_text())
    scenes = plan.get("scenes", [])
    k = next((i for i, s in enumerate(scenes) if s.get("id") == a.id), None)
    if k is None:
        sys.exit(f"brief: no scene '{a.id}' in plan.json (ids: {', '.join(s.get('id', '?') for s in scenes)})")
    keys = ("id", "title", "visual", "build", "transition", "energy", "theme", "say", "hands_off", "narration")
    near = lambda i: {kk: scenes[i][kk] for kk in keys if kk in scenes[i]} if 0 <= i < len(scenes) else None
    out = {"scene": scenes[k], "position": f"{k + 1} of {len(scenes)}", "theme": plan.get("theme", "classic"),
           "palette": plan.get("palette", {}), "previous": near(k - 1), "next": near(k + 1),
           "video": {kk: plan[kk] for kk in ("title", "audience", "question", "aha", "duration_target") if kk in plan}}
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import aspect
    out["aspect"] = aspect.aspect_of(job / "workspace")
    if out["aspect"] == aspect.VERTICAL:
        out["layout"] = "9:16 vertical: stack, don't spread; larger type; one central focus; nothing in the bottom 15% (manim-scenes style guide, 'Vertical 9:16')"
    if not (scenes[k].get("narration") or "").strip():
        # parallel script mode: the builder writes this scene's narration, so it needs the whole arc
        out["arc"] = [{kk: s.get(kk) for kk in ("id", "title", "say", "hands_off") if s.get(kk)} for s in scenes]
        out["voice"] = {kk: plan[kk] for kk in ("voice", "pronunciations") if kk in plan}
    print(json.dumps(out, indent=1, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("prompt"); n.add_argument("--attach", nargs="*")
    n.add_argument("--aspect", choices=["16:9", "9:16"], help="video format (default 16:9)")
    n.add_argument("--base", default="waitwhat-videos"); n.add_argument("--slug")
    r = sub.add_parser("refine"); r.add_argument("job"); r.add_argument("text")
    r.add_argument("--at", type=float, required=True); r.add_argument("--frame")
    c = sub.add_parser("check"); c.add_argument("job", nargs="?", default=".")
    b = sub.add_parser("brief"); b.add_argument("id"); b.add_argument("--job", default=".")
    nr = sub.add_parser("narrate"); nr.add_argument("id"); nr.add_argument("--job", default=".")
    nr.add_argument("--text"); nr.add_argument("--file"); nr.add_argument("--no-voice", action="store_true")
    sc = sub.add_parser("script"); sc.add_argument("--job", default=".")
    a = ap.parse_args()
    {"new": cmd_new, "refine": cmd_refine, "check": cmd_check, "brief": cmd_brief,
     "narrate": cmd_narrate, "script": cmd_script}[a.cmd](a)


if __name__ == "__main__":
    main()
