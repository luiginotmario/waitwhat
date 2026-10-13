"""Visual worlds for waitwhat videos: a palette plus a procedural background per theme.

Imported by waitwhat_style (scene files never import this directly). A theme is chosen per video
in plan.json (`"theme": "chalkboard"`), optionally per scene (`scenes[].theme`), and can be forced
for a quick look with the env var WAITWHAT_THEME. The background is painted with numpy straight
into the camera's background (never a mobject), so fades, `self.clear()`, the layout lint and
refine probes never see it. A few themes add slow ambient motion (twinkling stars, drifting
particles, passing clouds) so a held frame is never frozen.

Every palette is checked for contrast against its own background (`python waitwhat_themes.py`):
ink and secondary ink >= 4.5:1, concept and attention colours >= 3:1 (WCAG AA for large text and
graphics). All code here is original to waitwhat (MIT).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------- palettes

# Keys every theme defines. Concept colour names match the style lib's constants so scene code
# that says BLUE / color_of("a") adapts automatically.
COLOR_KEYS = ("BLUE", "TEAL", "PINK", "GOLD", "GREEN", "RED", "PURPLE", "ORANGE", "MAROON",
              "YELLOW", "YELLOW_SOFT")

_CLASSIC_COLORS = {
    "BLUE": "#58C4DD", "TEAL": "#5CD0B3", "PINK": "#D147BD", "GOLD": "#F0AC5F", "GREEN": "#83C167",
    "RED": "#FC6255", "PURPLE": "#9A72AC", "ORANGE": "#FF862F", "MAROON": "#C55F73",
    "YELLOW": "#FFFF00", "YELLOW_SOFT": "#F7D96F",
}
# Brighter cousins for dark themes whose background is not pure black (purple and pink need lift).
_DARK_LIFT = {**_CLASSIC_COLORS, "PINK": "#E06CCF", "PURPLE": "#B596C9", "MAROON": "#DA8496"}
_PASTEL = {
    "BLUE": "#8CCBF2", "TEAL": "#8FDCC4", "PINK": "#F4A3C8", "GOLD": "#F5C978", "GREEN": "#B5E08A",
    "RED": "#FF8A80", "PURPLE": "#C9AEEB", "ORANGE": "#FFB074", "MAROON": "#E8A2B0",
    "YELLOW": "#FFF27A", "YELLOW_SOFT": "#F7E3A1",
}
# Marker / ink colours for light backgrounds. "YELLOW" (attention) becomes a deep amber that
# still reads as the highlighter colour but passes contrast on white.
_INK_ON_LIGHT = {
    "BLUE": "#1C5DB8", "TEAL": "#0B7366", "PINK": "#B0287F", "GOLD": "#8F5B00", "GREEN": "#2C7A30",
    "RED": "#C62828", "PURPLE": "#6A3FA0", "ORANGE": "#B8460B", "MAROON": "#8E2440",
    "YELLOW": "#B36B00", "YELLOW_SOFT": "#8A6A00",
}

THEMES: dict[str, dict] = {
    # The 3Blue1Brown house look. Default; best for math.
    "classic": {
        "about": "pure black, the 3b1b look; default, best for math and abstract ideas",
        "dark": True, "bg": "#000000", "ink": "#FFFFFF", "ink_2": "#BBBBBB", "ink_3": "#777777",
        "ink_4": "#333333", "colors": _CLASSIC_COLORS, "write": "pencil", "code_bg": "#111317",
    },
    "studio": {
        "about": "warm charcoal with a soft spotlight; products, companies, modern tech",
        "dark": True, "bg": "#141519", "ink": "#FFFFFF", "ink_2": "#C4C6CC", "ink_3": "#8B8E96",
        "ink_4": "#34363D", "colors": _DARK_LIFT, "write": "pencil", "code_bg": "#0C0D10",
    },
    "chalkboard": {
        "about": "green-slate chalkboard with chalk dust; school-style derivations, history lessons, cosy teaching",
        "dark": True, "bg": "#1F2E28", "ink": "#F2F0E6", "ink_2": "#CDD0C6", "ink_3": "#9AA59D",
        "ink_4": "#3F5048", "colors": _PASTEL, "write": "chalk", "code_bg": "#16221D",
    },
    "blueprint": {
        "about": "engineering blueprint with a fine grid; machines, architecture, systems, how things are built",
        "dark": True, "bg": "#103C69", "ink": "#F2F7FF", "ink_2": "#CBDCF0", "ink_3": "#9DB6D4",
        "ink_4": "#2F5D8C",
        "colors": {**_PASTEL, "BLUE": "#9FDAFF", "TEAL": "#86F0D9", "YELLOW": "#FFF27A"},
        "write": "pencil", "code_bg": "#0B2D50",
    },
    "space": {
        "about": "night sky with stars and a faint nebula (stars twinkle); astronomy, physics, scale, big ideas",
        "dark": True, "bg": "#070A18", "ink": "#FFFFFF", "ink_2": "#C7CDE2", "ink_3": "#8F98B6",
        "ink_4": "#2B3252", "colors": _DARK_LIFT, "write": "pencil", "code_bg": "#0B0F22",
        "ambient": "twinkle",
    },
    "ocean": {
        "about": "deep ocean gradient with light rays and drifting particles; biology, oceans, flows, calm deep dives",
        "dark": True, "bg": "#08304A", "ink": "#EEF9FC", "ink_2": "#C2E0E9", "ink_3": "#93BCCA",
        "ink_4": "#1E4D63",
        "colors": {**_DARK_LIFT, "BLUE": "#7FD6F7", "TEAL": "#7FE7CF", "PURPLE": "#C6A8E0",
                   "PINK": "#EE86DA", "MAROON": "#EE9AAC", "RED": "#FF7A6E", "GREEN": "#9ED88A"},
        "write": "pencil", "code_bg": "#062538", "ambient": "drift",
    },
    "city": {
        "about": "city at night, a low skyline along the bottom edge; startups, economics, people and places (keep content above y = -2.6)",
        "dark": True, "bg": "#0C1430", "ink": "#FFFFFF", "ink_2": "#C9CFE4", "ink_3": "#939BBA",
        "ink_4": "#2B3456", "colors": _DARK_LIFT, "write": "pencil", "code_bg": "#090F25",
        "ambient": "windows", "floor": -2.6,
    },
    "whiteboard": {
        "about": "clean whiteboard with marker colours; product walkthroughs, business, office-style explanations",
        "dark": False, "bg": "#F7F7F4", "ink": "#1E2329", "ink_2": "#46505B", "ink_3": "#66707B",
        "ink_4": "#C9CDD2", "colors": _INK_ON_LIGHT, "write": "marker", "code_bg": "#ECEDEA",
    },
    "graph_paper": {
        "about": "light graph paper (grid on whole/half units); data, measurement, geometry, engineering maths",
        "dark": False, "bg": "#FAFAF6", "ink": "#1D2731", "ink_2": "#45515D", "ink_3": "#65717C",
        "ink_4": "#C7D6E6", "colors": _INK_ON_LIGHT, "write": "pencil", "code_bg": "#EEF0EC",
    },
    "paper": {
        "about": "warm notebook paper with faint ruled lines; stories, history, biographies, gentle intros",
        "dark": False, "bg": "#F3EAD7", "ink": "#2A251F", "ink_2": "#51473D", "ink_3": "#6C6153",
        "ink_4": "#CDBFA3",
        "colors": {**_INK_ON_LIGHT, "BLUE": "#22549E", "GOLD": "#865600", "YELLOW": "#A65F00",
                   "YELLOW_SOFT": "#7F6000", "TEAL": "#0A6B5F", "GREEN": "#2A7030", "ORANGE": "#A8420A"},
        "write": "pencil", "code_bg": "#EADFC7",
    },
    "hills": {
        "about": "illustrated daytime world, soft sky, drifting clouds, rolling hills along the bottom; nature, everyday life, stories for everyone (keep content above y = -2.6)",
        "dark": False, "bg": "#E6F0F4", "ink": "#16293A", "ink_2": "#3B4F61", "ink_3": "#56697A",
        "ink_4": "#B9CAD4",
        "colors": {**_INK_ON_LIGHT, "BLUE": "#1A58A8", "GOLD": "#7F5100", "YELLOW": "#A15C00",
                   "YELLOW_SOFT": "#7A5C00", "TEAL": "#09695D", "GREEN": "#2A6E2E", "ORANGE": "#A6420A"},
        "write": "pencil", "code_bg": "#DCE7EC", "ambient": "clouds", "floor": -2.6,
    },
}
DEFAULT_THEME = "classic"
ALIASES = {"default": "classic", "dark": "classic", "3b1b": "classic", "black": "classic",
           "chalk": "chalkboard", "blackboard": "chalkboard", "graph": "graph_paper", "grid": "graph_paper",
           "notebook": "paper", "warm_paper": "paper", "night_sky": "space", "stars": "space",
           "deep_ocean": "ocean", "sea": "ocean", "underwater": "ocean", "drafting": "blueprint",
           "skyline": "city", "night_city": "city", "meadow": "hills", "countryside": "hills",
           "dark_studio": "studio"}


def canonical(name: str | None) -> str:
    n = (name or DEFAULT_THEME).strip().lower().replace("-", "_").replace(" ", "_")
    n = ALIASES.get(n, n)
    return n if n in THEMES else DEFAULT_THEME


# --------------------------------------------------------------------------- choosing the theme

def resolve(plan: dict, scene_id: str | None) -> tuple[str, dict]:
    """→ (theme name, options) for a scene. Precedence: WAITWHAT_THEME env, scenes[].theme,
    plan.theme. plan.theme may be a name or {"name", "ambient", "backdrop", "backdrop_dim"}."""
    opts: dict = {}
    spec = plan.get("theme")
    if isinstance(spec, dict):
        opts.update({k: v for k, v in spec.items() if k != "name"})
        spec = spec.get("name")
    sc = next((s for s in plan.get("scenes") or [] if s.get("id") == scene_id), None) if scene_id else None
    if sc and sc.get("theme"):
        st = sc["theme"]
        if isinstance(st, dict):
            opts.update({k: v for k, v in st.items() if k != "name"})
            st = st.get("name")
        spec = st or spec
    env = os.environ.get("WAITWHAT_THEME")
    if env:
        spec = env
    return canonical(spec if isinstance(spec, str) else None), opts


# --------------------------------------------------------------------------- colour maths

def rgb(hex_: str) -> np.ndarray:
    h = hex_.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def _lum(hex_: str) -> float:
    c = rgb(hex_) / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def check_contrast(name: str) -> list[str]:
    """Problems with a theme's palette against its own background (empty list = passes)."""
    t = THEMES[name]
    bgs = [t["bg"], *t.get("check_bg", [])]
    bad = []
    for bg in bgs:
        for key, need in (("ink", 4.5), ("ink_2", 4.5), ("ink_3", 3.0)):
            r = contrast(t[key], bg)
            if r < need:
                bad.append(f"{name}: {key} {t[key]} on {bg} = {r:.2f} < {need}")
        for key in COLOR_KEYS:
            r = contrast(t["colors"][key], bg)
            if r < 3.0:
                bad.append(f"{name}: {key} {t['colors'][key]} on {bg} = {r:.2f} < 3.0")
    return bad


