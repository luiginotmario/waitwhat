"""waitwhat house style for Manim Community Edition.

Every scene file does:

    from waitwhat_style import *

    class Hook(WaitwhatScene):
        def construct(self):
            tri = ...
            self.play(Create(tri), run_time=self.until("squares"))
            ...
            self.finish()

What you get:
  * the 3b1b look: black background, CMU Serif text, the classic accent palette
  * concept colours that stay consistent across scenes (`color_of("hypotenuse")`, read from plan.json)
  * narration-driven timing (`until`, `play_until`, `wait_until`, `finish`) using the per-scene
    audio timings written by scripts/tts.py
  * a layout lint that records overlapping or off-frame text to workspace/logs/<id>.layout.json
  * small helpers (text, math, pencil circle, flow boxes, arrows, entrances) and the brand stings

The narration-timing part is adapted from manim-voiceover (MIT, (c) 2022 the Manim Community
Developers): bookmarks in narration text become times the animation can wait for.
See THIRD_PARTY.md.
"""

from __future__ import annotations

import glob
import hashlib
import inspect
import json
import math
import os
import re
from pathlib import Path

import numpy as np
from manim import *  # noqa: F401,F403  (re-exported so scene files need one import)
from manim import (
    BLACK, DOWN, LEFT, ORIGIN, RIGHT, UP, UL, UR, DL, DR, PI, TAU,
    Arrow, Circumscribe, Create, CurvedArrow, FadeIn, FadeOut, Line, MathTex,
    Mobject, RoundedRectangle, Scene, Tex, Text, MarkupText, VGroup, VMobject,
    config, logger, rate_functions, smooth,
)

# --------------------------------------------------------------------------- frame + palette

config.background_color = "#000000"
FRAME_W = config.frame_width      # 14.22
FRAME_H = config.frame_height     # 8.0
SAFE_W = FRAME_W - 1.2            # keep ~0.6 units of margin left/right
SAFE_H = FRAME_H - 0.9            # and ~0.45 top/bottom

BG = "#000000"
INK = "#FFFFFF"        # primary text / strokes
INK_2 = "#BBBBBB"      # secondary text (GREY_B)
INK_3 = "#777777"      # tertiary / structural
INK_4 = "#333333"      # grids, guides

BLUE = "#58C4DD"
YELLOW = "#FFFF00"     # emphasis, the pencil, "look here"
YELLOW_SOFT = "#F7D96F"
TEAL = "#5CD0B3"
GREEN = "#83C167"
RED = "#FC6255"
PINK = "#D147BD"
GOLD = "#F0AC5F"
PURPLE = "#9A72AC"
ORANGE = "#FF862F"
MAROON = "#C55F73"

NAMED = {
    "BLUE": BLUE, "YELLOW": YELLOW, "YELLOW_SOFT": YELLOW_SOFT, "TEAL": TEAL, "GREEN": GREEN,
    "RED": RED, "PINK": PINK, "GOLD": GOLD, "PURPLE": PURPLE, "ORANGE": ORANGE,
    "MAROON": MAROON, "WHITE": INK, "INK": INK, "GREY": INK_2, "GRAY": INK_2,
}
# Order used when a concept has no colour in plan.json yet. Yellow is skipped on purpose:
# it is reserved for emphasis.
CONCEPT_CYCLE = [BLUE, TEAL, PINK, GOLD, GREEN, RED, PURPLE, ORANGE]

# Opacity layers: what is being explained now / still-relevant context / scaffolding.
PRIMARY, CONTEXT, SCAFFOLD = 1.0, 0.35, 0.15

# Type scale (Manim font_size units; 48 is Manim's default).
SIZE_TITLE = 64
SIZE_HEAD = 48
SIZE_BODY = 38
SIZE_LABEL = 32
SIZE_SMALL = 26  # never go below this; it is unreadable on a phone

# --------------------------------------------------------------------------- fonts

