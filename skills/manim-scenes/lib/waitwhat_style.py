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
  * both aspects: 16:9 (1920x1080, 14.22 x 8 units) or 9:16 (1080x1920, 8 x 14.22 units) from
    plan.json "aspect"; ASPECT, IS_VERTICAL, the SAFE_* area, MAIN axis and helpers (place_title,
    side_by_side, flow, spots, fit_safe, by_aspect) so one layout adapts; type scales up in 9:16
  * a layout lint that records overlapping or off-frame text to workspace/logs/<id>.layout.json
  * small helpers (text, math, pencil circle, flow boxes, arrows, entrances) and the brand stings
  * themes (plan.json "theme"): the palette constants below adapt to the video's world, and a
    procedural background (chalkboard, blueprint, paper, night sky...) is painted behind everything
  * sound cues: appear/write/draw/erase animations are logged as sound-effect cues against the
    renderer clock (`self.play(..., sfx="coin")`, `self.sfx("chime", at="reveal")`); stitch.py
    mixes them under the voice

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

import waitwhat_themes as _themes


def _read_plan_for_theme() -> dict:
    ws = os.environ.get("WAITWHAT_WORKSPACE")
    if not ws:
        return {}
    try:
        return json.loads((Path(ws) / "plan.json").read_text())
    except Exception:
        return {}


_PLAN0 = _read_plan_for_theme()

# The video's world, resolved once per render (one scene per process): WAITWHAT_THEME env, then
# plan.scenes[].theme, then plan.theme, else "classic" (pure black). Scene code never hard-codes
# hex colours: the names below (INK, BLUE, YELLOW...) already hold this theme's values.
THEME, THEME_OPTS = _themes.resolve(_PLAN0, os.environ.get("WAITWHAT_SCENE_ID"))
_T = _themes.THEMES[THEME]
_C = _T["colors"]
THEMES = ("classic", "studio", "chalkboard", "blueprint", "space", "ocean", "city", "whiteboard", "graph_paper", "paper", "hills")
assert set(THEMES) == set(_themes.THEMES)
IS_DARK = bool(_T["dark"])

# --------------------------------------------------------------------------- aspect + frame
# One render per video, laid out for its aspect from the start (never cropped): WAITWHAT_ASPECT env,
# then plan.json "aspect", then <job>/request.json "aspect", else 16:9. Same rule as scripts/aspect.py.
_ASPECT_WORDS = {"16:9": "16:9", "landscape": "16:9", "horizontal": "16:9", "wide": "16:9",
                 "9:16": "9:16", "vertical": "9:16", "portrait": "9:16", "tall": "9:16"}


def _resolve_aspect(plan: dict) -> str:
    req = {}
    ws = os.environ.get("WAITWHAT_WORKSPACE")
    if ws:
        try:
            req = json.loads((Path(ws).parent / "request.json").read_text())
        except Exception:
            req = {}
    for v in (os.environ.get("WAITWHAT_ASPECT"), plan.get("aspect"), req.get("aspect")):
        if isinstance(v, str) and v.strip().lower() in _ASPECT_WORDS:
            return _ASPECT_WORDS[v.strip().lower()]
    return "16:9"


#: "16:9" (1920x1080, 14.22 x 8 units) or "9:16" (1080x1920, 8 x 14.22 units)
ASPECT = _resolve_aspect(_PLAN0)
IS_VERTICAL = ASPECT == "9:16"
if IS_VERTICAL:
    # Same 135 px per unit as 16:9, turned on its side: 8 units wide, 14.22 tall.
    if config.pixel_width > config.pixel_height:
        config.pixel_width, config.pixel_height = config.pixel_height, config.pixel_width
    config.frame_height = 8.0 * 16 / 9
    config.frame_width = 8.0