# --------------------------------------------------------------------------- painting helpers
# All painting works on float32 RGB arrays in 0..255, shape (h, w, 3). `u` = pixels per unit.

_VERSION = "1"  # bump to invalidate cached backgrounds


def _grid(h: int, w: int):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return xs, ys


def _noise(h: int, w: int, cell: float, rng, octaves: int = 3) -> np.ndarray:
    """Smooth value noise in [0, 1] (bicubic-upsampled random grids, summed over octaves)."""
    from PIL import Image
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = max(2.0, cell / (2 ** o))
        gh, gw = int(h / c) + 3, int(w / c) + 3
        g = rng.random((gh, gw)).astype(np.float32)
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((int(gw * c), int(gh * c)), Image.BICUBIC)
        a = np.asarray(img, np.float32)[:h, :w] / 255.0
        if a.shape != (h, w):
            a = np.pad(a, ((0, h - a.shape[0]), (0, w - a.shape[1])), mode="edge")
        out += amp * a
        tot += amp
        amp *= 0.5
    return out / tot


def _blend(img: np.ndarray, color, alpha) -> None:
    """In place: img = img*(1-a) + color*a; alpha is a scalar or an (h, w) map."""
    c = np.asarray(color, np.float32).reshape(1, 1, 3)
    a = alpha[..., None] if np.ndim(alpha) == 2 else alpha
    img *= (1 - a)
    img += c * a