def _register_fonts() -> tuple[str, str]:
    """Register CMU Serif (3b1b's text face) from TinyTeX's cm-unicode package if present."""
    serif, hand = "Georgia", "Bradley Hand"
    try:
        import manimpango
    except Exception:  # pragma: no cover
        return serif, hand
    roots = []
    texbin = Path(os.environ.get("WAITWHAT_ROOT", "")) / ".venv" / "texbin"
    if texbin.is_file():
        roots.append(Path(texbin.read_text().strip()).parent.parent / "texmf-dist")
    roots += [Path.home() / "Library/TinyTeX/texmf-dist", Path.home() / ".TinyTeX/texmf-dist",
              Path("/usr/share/texlive/texmf-dist"), Path("/usr/local/texlive")]
    for root in roots:
        hits = glob.glob(str(root / "**/cm-unicode/cmun*.otf"), recursive=True) if root.exists() else []
        wanted = [h for h in hits if Path(h).stem in ("cmunrm", "cmunbx", "cmunti", "cmunbi", "cmunss", "cmunsx")]
        if wanted:
            for h in wanted:
                try:
                    manimpango.register_font(h)
                except Exception:
                    pass
            serif = "CMU Serif"
            break
    fonts = set(manimpango.list_fonts())
    if serif not in fonts and "CMU Serif" not in fonts:
        serif = next((f for f in ("Georgia", "Times New Roman", "DejaVu Serif", "Liberation Serif") if f in fonts), "serif")
    if hand not in fonts:
        hand = next((f for f in ("Architects Daughter", "Segoe Print", "Comic Neue") if f in fonts), serif)
    return serif, hand


FONT, FONT_HAND = _register_fonts()
FONT_MONO = "Menlo"

# --------------------------------------------------------------------------- easing
# Entrances ease out (fast start, gentle landing); on-screen moves ease in and out.

def ease_out(t: float) -> float:
    """Strong ease-out, close to cubic-bezier(0.23, 1, 0.32, 1)."""
    return 1 - (1 - t) ** 4


def ease_in_out(t: float) -> float:
    """Strong ease-in-out, close to cubic-bezier(0.77, 0, 0.175, 1)."""
    return 8 * t ** 4 if t < 0.5 else 1 - (-2 * t + 2) ** 4 / 2


# --------------------------------------------------------------------------- workspace + plan

def _scene_file(scene: Scene) -> Path:
    try:
        return Path(inspect.getfile(type(scene))).resolve()
    except Exception:
        return Path.cwd() / "scene.py"


def workspace_of(path: Path) -> Path:
    """workspace/ is the parent of scenes/."""
    p = path.resolve()
    return p.parent.parent if p.parent.name == "scenes" else p.parent


_PLAN_CACHE: dict = {}


def load_plan(ws: Path | None = None) -> dict:
    ws = ws or Path(os.environ.get("WAITWHAT_WORKSPACE", Path.cwd()))
    key = str(ws)
    if key not in _PLAN_CACHE:
        f = Path(ws) / "plan.json"
        try:
            _PLAN_CACHE[key] = json.loads(f.read_text()) if f.exists() else {}
        except Exception as e:  # malformed plan should not kill a render
            logger.warning(f"waitwhat: could not read {f}: {e}")
            _PLAN_CACHE[key] = {}
    return _PLAN_CACHE[key]


def color_of(concept: str, default: str | None = None) -> str:
    """The colour assigned to a concept in plan.json["palette"], so every scene agrees.

    Values may be names ("BLUE") or hex. Unknown concepts get a stable colour from the cycle.
    """
    pal = load_plan().get("palette", {}) or {}
    v = pal.get(concept)
    if v:
        return NAMED.get(str(v).upper(), v)
    if default:
        return default
    h = int(hashlib.md5(concept.encode()).hexdigest(), 16)
    return CONCEPT_CYCLE[h % len(CONCEPT_CYCLE)]


# --------------------------------------------------------------------------- text + math

def fit(mob: Mobject, max_w: float = SAFE_W, max_h: float = SAFE_H) -> Mobject:
    """Shrink (never grow) a mobject to fit a box."""
    if mob.width > max_w:
        mob.scale_to_fit_width(max_w)
    if mob.height > max_h:
        mob.scale_to_fit_height(max_h)
    return mob


def T(text: str, size: float = SIZE_BODY, color: str = INK, *, weight: str = "NORMAL",
      slant: str = "NORMAL", font: str | None = None, max_w: float = SAFE_W, **kw) -> Text:
    """Plain text in the house face. Keep it short: narration carries the words."""
    t = Text(text, font_size=size, color=color, font=font or FONT, weight=weight, slant=slant, **kw)
    return fit(t, max_w)


