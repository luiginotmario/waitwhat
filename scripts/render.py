#!/usr/bin/env python3
"""Render scenes one file at a time, cache by content hash, and extract review frames.

  render.py hook squares            # final 1080p30 renders of these scene ids (workspace/scenes/<id>.py)
  render.py hook --preview          # fast 480p15 preview (≈2x faster); --draft = same
  render.py --all -j 4              # final renders of every scene in plan.json that changed, 4 at a time
  render.py --check                 # import workspace/scenes/shared.py (+ the style lib): ok or traceback
  render.py --review                # one look at the whole video: frames/_review_<n>.jpg, a row per scene
  render.py --stings                # brand intro/outro → workspace/renders/_intro.mp4, _outro.mp4
  render.py --probe 42.5            # what is on screen at 42.5 s of out/video.mp4 (for refine)

Per scene it writes:
  renders/<id>.mp4 + renders/<id>.json   (hash, duration, quality); previews go to previews/ instead,
  renders/<id>.cues.json                 sound-effect cues the scene logged (mixed by stitch.py)
                                         so a preview never replaces a final render
  frames/<id>_1.jpg … and frames/<id>_sheet.jpg   (look at the sheet! from the latest render, either kind:
                                         a 2x2 grid, in time order: first frame | ~40 %, ~75 % | last frame
                                         before any fade-out, so the handoffs are on it too)
  logs/<id>.render.log                   (full manim output; on failure the traceback is printed)
  logs/<id>.layout.json                  (written by WaitwhatScene: overlapping / off-frame text)

A scene is skipped when its code, shared code, style lib and narration timing are unchanged, so a
refine re-renders only what it touched. Exit code 1 if any scene failed.

Progress: a final (non-preview) render marks the scene `rendering` in .waitwhat/progress.json when
it starts and `done` when it succeeds (--no-progress to skip), so a scene builder never needs a
separate `ww progress scene` call. Final 1080p renders take seconds, so render the final directly
and look at its sheet; previews are for heavy scenes only.

Aspect: plan.json "aspect" (else <job>/request.json, else WAITWHAT_ASPECT; scripts/aspect.py) picks the
frame: 16:9 renders 1920x1080, 9:16 renders 1080x1920 (previews 480x854); the style lib sets the
matching frame size, the stings and review frames follow it.

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
import contextlib
import fcntl
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import aspect as _aspect  # noqa: E402  (stdlib-only sibling: 16:9 or 9:16, and its pixel sizes)
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
    if _aspect.is_vertical(ws):
        h.update(b"9:16")  # only vertical changes the key, so existing 16:9 renders stay cached
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


def frame_times(dur: float, n: int) -> list[float]:
    """n review times: the first frame, evenly spread middles, and the last frame before a fade-out
    (finish(fade=True) fades over the final 0.5 s), so the handoffs to the neighbours are visible."""
    if dur <= 0:
        return []
    if n <= 1:
        return [round(dur * 0.5, 2)]
    first, last = min(0.05, dur * 0.1), max(0.0, dur - 0.6) if dur > 1.5 else dur * 0.85
    mids = [0.4, 0.75] if n == 4 else [0.12 + 0.76 * i / (n - 1) for i in range(1, n - 1)]
    times = [first] + [dur * f for f in mids] + [last]
    return sorted(set(round(min(max(t, 0.0), dur - 0.04), 2) for t in times))


def resolution_args(ws: Path, quality: str) -> list[str]:
    """Manim's -r for a vertical video (-qh 1080x1920, -qm 720x1280, -ql 480x854); none for 16:9."""
    if not _aspect.is_vertical(ws):
        return []
    w, h = {"h": (1080, 1920), "m": (720, 1280), "l": (480, 854)}[quality]
    return ["-r", f"{w},{h}"]