def _vertical(h: int, w: int, top: str, bottom: str, curve: float = 1.0) -> np.ndarray:
    t = (np.linspace(0, 1, h, dtype=np.float32) ** curve)[:, None, None]
    return (rgb(top) * (1 - t) + rgb(bottom) * t) * np.ones((1, w, 1), np.float32)


def _radial(h: int, w: int, center: str, edge: str, cx: float = 0.5, cy: float = 0.5,
            spread: float = 1.0) -> np.ndarray:
    xs, ys = _grid(h, w)
    d = np.sqrt(((xs / w - cx) * (w / h)) ** 2 + (ys / h - cy) ** 2) / (0.9 * spread)
    t = np.clip(d, 0, 1)[..., None] ** 1.5
    return rgb(center) * (1 - t) + rgb(edge) * t


def _vignette(img: np.ndarray, strength: float = 0.25, color: str = "#000000") -> None:
    h, w = img.shape[:2]
    xs, ys = _grid(h, w)
    d = np.sqrt(((xs / w - 0.5) * 1.6) ** 2 + ((ys / h - 0.5) * 1.6) ** 2)
    a = np.clip((d - 0.45) / 0.75, 0, 1) ** 2 * strength
    _blend(img, rgb(color), a)


def _hlines(img, ys_px, color, alpha, width=1):
    c = rgb(color)
    h = img.shape[0]
    for y in ys_px:
        y0 = int(round(y))
        if 0 <= y0 < h:
            img[y0:y0 + width] = img[y0:y0 + width] * (1 - alpha) + c * alpha