config.background_color = _T["bg"]
FRAME_W = config.frame_width      # 14.22 (9:16: 8.0)
FRAME_H = config.frame_height     # 8.0 (9:16: 14.22)
#: lowest y content should use; themes with a skyline or hills along the bottom raise it
FLOOR_Y = float(_themes.content_floor(THEME, FRAME_H))
# Margins. 9:16 keeps thumb-safe sides, clears the feed's top bar, and leaves the bottom ~15 % (where
# vertical players put captions, buttons and their progress bar) free of anything that must be read.
SAFE_W = FRAME_W - (1.1 if IS_VERTICAL else 1.2)              # 16:9: ~0.6 units of margin left/right
SAFE_TOP = FRAME_H / 2 - (0.9 if IS_VERTICAL else 0.45)       # highest y for content
SAFE_BOTTOM = max(-FRAME_H / 2 + (0.15 * FRAME_H if IS_VERTICAL else 0.45),
                  FLOOR_Y if "floor" in _T else -FRAME_H)       # lowest y for text
SAFE_H = (SAFE_TOP - SAFE_BOTTOM) if IS_VERTICAL else FRAME_H - 0.9
SAFE_LEFT, SAFE_RIGHT = -SAFE_W / 2, SAFE_W / 2
#: centre of the area content may use (9:16: a little above the frame's centre)
SAFE_CENTER = np.array([0.0, (SAFE_TOP + SAFE_BOTTOM) / 2, 0.0])
#: the frame's long axis (sequences, pipelines, comparisons run along it) and its short one
MAIN = DOWN if IS_VERTICAL else RIGHT
CROSS = RIGHT if IS_VERTICAL else DOWN
#: type is set larger in 9:16: a vertical video is watched on a phone, full width
TYPE_SCALE = 1.3 if IS_VERTICAL else 1.0
#: pixel size of the final video (the probe and refine frames use it)
SIZE_PX = (1080, 1920) if IS_VERTICAL else (1920, 1080)

BG = _T["bg"]          # classic: #000000
INK = _T["ink"]        # primary text / strokes (classic #FFFFFF)
INK_2 = _T["ink_2"]    # secondary text (classic #BBBBBB)
INK_3 = _T["ink_3"]    # tertiary / structural (classic #777777)
INK_4 = _T["ink_4"]    # grids, guides (classic #333333)

BLUE = _C["BLUE"]          # classic #58C4DD
YELLOW = _C["YELLOW"]      # emphasis, the pencil, "look here" (classic #FFFF00; amber on light themes)
YELLOW_SOFT = _C["YELLOW_SOFT"]
TEAL = _C["TEAL"]
GREEN = _C["GREEN"]
RED = _C["RED"]
PINK = _C["PINK"]
GOLD = _C["GOLD"]
PURPLE = _C["PURPLE"]
ORANGE = _C["ORANGE"]
MAROON = _C["MAROON"]

NAMED = {
    "BLUE": BLUE, "YELLOW": YELLOW, "YELLOW_SOFT": YELLOW_SOFT, "TEAL": TEAL, "GREEN": GREEN,
    "RED": RED, "PINK": PINK, "GOLD": GOLD, "PURPLE": PURPLE, "ORANGE": ORANGE,
    "MAROON": MAROON, "WHITE": INK, "INK": INK, "GREY": INK_2, "GRAY": INK_2,
}
_CLASSIC_HEX = {h.upper(): n for n, h in _themes.THEMES["classic"]["colors"].items()}
# Order used when a concept has no colour in plan.json yet. Yellow is skipped on purpose:
# it is reserved for emphasis.
CONCEPT_CYCLE = [BLUE, TEAL, PINK, GOLD, GREEN, RED, PURPLE, ORANGE]

# Opacity layers: what is being explained now / still-relevant context / scaffolding.
PRIMARY, CONTEXT, SCAFFOLD = 1.0, 0.35, 0.15

# Type scale (Manim font_size units; 48 is Manim's default). Nominal sizes: T(), M(), hand(), label(),
# node() and code_block() multiply them by TYPE_SCALE (1.3 in 9:16), so the same code reads well on a
# phone. Raw Text/MathTex(font_size=...) do not: wrap the number in sz() there.
SIZE_TITLE = 64
SIZE_HEAD = 48
SIZE_BODY = 38
SIZE_LABEL = 32
SIZE_SMALL = 26  # never go below this; it is unreadable on a phone