def M(tex: str | list[str], size: float = 48, color: str = INK, colors: dict | None = None,
      max_w: float = SAFE_W, **kw) -> MathTex:
    """MathTex with an optional {substring: colour} map, e.g. M("x^2 + y^2", colors={"x": BLUE}).

    Coloured substrings are isolated automatically, so they become their own submobjects (and can
    be transformed separately). Double braces isolate other parts: M("{{a^2}} + {{b^2}} = {{c^2}}").
    """
    parts = tex if isinstance(tex, list) else [tex]
    m = MathTex(*parts, font_size=size, color=color,
                substrings_to_isolate=list(colors or {}) + list(kw.pop("substrings_to_isolate", [])), **kw)
    for sub, c in (colors or {}).items():
        m.set_color_by_tex(sub, c)
    return fit(m, max_w)


def hand(text: str, size: float = SIZE_LABEL, color: str = YELLOW, **kw) -> Text:
    """Handwritten annotation (the pencil voice). Use sparingly, for asides and 'look here'."""
    return T(text, size=size, color=color, font=FONT_HAND, **kw)


def label(text: str, target: Mobject, direction=UP, size: float = SIZE_LABEL, color: str | None = None,
          buff: float = 0.2, math: bool = False) -> Mobject:
    """A label attached to its target (never floating far away)."""
    lab = M(text, size=size * 1.25, color=color or INK) if math else T(text, size=size, color=color or INK)
    return lab.next_to(target, direction, buff=buff)


# --------------------------------------------------------------------------- shapes + diagrams

def pencil_circle(target: Mobject | None = None, color: str = YELLOW, buff: float = 0.25,
                  width: float | None = None, height: float | None = None, center=None,
                  seed: int = 3, stroke: float = 5) -> VMobject:
    """Hand-drawn loop around something: the waitwhat signature. Animate with Create(...).

    Slightly wobbly, starts at upper-left and overshoots its own start like a real pencil circle.
    """
    rng = np.random.default_rng(seed)
    if target is not None:
        w = (width or target.width) / 2 + buff
        h = (height or target.height) / 2 + buff
        c = target.get_center() if center is None else center
    else:
        w, h = (width or 2) / 2, (height or 1) / 2
        c = ORIGIN if center is None else center
    n = 120
    turn = TAU * 1.12
    start = 0.75 * PI
    pts = []
    k1, k2 = rng.uniform(0.02, 0.05, 2)
    ph1, ph2 = rng.uniform(0, TAU, 2)
    for i in range(n):
        s = i / (n - 1)
        a = start - turn * s
        r = 1 + k1 * math.sin(3 * a + ph1) + k2 * math.sin(5 * a + ph2) + 0.06 * s
        pts.append(np.array([c[0] + w * r * math.cos(a), c[1] + h * r * math.sin(a) * (1 - 0.04 * s), 0]))
    loop = VMobject(stroke_color=color, stroke_width=stroke)
    loop.set_points_smoothly(pts)
    return loop


def underline(target: Mobject, color: str = YELLOW, buff: float = 0.1, seed: int = 5) -> VMobject:
    rng = np.random.default_rng(seed)
    left, right = target.get_corner(DL) + DOWN * buff, target.get_corner(DR) + DOWN * buff
    pts = [left + (right - left) * s + UP * 0.03 * math.sin(s * 7 + rng.uniform(0, 3)) for s in np.linspace(0, 1, 30)]
    u = VMobject(stroke_color=color, stroke_width=4)
    u.set_points_smoothly(pts)
    return u


def node(text: str, color: str = BLUE, width: float | None = None, height: float = 1.0,
         size: float = SIZE_LABEL, fill: float = 0.12) -> VGroup:
    """Rounded box with a centred label, for flows, pipelines and org charts."""
    lab = T(text, size=size, color=INK)
    w = width or max(lab.width + 0.7, 1.8)
    box = RoundedRectangle(corner_radius=0.18, width=w, height=max(height, lab.height + 0.45),
                           stroke_color=color, stroke_width=3, fill_color=color, fill_opacity=fill)
    fit(lab, box.width - 0.3, box.height - 0.2).move_to(box)
    return VGroup(box, lab)