def _vlines(img, xs_px, color, alpha, width=1):
    c = rgb(color)
    w = img.shape[1]
    for x in xs_px:
        x0 = int(round(x))
        if 0 <= x0 < w:
            img[:, x0:x0 + width] = img[:, x0:x0 + width] * (1 - alpha) + c * alpha


def _unit_lines(n_px: int, u: float, step: float, center_px: float):
    """Pixel positions of lines every `step` units, aligned so 0 units falls on a line."""
    k0 = math.floor(-center_px / (u * step)) - 1
    k1 = math.ceil((n_px - center_px) / (u * step)) + 1
    return [(k, center_px + k * step * u) for k in range(k0, k1 + 1)]


def _sprite(r: float) -> np.ndarray:
    """A soft round dot (gaussian core + glow), values 0..1, odd size."""
    s = int(max(3, math.ceil(r * 4))) | 1
    c = s // 2
    ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
    d2 = (xs - c) ** 2 + (ys - c) ** 2
    return np.exp(-d2 / (2 * max(0.35, r * 0.6) ** 2)) + 0.25 * np.exp(-d2 / (2 * (r * 1.6) ** 2))


def _stamp(img: np.ndarray, x: float, y: float, spr: np.ndarray, color, strength: float) -> None:
    """Additive-ish blend of a sprite centred at (x, y) px."""
    h, w = img.shape[:2]
    s = spr.shape[0]
    x0, y0 = int(round(x)) - s // 2, int(round(y)) - s // 2
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(w, x0 + s), min(h, y0 + s)
    if xa >= xb or ya >= yb:
        return
    a = np.clip(spr[ya - y0:yb - y0, xa - x0:xb - x0] * strength, 0, 1)[..., None]
    region = img[ya:yb, xa:xb]
    region[:] = region * (1 - a) + np.asarray(color, np.float32) * a


def content_floor(name: str, frame_h: float = 8.0) -> float:
    """Lowest y content may use on this theme, in frame units (scenery such as a skyline or hills
    sits below it). Themes declare it for the 8-unit-tall 16:9 frame; a taller frame (9:16, 14.22
    units) keeps the scenery band in proportion to the frame's height."""
    f = THEMES[canonical(name)].get("floor")
    if f is None:
        return -frame_h / 2 + 0.5
    if abs(frame_h - 8.0) < 1e-6:
        return float(f)
    return -frame_h / 2 + (4.0 + float(f)) * (frame_h / 8.0) * 0.79


# --------------------------------------------------------------------------- per-theme painters