def _theme_defaults() -> None:
    """On light themes Manim's own default colour (white) would be invisible: make plain
    Text/MathTex/Line/Arrow/Square/... default to the theme's ink instead."""
    if IS_DARK:
        return
    import manim as _m
    for name in ("Text", "MarkupText", "Paragraph", "MathTex", "Tex", "SingleStringMathTex",
                 "DecimalNumber", "Integer", "Variable", "Line", "DashedLine", "Arrow", "DoubleArrow",
                 "Vector", "Dot", "Brace", "BraceLabel", "Square", "Rectangle", "RoundedRectangle",
                 "Polygon", "RegularPolygon", "Triangle", "Arc", "ArcBetweenPoints", "CurvedArrow",
                 "Angle", "RightAngle", "Elbow", "NumberLine", "Cross", "Star", "Annulus", "Ellipse",
                 "SurroundingRectangle", "Underline", "ParametricFunction", "FunctionGraph", "VMobject"):
        cls = getattr(_m, name, None)
        if cls is None:
            continue
        try:
            cls.set_default(color=INK_2 if name in ("NumberLine",) else INK)
        except Exception:  # pragma: no cover - never let theming break a render
            pass


_theme_defaults()

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
        v = str(v)
        # classic hex values written into the palette still follow the theme
        v = _CLASSIC_HEX.get(v.upper(), v)
        return NAMED.get(v.upper(), v)
    if default:
        return default
    h = int(hashlib.md5(concept.encode()).hexdigest(), 16)
    return CONCEPT_CYCLE[h % len(CONCEPT_CYCLE)]


# --------------------------------------------------------------------------- text + math

def sz(size: float) -> float:
    """A nominal font size at this video's type scale, for raw Text/MathTex(font_size=sz(40))."""
    return size * TYPE_SCALE


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
    t = Text(text, font_size=size * TYPE_SCALE, color=color, font=font or FONT, weight=weight, slant=slant, **kw)
    return fit(t, max_w)