def extract_frames(ws: Path, sid: str, mp4: Path, n: int, extra: list[float] | None = None) -> tuple[list[str], str]:
    """Review frames (≤960 px on the long side) and a contact sheet: a 2x2 grid for 4 frames, else a stack."""
    fdir = ws / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    for old in fdir.glob(f"{sid}_*.jpg"):
        old.unlink()
    dur = ffprobe_duration(mp4)
    times = sorted(set(frame_times(dur, n) + [round(t, 2) for t in (extra or []) if 0 <= t < dur]))
    scale = "scale=-2:'min(960,ih)'" if _aspect.is_vertical(ws) else "scale='min(960,iw)':-2"

    def grab(it: tuple[int, float]) -> str | None:
        i, t = it
        out = fdir / f"{sid}_{i}.jpg"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(mp4),
                        "-frames:v", "1", "-vf", scale, "-q:v", "3", str(out)], check=False)
        return str(out) if out.exists() else None

    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        frames = [f for f in pool.map(grab, enumerate(times, start=1)) if f]
    sheet = fdir / f"{sid}_sheet.jpg"
    if frames:
        ins = sum([["-i", f] for f in frames], [])
        k = len(frames)
        pads = "".join(f"[{i}]pad=iw+8:ih+8:0:0:0x333333[p{i}];" for i in range(k))
        if k == 4:
            fc = pads + "[p0][p1][p2][p3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0"
        elif k > 1:
            fc = pads + "".join(f"[p{i}]" for i in range(k)) + f"vstack=inputs={k}"
        else:
            fc = "null"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", fc, "-q:v", "3", str(sheet)],
                       check=False)
    return frames, str(sheet)


SLOTS_DIR = ROOT / ".cache" / "render-slots"


def _env_int(name: str) -> int:
    try:
        return max(0, int(os.environ.get(name, "") or 0))
    except ValueError:
        return 0


