#!/usr/bin/env python3
"""Narrate every scene in workspace/plan.json BEFORE animating, with word-level timings.

For each scene it writes:
  workspace/audio/<id>.wav    48 kHz mono narration (no lead-in silence; stitch adds it)
  workspace/audio/<id>.json   {duration, lead_in, words:[{w,start,end}], marks:{name:t}, text, sha, ...}

Scene code reads the json through WaitwhatScene (until / wait_until / finish), so the animation
is timed to the voice, not the other way round.

Narration markup (inside plan.json scenes[].narration):
  <bookmark mark="squares"/>   a named moment the animation can wait for
  <bookmark tag="curious"/>    an Eleven v3/v4 audio tag ([curious]) spoken into the audio only;
                               dropped for other models. Can share a bookmark: mark="x" tag="softly"
  <break time="0.8s"/>         a deliberate pause (v3/v4 get "…", [pause] or [long pause] instead)
Per-scene delivery: scenes[].voice may override stability / similarity_boost / style / speed /
max_pause. After synthesis, natural pauses over 0.3 s are compressed (to 0.3 s + 35% of the
excess, at most voice.max_pause, default 0.7 s) and word times shifted to match; pauses written as
<break/> are kept. Set max_pause to 0 to leave the audio untouched.

Providers (first available wins; order from --backend, else WAITWHAT_TTS_PROVIDER, else
plan.voice.backend, else openrouter → elevenlabs → say):
  openrouter  ElevenLabs models through OpenRouter (needs OPENROUTER_API_KEY). One key, one bill.
              Same ElevenLabs engine and controls (voice_settings, previous/next_text, seed,
              mp3 44.1 kHz), but POST /api/v1/audio/speech returns audio only, so word timings
              come from forced alignment: the audio is transcribed with ElevenLabs Scribe
              (POST /api/v1/audio/transcriptions, word timestamps) and the transcript is aligned
              to the script. If that fails, words are timed proportionally inside each sentence.
  elevenlabs  direct ElevenLabs API, /v1/text-to-speech/{voice_id}/with-timestamps
              (needs ELEVENLABS_API_KEY); native character timings.
  say         macOS `say`, free and offline. Sentence-by-sentence, so sentence boundaries, pauses
              and bookmarks at sentence starts are exact; word times inside a sentence are estimated.

WAITWHAT_TTS_PROVIDER may be one provider or a comma-separated order, e.g. "elevenlabs,say".

Billing: every OpenRouter call's real cost (generation stats for speech, the usage object for
transcription) is added to <job>/.waitwhat/usage.json:
  {"openrouter_audio_cost_usd", "tts_characters", "stt_seconds", "tts_model", "voice",
   "elevenlabs_characters" (legacy, = tts_characters)}

Usage:
  tts.py                         # all scenes whose narration or voice changed (cache by sha)
  tts.py --scene hook --scene aha --force
  tts.py --backend say
  tts.py --voices                # list voices and models (no characters spent)
"""
from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import wave
from pathlib import Path

EL_API = "https://api.elevenlabs.io/v1"
OR_API = "https://openrouter.ai/api/v1"
SR = 48000
DEFAULT_LEAD = 0.35
SENTENCE_GAP = 0.28
PROVIDERS = ("openrouter", "elevenlabs", "say")
SETTINGS = ("stability", "similarity_boost", "style", "use_speaker_boost", "speed")
DEFAULTS = {
    "model_id": "elevenlabs/eleven-multilingual-v2",
    "stability": 0.45,
    "similarity_boost": 0.8,
    "style": 0.15,
    "speed": 1.12,           # multilingual-v2: ~170 wpm at 1.0, ~200-210 at 1.12 for the US default voices
    "use_speaker_boost": True,
    "max_pause": 0.7,        # natural pauses are compressed and capped here (explicit <break/>s are kept)
    "stt_model": "elevenlabs/scribe-v2",
    "say_voice": "Daniel",
    "say_rate": 182,
}
DEFAULT_VOICE = "brian"                     # deep, resonant American narrator (premade)
DEFAULT_VOICE_ID = "nPczCjzI2devNBz1zQrb"   # the same voice by ElevenLabs id (direct API)
# Premade voices OpenRouter accepts by name (GET /api/v1/models?output_modalities=speech →
# supported_voices). Any ElevenLabs voice id also works; cloned/designed voices need BYOK.
OR_VOICES = ("george", "sarah", "adam", "alice", "bella", "bill", "brian", "callum", "charlie",
             "chris", "daniel", "eric", "harry", "jessica", "laura", "liam", "lily", "matilda",
             "river", "roger", "will")