def M(tex: str | list[str], size: float = 48, color: str = INK, colors: dict | None = None,
      max_w: float = SAFE_W, **kw) -> MathTex:
    """MathTex with an optional {substring: colour} map, e.g. M("x^2 + y^2", colors={"x": BLUE}).

    Coloured substrings are isolated automatically, so they become their own submobjects (and can
    be transformed separately). Double braces isolate other parts: M("{{a^2}} + {{b^2}} = {{c^2}}").
    """
    parts = tex if isinstance(tex, list) else [tex]
    m = MathTex(*parts, font_size=size * TYPE_SCALE, color=color,
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


# --------------------------------------------------------------------------- layout (both aspects)
# Lay a scene out with these and the same code works in 16:9 and 9:16: things spread along x in a
# landscape frame and stack along y in a vertical one, titles sit at the top of the safe area, and
# everything is fitted to the area that is free (in 9:16, the bottom ~15 % stays clear).

def by_aspect(landscape, vertical):
    """One value per aspect: by_aspect(LEFT * 3.5, UP * 2.5), by_aspect(6, 3)."""
    return vertical if IS_VERTICAL else landscape


def safe_point(fx: float, fy: float) -> np.ndarray:
    """A point by fraction of the safe area: safe_point(-1, 1) is its top-left corner, (0, 0) its centre."""
    return np.array([SAFE_CENTER[0] + fx * SAFE_W / 2, SAFE_CENTER[1] + fy * (SAFE_TOP - SAFE_BOTTOM) / 2, 0.0])


def content_box(below: Mobject | None = None, above: Mobject | None = None, buff: float = 0.35):
    """(x0, y0, x1, y1) of the free safe area: under `below` (e.g. a title), over `above` (e.g. a caption)."""
    top = SAFE_TOP if below is None else min(SAFE_TOP, below.get_bottom()[1] - buff)
    bot = SAFE_BOTTOM if above is None else max(SAFE_BOTTOM, above.get_top()[1] + buff)
    return SAFE_LEFT, bot, SAFE_RIGHT, top


def fit_safe(mob: Mobject, below: Mobject | None = None, above: Mobject | None = None, fill: float = 1.0,
             buff: float = 0.35) -> Mobject:
    """Shrink (never grow) a mobject to the free safe area (see content_box) and centre it there."""
    x0, y0, x1, y1 = content_box(below, above, buff)
    fit(mob, (x1 - x0) * fill, (y1 - y0) * fill)
    return mob.move_to([(x0 + x1) / 2, (y0 + y1) / 2, 0])


def place_title(mob: Mobject, buff: float = 0.0) -> Mobject:
    """Put a title or header at the top of the safe area, centred and fitted to its width."""
    fit(mob, SAFE_W, SAFE_H * 0.25)
    return mob.move_to([0, SAFE_TOP - buff - mob.height / 2, 0])


def side_by_side(*mobs: Mobject, buff: float | None = None, below: Mobject | None = None,
                 above: Mobject | None = None, fill: float = 1.0, aligned_edge=ORIGIN) -> VGroup:
    """Things to compare (A vs B, before/after): a row in 16:9, a stack in 9:16. Arranged along MAIN,
    fitted to the free safe area (under `below`) and centred in it. Returns the VGroup."""
    gap = buff if buff is not None else by_aspect(1.2, 0.7)
    g = VGroup(*mobs).arrange(MAIN, buff=gap, aligned_edge=aligned_edge)
    return fit_safe(g, below, above, fill)


def flow(*mobs: Mobject, buff: float | None = None, below: Mobject | None = None,
         above: Mobject | None = None) -> VGroup:
    """A sequence or pipeline (steps, stages, a timeline) along the frame's long axis: left to right
    in 16:9, top to bottom in 9:16. Join the steps with link(a, b); it follows either direction."""
    return side_by_side(*mobs, buff=buff if buff is not None else by_aspect(1.0, 0.55), below=below, above=above)


def spots(n: int, below: Mobject | None = None, above: Mobject | None = None,
          span: float | None = None) -> list[np.ndarray]:
    """n evenly spread anchor points along the long axis (x in 16:9, top to bottom in 9:16), centred
    in the free safe area. For things placed by position: a.move_to(spots(2)[0]), b.move_to(spots(2)[1])."""
    x0, y0, x1, y1 = content_box(below, above)
    c = np.array([(x0 + x1) / 2, (y0 + y1) / 2, 0.0])
    if n <= 1:
        return [c]
    length = (y1 - y0) if IS_VERTICAL else (x1 - x0)
    span = length * (n - 1) / n if span is None else span
    return [c + MAIN * (-span / 2 + span * i / (n - 1)) for i in range(n)]


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
    """Faint graph-paper backdrop (brand nod). Keep it below ~0.1 effective opacity.
    (The blueprint and graph_paper themes already draw a grid behind everything.)"""
    col = "#2b3a46" if THEME == "classic" else INK_4
    lines = VGroup()
    hw, hh = math.ceil(FRAME_W / 2), math.ceil(FRAME_H / 2)
    for x in np.arange(-hw, hw + 0.01, 0.5):
        lines.add(Line([x, -hh, 0], [x, hh, 0], stroke_width=1 if x % 2 else 1.5,
                       stroke_color=col, stroke_opacity=0.35 * opacity))
    for y in np.arange(-hh, hh + 0.01, 0.5):
        lines.add(Line([-hw - 0.2, y, 0], [hw + 0.2, y, 0], stroke_width=1 if y % 2 else 1.5,
                       stroke_color=col, stroke_opacity=0.35 * opacity))
    return lines


#: default width of a world map: 12 units in 16:9, the safe width in 9:16
MAP_W = SAFE_W if IS_VERTICAL else 12.0


def latlon(lat: float, lon: float, width: float = MAP_W, center=ORIGIN) -> np.ndarray:
    """Equirectangular projection of (lat, lon) into a width-wide map centred at `center`."""
    return np.array(center) + np.array([lon / 180 * width / 2, lat / 90 * width / 4, 0])


def geojson_shapes(path: str | Path, width: float = MAP_W, center=ORIGIN, color: str = INK_3,
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
CPK = {"H": "#EEEEEE" if IS_DARK else "#A9B2BC", "C": "#8A8F98" if IS_DARK else "#5F6670", "N": BLUE, "O": RED, "S": YELLOW_SOFT, "P": ORANGE,
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
            grp.add(T(sym, size=SIZE_SMALL * scale / TYPE_SCALE, color=BLACK if sym in ("H", "S", "Cl", "F") else INK).move_to(p))
        balls.add(grp)
    return VGroup(sticks, balls)


def code_block(code: str, language: str = "python", size: float = 24) -> VGroup:
    """Syntax-highlighted code on a subtle panel (no window chrome). 9:16: keep lines under ~30 chars."""
    from manim import Code
    c = Code(code_string=code.strip("\n"), language=language,
             formatter_style="monokai" if IS_DARK else "friendly",
             add_line_numbers=False, background="rectangle",
             background_config={"fill_color": _T["code_bg"], "stroke_color": INK_4, "stroke_width": 1,
                                "corner_radius": 0.15},
             paragraph_config={"font": FONT_MONO, "font_size": size * TYPE_SCALE})
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


def beat(mob: Mobject, scale: float = 1.08, run_time: float = 0.45):
    """A quick swell-and-settle on the stressed word's object: a visual beat, not a highlight."""
    return mob.animate(rate_func=rate_functions.there_and_back, run_time=run_time).scale(scale)


def erase(*mobs: Mobject, run_time: float = 0.6):
    """Rub things out (reverse-draw), the board way to remove. Gets the eraser sound automatically."""
    from manim import AnimationGroup, Uncreate
    return AnimationGroup(*[Uncreate(m, run_time=run_time) for m in mobs])


# --------------------------------------------------------------------------- sound cues
# Sound effects are tied to on-screen events: WaitwhatScene logs {t, name, gain} cues against the
# renderer clock into workspace/logs/<id>.cues.json (render.py keeps a copy next to the video) and
# stitch.py mixes them under the voice from the library in assets/sfx (several takes per sound,
# rotated so nothing repeats, thinned so it never gets busy).

#: sound names (assets/sfx/library.json); aliases: appear=pop, write=<theme's pen>, draw=pencil, erase=eraser, transition=whoosh, reveal=rise, aha=chime, money=coin, payment=register, typing=keys, error=wrong
SFX = ("pop", "tick", "click", "pencil", "chalk", "marker", "eraser", "whoosh", "swish", "rise", "chime", "shimmer", "coin", "register", "keys", "paper", "thud", "stamp", "notify", "wrong")
SFX_ALIASES = {"appear": "pop", "draw": "pencil", "erase": "eraser", "transition": "whoosh", "reveal": "rise",
               "aha": "chime", "money": "coin", "payment": "register", "typing": "keys", "code": "keys",
               "error": "wrong", "approve": "stamp", "message": "notify", "land": "thud", "move": "swish"}
#: the writing sound of this theme's medium: chalk on a chalkboard, marker on a whiteboard, else pencil
SFX_WRITE = _T.get("write", "pencil")


def _sfx_name(name: str) -> str:
    n = str(name).strip().lower()
    if n == "write":
        return SFX_WRITE
    return SFX_ALIASES.get(n, n)


def _anim_kind(anim) -> tuple[str | None, int]:
    """What an animation does, for sound: (kind, how many staggered parts)."""
    import manim as _m
    if isinstance(anim, getattr(_m, "Wait", ())):
        return None, 0
    emph = tuple(c for c in (getattr(_m, n, None) for n in (
        "Circumscribe", "Indicate", "Flash", "ShowPassingFlash", "Wiggle", "FocusOn", "ApplyWave", "Blink",
        "ShowPassingFlashWithThinningStrokeWidth")) if c)
    if emph and isinstance(anim, emph):
        return None, 0
    tm = getattr(_m, "TransformMatchingAbstractBase", None)
    if tm and isinstance(anim, tm):
        return "move", 1
    if isinstance(anim, (_m.Unwrite, _m.Uncreate)):
        return "erase", 1
    if isinstance(anim, getattr(_m, "AddTextLetterByLetter", ())):
        return "type", 1
    if isinstance(anim, _m.Write):
        return "write", 1
    if isinstance(anim, (_m.Create, _m.DrawBorderThenFill)):
        return "draw", 1
    if isinstance(anim, _m.FadeOut):
        return None, 0
    if isinstance(anim, (_m.FadeIn, _m.GrowFromPoint, getattr(_m, "SpinInFromNothing", _m.GrowFromPoint))):
        return "appear", 1
    if isinstance(anim, _m.AnimationGroup):
        kinds = [_anim_kind(a) for a in getattr(anim, "animations", [])]
        kinds = [k for k in kinds if k[0]]
        if not kinds:
            return None, 0
        order = ("erase", "write", "type", "draw", "appear", "move")
        best = min(kinds, key=lambda k: order.index(k[0]))[0]
        n = sum(k[1] for k in kinds if k[0] == best)
        lagged = getattr(anim, "lag_ratio", 0) > 0 or isinstance(anim, getattr(_m, "Succession", ()))
        return best, (n if lagged else 1)
    if isinstance(anim, (_m.Transform,)) or type(anim).__name__ in ("_MethodAnimation", "MoveAlongPath", "Rotate"):
        return "move", 1
    return None, 0


# kind -> (sound, gain dB relative to the library level, is a texture that lasts as long as the motion)
_AUTO_SFX = {"write": (None, 0.0, True), "type": ("keys", -2.0, True), "draw": (None, -4.0, True),
             "appear": ("pop", -3.0, False), "erase": ("eraser", -1.0, True)}


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
    #: log sound cues automatically for appear / write / draw / erase animations (see play(sfx=...))
    sfx_auto: bool = True

    def setup(self):
        super().setup()
        self.camera.background_color = BG
        self._sfx_cues: list[dict] = []
        self._ambient = None
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
        self._install_background()

    # ---- theme background (painted into the camera, never a mobject)
    def _scene_offset(self) -> float:
        """Approximate start of this scene in the video, so ambient motion continues across scenes."""
        t = 0.0
        for sc in load_plan(self.ws).get("scenes") or []:
            if sc.get("id") == self.scene_id:
                break
            try:
                a = json.loads((self.ws / "audio" / f"{sc['id']}.json").read_text())
                t += float(a.get("lead_in", 0.35)) + float(a.get("duration", 0)) + 0.8
            except Exception:
                t += 15.0
        return t

    def _install_background(self):
        if THEME == "classic" and not THEME_OPTS.get("backdrop"):
            return  # the house look: plain black, nothing to paint
        try:
            cam = self.camera
            seed = int(hashlib.md5(str(load_plan(self.ws).get("title", "waitwhat")).encode()).hexdigest()[:6], 16)
            bg, amb = _themes.background(THEME, cam.pixel_width, cam.pixel_height, cam.frame_width,
                                         THEME_OPTS, seed=seed)
            if bg.shape != cam.pixel_array.shape:
                return
            cam.background = bg
            cam.set_pixel_array(bg)
            if amb and THEME_OPTS.get("ambient", True) and not os.environ.get("WAITWHAT_NO_AMBIENT"):
                self._ambient = _themes.Ambient(THEME, bg, amb, config.frame_rate)
                offset, renderer = self._scene_offset(), self.renderer

                def reset(_cam=cam):
                    self._ambient.paint(_cam.pixel_array, offset + float(renderer.time))
                    return _cam

                cam.reset = reset
                # a scene updater keeps waits rendering frame by frame, so the background keeps moving
                self.add_updater(lambda dt: None)
        except Exception as e:  # a background must never break a render
            logger.warning(f"waitwhat: theme background failed ({THEME}): {e}")
            self._ambient = None

    def get_moving_and_static_mobjects(self, animations):
        moving, static = super().get_moving_and_static_mobjects(animations)
        if self._ambient is not None:
            # the background changes every frame, so nothing can be cached as a static image
            return [*static, *moving], []
        return moving, static

    # ---- sound cues
    def sfx(self, name: str, at: float | str | None = None, gain: float = 0.0, dur: float | None = None):
        """Log a sound effect at a moment of this scene: now (default), a bookmark ("reveal"),
        a word ("word:seven") or absolute seconds. gain is dB relative to the library level
        (keep within about ±4); dur stretches textures (pencil, chalk, keys, eraser) to a motion."""
        if at is None:
            t = self.now
        elif isinstance(at, str):
            t = self.mark_time(at)
        else:
            t = float(at)
        self._cue(_sfx_name(name), t, gain, dur, auto=False)

    def _cue(self, name: str, t: float, gain: float = 0.0, dur: float | None = None, auto: bool = False,
             kind: str | None = None):
        if name not in SFX:
            logger.warning(f"waitwhat: unknown sound '{name}' (known: {', '.join(SFX)})")
        c = {"t": round(max(0.0, t), 3), "name": name, "gain": round(float(gain), 2)}
        if dur:
            c["dur"] = round(float(dur), 3)
        if auto:
            c["auto"] = True
        if kind:
            c["kind"] = kind
        self._sfx_cues.append(c)

    def _auto_cues(self, anims, t0: float, t1: float):
        kinds = [_anim_kind(a) for a in anims]
        kinds = [k for k in kinds if k[0]]
        if not kinds or t1 - t0 < 0.25:
            return
        order = ("erase", "write", "type", "draw", "appear", "move")
        kind = min(kinds, key=lambda k: order.index(k[0]))[0]
        n = sum(k[1] for k in kinds if k[0] == kind)
        if kind not in _AUTO_SFX:
            return  # moves are silent unless asked for (sfx="swish")
        snd, gain, texture = _AUTO_SFX[kind]
        snd = snd or SFX_WRITE
        dur = t1 - t0
        if kind == "appear" and n >= 3:
            k = min(n, 4)
            for i in range(k):
                self._cue("tick", t0 + dur * 0.8 * i / k, gain - 1.0, auto=True, kind="appear")
            return
        self._cue(snd, t0 + 0.02, gain, min(dur, 2.5) if texture else None, auto=True, kind=kind)

    def _explicit_cues(self, spec, t0: float, t1: float):
        for item in (spec if isinstance(spec, (list, tuple)) else [spec]):
            if not item:
                continue
            gain = 0.0
            if isinstance(item, dict):
                name, where, gain = item.get("name", "pop"), item.get("at", "start"), float(item.get("gain", 0))
            else:
                name, _, where = str(item).partition("@")
                where = where or "start"
            if where == "start":
                t = t0
            elif where == "mid":
                t = (t0 + t1) / 2
            elif where == "end":
                t = t1
            else:
                try:
                    t = t0 + float(where)
                except ValueError:
                    t = self.mark_time(where)
            n = _sfx_name(name)
            dur = (t1 - t0) if n in ("pencil", "chalk", "marker", "keys", "eraser") and where == "start" else None
            self._cue(n, t, gain, min(dur, 2.5) if dur else None)

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
            elif IS_VERTICAL and y0 < SAFE_BOTTOM - 0.05:
                self._lint.append({"t": round(self.now, 2),
                                   "issue": f"in the bottom 15% of the 9:16 frame, under the phone's player UI (keep text above y={SAFE_BOTTOM:.2f})",
                                   "what": name, "box": [round(v, 2) for v in (x0, y0, x1, y1)]})
            elif IS_VERTICAL and (x0 < SAFE_LEFT - 0.1 or x1 > SAFE_RIGHT + 0.1 or y1 > SAFE_TOP + 0.1):
                self._lint.append({"t": round(self.now, 2), "issue": "outside the 9:16 safe area (thumb-safe sides / top bar)",
                                   "what": name, "box": [round(v, 2) for v in (x0, y0, x1, y1)]})
            elif "floor" in _T and y0 < FLOOR_Y - 0.05:
                self._lint.append({"t": round(self.now, 2), "issue": f"below the {THEME} scenery (keep text above y={FLOOR_Y:.2f})",
                                   "what": name, "box": [round(v, 2) for v in (x0, y0, x1, y1)]})
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
        pw, ph = SIZE_PX  # output pixels (1920x1080, or 1080x1920 in 9:16)
        px = lambda x, y: [round((x / FRAME_W + 0.5) * pw), round((0.5 - y / FRAME_H) * ph)]
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
        out.write_text(json.dumps({"scene": self.scene_id, "t": round(self.now, 2), "aspect": ASPECT,
                                   "frame_px": list(SIZE_PX), "mobjects": items}, indent=1))

    def play(self, *args, sfx=None, **kwargs):
        """Scene.play, plus sound: sfx="coin" (at the start), "chime@end", "swish@mid",
        "pop@0.4" (seconds after the start), a bookmark name ("rise@reveal"), a list of those, or
        sfx=False for silence. Without sfx, appear/write/draw/erase animations get a quiet cue."""
        t0 = self.now
        super().play(*args, **kwargs)
        t1 = self.now
        try:
            if sfx:
                self._explicit_cues(sfx, t0, t1)
            elif sfx is None and self.sfx_auto:
                self._auto_cues(args, t0, t1)
        except Exception as e:  # sound bookkeeping must never break a render
            logger.debug(f"sfx cue failed: {e}")
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
        cues = sorted(getattr(self, "_sfx_cues", []), key=lambda c: c["t"])
        (self.ws / "logs" / f"{self.scene_id}.cues.json").write_text(json.dumps(
            {"scene": self.scene_id, "theme": THEME, "write": SFX_WRITE, "duration": round(self.now, 3),
             "cues": cues}, indent=1))

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
        strokes.scale_to_fit_height(height)
        if strokes.width > FRAME_W * 0.78:  # 9:16: the wide wordmark fits the narrow frame
            strokes.scale_to_fit_width(FRAME_W * 0.78)
            height = strokes.height
        strokes.move_to(ORIGIN)
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
    wait = Text("wait", font=FONT, font_size=size, color="#FFFFFF")
    what = Text("what?", font=FONT, font_size=size, color="#FFFF00")
    return fit(VGroup(wait, what).arrange(RIGHT, buff=0.62, aligned_edge=DOWN), FRAME_W * 0.78)


class WaitwhatIntro(Scene):
    """~1.7 s opening sting: the wordmark draws itself on, like pencil on a blackboard, then clears."""

    def construct(self):
        self.camera.background_color = "#000000"
        mark = brand_wordmark(1.6)
        if mark is not None:
            self.play(LaggedStart(*[Create(s, rate_func=ease_out) for s in mark], lag_ratio=0.12), run_time=1.15)
            self.wait(0.3)
            self.play(FadeOut(mark, scale=1.03), run_time=0.25)
            return
        mark = _typeset_wordmark(84).move_to(ORIGIN)
        loop = pencil_circle(mark[1], color="#FFFF00", buff=0.28, seed=7, stroke=6)
        self.play(FadeIn(mark[0], shift=UP * 0.12, scale=0.96, rate_func=ease_out), run_time=0.35)
        self.play(FadeIn(mark[1], shift=UP * 0.12, scale=0.96, rate_func=ease_out), run_time=0.3)
        self.play(Create(loop, rate_func=ease_out), run_time=0.45)
        self.wait(0.25)
        self.play(FadeOut(VGroup(mark, loop), scale=1.03), run_time=0.25)


class WaitwhatOutro(Scene):
    """~2.4 s closing sting: the wordmark, a quiet credit line, fade to black."""

    def construct(self):
        self.camera.background_color = "#000000"
        mark = brand_wordmark(1.2)
        if mark is None:
            mark = _typeset_wordmark(64).move_to(ORIGIN)
        sub = Text("made with waitwhat", font=FONT, font_size=SIZE_SMALL, color="#777777").next_to(mark, DOWN, buff=0.6)
        self.play(FadeIn(mark, shift=UP * 0.12, scale=0.96, rate_func=ease_out), run_time=0.5)
        self.play(FadeIn(sub, rate_func=ease_out), run_time=0.5)
        self.wait(0.9)
        self.play(FadeOut(VGroup(mark, sub)), run_time=0.55)
