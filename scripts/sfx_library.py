#!/usr/bin/env python3
"""Build the curated sound-effect library in assets/sfx/ (run ONCE; the files are committed).

  sfx_library.py generate [--only pop,tick] [--force]   # ElevenLabs Sound Effects API → raw/ (needs ELEVENLABS_API_KEY)
  sfx_library.py process                               # raw/ → trimmed, loudness-matched 48 kHz mono WAVs + library.json
  sfx_library.py list                                  # what the library holds

Every video then reuses these files, so sound costs nothing per video and stays consistent.
Generated on a paid ElevenLabs plan, which includes a commercial licence for generated audio
(see THIRD_PARTY.md). Processing: decode, trim leading/trailing silence, short fades, match the
loudness of the active part (RMS -20 dBFS, peak <= -1 dBFS), and record each take's "onset"
(the attack of a hit; the crest of a swell such as a whoosh) so stitch.py can land the hit exactly on the animation event.
Raw downloads go to .cache/sfx-raw/ (git-ignored).
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "sfx"
RAW = ROOT / ".cache" / "sfx-raw"
SR = 48000
API = "https://api.elevenlabs.io/v1/sound-generation"
STYLE = "clean studio recording, close and dry, no music, no voices, no background noise"

# name → (kind, generation seconds, default gain dB in the mix, what it is for, [prompt per take])
# kind "hit": a one-shot whose loudest moment lands on the event; "texture": stretched or
# trimmed to the length of the motion it accompanies (writing, typing, erasing).
SOUNDS: dict[str, tuple[str, float, float, str, list[str]]] = {
    "pop": ("hit", 0.5, -13, "an object appears", [
        "a single soft muted pop, like a tiny bubble bursting",
        "a gentle soft pop, a small cork leaving a bottle, very short",
        "a soft round plop, a single drop, muted and warm",
        "a light soft pop of a small balloon, quiet, short"]),
    "tick": ("hit", 0.5, -15, "small items in a list, counting", [
        "a single tiny soft wooden tick, very short",
        "one small soft tap of a pencil on a wooden desk",
        "a tiny soft click of a ballpoint pen, single"]),
    "click": ("hit", 0.5, -15, "a UI click, a piece snapping into place", [
        "a single soft computer mouse click",
        "a small soft plastic snap, two parts clicking together",
        "a single soft button press click on a trackpad"]),
    "pencil": ("texture", 1.6, -14, "writing or drawing with a pencil", [
        "a pencil writing a short word on paper, graphite scratching, steady strokes",
        "a sharp pencil drawing a quick line and a circle on paper",
        "a pencil sketching quickly on a notepad, light scratchy strokes",
        "a mechanical pencil writing on paper, soft scratching"]),
    "chalk": ("texture", 1.6, -14, "writing on a chalkboard", [
        "chalk writing quickly on a blackboard, short scratchy strokes",
        "a piece of chalk drawing a line and tapping on a chalkboard",
        "writing a short equation in chalk on a slate blackboard"]),
    "marker": ("texture", 1.6, -15, "writing on a whiteboard", [
        "a dry erase marker writing quickly on a whiteboard, soft squeaky strokes",
        "a whiteboard marker drawing a line and a circle, felt tip squeak",
        "writing a short word with a marker on a whiteboard"]),
    "eraser": ("texture", 1.2, -15, "rubbing something out", [
        "a felt board eraser rubbing a chalkboard briefly, soft brushing",
        "a rubber eraser rubbing on paper quickly, short",
        "wiping a whiteboard with an eraser, two quick soft strokes"]),
    "whoosh": ("hit", 1.0, -15, "a scene transition or a big move", [
        "a soft airy whoosh transition, smooth and gentle, no impact",
        "a subtle cinematic swoosh passing by, airy, soft",
        "a gentle wind whoosh, short, smooth rise and fall",
        "a soft fabric swish whoosh, quick, airy"]),
    "swish": ("hit", 0.5, -18, "a quick small movement, a card sliding", [
        "a very short quick swish of air, subtle",
        "a playing card sliding quickly across a table, short swish",
        "a fast tiny whoosh, a flick of a page"]),
    "rise": ("hit", 1.6, -17, "a reveal, something becoming clear", [
        "a gentle short rising shimmer, soft synth swell that resolves, calm reveal",
        "a soft magical upward sweep, airy and warm, short",
        "a quiet rising tone swell, smooth, ending softly"]),
    "chime": ("hit", 1.5, -18, "the aha moment, a correct answer", [
        "a single soft glass chime, bright but gentle, short decay",
        "a soft bell ding, warm and clear, single note",
        "a gentle two-note positive chime, soft marimba"]),
    "shimmer": ("hit", 1.2, -19, "something special or magical, a glow", [
        "a short delicate sparkle shimmer, quiet twinkle",
        "a soft magical glitter sound, short and light"]),
    "coin": ("hit", 0.8, -15, "money, a price, a fee", [
        "a single coin dropping onto a wooden table, short clink",
        "two coins clinking together once, bright and short",
        "a single coin landing in a ceramic jar, clink"]),
    "register": ("hit", 1.0, -16, "a payment going through, a sale", [
        "a soft modern payment success chime from a card reader, short",
        "a gentle cash register ding, short and soft"]),
    "keys": ("texture", 1.6, -16, "typing, code, a request being sent", [
        "fast typing on a laptop keyboard, a short burst of soft keystrokes",
        "a few quick keystrokes on a mechanical keyboard, soft",
        "typing a short line of code on a quiet laptop keyboard"]),
    "paper": ("hit", 1.0, -16, "a document, an invoice, a page", [
        "a sheet of paper being picked up and placed, short paper rustle",
        "a single page turning in a notebook, crisp"]),
    "thud": ("hit", 0.6, -15, "something landing, weight, a block stacking", [
        "a soft muffled thud of a book placed on a table, low and gentle",
        "a soft wooden block set down on a table, warm thump"]),
    "stamp": ("hit", 0.6, -16, "approved, verified, done", [
        "a rubber stamp pressed firmly onto paper, short thump",
        "an approval stamp on a document, one soft thunk"]),
    "notify": ("hit", 0.8, -18, "a message or notification arrives", [
        "a soft friendly two-note notification blip, modern phone",
        "a gentle short message received ping, soft"]),
    "wrong": ("hit", 0.8, -18, "an error, a declined card, a wrong answer", [
        "a soft low muted error buzz, two short tones, gentle not harsh",
        "a soft low descending two-note wrong-answer tone, muted"]),
}


def _ctx():
    ctx = ssl.create_default_context()
    for f in (os.environ.get("SSL_CERT_FILE"), "/etc/ssl/cert.pem"):
        if f and os.path.exists(f):
            ctx.load_verify_locations(f)
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


def generate(only: set[str] | None, force: bool) -> None:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        sys.exit("sfx_library: ELEVENLABS_API_KEY is not set")
    RAW.mkdir(parents=True, exist_ok=True)
    ctx = _ctx()
    for name, (kind, secs, _, _, prompts) in SOUNDS.items():
        if only and name not in only:
            continue
        for i, prompt in enumerate(prompts, start=1):
            f = RAW / f"{name}_{i}.mp3"
            if f.exists() and not force:
                continue
            body = {"text": f"{prompt}. {STYLE}.", "duration_seconds": secs, "prompt_influence": 0.8,
                    "model_id": "eleven_text_to_sound_v2"}
            req = urllib.request.Request(API + "?output_format=mp3_44100_128", data=json.dumps(body).encode(),
                                         headers={"xi-api-key": key, "Content-Type": "application/json"})
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
                        f.write_bytes(r.read())
                    print(f"  + {f.name}", flush=True)
                    break
                except urllib.error.HTTPError as e:
                    msg = e.read().decode(errors="ignore")[:300]
                    if e.code == 429 and attempt < 3:
                        time.sleep(3 * (attempt + 1))
                        continue
                    sys.exit(f"sfx_library: {name}_{i}: HTTP {e.code}: {msg}")


def _decode(src: Path) -> np.ndarray:
    with tempfile.TemporaryDirectory() as td:
        w = Path(td) / "x.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-ar", str(SR),
                        "-sample_fmt", "s16", str(w)], check=True)
        with wave.open(str(w)) as r:
            return np.frombuffer(r.readframes(r.getnframes()), "<i2").astype(np.float32) / 32768


def _env(x: np.ndarray, win: int = 480) -> np.ndarray:
    n = len(x) // win
    return np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1) + 1e-12)


PEAK_ONSET = {"whoosh", "swish", "rise"}


def process_one(x: np.ndarray, kind: str, peak_onset: bool = False) -> tuple[np.ndarray, float]:
    """Trim silence, fade, loudness-match. → (audio, onset seconds)."""
    x = x - np.mean(x)
    win = 480  # 10 ms
    e = _env(x, win)
    if not len(e) or e.max() < 1e-5:
        return x, 0.0
    db = 20 * np.log10(e / e.max())
    act = np.where(db > -38)[0]
    a = max(0, act[0] * win - 240)
    b = min(len(x), (np.where(db > -45)[0][-1] + 1) * win + 1440)
    y = x[a:b].copy()
    fi, fo = int(0.003 * SR), int((0.06 if kind == "texture" else 0.03) * SR)
    y[:fi] *= np.linspace(0, 1, fi)
    y[-fo:] *= np.linspace(1, 0, fo)
    e = _env(y, win)
    loud = e[e > e.max() * 0.1]
    rms = float(np.sqrt(np.mean(loud ** 2))) if len(loud) else float(e.max())
    y *= 10 ** (-20 / 20) / max(rms, 1e-6)
    peak = float(np.max(np.abs(y)))
    if peak > 10 ** (-1 / 20):
        y *= 10 ** (-1 / 20) / peak
    e5 = _env(y, 240)
    if kind == "texture":
        onset = 0.0
    elif peak_onset:  # swells (whoosh, rise): their loudest moment is the event
        onset = float(np.argmax(e5) * 240 / SR)
    else:             # hits: the attack of the first strong transient
        onset = float(np.argmax(e5 >= e5.max() * 0.5) * 240 / SR)
    return y, round(onset, 3)


def process() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lib = {"source": "ElevenLabs Sound Effects API (eleven_text_to_sound_v2), generated once on a paid plan "
                     "with a commercial licence; trimmed and loudness-matched by scripts/sfx_library.py",
           "sample_rate": SR, "level": "RMS of the active part -20 dBFS, peak <= -1 dBFS",
           "sounds": {}}
    for name, (kind, _, gain, use, prompts) in SOUNDS.items():
        takes = []
        for i in range(1, len(prompts) + 1):
            src = RAW / f"{name}_{i}.mp3"
            if not src.exists():
                continue
            y, onset = process_one(_decode(src), kind, name in PEAK_ONSET)
            out = OUT / f"{name}_{i}.wav"
            with wave.open(str(out), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
            takes.append({"file": out.name, "seconds": round(len(y) / SR, 3), "onset": onset,
                          "prompt": prompts[i - 1]})
        if takes:
            lib["sounds"][name] = {"kind": kind, "gain_db": gain, "use": use, "takes": takes}
    (OUT / "library.json").write_text(json.dumps(lib, indent=1))
    n = sum(len(v["takes"]) for v in lib["sounds"].values())
    print(f"{n} takes of {len(lib['sounds'])} sounds → {OUT}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("--only"); g.add_argument("--force", action="store_true")
    sub.add_parser("process"); sub.add_parser("list")
    a = ap.parse_args()
    if a.cmd == "generate":
        generate(set(a.only.split(",")) if a.only else None, a.force)
    elif a.cmd == "process":
        process()
    else:
        lib = json.loads((OUT / "library.json").read_text())
        for k, v in lib["sounds"].items():
            print(f"{k:9s} {v['kind']:7s} {len(v['takes'])} takes  {v['use']}")


if __name__ == "__main__":
    main()
