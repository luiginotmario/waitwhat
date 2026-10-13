#!/usr/bin/env python3
"""Write <job>/.waitwhat/progress.json (the worker polls it; the Mac app shows it).

Shape (CONTRACT.md):
  {stage, message, scenes:[{index, title, status}], outline?:[{index, title, status}]}
  stage  ∈ understanding | research | script | voice | animating | stitching | done
  status ∈ pending | rendering | done | failed

Usage (run from the job dir, or pass --job DIR):
  progress.py stage understanding "Reading the request"
  progress.py plan                      # (re)load scene list (+ outline coverage) from workspace/plan.json
  progress.py scene 3 rendering         # by 1-based index ...
  progress.py scene squares done        # ... or by scene id
  progress.py show
Safe under concurrent calls (parallel scene subagents): every read-modify-write holds an exclusive
lock on .waitwhat/progress.lock, and the file is replaced atomically.
Stdlib only, so it runs with any python3.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import sys
import tempfile
import time
from pathlib import Path

STAGES = ["understanding", "research", "script", "voice", "animating", "stitching", "done"]
STATUSES = ["pending", "rendering", "done", "failed"]


def _path(job: Path) -> Path:
    return job / ".waitwhat" / "progress.json"


def load(job: Path) -> dict:
    p = _path(job)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"stage": "understanding", "message": "", "scenes": []}


def save(job: Path, data: dict) -> None:
    p = _path(job)
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".progress.")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, p)  # atomic: the poller never sees half a file


@contextlib.contextmanager
def locked(job: Path):
    """Exclusive lock for one load → modify → save, so concurrent `scene` calls never lose updates."""
    lock = job / ".waitwhat" / "progress.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def refresh_outline(data: dict) -> None:
    """Outline item status from the scenes that cover it: done when all are done."""
    outline = data.get("outline")
    if not outline:
        return
    for item in outline:
        mine = [sc for sc in data.get("scenes", []) if item["index"] in (sc.get("covers") or [])]
        sts = [sc.get("status") for sc in mine]
        if mine and all(st == "done" for st in sts):
            item["status"] = "done"
        elif any(st in ("rendering", "done") for st in sts):
            item["status"] = "rendering"
        elif any(st == "failed" for st in sts):
            item["status"] = "failed"
        else:
            item["status"] = "pending"


def covers_of(scene: dict, n_outline: int) -> list[int]:
    out = []
    for c in scene.get("covers") or []:
        try:
            i = int(c)
        except (TypeError, ValueError):
            continue
        if 1 <= i <= n_outline and i not in out:
            out.append(i)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job", default=".", help="job dir (default: cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage"); s.add_argument("stage", choices=STAGES); s.add_argument("message", nargs="?", default="")
    sub.add_parser("plan")
    sc = sub.add_parser("scene"); sc.add_argument("which"); sc.add_argument("status", choices=STATUSES)
    sc.add_argument("message", nargs="?")
    sub.add_parser("show")
    a = ap.parse_args()

    job = Path(a.job).resolve()
    if a.cmd == "show":
        data = load(job)
        refresh_outline(data)
        print(json.dumps(data, indent=1))
        return
    with locked(job):
        update(job, a)


def update(job: Path, a: argparse.Namespace) -> None:
    data = load(job)

    if a.cmd == "stage":
        data["stage"] = a.stage
        data["message"] = a.message
        if a.stage == "done":
            for sc_ in data.get("scenes", []):
                if sc_.get("status") in ("pending", "rendering"):
                    sc_["status"] = "done"
    elif a.cmd == "plan":
        plan_f = job / "workspace" / "plan.json"
        if not plan_f.exists():
            sys.exit(f"progress: {plan_f} not found")
        plan = json.loads(plan_f.read_text())
        old = {s.get("id"): s for s in data.get("scenes", [])}
        scenes = []
        for i, s in enumerate(plan.get("scenes", []), start=1):
            prev = old.get(s.get("id"), {})
            status = s.get("status") or prev.get("status") or "pending"
            if status not in STATUSES:
                status = "pending"
            scenes.append({"index": i, "id": s.get("id"), "title": s.get("title", f"Scene {i}"), "status": status})
        outline = plan.get("outline") or []
        if outline:
            for sc_, s in zip(scenes, plan.get("scenes", [])):
                sc_["covers"] = covers_of(s, len(outline))
            data["outline"] = [{"index": i, "title": str(o.get("title", f"Part {i}"))}
                               for i, o in enumerate(outline, start=1)]
            dropped = {str(d.get("title", "")).strip().lower() for d in plan.get("dropped") or [] if isinstance(d, dict)}
            for o in data["outline"]:
                if o["title"].strip().lower() in dropped:
                    o["dropped"] = True
            covered = {c for sc_ in scenes for c in sc_["covers"]}
            gaps = [o["title"] for o in data["outline"] if o["index"] not in covered and not o.get("dropped")]
            if gaps and scenes:
                print("progress: WARNING outline items no scene covers (add scenes, set `covers`, "
                      "or record them in plan.dropped with a reason): " + "; ".join(gaps), file=sys.stderr)
        else:
            data.pop("outline", None)
        data["scenes"] = scenes
    elif a.cmd == "scene":
        hit = None
        for sc_ in data.get("scenes", []):
            if str(sc_.get("index")) == a.which or sc_.get("id") == a.which:
                hit = sc_
        if hit is None:
            sys.exit(f"progress: no scene '{a.which}' (run `progress.py plan` first)")
        hit["status"] = a.status
        if a.message:
            data["message"] = a.message
    refresh_outline(data)
    save(job, data)


if __name__ == "__main__":
    main()