def render_slots() -> int:
    """Manim processes allowed at once on this machine, across every job (WAITWHAT_RENDER_SLOTS).
    A 1080p render keeps ~3-4 cores busy, so the default is a third of the cores: more only
    oversubscribes the CPU (same throughput, every render slower)."""
    return _env_int("WAITWHAT_RENDER_SLOTS") or max(2, (os.cpu_count() or 4) // 3)


def _try_slot(d: Path, n: int):
    """Take one of n flock'd lock files in d without blocking: the open file, or None."""
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        fh = open(d / f"slot-{i}.lock", "a")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except BlockingIOError:
            fh.close()
    return None


@contextlib.contextmanager
def render_slot(ws: Path | None = None):
    """A machine-wide semaphore: one of N lock files under the plugin's .cache, held with flock while a
    Manim render runs, so concurrent jobs (WORKER_CONCURRENCY > 1) can't oversubscribe the CPU. A job
    also holds one of its own WAITWHAT_RENDER_JOB_SLOTS (default: all of them) under
    <job>/.waitwhat/render-slots first, so one job can't take every machine slot while another waits.
    The kernel drops a lock when its process dies, so a crashed render never leaks a slot. Yields the
    seconds spent waiting."""
    n = render_slots()
    per_job = min(n, _env_int("WAITWHAT_RENDER_JOB_SLOTS") or n)
    job_dir = (ws.parent / ".waitwhat" / "render-slots") if ws is not None and per_job < n else None
    t0 = time.time()
    k = 0
    mine = machine = None
    try:
        while machine is None:
            if job_dir is not None and mine is None:
                mine = _try_slot(job_dir, per_job)
            if job_dir is None or mine is not None:
                machine = _try_slot(SLOTS_DIR, n)
            if machine is None:
                k += 1
                time.sleep(min(0.5, 0.05 * k))
        yield round(time.time() - t0, 1)
    finally:
        for fh in (machine, mine):
            if fh is not None:
                fcntl.flock(fh, fcntl.LOCK_UN)
                fh.close()


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


def mark_progress(ws: Path, sid: str, status: str) -> None:
    """Best effort: the scene's status in <job>/.waitwhat/progress.json (only if the job tracks it)."""
    job = ws.parent
    if not (job / ".waitwhat" / "progress.json").exists():
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import progress as _pg  # stdlib-only sibling script (same lock as `ww progress`)
        with _pg.locked(job):
            data = _pg.load(job)
            hit = next((sc for sc in data.get("scenes", []) if sc.get("id") == sid), None)
            if hit is None or hit.get("status") == status:
                return
            hit["status"] = status
            _pg.refresh_outline(data)
            _pg.save(job, data)
    except Exception as e:  # progress is cosmetic; never fail a render over it
        print(f"render: could not update progress for '{sid}': {e}", file=sys.stderr)


def check_shared(ws: Path) -> dict:
    """Import workspace/scenes/shared*.py with the toolchain, before scene builders rely on it."""
    files = sorted((ws / "scenes").glob("shared*.py"))
    if not files:
        return {"ok": True, "checked": [], "note": "no shared.py"}
    code = "import importlib, sys\nfor m in sys.argv[1:]:\n    importlib.import_module(m)\n"
    t0 = time.time()
    proc = subprocess.run([str(VENV_BIN / "python"), "-c", code, *[f.stem for f in files]], cwd=ws / "scenes",
                          env=toolchain_env(ws), capture_output=True, text=True)
    res = {"ok": proc.returncode == 0, "checked": [f.name for f in files], "seconds": round(time.time() - t0, 1)}
    if proc.returncode != 0:
        res["error"] = summarize_failure(proc.stdout + "\n" + proc.stderr)
    return res


def review_sheets(ws: Path, per_image: int = 6) -> dict:
    """The whole video at a glance, for the director's one review turn: frames/_review_<n>.jpg, one row
    per scene in plan order (first frame | middle | last frame before any fade-out), from the final
    render (else the preview). The end of row k next to the start of row k+1 is the handoff."""
    plan = json.loads((ws / "plan.json").read_text())
    ids = [s["id"] for s in plan.get("scenes", [])]
    fdir = ws / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    for old in fdir.glob("_review_*.jpg"):
        old.unlink()
    tw, th = 448, 252
    if _aspect.is_vertical(ws):  # tall tiles; fewer rows per sheet so it stays a readable size
        tw, th, per_image = 216, 384, min(per_image, 4)
    srcs: dict[str, Path] = {}
    missing = []
    for sid in ids:
        for d in ("renders", "previews"):
            if (ws / d / f"{sid}.mp4").exists():
                srcs[sid] = ws / d / f"{sid}.mp4"
                break
        else:
            missing.append(sid)
    tmp = fdir / ".review"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()

    def grab(job: tuple[str, int, float]) -> None:
        sid, j, t = job
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(srcs[sid]), "-frames:v", "1",
                        "-vf", f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2",
                        str(tmp / f"{sid}_{j}.png")], check=False)

    jobs = []
    for sid, src in srcs.items():
        dur = ffprobe_duration(src)
        ts = frame_times(dur, 3)
        if len(ts) == 3:
            ts = [ts[0], dur * 0.5, ts[2]]
        jobs += [(sid, j, t) for j, t in enumerate(ts)]
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(grab, jobs))
    rows = [sid for sid in ids if sid in srcs and all((tmp / f"{sid}_{j}.png").exists() for j in range(3))]
    images = []
    for n, k0 in enumerate(range(0, len(rows), per_image), start=1):
        chunk = rows[k0:k0 + per_image]
        ins = sum([["-i", str(tmp / f"{sid}_{j}.png")] for sid in chunk for j in range(3)], [])
        m = len(chunk) * 3
        pads = "".join(f"[{i}]pad=iw+6:ih+6:0:0:0x444444[p{i}];" for i in range(m))
        layout = "|".join(f"{c * (tw + 6)}_{r * (th + 6)}" for r in range(len(chunk)) for c in range(3))
        out = fdir / f"_review_{n}.jpg"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex",
                        pads + "".join(f"[p{i}]" for i in range(m)) + f"xstack=inputs={m}:layout={layout}",
                        "-q:v", "3", str(out)], check=False)
        if out.exists():
            images.append({"image": str(out), "rows": chunk})
    shutil.rmtree(tmp, ignore_errors=True)
    res = {"ok": bool(images), "images": images,
           "layout": "one row per scene, top to bottom in plan order: first frame | middle | last frame"}
    if missing:
        res["not_rendered"] = missing
    return res