def _exit_point(mob: Mobject, direction: np.ndarray) -> np.ndarray:
    """Where a ray from mob's centre in `direction` leaves its bounding box."""
    c = mob.get_center()
    d = np.array(direction, dtype=float)
    hw, hh = mob.width / 2, mob.height / 2
    tx = hw / abs(d[0]) if abs(d[0]) > 1e-9 else np.inf
    ty = hh / abs(d[1]) if abs(d[1]) > 1e-9 else np.inf
    return c + d * min(tx, ty)


def link(a: Mobject, b: Mobject, color: str = INK_2, curved: float = 0.0, buff: float = 0.15,
         stroke: float = 3) -> Mobject:
    """Arrow from the edge of a to the edge of b along the line between their centres.

    curved != 0 bends it (radians; negative = clockwise), good for cycles and feedback loops.
    """
    d = b.get_center() - a.get_center()
    start, end = _exit_point(a, d), _exit_point(b, -d)
    u = (end - start) / (np.linalg.norm(end - start) + 1e-9)
    start, end = start + u * buff, end - u * buff
    if curved:
        return CurvedArrow(start, end, angle=curved, color=color, stroke_width=stroke, tip_length=0.2)
    return Arrow(start, end, buff=0, color=color, stroke_width=stroke,
                 max_tip_length_to_length_ratio=0.25, tip_length=0.22)


def grid_paper(opacity: float = 1.0) -> VGroup:
    """Faint graph-paper backdrop (brand nod). Keep it below ~0.1 effective opacity."""
    lines = VGroup()
    for x in np.arange(-7, 7.01, 0.5):
        lines.add(Line([x, -4, 0], [x, 4, 0], stroke_width=1 if x % 2 else 1.5,
                       stroke_color="#2b3a46", stroke_opacity=0.35 * opacity))
    for y in np.arange(-4, 4.01, 0.5):
        lines.add(Line([-7.2, y, 0], [7.2, y, 0], stroke_width=1 if y % 2 else 1.5,
                       stroke_color="#2b3a46", stroke_opacity=0.35 * opacity))
    return lines


def latlon(lat: float, lon: float, width: float = 12.0, center=ORIGIN) -> np.ndarray:
    """Equirectangular projection of (lat, lon) into a width-wide map centred at `center`."""
    return np.array(center) + np.array([lon / 180 * width / 2, lat / 90 * width / 4, 0])


def geojson_shapes(path: str | Path, width: float = 12.0, center=ORIGIN, color: str = INK_3,
                   fill: float = 0.15, min_points: int = 8) -> VGroup:
    """Outline polygons from a GeoJSON file (e.g. public-domain Natural Earth land/countries)."""
    data = json.loads(Path(path).read_text())
    group = VGroup()
    feats = data["features"] if "features" in data else [data]
    for f in feats:
        g = f.get("geometry") or f
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            ring = poly[0]
            if len(ring) < min_points:
                continue
            pts = [latlon(lat, lon, width, center) for lon, lat in ring]
            shape = VMobject(stroke_color=color, stroke_width=1.5, fill_color=color, fill_opacity=fill)
            shape.set_points_as_corners(pts)
            group.add(shape)
    return group


# CPK-like element colours, softened to sit in the house palette.
CPK = {"H": "#EEEEEE", "C": "#8A8F98", "N": BLUE, "O": RED, "S": YELLOW_SOFT, "P": ORANGE,
       "Cl": GREEN, "F": "#A6D785", "Na": PURPLE, "Fe": GOLD}


def molecule(atoms: list[tuple[str, tuple[float, float]]], bonds: list[tuple[int, int, int]],
             scale: float = 1.0, show_symbols: bool = True) -> VGroup:
    """2D ball-and-stick: atoms=[("O",(0,0)),("H",(0.8,0.6))...], bonds=[(i,j,order)]."""
    from manim import Circle
    pos = [np.array([x * scale, y * scale, 0]) for _, (x, y) in atoms]
    sticks = VGroup()
    for i, j, order in bonds:
        d = pos[j] - pos[i]
        n = np.array([-d[1], d[0], 0]) / (np.linalg.norm(d) + 1e-9)
        for k in range(order):
            off = n * 0.09 * (k - (order - 1) / 2)
            sticks.add(Line(pos[i] + off, pos[j] + off, stroke_color=INK_2, stroke_width=5))
    balls = VGroup()
    for (sym, _), p in zip(atoms, pos):
        r = (0.22 if sym == "H" else 0.34) * scale
        ball = Circle(radius=r, stroke_width=0, fill_color=CPK.get(sym, PINK), fill_opacity=1).move_to(p)
        grp = VGroup(ball)
        if show_symbols:
            grp.add(T(sym, size=SIZE_SMALL * scale, color=BLACK if sym in ("H", "S", "Cl", "F") else INK).move_to(p))
        balls.add(grp)
    return VGroup(sticks, balls)