def _paint(name: str, h: int, w: int, u: float, rng) -> tuple[np.ndarray, dict]:
    """→ (RGB float image, ambient state)."""
    t = THEMES[name]
    cx, cy = w / 2, h / 2
    px = min(w, h) / 1080          # sprite scale: the short side, so 9:16 stars are not bigger
    amb: dict = {}
    if name == "classic":
        img = np.zeros((h, w, 3), np.float32) + rgb(t["bg"])
    elif name == "studio":
        img = _radial(h, w, "#202228", "#0B0B0D", cy=0.42, spread=1.1)
        img += (_noise(h, w, 3, rng, 1)[..., None] - 0.5) * 3
    elif name == "chalkboard":
        img = _radial(h, w, "#24362F", "#16211C", spread=1.2)
        smudge = _noise(h, w, 160 * u / 100, rng, 4)
        _blend(img, rgb("#D9DDD2"), np.clip(smudge - 0.45, 0, 1) * 0.10)          # old erased chalk
        streak = _noise(h, w, 30 * u / 100, rng, 2)
        _blend(img, rgb("#D9DDD2"), np.clip(streak - 0.62, 0, 1) * 0.08)
        dust = rng.random((h, w)).astype(np.float32)
        _blend(img, rgb("#E8EBE2"), (dust > 0.9975) * 0.18)                        # chalk specks
        img += (_noise(h, w, 2, rng, 1)[..., None] - 0.5) * 6                       # slate grain
        _vignette(img, 0.35, "#0A100D")
    elif name == "blueprint":
        img = _radial(h, w, "#13457A", "#0B2D52", spread=1.25)
        img += (_noise(h, w, 2.5, rng, 1)[..., None] - 0.5) * 5
        for k, x in _unit_lines(w, u, 0.25, cx):
            _vlines(img, [x], "#CFE3FF", 0.16 if k % 4 == 0 else 0.06)
        for k, y in _unit_lines(h, u, 0.25, cy):
            _hlines(img, [y], "#CFE3FF", 0.16 if k % 4 == 0 else 0.06)
        _vignette(img, 0.3, "#061A30")
    elif name == "space":
        img = _radial(h, w, "#0E1430", "#03040A", cx=0.55, cy=0.45, spread=1.3)
        neb = _noise(h, w, 260 * u / 100, rng, 4)
        _blend(img, rgb("#5B3C8C"), np.clip(neb - 0.55, 0, 1) ** 1.3 * 0.55)
        neb2 = _noise(h, w, 200 * u / 100, rng, 4)
        _blend(img, rgb("#1E6A86"), np.clip(neb2 - 0.58, 0, 1) ** 1.3 * 0.45)
        n = int(w * h / 2600)
        for _ in range(n):                                                          # static stars
            r = float(rng.choice([0.7, 0.9, 1.2, 1.7], p=[0.5, 0.3, 0.15, 0.05])) * px
            _stamp(img, rng.random() * w, rng.random() * h, _sprite(r), rgb("#F4F6FF"),
                   float(rng.uniform(0.3, 0.9)))
        stars = []
        for _ in range(int(70 * w / 1920) + 10):                                    # twinkling ones
            r = float(rng.uniform(1.3, 2.2)) * px
            stars.append((rng.random() * w, rng.random() * h, _sprite(r), float(rng.uniform(0.3, 1.2)),
                          float(rng.uniform(0, 6.28)), float(rng.uniform(0.35, 0.9))))
        amb = {"stars": stars}
    elif name == "ocean":
        img = _vertical(h, w, "#0E5578", "#03121F", curve=0.9)
        xs, ys = _grid(h, w)
        ang = math.radians(-18)
        along = (xs - w * 0.35) * math.cos(ang) + ys * math.sin(ang)
        rays = (np.sin(along / (w * 0.035)) * 0.5 + 0.5) * (np.sin(along / (w * 0.011) + 1.3) * 0.5 + 0.5)
        fall = np.clip(1 - ys / (h * 0.85), 0, 1) ** 1.8
        _blend(img, rgb("#9FE3F5"), rays * fall * 0.10)
        img += (_noise(h, w, 120 * u / 100, rng, 3)[..., None] - 0.5) * 10
        parts = []
        for _ in range(int(60 * w / 1920) + 8):
            r = float(rng.uniform(0.6, 1.5)) * px
            parts.append([rng.random() * w, rng.random() * h, _sprite(r), float(rng.uniform(4, 14)) * px,
                          float(rng.uniform(0, 6.28)), float(rng.uniform(0.15, 0.45))])
        amb = {"particles": parts}
        _vignette(img, 0.25, "#020A12")
    elif name == "city":
        img = _vertical(h, w, "#0A1029", "#1F2747", curve=1.2)
        for _ in range(int(w * h / 14000)):
            _stamp(img, rng.random() * w, rng.random() * h * 0.6, _sprite(0.6 * px), rgb("#E8ECFF"),
                   float(rng.uniform(0.15, 0.55)))
        floor_y = cy - content_floor(name, h / u) * u                      # px of the content floor
        base = h
        windows = []
        x = -rng.random() * 40
        layers = [("#141A33", 0.55, 0.9), ("#0B0F22", 1.0, 1.0)]
        for col, hmul, wmul in layers:
            x = -rng.random() * 60
            while x < w:
                bw = float(rng.uniform(0.35, 0.9)) * u * wmul
                top = floor_y + (base - floor_y) * float(rng.uniform(0.15, 0.75)) * (1.15 - hmul * 0.3)
                x0, x1 = int(x), int(min(w, x + bw))
                img[int(top):base, max(0, x0):x1] = rgb(col)
                if col == "#0B0F22":
                    gx, gy = 0.11 * u, 0.13 * u
                    yy = top + gy * 0.6
                    while yy < base - gy:
                        xx = x0 + gx * 0.6
                        while xx < x1 - gx * 0.8:
                            if rng.random() < 0.28:
                                windows.append((int(xx), int(yy), max(2, int(gx * 0.45)), max(2, int(gy * 0.45)),
                                                float(rng.random())))
                            xx += gx
                        yy += gy
                x += bw + float(rng.uniform(0.0, 0.18)) * u
        lit = np.zeros(len(windows), bool)
        for i, (wx, wy, ww, wh, p) in enumerate(windows):
            if p < 0.8:
                img[wy:wy + wh, wx:wx + ww] = rgb("#F2C66D") * 0.75 + img[wy:wy + wh, wx:wx + ww] * 0.25
                lit[i] = True
        amb = {"windows": windows, "lit": lit}
    elif name == "whiteboard":
        img = _radial(h, w, "#FBFBF9", "#ECEDEA", cx=0.4, cy=0.35, spread=1.4)
        ghost = _noise(h, w, 140 * u / 100, rng, 4)
        _blend(img, rgb("#B8C0C8"), np.clip(ghost - 0.6, 0, 1) * 0.10)            # faint old marker
        img += (_noise(h, w, 2, rng, 1)[..., None] - 0.5) * 2
    elif name == "graph_paper":
        img = np.zeros((h, w, 3), np.float32) + rgb(t["bg"])
        img += (_noise(h, w, 2, rng, 1)[..., None] - 0.5) * 3
        for k, x in _unit_lines(w, u, 0.25, cx):
            _vlines(img, [x], "#7FB0DA", 0.42 if k % 4 == 0 else (0.22 if k % 2 == 0 else 0.12))
        for k, y in _unit_lines(h, u, 0.25, cy):
            _hlines(img, [y], "#7FB0DA", 0.42 if k % 4 == 0 else (0.22 if k % 2 == 0 else 0.12))
        _vignette(img, 0.08, "#8A8F8A")
    elif name == "paper":
        img = np.zeros((h, w, 3), np.float32) + rgb(t["bg"])
        fib = _noise(h, w, 40 * u / 100, rng, 4)
        _blend(img, rgb("#D9C9A6"), np.clip(fib - 0.5, 0, 1) * 0.35)
        img += (_noise(h, w, 1.6, rng, 1)[..., None] - 0.5) * 7
        for k, y in _unit_lines(h, u, 0.5, cy):
            _hlines(img, [y], "#7FA3C9", 0.22, width=max(1, int(px)))
        _vlines(img, [cx - (w / (2 * u) - 0.36) * u], "#D9534F", 0.45, width=max(1, int(2 * px)))  # margin line, 0.36 in from the left edge
        _vignette(img, 0.18, "#7A5E35")
    elif name == "hills":
        img = _vertical(h, w, "#BFDDF0", "#F3EFDF", curve=1.1)
        xs = np.arange(w, dtype=np.float32)
        ys = np.arange(h, dtype=np.float32)[:, None]
        floor_y = cy - content_floor(name, h / u) * u
        for col, lvl, amp, f, ph in (("#B9D7A8", 0.15, 0.35, 1.3, rng.random() * 6),
                                     ("#93C285", 0.45, 0.30, 2.1, rng.random() * 6),
                                     ("#6FA76A", 0.75, 0.22, 3.0, rng.random() * 6)):
            top = floor_y + (h - floor_y) * lvl - amp * u * (0.6 * np.sin(xs / w * f * 3.1 + ph) +
                                                              0.4 * np.sin(xs / w * f * 7.3 + ph * 2))
            a = np.clip(ys - top[None, :] + 0.5, 0, 1)
            _blend(img, rgb(col), a)
        # clouds: a wide soft strip that drifts sideways
        sh = int((h / 2 - 1.2 * u))
        strip_w = int(w * 1.6)
        cl = _noise(sh, strip_w, 420 * u / 100, rng, 5)
        mask = np.clip((cl - 0.46) * 3.2, 0, 1) ** 1.4 * np.clip(1 - np.arange(sh)[:, None] / sh, 0, 1) ** 0.8
        amb = {"clouds": (mask * 0.75).astype(np.float32), "cloud_color": rgb("#FFFFFF")}
    else:  # pragma: no cover
        img = np.zeros((h, w, 3), np.float32) + rgb(t["bg"])
    return np.clip(img, 0, 255), amb


