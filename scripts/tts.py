#!/usr/bin/env python3
"""Narrate every scene in workspace/plan.json BEFORE animating, with word-level timings.

For each scene it writes:
  workspace/audio/<id>.wav    48 kHz mono narration (no lead-in silence; stitch adds it)
  workspace/audio/<id>.json   {duration, lead_in, words:[{w,start,end}], marks:{name:t}, text, sha, ...}

Scene code reads the json through WaitwhatScene (until / wait_until / finish), so the animation
is timed to the voice, not the other way round.

Narration markup (inside plan.json scenes[].narration):
  <bookmark mark="squares"/>   a named moment the animation can wait for
  <break time="0.8s"/>         a deliberate pause

Backends:
  elevenlabs  POST /v1/text-to-speech/{voice_id}/with-timestamps (needs ELEVENLABS_API_KEY).
              The ElevenLabs MCP is great for browsing voices but returns no timestamps, hence this.
  say         macOS `say`, free and offline. Sentence-by-sentence, so sentence boundaries, pauses
              and bookmarks at sentence starts are exact; word times inside a sentence are estimated.
  auto        elevenlabs when a key is set, else say.

Usage:
  tts.py                         # all scenes whose narration or voice changed (cache by sha)
  tts.py --scene hook --scene aha --force
  tts.py --backend say
  tts.py --voices                # list voices on the ElevenLabs account (no characters spent)
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import wave
from pathlib import Path

API = "https://api.elevenlabs.io/v1"
SR = 48000
DEFAULT_LEAD = 0.35
SENTENCE_GAP = 0.28
DEFAULTS = {
    "model_id": "eleven_multilingual_v2",
    "stability": 0.45,
    "similarity_boost": 0.8,
    "style": 0.15,
    "speed": 1.0,
    "use_speaker_boost": True,
    "say_voice": "Daniel",
    "say_rate": 182,
}
def _ssl_context():
    """Verified TLS even on Pythons without a CA bundle (e.g. python.org builds on macOS)."""
    import ssl
    ctx = ssl.create_default_context()
    for cafile in (os.environ.get("SSL_CERT_FILE"), "/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if cafile and os.path.exists(cafile):
            try:
                ctx.load_verify_locations(cafile)
            except Exception:
                pass
    try:
        import certifi  # type: ignore
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


SSL_CTX = _ssl_context()


TAG = re.compile(r"""<\s*(bookmark|break)\b([^>]*)/\s*>""", re.I)
ATTR = re.compile(r"""(\w+)\s*=\s*["']([^"']*)["']""")


# --------------------------------------------------------------------------- parsing

def parse(narration: str, pron: dict[str, str]) -> list[tuple]:
    """→ items: ("word", original, [spoken...]) | ("break", seconds) | ("mark", name)."""
    items: list[tuple] = []
    pos = 0
    lowered = {k.lower(): v for k, v in pron.items()}

    def add_text(chunk: str):
        for tok in chunk.split():
            core = tok.strip(".,;:!?\"'()[]")
            rep = pron.get(core) or lowered.get(core.lower())
            if rep:
                spoken = tok.replace(core, rep).split()
            else:
                spoken = [tok]
            items.append(("word", tok, spoken))

    for m in TAG.finditer(narration):
        add_text(narration[pos:m.start()])
        kind, attrs = m.group(1).lower(), dict(ATTR.findall(m.group(2)))
        if kind == "bookmark":
            items.append(("mark", attrs.get("mark") or attrs.get("name") or f"m{len(items)}"))
        else:
            t = attrs.get("time", "0.5s").strip().lower()
            secs = float(t[:-2]) / 1000 if t.endswith("ms") else float(t.rstrip("s") or 0.5)
            items.append(("break", max(0.0, min(secs, 3.0))))
        pos = m.end()
    add_text(narration[pos:])
    return items


def plain_text(narration: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub(" ", narration)).strip()


# --------------------------------------------------------------------------- audio utils

def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def to_wav(src: Path, dst: Path, trim: bool = False) -> None:
    af = ["-af", "silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.02,"
                 "areverse,silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.05,areverse"] if trim else []
    ffmpeg("-i", str(src), *af, "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", str(dst))


def wav_duration(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def concat_wavs(parts: list[tuple[Path | None, float]], dst: Path) -> None:
    """parts: (wav or None, seconds of silence if None)."""
    with wave.open(str(dst), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(SR)
        for p, secs in parts:
            if p is None:
                out.writeframes(b"\x00\x00" * int(secs * SR))
            else:
                with wave.open(str(p)) as w:
                    out.writeframes(w.readframes(w.getnframes()))


# --------------------------------------------------------------------------- elevenlabs

def el_request(path: str, key: str, body: dict | None = None, query: str = "") -> dict:
    url = f"{API}{path}{query}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                                 headers={"xi-api-key": key, "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180, context=SSL_CTX) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:600]
        raise SystemExit(f"tts: ElevenLabs {e.code} on {path}: {detail}")


def resolve_voice(key: str, voice: dict) -> str:
    if voice.get("voice_id"):
        return voice["voice_id"]
    name = (voice.get("voice_name") or voice.get("name") or "").lower()
    if name:
        for v in el_request("/voices", key).get("voices", []):
            if v.get("name", "").lower().startswith(name):
                return v["voice_id"]
        raise SystemExit(f"tts: no voice named '{name}' in this ElevenLabs account; pass voice_id")
    return "JBFqnCBsd6RMkjVDRZzb"  # "George": warm, measured British narrator from the default library


def synth_elevenlabs(items, key, voice, prev_text, next_text, out_wav: Path, tmp: Path):
    model = voice.get("model_id", DEFAULTS["model_id"])
    v3 = model.startswith("eleven_v3")      # v3 ignores <break/>; an ellipsis is its pause cue
    pieces: list[str] = []
    word_counts: list[tuple[str, int]] = []  # (original word, number of spoken tokens)
    marks_at: dict[str, int] = {}
    for it in items:
        if it[0] == "word":
            pieces.extend(it[2])
            word_counts.append((it[1], len(it[2])))
        elif it[0] == "break":
            if v3 and pieces:
                pieces[-1] += "…"
            elif not v3:
                pieces.append(f'<break time="{it[1]:.2f}s" />')
        else:
            marks_at[it[1]] = len(word_counts)
    text = " ".join(pieces)
    tagfree = re.sub(r"\s+", " ", TAG.sub(" ", text)).strip()
    body = {
        "text": text,
        "model_id": model,
        "voice_settings": {k: voice.get(k, DEFAULTS[k]) for k in
                           ("stability", "similarity_boost", "style", "use_speaker_boost", "speed")},
    }
    if prev_text and not v3:
        body["previous_text"] = prev_text[-600:]
    if next_text and not v3:
        body["next_text"] = next_text[:300]
    if voice.get("language"):
        body["language_code"] = voice["language"]
    vid = resolve_voice(key, voice)
    res = el_request(f"/text-to-speech/{vid}/with-timestamps", key, body, "?output_format=mp3_44100_128")
    mp3 = tmp / "el.mp3"
    mp3.write_bytes(base64.b64decode(res["audio_base64"]))
    to_wav(mp3, out_wav)
    dur = wav_duration(out_wav)

    # Character alignment → tag-free, whitespace-collapsed stream that matches `tagfree`.
    al = res.get("alignment") or res.get("normalized_alignment") or {}
    chars = al.get("characters", [])
    starts = al.get("character_start_times_seconds", [])
    ends = al.get("character_end_times_seconds", [])
    joined = "".join(chars)
    keep = [True] * len(chars)
    for m in TAG.finditer(joined):
        for i in range(m.start(), m.end()):
            keep[i] = False
    stream: list[tuple[str, float, float]] = []
    for c, st, en, k in zip(chars, starts, ends, keep):
        if not k:
            continue
        if c.isspace():
            if not stream or stream[-1][0] == " ":
                continue
            c = " "
        stream.append((c, float(st), float(en)))
    while stream and stream[-1][0] == " ":
        stream.pop()
    ratio = len(stream) / max(1, len(tagfree)) if stream else 1.0

    def t_at(off: int, end: bool) -> float:
        if not stream:
            return dur * off / max(1, len(tagfree))
        j = min(len(stream) - 1, max(0, int(round(off * ratio))))
        return stream[j][2] if end else stream[j][1]

    offs, o = [], 0
    for tok in tagfree.split(" "):
        offs.append((o, o + len(tok))); o += len(tok) + 1
    words, k = [], 0
    for orig, n in word_counts:
        seg = offs[k:k + n] or [offs[-1]]
        k += n
        words.append({"w": orig, "start": round(t_at(seg[0][0], False), 3),
                      "end": round(t_at(max(seg[-1][1] - 1, seg[-1][0]), True), 3)})
    return words, marks_at, {"backend": "elevenlabs", "voice_id": vid, "model_id": model}


# --------------------------------------------------------------------------- say

def synth_say(items, voice, out_wav: Path, tmp: Path):
    if not shutil.which("say"):
        raise SystemExit("tts: no ELEVENLABS_API_KEY and macOS `say` is unavailable. "
                         "Set ELEVENLABS_API_KEY or install a local TTS.")
    sv, rate = voice.get("say_voice", DEFAULTS["say_voice"]), int(voice.get("say_rate", DEFAULTS["say_rate"]))
    # chunk at sentence ends and breaks
    chunks: list[dict] = []
    cur = {"words": [], "marks": [], "pause": SENTENCE_GAP}
    marks_at: dict[str, int] = {}
    nword = 0
    for it in items:
        if it[0] == "word":
            cur["words"].append(it)
            nword += 1
            if re.search(r"[.!?…]['\")\]]*$", it[1]):
                chunks.append(cur); cur = {"words": [], "marks": [], "pause": SENTENCE_GAP}
        elif it[0] == "break":
            if cur["words"]:
                cur["pause"] = it[1]; chunks.append(cur); cur = {"words": [], "marks": [], "pause": SENTENCE_GAP}
            elif chunks:
                chunks[-1]["pause"] = max(chunks[-1]["pause"], it[1])
            else:
                chunks.append({"words": [], "marks": [], "pause": it[1]})
        else:
            marks_at[it[1]] = nword
    if cur["words"]:
        chunks.append(cur)
    parts, words, t = [], [], 0.0
    for i, ch in enumerate(chunks):
        if ch["words"]:
            spoken = " ".join(s for w in ch["words"] for s in w[2])
            aiff, wav = tmp / f"c{i}.aiff", tmp / f"c{i}.wav"
            subprocess.run(["say", "-v", sv, "-r", str(rate), "-o", str(aiff), spoken], check=True)
            to_wav(aiff, wav, trim=True)
            d = wav_duration(wav)
            weights = [sum(len(s) for s in w[2]) + 2.5 for w in ch["words"]]
            total, acc = sum(weights), 0.0
            for w, wt in zip(ch["words"], weights):
                st = t + d * acc / total
                acc += wt
                words.append({"w": w[1], "start": round(st, 3), "end": round(t + d * acc / total - 0.04, 3)})
            parts.append((wav, 0)); t += d
        last = i == len(chunks) - 1
        if not last:
            parts.append((None, ch["pause"])); t += ch["pause"]
    concat_wavs(parts or [(None, 0.5)], out_wav)
    return words, marks_at, {"backend": "say", "voice": sv, "rate": rate}


# --------------------------------------------------------------------------- main

def marks_from_items(items: list[tuple], words: list[dict], duration: float) -> dict[str, float]:
    """A bookmark lands on the start of the next spoken word, unless a <break/> follows it,
    in which case it lands right where the previous word ends (the start of the pause)."""
    out, idx = {}, 0
    for k, it in enumerate(items):
        if it[0] == "word":
            idx += 1
        elif it[0] == "mark":
            nxt = next((x for x in items[k + 1:] if x[0] != "mark"), None)
            if nxt is not None and nxt[0] == "break":
                out[it[1]] = round(words[idx - 1]["end"] + 0.05, 3) if idx > 0 else 0.0
            elif idx < len(words):
                out[it[1]] = words[idx]["start"]
            else:
                out[it[1]] = round(words[-1]["end"] if words else duration, 3)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ws", default="workspace", help="workspace dir (default ./workspace)")
    ap.add_argument("--scene", action="append", help="only these scene ids")
    ap.add_argument("--backend", choices=["auto", "elevenlabs", "say"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--voices", action="store_true", help="list ElevenLabs voices and exit")
    a = ap.parse_args()

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if a.voices:
        if not key:
            sys.exit("tts: ELEVENLABS_API_KEY not set")
        for v in el_request("/voices", key).get("voices", []):
            labels = ", ".join(f"{k}={val}" for k, val in (v.get("labels") or {}).items())
            print(f"{v['voice_id']}  {v.get('name', ''):28s} {labels}")
        return

    ws = Path(a.ws).resolve()
    plan = json.loads((ws / "plan.json").read_text())
    voice = {**DEFAULTS, **(plan.get("voice") or {})}
    backend = a.backend or voice.get("backend") or "auto"
    if backend == "auto":
        backend = "elevenlabs" if key else "say"
    if backend == "elevenlabs" and not key:
        print("tts: ELEVENLABS_API_KEY not set, falling back to macOS say", file=sys.stderr)
        backend = "say"
    pron = plan.get("pronunciations") or {}
    scenes = plan.get("scenes", [])
    (ws / "audio").mkdir(parents=True, exist_ok=True)

    total_chars = 0
    for i, sc in enumerate(scenes):
        sid = sc["id"]
        if a.scene and sid not in a.scene:
            continue
        narration = sc.get("narration", "").strip()
        lead = float(sc.get("lead_in", DEFAULT_LEAD))
        vkey = {k: voice.get(k) for k in sorted(voice) if k != "backend"}
        sha = hashlib.sha256(json.dumps([narration, backend, vkey, pron], sort_keys=True).encode()).hexdigest()[:16]
        jf, wf = ws / "audio" / f"{sid}.json", ws / "audio" / f"{sid}.wav"
        if not a.force and jf.exists() and wf.exists():
            try:
                if json.loads(jf.read_text()).get("sha") == sha:
                    print(f"  = {sid}: unchanged")
                    continue
            except Exception:
                pass
        if not narration:
            concat_wavs([(None, 1.0)], wf)
            jf.write_text(json.dumps({"id": sid, "text": "", "duration": 1.0, "lead_in": 0.0,
                                      "words": [], "marks": {}, "sha": sha}, indent=1))
            continue
        items = parse(narration, pron)
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            if backend == "elevenlabs":
                prev_t = plain_text(scenes[i - 1]["narration"]) if i > 0 else ""
                next_t = plain_text(scenes[i + 1]["narration"]) if i + 1 < len(scenes) else ""
                words, marks_at, meta = synth_elevenlabs(items, key, voice, prev_t, next_t, wf, tmp)
                total_chars += len(plain_text(narration))
            else:
                words, marks_at, meta = synth_say(items, voice, wf, tmp)
        dur = wav_duration(wf)
        data = {"id": sid, "text": plain_text(narration), "duration": round(dur, 3), "lead_in": lead,
                "words": words, "marks": marks_from_items(items, words, dur), "sha": sha, **meta}
        jf.write_text(json.dumps(data, indent=1))
        print(f"  + {sid}: {dur:5.1f}s, {len(words)} words, marks={list(data['marks'])} [{meta['backend']}]")
    if total_chars:
        print(f"tts: ~{total_chars} ElevenLabs characters used")
        # running total for the worker's cost accounting: <job>/.waitwhat/usage.json
        uf = ws.parent / ".waitwhat" / "usage.json"
        try:
            usage = json.loads(uf.read_text()) if uf.exists() else {}
        except Exception:
            usage = {}
        usage["elevenlabs_characters"] = int(usage.get("elevenlabs_characters", 0)) + total_chars
        uf.parent.mkdir(parents=True, exist_ok=True)
        uf.write_text(json.dumps(usage))


if __name__ == "__main__":
    main()