def code_block(code: str, language: str = "python", size: float = 24) -> VGroup:
    """Syntax-highlighted code on a subtle panel (no window chrome)."""
    from manim import Code
    c = Code(code_string=code.strip("\n"), language=language, formatter_style="monokai",
             add_line_numbers=False, background="rectangle",
             background_config={"fill_color": "#111317", "stroke_color": "#2a2d33", "stroke_width": 1,
                                "corner_radius": 0.15},
             paragraph_config={"font": FONT_MONO, "font_size": size})
    return fit(c)


# --------------------------------------------------------------------------- animation helpers

def enter(*mobs: Mobject, shift=None, scale: float = 0.94, run_time: float = 0.7, lag: float = 0.08):
    """Arrive: fade up from a slightly smaller size, ease-out. Staggers multiple mobjects."""
    from manim import LaggedStart
    anims = [FadeIn(m, shift=shift if shift is not None else UP * 0.15, scale=scale,
                    rate_func=ease_out, run_time=run_time) for m in mobs]
    return anims[0] if len(anims) == 1 else LaggedStart(*anims, lag_ratio=lag)


def leave(*mobs: Mobject, run_time: float = 0.4):
    """Exit faster than you entered."""
    from manim import AnimationGroup
    return AnimationGroup(*[FadeOut(m, run_time=run_time, rate_func=smooth) for m in mobs])


def dim(*mobs: Mobject, to: float = CONTEXT):
    """Push things to the background without removing them (keeps context)."""
    from manim import AnimationGroup
    return AnimationGroup(*[m.animate.set_opacity(to) for m in mobs])


def focus(mob: Mobject, color: str = YELLOW):
    """Trace a box around text or a compact group. For tilted or irregular shapes use pulse()."""
    return Circumscribe(mob, color=color, time_width=0.6, run_time=1.2)


def pulse(mob: Mobject, opacity: float = 0.85, run_time: float = 1.0):
    """Briefly brighten a filled shape and settle back: emphasis without extra outlines."""
    base = mob.get_fill_opacity()
    return mob.animate(rate_func=rate_functions.there_and_back, run_time=run_time).set_fill(
        opacity=max(opacity, base))


# --------------------------------------------------------------------------- narration timing

_TAG = re.compile(r"<\s*(bookmark|break)[^>]*/\s*>", re.I)


def strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", text)).strip()


_TAG_ATTRS = re.compile(r"""<\s*(bookmark|break)\b([^>]*)/\s*>""", re.I)
_ATTR = re.compile(r"""(\w+)\s*=\s*["']([^"']*)["']""")


def estimate_timing(narration: str, wps: float = 3.3) -> dict:
    """Timing estimated from narration text (≈200 wpm, sentence ends +0.25 s, <break/> as written),
    in the shape tts.py writes. Lets a scene preview before its audio exists; the real audio replaces it."""
    words, marks, t = [], {}, 0.0
    pos = 0

    def add(chunk: str):
        nonlocal t
        for tok in chunk.split():
            d = max(0.18, (0.6 + len(tok.strip(".,;:!?")) / 6.0) / wps)
            words.append({"w": tok, "start": round(t, 3), "end": round(t + d, 3)})
            t += d + (0.25 if re.search(r"[.!?…]['\")\]]*$", tok) else 0.0)

    for m in _TAG_ATTRS.finditer(narration or ""):
        add(narration[pos:m.start()])
        attrs = dict(_ATTR.findall(m.group(2)))
        if m.group(1).lower() == "bookmark":
            name = attrs.get("mark") or attrs.get("name")
            if name:
                marks[name] = round(t, 3)
        else:
            v = attrs.get("time", "0.5s").strip().lower()
            try:
                t += float(v[:-2]) / 1000 if v.endswith("ms") else float(v.rstrip("s") or 0.5)
            except ValueError:
                t += 0.5
        pos = m.end()
    add((narration or "")[pos:])
    return {"duration": round(t, 3), "lead_in": 0.35, "words": words, "marks": marks,
            "text": strip_tags(narration or ""), "estimated": True}


