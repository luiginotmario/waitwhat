#!/usr/bin/env python3
"""Procedural, license-free sound for waitwhat videos (numpy + scipy, no samples).

  music.py bed  --mood calm --seconds 150 -o bed.wav    # ambient pad bed, loops seamlessly
  music.py sfx  -o DIR                                   # whoosh.wav, scribble.wav, pop.wav
  music.py loops -o assets/music                         # (re)generate the shipped 60 s loops

Moods: calm (warm major 7ths), curious (minor 9ths, a little suspense),
       bright (lydian, gentle pluck arpeggio), focus (sparse, low, for dense technical topics).
Everything here is generated from scratch by this file, so it is MIT like the rest of the repo.
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000

MOODS = {
    #           chords as MIDI notes (bass first),                       pluck?, tempo (s/chord), brightness
    "calm":    ([[48, 55, 59, 62, 64], [45, 52, 55, 59, 60], [41, 48, 52, 55, 57], [43, 50, 53, 57, 59]], False, 8.0, 1600),
    "curious": ([[50, 57, 60, 64, 65], [46, 53, 57, 60, 64], [43, 50, 55, 58, 62], [45, 52, 55, 59, 61]], True, 8.0, 1400),
    "bright":  ([[41, 48, 52, 57, 59], [43, 50, 55, 59, 62], [40, 47, 50, 55, 59], [45, 52, 55, 59, 60]], True, 6.0, 2200),
    "focus":   ([[45, 52, 57, 59], [41, 48, 53, 57], [43, 50, 55, 57], [40, 47, 52, 55]], False, 10.0, 1100),
}


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def write_wav(path: Path, x: np.ndarray) -> None:
    x = np.clip(x, -1, 1)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def reverb(x: np.ndarray, seconds: float = 3.2, wet: float = 0.35, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = []
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-t * 6.9 / seconds)
        ir = sosfilt(butter(2, 5000, "low", fs=SR, output="sos"), ir)
        ir /= np.sqrt(np.sum(ir ** 2))
        out.append(fftconvolve(x[:, ch], ir)[: len(x)])
    y = np.stack(out, axis=1)
    return (1 - wet) * x + wet * y


def pad_note(freq: float, n: int, rng, harmonics: int = 6) -> np.ndarray:
    t = np.arange(n) / SR
    sig = np.zeros((n, 2))
    for side, cents in ((0, -4), (1, 4)):
        f = freq * 2 ** (cents / 1200)
        ph = rng.uniform(0, 2 * np.pi, harmonics)
        vib = 1 + 0.0015 * np.sin(2 * np.pi * rng.uniform(0.1, 0.25) * t)
        for k in range(1, harmonics + 1):
            sig[:, side] += np.sin(2 * np.pi * f * k * t * vib + ph[k - 1]) / k ** 1.7
    return sig


def bed(mood: str = "calm", seconds: float = 120.0, seed: int = 7) -> np.ndarray:
    chords, pluck, span, bright = MOODS[mood]
    rng = np.random.default_rng(seed)
    total = int(seconds * SR)
    xf = int(2.5 * SR)                     # chord crossfade
    seg = int(span * SR)
    out = np.zeros((total + seg + xf, 2))
    i, pos = 0, 0
    while pos < total:
        chord = chords[i % len(chords)]
        n = seg + xf
        env = np.ones(n)
        env[:xf] = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2
        env[-xf:] = np.cos(np.linspace(0, np.pi / 2, xf)) ** 2
        layer = np.zeros((n, 2))
        for j, m in enumerate(chord):
            amp = 0.5 if j == 0 else 0.22
            note = pad_note(hz(m - (12 if j == 0 else 0)), n, rng, harmonics=3 if j == 0 else 6)
            pan = 0.5 + 0.35 * (j / max(1, len(chord) - 1) - 0.5)
            layer[:, 0] += note[:, 0] * amp * (1 - pan) * 2
            layer[:, 1] += note[:, 1] * amp * pan * 2
        out[pos:pos + n] += layer * env[:, None]
        if pluck:
            step = span / 8
            for k in range(8):
                if rng.random() < 0.7:
                    m = chord[1 + rng.integers(0, len(chord) - 1)] + 12
                    start = pos + int(k * step * SR)
                    ln = int(1.6 * SR)
                    tt = np.arange(ln) / SR
                    tone = (np.sin(2 * np.pi * hz(m) * tt) + 0.3 * np.sin(4 * np.pi * hz(m) * tt)) * np.exp(-tt * 3.2)
                    tone *= np.minimum(1, tt / 0.004)
                    p = rng.uniform(0.3, 0.7)
                    end = min(start + ln, len(out))
                    out[start:end, 0] += 0.09 * tone[: end - start] * (1 - p)
                    out[start:end, 1] += 0.09 * tone[: end - start] * p
        pos += seg
        i += 1
    out = out[:total]
    # slow filter sweep for movement
    sos = butter(2, bright, "low", fs=SR, output="sos")
    out = np.stack([sosfilt(sos, out[:, c]) for c in range(2)], axis=1)
    sos_hp = butter(2, 45, "high", fs=SR, output="sos")
    out = np.stack([sosfilt(sos_hp, out[:, c]) for c in range(2)], axis=1)
    out = reverb(out, wet=0.4, seed=seed)
    # fades
    fi, fo = int(2.0 * SR), int(3.0 * SR)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    peak = np.max(np.abs(out)) + 1e-9
    return out / peak * 0.7


def sfx() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(3)
    res = {}
    # whoosh: band-passed noise sweeping up then down, panned left → right
    n = int(0.75 * SR)
    t = np.linspace(0, 1, n)
    noise = rng.standard_normal(n)
    bands = [(250, 600), (600, 1400), (1400, 3200)]
    sig = np.zeros(n)
    for k, (lo, hi) in enumerate(bands):
        b = sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), noise)
        center = 0.35 + 0.15 * k
        sig += b * np.exp(-((t - center) / 0.18) ** 2)
    sig *= np.sin(np.pi * t) ** 1.5
    pan = t
    res["whoosh"] = np.stack([sig * (1 - pan), sig * pan], axis=1)
    # scribble: high-passed grain with a quick stroke rhythm (pencil on paper)
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    g = sosfilt(butter(2, [1800, 7000], "band", fs=SR, output="sos"), rng.standard_normal(n))
    strokes = 0.5 + 0.5 * np.sin(2 * np.pi * 11 * t + 2 * np.sin(2 * np.pi * 3 * t)) ** 2
    env = np.minimum(1, t / 0.03) * np.minimum(1, (0.5 - t) / 0.12)
    sc = g * strokes * env
    res["scribble"] = np.stack([sc, sc * 0.85], axis=1)
    # pop: tiny soft blip for reveals
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    f = 900 - 300 * t / t[-1]
    p = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 35) * np.minimum(1, t / 0.002)
    res["pop"] = np.stack([p, p], axis=1)
    for k in res:
        res[k] = res[k] / (np.max(np.abs(res[k])) + 1e-9) * 0.8
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bed"); b.add_argument("--mood", choices=list(MOODS), default="calm")
    b.add_argument("--seconds", type=float, default=120); b.add_argument("--seed", type=int, default=7)
    b.add_argument("-o", "--out", required=True)
    s = sub.add_parser("sfx"); s.add_argument("-o", "--out", required=True)
    lp = sub.add_parser("loops"); lp.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    if a.cmd == "bed":
        write_wav(Path(a.out), bed(a.mood, a.seconds, a.seed))
    elif a.cmd == "sfx":
        for name, x in sfx().items():
            write_wav(Path(a.out) / f"{name}.wav", x)
    else:
        for mood in MOODS:
            write_wav(Path(a.out) / f"{mood}.wav", bed(mood, 60, 7))
    print(a.out)


if __name__ == "__main__":
    main()