def render_one(ws: Path, sid: str, quality: str, fps: int, force: bool, nframes: int,
               preview: bool = False, wait_audio: float = 600, progress: bool = True) -> dict:
    res = _render_one(ws, sid, quality, fps, force, nframes, preview, wait_audio, progress)
    if progress and not preview and res.get("ok"):
        mark_progress(ws, sid, "done")
    return res


def _render_one(ws: Path, sid: str, quality: str, fps: int, force: bool, nframes: int,
                preview: bool, wait_audio: float, progress: bool) -> dict:
    src = ws / "scenes" / f"{sid}.py"
    if not src.exists():
        return {"id": sid, "ok": False, "error": f"missing {src}"}
    if progress and not preview:
        mark_progress(ws, sid, "rendering")
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
    cmd = [str(VENV_BIN / "manim"), "render", QUALITY[quality], *resolution_args(ws, quality), "--fps", str(fps),
           "--disable_caching", "--media_dir", str(media), "-o", sid, str(src), cls]
    with render_slot(ws) as slot_wait:
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
    if _aspect.is_vertical(ws):
        res["aspect"] = "9:16"  # a vertical video: stack, don't spread (manim-scenes style guide)
    if preview:
        res["preview"] = True
    if waited >= 1:
        res["waited_for_audio"] = waited
    if slot_wait >= 1:
        res["waited_for_render_slot"] = slot_wait
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
    asp = _aspect.aspect_of(ws)
    key = hashlib.sha256(src).hexdigest()[:12] + ("" if asp == _aspect.LANDSCAPE else "-9x16")
    env = toolchain_env(ws)
    env["WAITWHAT_THEME"] = "classic"  # the brand stings are always on black
    env["WAITWHAT_ASPECT"] = asp       # and in the video's aspect, so the concat stays a stream copy
    cache = ROOT / ".cache" / "stings" / key
    if not (cache / "Intro.mp4").exists() or not (cache / "Outro.mp4").exists():
        cache.mkdir(parents=True, exist_ok=True)
        f = cache / "sting.py"
        f.write_text("from waitwhat_style import *\n\nclass Intro(WaitwhatIntro):\n    pass\n\n"
                     "class Outro(WaitwhatOutro):\n    pass\n")
        proc = subprocess.run([str(VENV_BIN / "manim"), "render", "-qh", *resolution_args(ws, "h"), "--fps", "30", "--disable_caching",
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
    ap.add_argument("--frames", type=int, default=4, help="review frames per scene (0 = none; 4 = the 2x2 sheet)")
    ap.add_argument("--no-progress", action="store_true", help="don't touch .waitwhat/progress.json")
    ap.add_argument("--check", action="store_true", help="import shared.py with the toolchain and report")
    ap.add_argument("--review", action="store_true", help="frames/_review_<n>.jpg: a row of frames per scene")
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
    if a.check:
        r = check_shared(ws)
        print(json.dumps(r))
        if not r["ok"]:
            sys.exit(1)
        if not a.ids and not a.all:
            return
    if a.review:
        print(json.dumps(review_sheets(ws)))
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
        ap.error("give scene ids, --all, --check, --review, --stings or --probe")
    quality = "l" if a.preview else a.quality
    fps = 15 if a.preview and a.fps == 30 else a.fps
    failed = False
    with cf.ThreadPoolExecutor(max_workers=max(1, min(a.jobs, len(ids)))) as pool:
        futs = {pool.submit(render_one, ws, sid, quality, fps, a.force, a.frames, a.preview, a.wait_audio,
                            not a.no_progress): sid
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