def _apply_backdrop(img: np.ndarray, path: Path, dark: bool, dim: float) -> np.ndarray:
    """Blend an (AI-made or supplied) image behind everything: cover-fit, blurred, pushed toward
    the theme background so text stays legible. dim = how much of the theme background wins."""
    from PIL import Image, ImageFilter
    h, w = img.shape[:2]
    im = Image.open(path).convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(im.width * s + 0.5)), max(h, int(im.height * s + 0.5))), Image.LANCZOS)
    l, tp = (im.width - w) // 2, (im.height - h) // 2
    im = im.crop((l, tp, l + w, tp + h)).filter(ImageFilter.GaussianBlur(radius=max(2, h / 180)))
    a = np.asarray(im, np.float32)
    # compress the backdrop's own contrast, then lay the theme over it
    lum = a.mean(axis=2, keepdims=True)
    a = lum + (a - lum) * 0.75
    return img * dim + a * (1 - dim)


def background(name: str, w: int, h: int, frame_w: float, opts: dict | None = None,
               seed: int = 7) -> tuple[np.ndarray, dict]:
    """RGBA uint8 background (h, w, 4) for a theme at a pixel size, plus its ambient state.
    Cached in <plugin>/.cache/themes when possible (cheap to rebuild anyway)."""
    opts = opts or {}
    u = w / frame_w
    backdrop = opts.get("backdrop")
    bpath = None
    if backdrop:
        bp = Path(backdrop)
        if not bp.is_absolute():
            bp = Path(os.environ.get("WAITWHAT_WORKSPACE", ".")) / bp
        bpath = bp if bp.exists() else None
    key = hashlib.sha256(json.dumps([_VERSION, name, w, h, round(frame_w, 4), seed, THEMES[name],
                                     str(bpath), bpath.stat().st_mtime if bpath else 0,
                                     opts.get("backdrop_dim")], sort_keys=True, default=str).encode()
                         ).hexdigest()[:16]
    rng = np.random.default_rng(seed)
    amb_needed = bool(THEMES[name].get("ambient"))
    cache = None
    root = os.environ.get("WAITWHAT_ROOT")
    if root and not amb_needed:
        cache = Path(root) / ".cache" / "themes" / f"{name}-{w}x{h}-{key}.npy"
        if cache.exists():
            try:
                return np.load(cache), {}
            except Exception:
                pass
    img, amb = _paint(name, h, w, u, rng)
    if bpath:
        try:
            dim = float(opts.get("backdrop_dim", 0.72))
            img = _apply_backdrop(img, bpath, THEMES[name]["dark"], dim)
        except Exception:
            pass
    out = np.empty((h, w, 4), np.uint8)
    out[..., :3] = np.clip(img + 0.5, 0, 255).astype(np.uint8)
    out[..., 3] = 255
    if cache is not None:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.save(cache, out)
        except Exception:
            pass
    return out, amb