class _Timing:
    def __init__(self, data: dict | None, scene_id: str):
        self.scene_id = scene_id
        self.ok = bool(data)
        data = data or {}
        self.lead = float(data.get("lead_in", 0.35))
        self.duration = float(data.get("duration", 0.0))
        self.marks = {k: float(v) for k, v in (data.get("marks") or {}).items()}
        self.words = data.get("words") or []
        self.text = data.get("text", "")

    def word_time(self, word: str, occurrence: int = 1, edge: str = "start") -> float | None:
        w = word.lower().strip(".,;:!?\"'")
        n = 0
        for item in self.words:
            if item["w"].lower().strip(".,;:!?\"'()") == w:
                n += 1
                if n == occurrence:
                    return float(item[edge])
        return None


class WaitwhatScene(Scene):
    """Base class for every waitwhat scene. One per file; file stem = scene id."""

    #: seconds of silence before the narration starts in this scene (stitch.py honours the same value)
    lead_in: float | None = None

    def setup(self):
        super().setup()
        self.camera.background_color = BG
        f = _scene_file(self)
        self.scene_id = os.environ.get("WAITWHAT_SCENE_ID") or f.stem
        self.ws = Path(os.environ.get("WAITWHAT_WORKSPACE") or workspace_of(f))
        os.environ.setdefault("WAITWHAT_WORKSPACE", str(self.ws))
        audio_json = self.ws / "audio" / f"{self.scene_id}.json"
        data = None
        if audio_json.exists():
            try:
                data = json.loads(audio_json.read_text())
            except Exception as e:
                logger.warning(f"waitwhat: bad timing file {audio_json}: {e}")
        self.timing_estimated = False
        if not data:
            sc = next((x for x in (load_plan(self.ws).get("scenes") or []) if x.get("id") == self.scene_id), None)
            if sc and (sc.get("narration") or "").strip():
                data = estimate_timing(sc["narration"])
                if sc.get("lead_in") is not None:
                    data["lead_in"] = float(sc["lead_in"])
                self.timing_estimated = True
        self.timing = _Timing(data, self.scene_id)
        if self.lead_in is not None:
            self.timing.lead = float(self.lead_in)
        if self.timing_estimated:
            logger.warning(f"waitwhat: no narration audio for '{self.scene_id}' yet; timing estimated from "
                           f"plan.json (run `ww tts`, then re-render for the final cut).")
        elif not self.timing.ok:
            logger.warning(f"waitwhat: no narration timing for '{self.scene_id}' "
                           f"(run scripts/tts.py first). Using estimates.")
        self._lint: list[dict] = []
        self._missing: list[str] = []
        self._probe_t = float(os.environ["WAITWHAT_PROBE_T"]) if os.environ.get("WAITWHAT_PROBE_T") else None
        self._probed = False

    # ---- clock
    @property
    def now(self) -> float:
        return float(self.renderer.time)

    @property
    def narration_end(self) -> float:
        return self.timing.lead + self.timing.duration

    def mark_time(self, mark: str) -> float:
        """Absolute scene time of a <bookmark mark="..."/> (or of a word: until("word:hypotenuse"))."""
        if mark.startswith("word:"):
            t = self.timing.word_time(mark[5:])
            if t is not None:
                return self.timing.lead + t
        elif mark in self.timing.marks:
            return self.timing.lead + self.timing.marks[mark]
        if mark not in self._missing:
            self._missing.append(mark)
            logger.warning(f"waitwhat: mark '{mark}' not found in narration of '{self.scene_id}'")
        return self.now + 1.0

    def until(self, mark: str, buff: float = 0.0, minimum: float = 0.3) -> float:
        """Seconds from now until a narration mark; use as run_time so the visual lands on the word."""
        return max(minimum, self.mark_time(mark) - self.now + buff)

    def play_until(self, mark: str, *anims, minimum: float = 0.3, **kw):
        self.play(*anims, run_time=self.until(mark, minimum=minimum), **kw)

    def wait_until(self, mark: str, buff: float = 0.0):
        dt = self.mark_time(mark) - self.now + buff
        if dt > 0.02:
            self.wait(dt)

    def finish(self, tail: float = 0.8, fade: bool = False):
        """Hold until the narration has finished (+tail). Call once at the end of construct()."""
        dt = self.narration_end + tail - self.now
        if fade:
            fade_t = 0.5
            if dt > fade_t + 0.05:
                self.wait(dt - fade_t)
            self.play(*[FadeOut(m) for m in self.mobjects], run_time=fade_t)
        elif dt > 0.02:
            self.wait(dt)
        self._write_report()

    # ---- layout lint
    _TEXTY = (Text, MarkupText, MathTex, Tex)

    def _texts(self):
        out = []

        def walk(m):
            if isinstance(m, self._TEXTY):
                out.append(m)
                return
            for s in m.submobjects:
                walk(s)

        for m in self.mobjects:
            walk(m)
        return out

    @staticmethod
    def _visible(m) -> bool:
        try:
            ops = [s.get_fill_opacity() for s in m.family_members_with_points()]
            return bool(ops) and max(ops) > 0.2
        except Exception:
            return True

    def _check_layout(self):
        hw, hh = FRAME_W / 2, FRAME_H / 2
        texts = [t for t in self._texts() if self._visible(t) and t.width > 0]
        boxes = []
        for t in texts:
            x0, y0 = t.get_corner(DL)[:2]
            x1, y1 = t.get_corner(UR)[:2]
            name = (getattr(t, "original_text", None) or getattr(t, "tex_string", None)
                    or getattr(t, "text", None) or type(t).__name__)
            name = str(name)[:40]
            if x0 < -hw + 0.15 or x1 > hw - 0.15 or y0 < -hh + 0.1 or y1 > hh - 0.1:
                self._lint.append({"t": round(self.now, 2), "issue": "off-frame", "what": name,
                                   "box": [round(v, 2) for v in (x0, y0, x1, y1)]})
            boxes.append((name, x0, y0, x1, y1, id(t)))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                ix = min(a[3], b[3]) - max(a[1], b[1])
                iy = min(a[4], b[4]) - max(a[2], b[2])
                if ix > 0.05 and iy > 0.05:
                    small = min((a[3] - a[1]) * (a[4] - a[2]), (b[3] - b[1]) * (b[4] - b[2]))
                    if small > 0 and ix * iy / small > 0.12:
                        self._lint.append({"t": round(self.now, 2), "issue": "text-overlap",
                                           "what": [a[0], b[0]]})
        if self._probe_t is not None and not self._probed and self.now >= self._probe_t:
            self._probed = True
            self._dump_probe()

    def _dump_probe(self):
        """Describe what is on screen (for refine: which element did the user circle?)."""
        items = []
        px = lambda x, y: [round((x / FRAME_W + 0.5) * 1920), round((0.5 - y / FRAME_H) * 1080)]
        for m in self.mobjects:
            for sub in [m] + [s for s in m.submobjects if s.submobjects or isinstance(s, self._TEXTY)][:12]:
                if sub.width == 0 and sub.height == 0:
                    continue
                x0, y0 = sub.get_corner(DL)[:2]
                x1, y1 = sub.get_corner(UR)[:2]
                items.append({
                    "type": type(sub).__name__,
                    "text": str(getattr(sub, "original_text", None) or getattr(sub, "tex_string", "")
                                or getattr(sub, "text", "") or "")[:60],
                    "color": str(sub.get_color()),
                    "box_units": [round(v, 2) for v in (x0, y0, x1, y1)],
                    "box_px_1080p": px(x0, y1) + px(x1, y0),
                    "top_level": sub is m,
                })
        out = self.ws / "logs" / f"{self.scene_id}.probe.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"scene": self.scene_id, "t": round(self.now, 2), "mobjects": items}, indent=1))

    def play(self, *args, **kwargs):
        super().play(*args, **kwargs)
        try:
            self._check_layout()
        except Exception as e:  # lint must never break a render
            logger.debug(f"layout lint failed: {e}")

    def _write_report(self):
        out = self.ws / "logs" / f"{self.scene_id}.layout.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        seen, uniq = set(), []
        for item in self._lint:
            key = json.dumps({k: v for k, v in item.items() if k != "t"}, sort_keys=True)
            if key not in seen:
                seen.add(key)
                uniq.append(item)
        out.write_text(json.dumps({"scene": self.scene_id, "issues": uniq,
                                   "missing_marks": self._missing,
                                   "duration": round(self.now, 2),
                                   "narration_end": round(self.narration_end, 2)}, indent=1))

    def tear_down(self):
        self._write_report()
        super().tear_down()