# Max characters per request (OpenRouter launch post, 2026-10-07). Tags count as characters.
OR_LIMITS = {
    "elevenlabs/eleven-v4": 10000, "elevenlabs/eleven-v4-turbo": 10000,
    "elevenlabs/eleven-v3": 5000, "elevenlabs/eleven-v3-conversational": 5000,
    "elevenlabs/eleven-multilingual-v2": 10000,
    "elevenlabs/eleven-flash-v2.5": 40000, "elevenlabs/eleven-flash-v2": 30000,
    "elevenlabs/eleven-turbo-v2.5": 40000, "elevenlabs/eleven-turbo-v2": 30000,
}
RETRY_STATUS = {408, 429, 500, 502, 503, 504, 524, 529}


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
AUDIO_TAG = re.compile(r"\[[A-Za-z][A-Za-z \-']*\]")
SENT_END = re.compile(r"[.!?…]['\")\]]*$")


def warn(msg: str) -> None:
    print(f"tts: {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- parsing

def parse(narration: str, pron: dict[str, str]) -> list[tuple]:
    """→ items: ("word", original, [spoken...]) | ("break", seconds) | ("mark", name) | ("tag", "[x]")."""
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
            if attrs.get("tag"):
                items.append(("tag", "[" + attrs["tag"].strip("[] ").lower() + "]"))
            name = attrs.get("mark") or attrs.get("name")
            if name or not attrs.get("tag"):
                items.append(("mark", name or f"m{len(items)}"))
        else:
            t = attrs.get("time", "0.5s").strip().lower()
            secs = float(t[:-2]) / 1000 if t.endswith("ms") else float(t.rstrip("s") or 0.5)
            items.append(("break", max(0.0, min(secs, 3.0))))
        pos = m.end()
    add_text(narration[pos:])
    return items


def plain_text(narration: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub(" ", narration)).strip()


def sentence_groups(items: list[tuple]) -> list[list[int]]:
    """Word indices grouped into sentences (split at . ! ? … and at <break/>)."""
    groups, cur, n = [], [], 0
    for it in items:
        if it[0] == "word":
            cur.append(n); n += 1
            if SENT_END.search(it[1]):
                groups.append(cur); cur = []
        elif it[0] == "break" and cur:
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)
    return groups


def expressive(model: str) -> bool:
    """Eleven v3/v4: audio tags, no <break> support, no style/speed controls."""
    return bool(re.search(r"eleven[-_]v[34]", model))


def pause_cue(secs: float) -> str:
    """v3/v4 ignore <break/>; measured on eleven-v4: "…" ≈ 0.55 s, [pause] ≈ 1.0 s, [long pause] ≈ 1.7 s."""
    return "…" if secs < 0.8 else "[pause]" if secs < 1.4 else "[long pause]"


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


def silences(wav: Path, noise_db: int = -40, min_d: float = 0.15) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af",
                        f"silencedetect=n={noise_db}dB:d={min_d}", "-f", "null", "-"],
                       capture_output=True, text=True)
    out, start = [], None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            out.append((start, float(m.group(1)))); start = None
    if start is not None:
        out.append((start, wav_duration(wav)))
    return out


def tighten(wav: Path, items: list[tuple], words: list[dict], max_pause: float,
            knee: float = 0.3, ratio: float = 0.35) -> list[dict]:
    """Compress natural pauses (sentence ends the model lingers on): silence beyond `knee` is
    shortened to `ratio` of its length and capped at `max_pause`, cutting from the middle so the
    breath on each side stays. Pauses that follow an explicit <break/> are kept. Word times are
    shifted to match. Returns the remapped words; rewrites `wav` in place."""
    if not max_pause or not words:
        return words
    after_break: set[int] = set()
    n = 0
    for it in items:
        if it[0] == "word":
            n += 1
        elif it[0] == "break" and n:
            after_break.add(n - 1)
    total = wav_duration(wav)
    cuts: list[tuple[float, float]] = []
    for s, e in silences(wav, -38, knee + 0.04):
        if s <= 0.02 or e >= total - 0.02:
            continue
        prev = min(range(len(words)), key=lambda i: abs(words[i]["end"] - s))
        if prev in after_break and abs(words[prev]["end"] - s) < 0.4:
            continue
        gap = e - s
        keep = min(max_pause, knee + ratio * (gap - knee))
        if gap - keep > 0.03:
            cuts.append((s + keep / 2, e - keep / 2))
    if not cuts:
        return words
    with wave.open(str(wav)) as w:
        sr, frames = w.getframerate(), w.readframes(w.getnframes())
    out, pos = bytearray(), 0
    for a, b in cuts:
        out += frames[pos * 2:int(a * sr) * 2]
        pos = int(b * sr)
    out += frames[pos * 2:]
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(bytes(out))

    def remap(t: float) -> float:
        shift = 0.0
        for a, b in cuts:
            if t >= b:
                shift += b - a
            elif t > a:
                return round(a - shift, 3)
        return round(t - shift, 3)
    return [{**w, "start": remap(w["start"]), "end": remap(w["end"])} for w in words]


# --------------------------------------------------------------------------- http