class Ambient:
    """Per-frame slow motion painted over the background (stars, particles, windows, clouds)."""

    def __init__(self, name: str, base: np.ndarray, state: dict, fps: float):
        self.name, self.base, self.state, self.fps = name, base, state, fps
        self.kind = THEMES[name].get("ambient")

    def paint(self, out: np.ndarray, t: float) -> None:
        """Write the background for time t (seconds) into `out` (h, w, 4 uint8), in place."""
        np.copyto(out, self.base)
        if not self.kind or not self.state:
            return
        h, w = out.shape[:2]
        rgbv = out[..., :3]
        if self.kind == "twinkle":
            for x, y, spr, f, ph, amp in self.state["stars"]:
                b = amp * (0.55 + 0.45 * math.sin(t * f * 2.2 + ph))
                self._stamp(rgbv, x, y, spr, (244, 246, 255), b)
        elif self.kind == "drift":
            for p in self.state["particles"]:
                x0, y0, spr, speed, ph, amp = p
                y = (y0 - t * speed) % (h + 20) - 10
                x = x0 + math.sin(t * 0.35 + ph) * 6 * min(w, h) / 1080
                self._stamp(rgbv, x, y, spr, (200, 236, 245), amp)
        elif self.kind == "windows":
            wins, lit = self.state["windows"], self.state["lit"]
            if len(wins):
                k = int(t / 1.7)
                rng = np.random.default_rng(k)
                for i in rng.choice(len(wins), size=min(3, len(wins)), replace=False):
                    wx, wy, ww, wh, p = wins[i]
                    if lit[i]:
                        rgbv[wy:wy + wh, wx:wx + ww] = (14, 18, 38)
                    else:
                        rgbv[wy:wy + wh, wx:wx + ww] = (190, 155, 90)
        elif self.kind == "clouds":
            m = self.state["clouds"]
            sh, sw = m.shape
            off = int(t * 9 * min(w, h) / 1080) % (sw - w) if sw > w else 0
            a = m[:, off:off + w][..., None]
            region = rgbv[:sh].astype(np.float32)
            region = region * (1 - a) + self.state["cloud_color"] * a
            rgbv[:sh] = np.clip(region, 0, 255).astype(np.uint8)

    @staticmethod
    def _stamp(img: np.ndarray, x: float, y: float, spr: np.ndarray, color, strength: float) -> None:
        h, w = img.shape[:2]
        s = spr.shape[0]
        x0, y0 = int(round(x)) - s // 2, int(round(y)) - s // 2
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(w, x0 + s), min(h, y0 + s)
        if xa >= xb or ya >= yb:
            return
        a = np.clip(spr[ya - y0:yb - y0, xa - x0:xb - x0] * strength, 0, 1)[..., None]
        region = img[ya:yb, xa:xb].astype(np.float32)
        img[ya:yb, xa:xb] = np.clip(region * (1 - a) + np.asarray(color, np.float32) * a, 0, 255).astype(np.uint8)


if __name__ == "__main__":  # contrast report + preview PNGs (16:9 and 9:16):  python waitwhat_themes.py [outdir]
    import sys
    problems = [p for n in THEMES for p in check_contrast(n)]
    print("\n".join(problems) if problems else f"contrast ok for {len(THEMES)} themes")
    if len(sys.argv) > 1:
        from PIL import Image
        d = Path(sys.argv[1])
        d.mkdir(parents=True, exist_ok=True)
        for n in THEMES:
            for suffix, (pw, ph, fw) in (("", (960, 540, 14.222)), ("_9x16", (540, 960, 8.0))):
                img, amb = background(n, pw, ph, fw)
                if amb:
                    buf = img.copy()
                    Ambient(n, img, amb, 15).paint(buf, 3.0)
                    img = buf
                Image.fromarray(img[..., :3]).save(d / f"{n}{suffix}.png")
        print(d)
    sys.exit(1 if problems else 0)
