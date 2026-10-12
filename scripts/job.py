#!/usr/bin/env python3
"""Create and validate job dirs that follow the waitwhat job I/O contract.

  job.py new "Why is the sky blue?" [--attach a.pdf ...] [--base ./waitwhat-videos]
        → ./waitwhat-videos/why-is-the-sky-blue/   (prints the path)
  job.py refine ./waitwhat-videos/why-is-the-sky-blue "wait, what is scattering?" --at 42.5 [--frame f.png]
        → ./waitwhat-videos/why-is-the-sky-blue-v2/  with the previous workspace copied in
  job.py check [JOB]      → validates out/ against the contract (exit 1 on problems)

The worker creates job dirs itself; these commands make local Claude Code use behave the same way.
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
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
    (job / "request.json").write_text(json.dumps({"prompt": a.prompt, "attachments": atts}, indent=1))
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
        elif (vs[0].get("width"), vs[0].get("height")) != (1920, 1080):
            problems.append(f"video is {vs[0].get('width')}x{vs[0].get('height')}, expected 1920x1080")
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("prompt"); n.add_argument("--attach", nargs="*")
    n.add_argument("--base", default="waitwhat-videos"); n.add_argument("--slug")
    r = sub.add_parser("refine"); r.add_argument("job"); r.add_argument("text")
    r.add_argument("--at", type=float, required=True); r.add_argument("--frame")
    c = sub.add_parser("check"); c.add_argument("job", nargs="?", default=".")
    a = ap.parse_args()
    {"new": cmd_new, "refine": cmd_refine, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