def http(method: str, url: str, headers: dict, body: bytes | None = None, timeout: int = 180,
         label: str = "", tries: int = 3) -> tuple[int, dict, bytes]:
    """Request with retry on transient failures. Returns (status, headers, body); raises SystemExit
    with the API's error message (never the key) on a permanent error."""
    last = ""
    for attempt in range(tries):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:600]
            last = f"{e.code}: {detail}"
            if e.code not in RETRY_STATUS:
                raise SystemExit(f"tts: {label or url} failed {last}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = str(e)
        time.sleep(2 * (attempt + 1))
    raise SystemExit(f"tts: {label or url} failed after {tries} tries ({last})")


def or_headers(key: str, json_body: bool = True) -> dict:
    h = {"Authorization": f"Bearer {key}", "X-Title": "waitwhat",
         "HTTP-Referer": "https://github.com/luiginotmario/waitwhat"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def or_json(key: str, path: str) -> dict:
    _, _, raw = http("GET", f"{OR_API}{path}", or_headers(key, False), label=f"OpenRouter GET {path}")
    return json.loads(raw)


# --------------------------------------------------------------------------- usage / cost

class Usage:
    """Measured spend for this run, merged into <job>/.waitwhat/usage.json at the end."""

    def __init__(self, key: str = ""):
        self.key = key
        self.cost = 0.0
        self.tts_chars = 0
        self.stt_seconds = 0.0
        self.model: str | None = None
        self.voice: str | None = None
        self.pending: list[tuple[str, float]] = []   # (generation id, list-price estimate)
        self._prices: dict[str, float] | None = None

    def price(self, model: str) -> float:
        if self._prices is None:
            self._prices = {}
            try:
                for m in or_json(self.key, "/models?output_modalities=all").get("data", []):
                    self._prices[m["id"]] = float((m.get("pricing") or {}).get("prompt") or 0)
            except BaseException:
                pass
        return self._prices.get(model, 0.0)

    def add_tts(self, gen_id: str | None, chars: int, model: str, voice: str) -> None:
        self.tts_chars += chars
        self.model, self.voice = model, voice
        if gen_id:
            self.pending.append((gen_id, chars * self.price(model)))
        else:
            self.cost += chars * self.price(model)
            warn("speech response had no X-Generation-Id; cost estimated from list price")

    def add_stt(self, gen_id: str | None, usage: dict, seconds: float, model: str) -> None:
        secs = float(usage.get("seconds") or seconds or 0)
        self.stt_seconds += secs
        if usage.get("cost") is not None:
            self.cost += float(usage["cost"])
        elif gen_id:
            self.pending.append((gen_id, secs * self.price(model)))
        else:
            self.cost += secs * self.price(model)

    def resolve(self) -> None:
        """Generation stats appear a few seconds after the call; poll until each is in."""
        deadline = time.time() + 60
        for gen_id, est in self.pending:
            got = None
            while got is None and time.time() < deadline:
                try:
                    req = urllib.request.Request(f"{OR_API}/generation?id={gen_id}",
                                                 headers=or_headers(self.key, False))
                    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
                        d = json.loads(r.read()).get("data") or {}
                    tc = d.get("total_cost", d.get("usage"))
                    if tc is not None:
                        got = float(tc)
                        break
                except urllib.error.HTTPError as e:
                    if e.code not in (404, 429, 500, 502, 503):
                        break
                except Exception:
                    pass
                time.sleep(2)
            if got is None:
                warn(f"no generation stats for {gen_id}; using the list-price estimate ${est:.5f}")
                got = est
            self.cost += got
        self.pending = []

    def write(self, uf: Path) -> None:
        if not (self.tts_chars or self.stt_seconds or self.cost):
            return
        try:
            usage = json.loads(uf.read_text()) if uf.exists() else {}
        except Exception:
            usage = {}
        base_chars = int(usage.get("tts_characters", usage.get("elevenlabs_characters", 0)) or 0)
        usage["openrouter_audio_cost_usd"] = round(float(usage.get("openrouter_audio_cost_usd", 0) or 0)
                                                   + self.cost, 6)
        usage["tts_characters"] = base_chars + self.tts_chars
        usage["stt_seconds"] = round(float(usage.get("stt_seconds", 0) or 0) + self.stt_seconds, 3)
        if self.model:
            usage["tts_model"] = self.model
        if self.voice:
            usage["voice"] = self.voice
        usage["elevenlabs_characters"] = usage["tts_characters"]  # legacy key
        uf.parent.mkdir(parents=True, exist_ok=True)
        uf.write_text(json.dumps(usage))


# --------------------------------------------------------------------------- model / voice ids

def or_model(m: str | None) -> str:
    """eleven_multilingual_v2 / eleven_flash_v2_5 → elevenlabs/eleven-multilingual-v2 / -flash-v2.5."""
    m = (m or DEFAULTS["model_id"]).strip()
    if "/" in m:
        return m
    m = re.sub(r"v(\d)_(\d)$", r"v\1.\2", m)
    return "elevenlabs/" + m.replace("_", "-")


def el_model(m: str | None) -> str:
    m = (m or DEFAULTS["model_id"]).strip().split("/")[-1]
    return m.replace(".", "_").replace("-", "_")


def or_voice(voice: dict) -> str:
    vid = (voice.get("voice_id") or "").strip()
    if vid:
        return vid.lower() if vid.lower() in OR_VOICES else vid
    name = (voice.get("voice_name") or voice.get("name") or "").strip().lower()
    if name:
        first = re.split(r"[\s\-–,]+", name)[0]
        if first in OR_VOICES:
            return first
        raise SystemExit(f"tts: '{name}' is not an OpenRouter premade voice ({', '.join(OR_VOICES)}); "
                         "set plan.voice.voice_id to an ElevenLabs voice id instead")
    return DEFAULT_VOICE


def voice_settings(voice: dict, model: str) -> dict:
    """The ElevenLabs voice_settings object a model accepts. v3/v4 have no style or speed control
    (v4 returns 400 on speed); v3 only takes stability 0, 0.5 or 1."""
    if expressive(model):
        st = float(voice.get("stability", DEFAULTS["stability"]))
        if re.search(r"v3", model):
            st = min((0.0, 0.5, 1.0), key=lambda x: abs(x - st))
        return {"stability": st, "similarity_boost": voice.get("similarity_boost", DEFAULTS["similarity_boost"])}
    return {k: voice.get(k, DEFAULTS[k]) for k in SETTINGS}


def spoken_text(items: list[tuple], expr: bool, cut_breaks: bool = False) -> tuple[list[dict], list, dict]:
    """→ sentences [{pieces, pause}], words_sp [(orig, spoken)], marks_at {name: word index}.
    Breaks become <break/> tags (v2 family) or pause cues (v3/v4); audio tags are kept for v3/v4."""
    words_sp: list[tuple[str, list[str]]] = []
    marks_at: dict[str, int] = {}
    sents: list[dict] = []
    cur: list[str] = []
    pending_tags: list[str] = []
    for it in items:
        if it[0] == "word":
            cur.extend(pending_tags); pending_tags = []
            cur.extend(it[2]); words_sp.append((it[1], it[2]))
            if SENT_END.search(it[1]):
                sents.append({"pieces": cur, "pause": 0.0}); cur = []
        elif it[0] == "break":
            if cur:
                sents.append({"pieces": cur, "pause": it[1]}); cur = []
            elif sents:
                sents[-1]["pause"] = max(sents[-1]["pause"], it[1])
        elif it[0] == "tag":
            if expr:
                pending_tags.append(it[1])
        else:
            marks_at[it[1]] = len(words_sp)
    cur.extend(pending_tags)
    if cur:
        sents.append({"pieces": cur, "pause": 0.0})
    return sents, words_sp, marks_at


def render(sents: list[dict], expr: bool) -> str:
    out: list[str] = []
    for k, s in enumerate(sents):
        out.extend(s["pieces"])
        if s["pause"] and k < len(sents) - 1:
            if not expr:
                out.append(f'<break time="{s["pause"]:.2f}s" />')
            else:
                cue = pause_cue(s["pause"])
                if cue == "…":
                    out[-1] = out[-1].rstrip(".,;:") + "…"
                else:
                    out.append(cue)
    return " ".join(out)


# --------------------------------------------------------------------------- forced alignment

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen " \
       "fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
ORD = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
       "nine": "ninth", "twelve": "twelfth"}


def num_words(n: int) -> list[str]:
    if n < 20:
        return [ONES[n]]
    if n < 100:
        return [TENS[n // 10]] + (num_words(n % 10) if n % 10 else [])
    if n < 1000:
        return [ONES[n // 100], "hundred"] + (num_words(n % 100) if n % 100 else [])
    for size, word in ((10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= size:
            return num_words(n // size) + [word] + (num_words(n % size) if n % size else [])
    return [str(n)]


def ordinal(words: list[str]) -> list[str]:
    last = words[-1]
    last = ORD.get(last) or (last[:-1] + "ieth" if last.endswith("y") else last + "th")
    return words[:-1] + [last]


def norm_tokens(s: str) -> list[str]:
    """Lowercase, accent-free, punctuation-free tokens with digits spelled out, so "2,500" and
    "two thousand five hundred" (or "Pythagoras'" and "pythagoras") compare equal."""
    s = AUDIO_TAG.sub(" ", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ").replace("%", " percent ").replace("’", "'")
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    s = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", s)
    s = re.sub(r"\b(\d+) (st|nd|rd|th)\b", r"\1#", s)
    out: list[str] = []
    for tok in re.findall(r"\d+#|\d+(?:\.\d+)?|[a-z']+", s):
        if tok.endswith("#"):
            out += ordinal(num_words(int(tok[:-1])))
        elif tok[0].isdigit():
            whole, _, frac = tok.partition(".")
            out += num_words(int(whole)) if len(whole) <= 15 else list(whole)
            if frac:
                out += ["point"] + [ONES[int(d)] for d in frac]
        else:
            tok = tok.replace("'", "")
            if tok:
                out.append(tok)
    return out


def align(words_sp: list[tuple[str, list[str]]], stt: list[tuple[str, float, float]],
          dur: float) -> tuple[list[dict] | None, float]:
    """Map transcript word times onto the script's words. Returns (words, match ratio 0..1)."""
    S, S_owner = [], []
    for i, (_, spoken) in enumerate(words_sp):
        for t in norm_tokens(" ".join(spoken)):
            S.append(t); S_owner.append(i)
    T, T_time = [], []
    for w, st, en in stt:
        toks = norm_tokens(w)
        total = sum(len(t) for t in toks) or 1
        acc = 0
        for t in toks:
            a = st + (en - st) * acc / total
            acc += len(t)
            T.append(t); T_time.append((a, st + (en - st) * acc / total))
    if not S or not T:
        return None, 0.0
    sub: list[tuple[float, float] | None] = [None] * len(S)
    matched = 0.0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, S, T, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                sub[i1 + k] = T_time[j1 + k]
            matched += i2 - i1
        elif tag == "replace":
            if i2 - i1 == j2 - j1:   # same count: misheard or respelled words, pair them up
                for k in range(i2 - i1):
                    sub[i1 + k] = T_time[j1 + k]
                    matched += 0.5 + 0.5 * difflib.SequenceMatcher(None, S[i1 + k], T[j1 + k]).ratio()
            else:                    # e.g. "1905" said as "nineteen oh five": spread the span
                a, b = T_time[j1][0], T_time[j2 - 1][1]
                lens = [len(x) for x in S[i1:i2]]
                tot, acc = sum(lens) or 1, 0
                for k, ln in enumerate(lens):
                    sub[i1 + k] = (a + (b - a) * acc / tot, a + (b - a) * (acc + ln) / tot)
                    acc += ln
                matched += 0.5 * min(i2 - i1, j2 - j1)
    ratio = matched / len(S)

    n = len(words_sp)
    st: list[float | None] = [None] * n
    en: list[float | None] = [None] * n
    for k, t in enumerate(sub):
        if t is None:
            continue
        i = S_owner[k]
        st[i] = t[0] if st[i] is None else min(st[i], t[0])
        en[i] = t[1] if en[i] is None else max(en[i], t[1])
    # words the transcript skipped: interpolate between neighbours, weighted by length
    weight = [max(1, len(o)) for o, _ in words_sp]
    i = 0
    while i < n:
        if st[i] is not None:
            i += 1
            continue
        j = i
        while j < n and st[j] is None:
            j += 1
        lo = en[i - 1] if i > 0 else None
        hi = st[j] if j < n else None
        span = sum(weight[i:j]) * 0.07
        if lo is None and hi is None:
            lo, hi = 0.0, dur
        elif lo is None:
            lo = max(0.0, hi - span)
        elif hi is None:
            hi = min(dur, lo + span)
        tot, acc = sum(weight[i:j]), 0
        for k in range(i, j):
            st[k] = lo + (hi - lo) * acc / tot
            acc += weight[k]
            en[k] = lo + (hi - lo) * acc / tot
        i = j
    words, prev = [], 0.0
    for k, (orig, _) in enumerate(words_sp):
        s = min(max(st[k], prev), dur)
        e = min(max(en[k], s), dur)
        words.append({"w": orig, "start": round(s, 3), "end": round(e, 3)})
        prev = s
    return words, ratio


def proportional(items: list[tuple], wav: Path, dur: float) -> list[dict]:
    """Fallback timing: find the pauses between sentences in the audio, then spread each sentence's
    words over its stretch of speech by length."""
    orig = [it[1] for it in items if it[0] == "word"]
    groups = sentence_groups(items)
    sil = silences(wav)
    head = sil[0][1] if sil and sil[0][0] <= 0.02 else 0.0
    tail = sil[-1][0] if sil and sil[-1][1] >= dur - 0.02 else dur
    gaps = sorted([g for g in sil if g[0] > head + 0.05 and g[1] < tail - 0.05],
                  key=lambda g: g[1] - g[0], reverse=True)[:max(0, len(groups) - 1)]
    gaps.sort()
    if len(gaps) == len(groups) - 1:
        spans, a = [], head
        for g in gaps:
            spans.append((a, g[0])); a = g[1]
        spans.append((a, tail))
    else:
        groups = [[i for g in groups for i in g]]
        spans = [(head, tail)]
    words: list[dict] = [None] * len(orig)  # type: ignore[list-item]
    for g, (a, b) in zip(groups, spans):
        wt = [len(orig[i]) + 2.5 for i in g]
        tot, acc = sum(wt), 0.0
        for i, w in zip(g, wt):
            s = a + (b - a) * acc / tot
            acc += w
            words[i] = {"w": orig[i], "start": round(s, 3), "end": round(a + (b - a) * acc / tot - 0.03, 3)}
    return words


# --------------------------------------------------------------------------- openrouter

def chunk(sents: list[dict], limit: int, expr: bool) -> list[dict]:
    """Group sentences into requests under the model's character limit → [{text, pause_after}]."""
    chunks: list[dict] = []
    group: list[dict] = []
    for s in sents:
        if len(render([s], expr)) > limit:   # one huge sentence: split it at word boundaries
            if group:
                chunks.append({"text": render(group, expr), "pause_after": group[-1]["pause"]}); group = []
            buf: list[str] = []
            for w in s["pieces"]:
                if buf and len(" ".join(buf + [w])) > limit:
                    chunks.append({"text": " ".join(buf), "pause_after": 0.0}); buf = []
                buf.append(w)
            if buf:
                chunks.append({"text": " ".join(buf), "pause_after": s["pause"]})
            continue
        if group and len(render(group + [s], expr)) > limit:
            chunks.append({"text": render(group, expr), "pause_after": group[-1]["pause"]}); group = []
        group.append(s)
    if group:
        chunks.append({"text": render(group, expr), "pause_after": 0.0})
    return chunks


def or_speech(key: str, body: dict) -> tuple[bytes, str | None]:
    _, hdr, raw = http("POST", f"{OR_API}/audio/speech", or_headers(key), json.dumps(body).encode(),
                       label="OpenRouter /audio/speech")
    if not hdr.get("content-type", "").startswith("audio/"):
        raise SystemExit(f"tts: OpenRouter speech returned {hdr.get('content-type')}: {raw[:300]!r}")
    return raw, hdr.get("x-generation-id")


def or_transcribe(key: str, audio: Path, fmt: str, model: str, language: str | None,
                  acct: Usage, seconds: float) -> list[tuple[str, float, float]]:
    body = {"model": model,
            "input_audio": {"data": base64.b64encode(audio.read_bytes()).decode(), "format": fmt},
            "response_format": "verbose_json", "timestamp_granularities": ["word"]}
    if language:
        body["language"] = language
    _, hdr, raw = http("POST", f"{OR_API}/audio/transcriptions", or_headers(key),
                       json.dumps(body).encode(), label="OpenRouter /audio/transcriptions")
    res = json.loads(raw)
    acct.add_stt(hdr.get("x-generation-id"), res.get("usage") or {}, seconds, model)
    words = [(w["word"], float(w["start"]), float(w["end"])) for w in res.get("words") or []
             if w.get("type", "word") == "word" and w.get("start") is not None]
    if not words:
        raise RuntimeError("transcript has no word timestamps")
    return words


def synth_openrouter(items, key, voice, prev_text, next_text, out_wav: Path, tmp: Path, acct: Usage):
    model = or_model(voice.get("model_id"))
    expr = expressive(model)
    vname = or_voice(voice)
    sents, words_sp, marks_at = spoken_text(items, expr)
    chunks = chunk(sents, OR_LIMITS.get(model, 5000) - 100, expr)
    base_opts: dict = {"voice_settings": voice_settings(voice, model)}
    if voice.get("language"):
        base_opts["language_code"] = voice["language"]
    if voice.get("seed") is not None:
        base_opts["seed"] = int(voice["seed"])
    parts: list[tuple[Path | None, float]] = []
    stt: list[tuple[str, float, float]] = []
    offset, stt_ok = 0.0, True
    for ci, ch in enumerate(chunks):
        opts = dict(base_opts)
        before = chunks[ci - 1]["text"] if ci > 0 else prev_text
        after = chunks[ci + 1]["text"] if ci + 1 < len(chunks) else next_text
        if before:   # request stitching: intonation continues across scenes and chunks
            opts["previous_text"] = AUDIO_TAG.sub("", TAG.sub(" ", before))[-600:].strip()
        if after:
            opts["next_text"] = AUDIO_TAG.sub("", TAG.sub(" ", after))[:300].strip()
        body = {"model": model, "input": ch["text"], "voice": vname, "response_format": "mp3",
                "provider": {"options": {"elevenlabs": opts}}}
        audio, gen = or_speech(key, body)
        acct.add_tts(gen, len(ch["text"]), model, vname)
        mp3, wav = tmp / f"c{ci}.mp3", tmp / f"c{ci}.wav"
        mp3.write_bytes(audio)
        to_wav(mp3, wav)
        d = wav_duration(wav)
        if stt_ok:
            try:
                for w, s, e in or_transcribe(key, mp3, "mp3", voice.get("stt_model", DEFAULTS["stt_model"]),
                                             voice.get("language"), acct, d):
                    stt.append((w, s + offset, e + offset))
            except (RuntimeError, SystemExit, ValueError, KeyError) as e:
                warn(f"transcription failed ({e}); falling back to proportional timing")
                stt_ok = False
        parts.append((wav, 0.0)); offset += d
        if ch["pause_after"] and ci < len(chunks) - 1:
            parts.append((None, ch["pause_after"])); offset += ch["pause_after"]
    concat_wavs(parts, out_wav)
    dur = wav_duration(out_wav)
    words, ratio = align(words_sp, stt, dur) if stt_ok else (None, 0.0)
    method = "stt"
    if words is None or ratio < 0.6:
        if stt_ok:
            warn(f"alignment matched only {ratio:.0%} of words; using proportional timing per sentence")
        words, method = proportional(items, out_wav, dur), "proportional"
    return words, marks_at, {"backend": "openrouter", "voice": vname, "model_id": model,
                             "chunks": len(chunks), "align": {"method": method, "match": round(ratio, 3)}}


# --------------------------------------------------------------------------- elevenlabs (direct)

def el_request(path: str, key: str, body: dict | None = None, query: str = "") -> dict:
    _, _, raw = http("POST" if body is not None else "GET", f"{EL_API}{path}{query}",
                     {"xi-api-key": key, "Content-Type": "application/json", "Accept": "application/json"},
                     json.dumps(body).encode() if body is not None else None, label=f"ElevenLabs {path}")
    return json.loads(raw)


def resolve_voice(key: str, voice: dict) -> str:
    vid = (voice.get("voice_id") or "").strip()
    name = (voice.get("voice_name") or voice.get("name") or "").strip().lower()
    if vid and vid.lower() not in OR_VOICES:
        return vid
    name = vid.lower() or name
    if name:
        for v in el_request("/voices", key).get("voices", []):
            if v.get("name", "").lower().startswith(name):
                return v["voice_id"]
        raise SystemExit(f"tts: no voice named '{name}' in this ElevenLabs account; pass voice_id")
    return DEFAULT_VOICE_ID


def synth_elevenlabs(items, key, voice, prev_text, next_text, out_wav: Path, tmp: Path, acct: Usage):
    model = el_model(voice.get("model_id"))
    expr = expressive(model)
    sents, words_sp, marks_at = spoken_text(items, expr)
    text = render(sents, expr)
    # tag-free, whitespace-collapsed text: what the alignment's characters are matched against
    strip = lambda s: re.sub(r"\s+", " ", AUDIO_TAG.sub(" ", TAG.sub(" ", s))).strip()  # noqa: E731
    tagfree = strip(text)
    body = {"text": text, "model_id": model, "voice_settings": voice_settings(voice, model)}
    if prev_text:
        body["previous_text"] = prev_text[-600:]
    if next_text:
        body["next_text"] = next_text[:300]
    if voice.get("language"):
        body["language_code"] = voice["language"]
    if voice.get("seed") is not None:
        body["seed"] = int(voice["seed"])
    vid = resolve_voice(key, voice)
    res = el_request(f"/text-to-speech/{vid}/with-timestamps", key, body, "?output_format=mp3_44100_128")
    acct.tts_chars += len(text)
    acct.model, acct.voice = model, vid
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
    for rx in (TAG, AUDIO_TAG):
        for m in rx.finditer(joined):
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
    while stream and stream[0][0] == " ":
        stream.pop(0)
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
    for orig, spoken in words_sp:
        n = len(spoken)
        seg = offs[k:k + n] or [offs[-1]]
        k += n
        words.append({"w": orig, "start": round(t_at(seg[0][0], False), 3),
                      "end": round(t_at(max(seg[-1][1] - 1, seg[-1][0]), True), 3)})
    return words, marks_at, {"backend": "elevenlabs", "voice_id": vid, "model_id": model}


# --------------------------------------------------------------------------- say

def synth_say(items, voice, out_wav: Path, tmp: Path):
    if not shutil.which("say"):
        raise SystemExit("tts: no OPENROUTER_API_KEY / ELEVENLABS_API_KEY and macOS `say` is unavailable. "
                         "Set OPENROUTER_API_KEY or install a local TTS.")
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
            if SENT_END.search(it[1]):
                chunks.append(cur); cur = {"words": [], "marks": [], "pause": SENTENCE_GAP}
        elif it[0] == "break":
            if cur["words"]:
                cur["pause"] = it[1]; chunks.append(cur); cur = {"words": [], "marks": [], "pause": SENTENCE_GAP}
            elif chunks:
                chunks[-1]["pause"] = max(chunks[-1]["pause"], it[1])
            else:
                chunks.append({"words": [], "marks": [], "pause": it[1]})
        elif it[0] == "mark":
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
            nxt = next((x for x in items[k + 1:] if x[0] not in ("mark", "tag")), None)
            if nxt is not None and nxt[0] == "break":
                out[it[1]] = round(words[idx - 1]["end"] + 0.05, 3) if idx > 0 else 0.0
            elif idx < len(words):
                out[it[1]] = words[idx]["start"]
            else:
                out[it[1]] = round(words[-1]["end"] if words else duration, 3)
    return out


def available(p: str) -> bool:
    if p == "openrouter":
        return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    if p == "elevenlabs":
        return bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())
    return bool(shutil.which("say"))


def choose_provider(cli: str | None, plan_backend: str | None) -> str:
    env = os.environ.get("WAITWHAT_TTS_PROVIDER", "").strip().lower()
    wanted: list[str] = []
    for src in (cli, env, plan_backend):
        if src and src != "auto":
            wanted = [p.strip() for p in src.split(",") if p.strip()]
            break
    bad = [p for p in wanted if p not in PROVIDERS]
    if bad:
        raise SystemExit(f"tts: unknown provider {bad} (choose from {', '.join(PROVIDERS)})")
    order = wanted + [p for p in PROVIDERS if p not in wanted]
    for p in order:
        if available(p):
            if wanted and p != wanted[0]:
                warn(f"{wanted[0]} is not available (no key), using {p}")
            return p
    raise SystemExit("tts: no provider available: set OPENROUTER_API_KEY (or ELEVENLABS_API_KEY), "
                     "or run on macOS for the `say` fallback")


def list_voices(provider: str) -> None:
    if provider == "elevenlabs":
        key = os.environ["ELEVENLABS_API_KEY"].strip()
        for v in el_request("/voices", key).get("voices", []):
            labels = ", ".join(f"{k}={val}" for k, val in (v.get("labels") or {}).items())
            print(f"{v['voice_id']}  {v.get('name', ''):28s} {labels}")
        return
    if provider == "say":
        subprocess.run(["say", "-v", "?"])
        return
    key = os.environ["OPENROUTER_API_KEY"].strip()
    voices: set[str] = set()
    for m in or_json(key, "/models?output_modalities=speech").get("data", []):
        if not m["id"].startswith("elevenlabs/"):
            continue
        voices.update(m.get("supported_voices") or [])
        per_k = float((m.get("pricing") or {}).get("prompt") or 0) * 1000
        print(f"model  {m['id']:38s} ${per_k:.3f}/1k chars  limit {OR_LIMITS.get(m['id'], '?')} chars")
    print("voices", ", ".join(sorted(voices)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ws", default="workspace", help="workspace dir (default ./workspace)")
    ap.add_argument("--scene", action="append", help="only these scene ids")
    ap.add_argument("--backend", choices=["auto", *PROVIDERS])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--voices", action="store_true", help="list voices (and models) and exit")
    a = ap.parse_args()

    if a.voices:
        list_voices(choose_provider(a.backend, None))
        return

    ws = Path(a.ws).resolve()
    plan = json.loads((ws / "plan.json").read_text())
    voice = {**DEFAULTS, **(plan.get("voice") or {})}
    backend = choose_provider(a.backend, voice.get("backend"))
    or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    el_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    acct = Usage(or_key)
    pron = plan.get("pronunciations") or {}
    scenes = plan.get("scenes", [])
    (ws / "audio").mkdir(parents=True, exist_ok=True)

    try:
        for i, sc in enumerate(scenes):
            sid = sc["id"]
            if a.scene and sid not in a.scene:
                continue
            narration = sc.get("narration", "").strip()
            lead = float(sc.get("lead_in", DEFAULT_LEAD))
            sv = {**voice, **{k: v for k, v in (sc.get("voice") or {}).items() if k in (*SETTINGS, "max_pause")}}
            vkey = {k: sv.get(k) for k in sorted(sv) if k != "backend"}
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
            prev_t = plain_text(scenes[i - 1].get("narration", "")) if i > 0 else ""
            next_t = plain_text(scenes[i + 1].get("narration", "")) if i + 1 < len(scenes) else ""
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td)
                if backend == "openrouter":
                    words, marks_at, meta = synth_openrouter(items, or_key, sv, prev_t, next_t, wf, tmp, acct)
                elif backend == "elevenlabs":
                    words, marks_at, meta = synth_elevenlabs(items, el_key, sv, prev_t, next_t, wf, tmp, acct)
                else:
                    words, marks_at, meta = synth_say(items, sv, wf, tmp)
            words = tighten(wf, items, words, float(sv.get("max_pause") or 0))
            dur = wav_duration(wf)
            data = {"id": sid, "text": plain_text(narration), "duration": round(dur, 3), "lead_in": lead,
                    "words": words, "marks": marks_from_items(items, words, dur), "sha": sha, **meta}
            jf.write_text(json.dumps(data, indent=1))
            extra = f" align={meta['align']['method']}:{meta['align']['match']:.0%}" if "align" in meta else ""
            print(f"  + {sid}: {dur:5.1f}s, {len(words)} words, marks={list(data['marks'])} "
                  f"[{meta['backend']}]{extra}")
    finally:
        # running totals for the worker's cost accounting: <job>/.waitwhat/usage.json
        if acct.pending:
            acct.resolve()
        if acct.tts_chars or acct.stt_seconds:
            acct.write(ws.parent / ".waitwhat" / "usage.json")
            cost = f", ${acct.cost:.4f} measured" if backend == "openrouter" else ""
            print(f"tts: {acct.tts_chars} characters, {acct.stt_seconds:.1f}s transcribed{cost}")


if __name__ == "__main__":
    main()