# --------------------------------------------------------------------------- brand stings

CHALK = "#E3E6DF"   # brand "chalk on blackboard" ink
BRAND_BLUE = "#58C4DD"


def brand_wordmark(height: float = 1.5) -> VGroup | None:
    """The hand-lettered 'waitwhat?' wordmark from brand/wordmark.svg as drawable strokes.

    Returns None if the brand file is missing; callers fall back to a typeset wordmark.
    The ink strokes are chalk, the question mark is the brand's blue accent.
    """
    import re as _re
    f = Path(os.environ.get("WAITWHAT_ROOT", Path(__file__).resolve().parents[3])) / "brand" / "wordmark.svg"
    if not f.exists():
        return None
    try:
        import svgelements
        from manim.mobject.svg.svg_mobject import VMobjectFromSVGPath
        from manim import Dot
        paths = []
        for cls, d in _re.findall(r'<path class="(\w+)" d="([^"]+)"', f.read_text()):
            m = VMobjectFromSVGPath(svgelements.Path(d))
            paths.append((BRAND_BLUE if cls == "accent" else CHALK, m))
        if not paths:
            return None
        strokes = VGroup(*[m for _, m in paths])
        strokes.flip(RIGHT)            # SVG y grows downward
        strokes.scale_to_fit_height(height).move_to(ORIGIN)
        out = VGroup()
        for color, m in paths:
            if max(m.width, m.height) < 0.06 * height:   # dots (i, ?) are tiny round-capped strokes in SVG
                out.add(Dot(m.get_center(), radius=0.045 * height / 1.5, color=color))
            else:
                out.add(m.set_fill(opacity=0).set_stroke(color, width=7))
        return out
    except Exception as e:  # never let branding break a render
        logger.warning(f"waitwhat: could not load brand wordmark: {e}")
        return None


def _typeset_wordmark(size: float = 72):
    wait = Text("wait", font=FONT, font_size=size, color=INK)
    what = Text("what?", font=FONT, font_size=size, color=YELLOW)
    return VGroup(wait, what).arrange(RIGHT, buff=0.62, aligned_edge=DOWN)


class WaitwhatIntro(Scene):
    """~1.7 s opening sting: the wordmark draws itself on, like pencil on a blackboard, then clears."""

    def construct(self):
        self.camera.background_color = BG
        mark = brand_wordmark(1.6)
        if mark is not None:
            self.play(LaggedStart(*[Create(s, rate_func=ease_out) for s in mark], lag_ratio=0.12), run_time=1.15)
            self.wait(0.3)
            self.play(FadeOut(mark, scale=1.03), run_time=0.25)
            return
        mark = _typeset_wordmark(84).move_to(ORIGIN)
        loop = pencil_circle(mark[1], buff=0.28, seed=7, stroke=6)
        self.play(FadeIn(mark[0], shift=UP * 0.12, scale=0.96, rate_func=ease_out), run_time=0.35)
        self.play(FadeIn(mark[1], shift=UP * 0.12, scale=0.96, rate_func=ease_out), run_time=0.3)
        self.play(Create(loop, rate_func=ease_out), run_time=0.45)
        self.wait(0.25)
        self.play(FadeOut(VGroup(mark, loop), scale=1.03), run_time=0.25)


class WaitwhatOutro(Scene):
    """~2.4 s closing sting: the wordmark, a quiet credit line, fade to black."""

    def construct(self):
        self.camera.background_color = BG
        mark = brand_wordmark(1.2)
        if mark is None:
            mark = _typeset_wordmark(64).move_to(ORIGIN)
        sub = Text("made with waitwhat", font=FONT, font_size=SIZE_SMALL, color=INK_3).next_to(mark, DOWN, buff=0.6)
        self.play(FadeIn(mark, shift=UP * 0.12, scale=0.96, rate_func=ease_out), run_time=0.5)
        self.play(FadeIn(sub, rate_func=ease_out), run_time=0.5)
        self.wait(0.9)
        self.play(FadeOut(VGroup(mark, sub)), run_time=0.55)
