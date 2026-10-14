"""waitwhat 2.5D: the explainer-agency look in Manim. Flat illustrated vector art (rounded,
friendly shapes, a pastel-but-punchy palette, gentle gradients), layered in depth, seen through a
parallax camera, with soft shadows, rim highlights and snappy pop-in motion.

Loaded by waitwhat_style (scene files keep `from waitwhat_style import *`; never import this module
first, the two import each other):

    class Problem(WaitwhatScene25D):
        backdrop = "room"                                   # outdoors | city | room | office | plain
        def construct(self):
            maya = cast("maya").stand(x=-2.2)              # the same Maya in every scene
            self.play(pop_in(maya), run_time=0.5)
            phone_ = phone(screen="pay")
            self.wait_until("pay")
            self.play(maya.to_pose("phone", hold=phone_), maya.to_face("worried"))
            self.push_in(1.3, to=maya, run_time=1.4)
            self.finish()

What you get, on top of everything WaitwhatScene gives (bookmark timing, sound cues, both aspects,
the layout lint):
  * WaitwhatScene25D: a camera that draws every mobject through its depth layer (sky 0, far 0.2,
    mid 0.5, main 1, near 1.5, hud = fixed), so pan_to / push_in / dolly / drift move near layers
    faster than far ones; idle life (bob, sway, blink, pulse, spin, breathe) rendered by the camera,
    so it never fights an animation; the sky or wall painted once as the camera background
  * backdrops: outdoors (sky + hills), city, room, office, plain; palettes sunny / fresh / dusk
  * motion presets: pop_in (back-out overshoot, opacity leads), pop_out, slide_in/out, stagger,
    hop, travel, burst, ping, nudge
  * a character kit (cast("maya"), Character(...)): consistent flat people, 8 poses, 8 faces, blink
  * props: phone, laptop, desk, sofa, house, shop, bank, coin, card, cash, chart, envelope, cloud,
    tree, hill, skyline, server, gear, bulb, clock, plus icon glyphs and badges
  * text that always reads: pill(), tag(), bubble(), headline() (white cards, dark ink)
  * the 2.5D lint: shapes on screen and redrawn seconds (the render budget) in layout_issues

All code here is original to waitwhat (MIT).
"""
from __future__ import annotations

import math

import cairo
import numpy as np
from manim import (
    DL, DOWN, DR, LEFT, ORIGIN, PI, RIGHT, TAU, UL, UP, UR,
    Animation, AnimationGroup, Camera, Circle, Difference, Ellipse, FadeOut, Intersection, LaggedStart,
    ManimColor, Mobject, Polygon, RoundedRectangle, Union, VectorizedPoint, VGroup, VMobject,
    interpolate_color, logger,
)

import waitwhat_style as _ws
from waitwhat_style import (
    FRAME_H, FRAME_W, IS_VERTICAL, SAFE_BOTTOM, SAFE_CENTER, SAFE_LEFT, SAFE_RIGHT, SAFE_TOP,
    SAFE_W, SIZE_BODY, SIZE_HEAD, SIZE_LABEL, SIZE_SMALL, SIZE_TITLE, T, TYPE_SCALE, WaitwhatScene,
    by_aspect, fit,
)

__all__ = [
    "WaitwhatScene25D", "Camera25D", "Character", "Stage",
    "DEPTH", "GROUND_Y", "HORIZON_Y", "CHAR_H", "SHAPE_BUDGET", "RENDER_BUDGET_25D", "WORLD", "PAL",
    "PILL_BG", "PILL_INK", "SKIN", "HAIR", "CAST", "POSES", "FACES", "BACKDROPS",
    # colour + shape helpers
    "tint", "shade", "haze", "mix", "on_color", "rrect", "capsule", "blob", "soft_shadow", "glow",
    "rim_light", "side_shade", "extrude", "layer", "hud", "idle", "still",
    # motion
    "pop_in", "pop_out", "after", "slide_in", "slide_out", "stagger", "hop", "travel", "burst", "ping",
    "nudge", "swap", "walk", "back_out", "glide", "expo_out", "ease_io", "leave_ease",
    # characters
    "cast",
    # props + icons
    "merge", "panel", "phone", "laptop", "desk", "sofa", "house", "shop", "bank", "coin", "card", "cash", "chart",
    "envelope", "cloud", "tree", "pine", "bush", "hill", "skyline", "building", "server", "gear",
    "bulb", "clock", "plant", "lamp", "window", "icon", "badge", "route",
    # text
    "pill", "tag", "bubble", "thought", "headline", "big_number",
    # backdrops
    "backdrop",
]

# --------------------------------------------------------------------------- depth + budget

#: parallax factor per layer: how much of a camera move a layer follows (0 = fixed sky, 1 = the
#: plane the characters stand in, > 1 = foreground that sweeps past). "hud" is fixed on the screen.
DEPTH = {"sky": 0.0, "far": 0.2, "mid": 0.5, "main": 1.0, "near": 1.5, "hud": None}
_Z = {"sky": 0, "far": 10, "mid": 20, "main": 30, "near": 40, "hud": 50}
#: shapes (filled paths) on screen at once; above it every redrawn frame gets slow
SHAPE_BUDGET = 450
#: estimated seconds to render the scene; above it the lint says so (classic 2D: 2-7 s)
RENDER_BUDGET_25D = 14.0
#: where feet and props stand (top of the ground), the horizon, and a standing character's height
GROUND_Y = by_aspect(-2.45, -3.75)
HORIZON_Y = by_aspect(-0.55, -0.85)
CHAR_H = by_aspect(3.3, 5.3)
#: where the sun sits (outdoors and city backdrops); the sky's warm glow is painted around it
SUN_POS = (FRAME_W * by_aspect(0.3, 0.24), SAFE_TOP - by_aspect(1.25, 2.1))

# --------------------------------------------------------------------------- palette + world

PILL_BG = "#FFFFFF"
PILL_INK = "#1F2A44"
_SHADOW = "#2A2350"     # shadows are tinted, never black
_SHEEN = "#FFFFFF"

#: per-palette world colours (plan.theme in a 2.5D video: sunny | fresh | dusk)
WORLDS = {
    "sunny": {
        "sky": ("#8FCBF5", "#C9E9FB", "#FFF0D9"), "sun": "#FFD15C", "cloud": "#FFFFFF",
        "hill_far": "#B5DDC9", "hill_mid": "#86C99A", "ground": "#93D49C", "ground_lip": "#B4E3B3",
        "grass": "#5FAF77", "tree": "#4FAE7A", "trunk": "#9A6B4B",
        "far_city": "#B9D4EC", "bld": ("#F7C6A3", "#C8B8F0", "#9FCBF4", "#A9E2CF", "#FFD98A"),
        "glass": "#DDF1FF", "lit": "#FFE7A0", "street": "#5C6582", "walk": "#EDE5DA",
        "wall": ("#FFEBDA", "#FBD8BF"), "floor": "#E8BB91", "floor_edge": "#D9A47A", "trim": "#FFFFFF",
        "owall": ("#E8F2FB", "#D3E4F4"), "ofloor": "#C8D4E6", "plain": ("#F4F7FF", "#E2E9F9"),
    },
    "fresh": {
        "sky": ("#7FD8D0", "#C6F1EA", "#F3FBF4"), "sun": "#FFE27A", "cloud": "#FFFFFF",
        "hill_far": "#B7E6D6", "hill_mid": "#7FD0B4", "ground": "#8FDDB9", "ground_lip": "#B6EBD0",
        "grass": "#49B08F", "tree": "#3FAE8C", "trunk": "#8C6A55",
        "far_city": "#B5E2DD", "bld": ("#9FD8F5", "#B9C4F7", "#8EE0CB", "#FFC9B5", "#FFE29A"),
        "glass": "#E2F7FF", "lit": "#FFF0B0", "street": "#4F6A80", "walk": "#E6EEEA",
        "wall": ("#E6F6F2", "#D2EEE7"), "floor": "#D9C4A8", "floor_edge": "#C4AA8A", "trim": "#FFFFFF",
        "owall": ("#EAF6FB", "#D4EAF3"), "ofloor": "#C7DCE4", "plain": ("#F2FBF9", "#DDF1EC"),
    },
    "dusk": {
        "sky": ("#2E2A6E", "#7A4C9C", "#F59A7C"), "sun": "#FFC27A", "cloud": "#F6C8D6",
        "hill_far": "#6E4C93", "hill_mid": "#4E3A7E", "ground": "#3F3470", "ground_lip": "#59478C",
        "grass": "#2F2860", "tree": "#352C6A", "trunk": "#2A2350",
        "far_city": "#5A4A90", "bld": ("#4C4290", "#5E4E9E", "#3F3A80", "#6A4F96", "#544A94"),
        "glass": "#3A3672", "lit": "#FFD58A", "street": "#2B2650", "walk": "#4A4280",
        "wall": ("#4A3F86", "#3A3274"), "floor": "#6B4E7E", "floor_edge": "#553E68", "trim": "#E6DDF5",
        "owall": ("#3C3A7E", "#2F2E68"), "ofloor": "#4A4682", "plain": ("#3A3478", "#2A2660"),
    },
}
WORLD_NAME = _ws.THEME if _ws.THEME in WORLDS else "sunny"
WORLD = WORLDS[WORLD_NAME]
IS_DUSK = WORLD_NAME == "dusk"

#: concept colours by name (the video's palette): these are fills; text sits on pills in PILL_INK
PAL = {k: _ws.NAMED[k] for k in ("BLUE", "TEAL", "GREEN", "GOLD", "ORANGE", "RED", "PINK", "PURPLE",
                                  "MAROON", "YELLOW", "YELLOW_SOFT")}


def _c(color) -> str:
    """Palette names ("BLUE"), concept names (color_of) or hex → hex."""
    if isinstance(color, ManimColor):
        return color.to_hex()
    if isinstance(color, str) and not color.startswith("#"):
        u = color.upper()
        if u in _ws.NAMED:
            return _ws.NAMED[u]
        if u in ("INK", "INK_2", "INK_3", "INK_4"):
            return getattr(_ws, u)
        if u in ("WHITE",):
            return "#FFFFFF"
        return _ws.color_of(color)
    return str(color)


def mix(a, b, k: float) -> str:
    return interpolate_color(ManimColor(_c(a)), ManimColor(_c(b)), float(k)).to_hex()


def tint(color, k: float = 0.35) -> str:
    """A lighter cousin (highlights, rims, pastel versions)."""
    return mix(color, "#FFFFFF", k)


def shade(color, k: float = 0.22) -> str:
    """A darker, cooler cousin (side faces, shadows): mixed toward deep violet, never grey."""
    return mix(color, _SHADOW, k)


def haze(color, k: float = 0.45) -> str:
    """Atmospheric fade toward the horizon colour: far things are paler and bluer."""
    return mix(color, WORLD["sky"][2] if not IS_DUSK else WORLD["sky"][1], k)


def _lum(hex_: str) -> float:
    h = _c(hex_).lstrip("#")
    c = np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])


def on_color(fill) -> str:
    """Text colour that reads on a fill: PILL_INK on light fills, white on dark ones."""
    lf = _lum(fill)
    dark = (lf + 0.05) / (_lum(PILL_INK) + 0.05)
    light = (1.05) / (lf + 0.05)
    return PILL_INK if dark >= light else "#FFFFFF"


# --------------------------------------------------------------------------- easing
# Steep start, long tail (the handcrafted-motion curves), plus a back-out with a small overshoot
# for pops. All take t in 0..1.

def _bezier(x1, y1, x2, y2):
    def f(t: float) -> float:
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0
        u = t
        for _ in range(8):  # Newton on x(u) = t
            x = 3 * (1 - u) ** 2 * u * x1 + 3 * (1 - u) * u * u * x2 + u ** 3 - t
            dx = 3 * (1 - u) ** 2 * x1 + 6 * (1 - u) * u * (x2 - x1) + 3 * u * u * (1 - x2)
            if abs(dx) < 1e-6:
                break
            u = min(1.0, max(0.0, u - x / dx))
        return 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u * u * y2 + u ** 3
    return f


glide = _bezier(0.22, 1, 0.36, 1)          # easeOutQuint: the default arrival
leave_ease = _bezier(0.4, 0, 1, 1)         # quick exits of things being replaced
ease_io = _bezier(0.65, 0, 0.35, 1)        # camera moves: gentle start, gentle landing


def expo_out(t: float) -> float:
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def back_out(t: float, overshoot: float = 1.25) -> float:
    """Ease-out that passes the target by a few percent and settles (1.25 ≈ 6 % overshoot)."""
    c1, c3 = overshoot, overshoot + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


# --------------------------------------------------------------------------- tagging

def layer(mob: Mobject, name: str = "main", depth: float | None = None) -> Mobject:
    """Put a mobject in a depth layer (sky, far, mid, main, near, hud) or at an explicit depth.
    Untagged mobjects are in "main". Tags travel with the mobject (and its copies)."""
    if name not in _Z:
        raise ValueError(f"unknown layer '{name}' (one of {', '.join(_Z)})")
    d = DEPTH[name] if depth is None else float(depth)
    mob.ww_depth = d if name != "hud" else None
    mob.ww_layer = name
    z = _Z[name] if depth is None or name == "hud" else int(round(10 + 25 * float(depth)))
    mob.ww_z = z
    mob.set_z_index(z, family=True)
    return mob


def hud(mob: Mobject) -> Mobject:
    """Fixed on the screen (titles, captions, counters): ignores the camera."""
    return layer(mob, "hud")


_FX_DEFAULT = {"bob": (0.06, 3.2), "sway": (0.05, 3.8), "blink": (0.12, 3.6), "pulse": (0.35, 1.6),
               "spin": (1.0, 6.0), "breathe": (0.012, 3.4), "drift": (0.25, 9.0), "float": (0.08, 4.0),
               "flicker": (0.5, 0.9)}
_FX_N = [0]


def idle(mob: Mobject, kind: str = "bob", amp: float | None = None, period: float | None = None,
         phase: float | None = None) -> Mobject:
    """Subtle life drawn by the camera, so it never fights an animation and costs no updater:
    bob (up-down, units), float (bob + a little tilt), drift (side to side), sway (rotation about
    the base, radians), breathe (vertical scale about the base), blink (eyes), pulse (opacity dip),
    flicker (on/off-ish opacity, screens), spin (turns per period). Several kinds stack."""
    a0, p0 = _FX_DEFAULT[kind]
    _FX_N[0] += 1
    ph = phase if phase is not None else (_FX_N[0] * 2.399963) % TAU
    fx = list(getattr(mob, "ww_fx", []) or [])
    fx = [f for f in fx if f[0] != kind] + [(kind, a0 if amp is None else amp, p0 if period is None else period, ph)]
    mob.ww_fx = fx
    return mob


def still(mob: Mobject, kind: str | None = None) -> Mobject:
    """Remove idle life (all of it, or one kind)."""
    fx = getattr(mob, "ww_fx", None) or []
    mob.ww_fx = [f for f in fx if kind is not None and f[0] != kind]
    return mob


# --------------------------------------------------------------------------- the camera

_ID = np.eye(2)


def _fx_affine(fx, t: float, pts: np.ndarray):
    """Affine (A, b) and alpha multiplier of a member's idle effects at time t."""
    A = _ID.copy()
    b = np.zeros(2)
    alpha = 1.0
    if len(pts) == 0:
        return A, b, alpha
    lo, hi = pts[:, :2].min(axis=0), pts[:, :2].max(axis=0)
    base = np.array([(lo[0] + hi[0]) / 2, lo[1]])
    mid = (lo + hi) / 2
    for kind, amp, period, ph in fx:
        w = TAU * t / max(period, 1e-3) + ph
        if kind == "bob":
            b = b + [0, amp * math.sin(w)]
        elif kind == "drift":
            b = b + [amp * math.sin(w), 0.3 * amp * math.sin(2 * w)]
        elif kind in ("sway", "float"):
            ang = (amp if kind == "sway" else amp * 0.6) * math.sin(w)
            if kind == "float":
                b = b + [0, amp * math.sin(w)]
                ang = 0.04 * math.sin(w * 0.7)
            c, s = math.cos(ang), math.sin(ang)
            R = np.array([[c, -s], [s, c]])
            piv = base if kind == "sway" else mid
            A, b = R @ A, R @ (b - piv) + piv
        elif kind == "spin":
            ang = -TAU * amp * t / max(period, 1e-3) + ph
            c, s = math.cos(ang), math.sin(ang)
            R = np.array([[c, -s], [s, c]])
            A, b = R @ A, R @ (b - mid) + mid
        elif kind == "breathe":
            k = 1 + amp * math.sin(w)
            S = np.array([[1.0, 0.0], [0.0, k]])
            A, b = S @ A, S @ (b - base) + base
        elif kind == "blink":
            # a quick close-open about every `period` seconds, jittered so two characters differ
            u = ((t + ph) % period) / period
            dur = amp / period
            k = 1.0
            if u < dur:
                k = 0.08 + 0.92 * abs(math.cos(PI * u / dur))
            S = np.array([[1.0, 0.0], [0.0, k]])
            A, b = S @ A, S @ (b - mid) + mid
        elif kind == "pulse":
            alpha *= 1 - amp * (0.5 + 0.5 * math.sin(w))
        elif kind == "flicker":
            alpha *= 1 - amp * (0.5 + 0.5 * math.sin(w)) * (0.6 + 0.4 * math.sin(3.7 * w))
    return A, b, alpha


class Camera25D(Camera):
    """Cairo camera that draws each mobject through its depth layer and its idle effects.

    The rig is (x, y, zoom) in the main plane: the point (x, y) is shown at the screen's focus
    (SAFE_CENTER) and a layer at depth d is scaled by zoom**d and follows d of every pan."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.focus = np.array([float(SAFE_CENTER[0]), float(SAFE_CENTER[1])])
        self.rig = None            # a Mobject whose points[0] holds (x, y, zoom); set by the scene
        self.shake = np.zeros(2)
        self.clock = lambda: 0.0
        self.roots = lambda: []
        self._xf: dict = {}
        self._stamp = None

    def state(self):
        if self.rig is None:
            return self.focus[0], self.focus[1], 1.0
        x, y, z = self.rig.points[0]
        return float(x), float(y), max(0.05, float(z))

    def layer_affine(self, d):
        if d is None:
            return _ID, np.zeros(2)
        x, y, z = self.state()
        s = z ** d
        F = self.focus
        c = np.array([x, y])
        # screen = F + s * (p - F - d * (c - F)) + shake
        return _ID * s, F - s * (F + d * (c - F)) + self.shake * min(d, 1.5)

    def prepare(self):
        """Per frame: every member's affine (layer camera ∘ idle effects) and alpha multiplier."""
        t = float(self.clock())
        self._xf = {}
        xf = self._xf

        def walk(m, d, A, b, alpha, fx_on):
            if hasattr(m, "ww_depth"):
                d = m.ww_depth
                A, b = self.layer_affine(d)
            fx = getattr(m, "ww_fx", None)
            if fx:
                pts = m.get_all_points()
                FA, Fb, fa = _fx_affine(fx, t, pts)
                A, b = A @ FA, A @ Fb + b
                alpha *= fa
                fx_on = True
            xf[id(m)] = (A, b, alpha, d)
            for s in m.submobjects:
                walk(s, d, A, b, alpha, fx_on)

        A0, b0 = self.layer_affine(1.0)
        for m in self.roots():
            walk(m, 1.0, A0, b0, 1.0, False)

    def _get(self, m):
        r = self._xf.get(id(m))
        if r is None:
            d = getattr(m, "ww_depth", 1.0)
            A, b = self.layer_affine(d)
            r = (A, b, 1.0, d)
        return r

    def capture_mobjects(self, mobjects, **kwargs):
        self.prepare()
        super().capture_mobjects(mobjects, **kwargs)

    def transform_points_pre_display(self, mobject, points):
        points = np.asarray(super().transform_points_pre_display(mobject, points), dtype=float)
        A, b, _, _ = self._get(mobject)
        if A is _ID and not b.any():
            return points
        out = np.array(points, dtype=float, copy=True)
        out[:, :2] = points[:, :2] @ A.T + b
        return out

    def get_fill_rgbas(self, vmobject):
        r = vmobject.get_fill_rgbas()
        a = self._get(vmobject)[2]
        if a != 1.0:
            r = r.copy()
            r[:, 3] *= a
        return r

    def get_stroke_rgbas(self, vmobject, background: bool = False):
        r = vmobject.get_stroke_rgbas(background)
        a = self._get(vmobject)[2]
        if a != 1.0:
            r = r.copy()
            r[:, 3] *= a
        return r

    def apply_fill(self, ctx, vmobject):
        rad = getattr(vmobject, "ww_radial", None)
        if not rad:
            return super().apply_fill(ctx, vmobject)
        pts = self.transform_points_pre_display(vmobject, vmobject.points)
        if len(pts) == 0:
            return self
        lo, hi = pts[:, :2].min(axis=0), pts[:, :2].max(axis=0)
        cx, cy = (lo + hi) / 2
        rx, ry = max((hi[0] - lo[0]) / 2, 1e-4), max((hi[1] - lo[1]) / 2, 1e-4)
        pat = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
        a = self._get(vmobject)[2]
        for off, col, op in rad:
            h = col.lstrip("#")
            r, g, bb = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
            # cairo surfaces store BGR(A): same reversal as Camera.set_cairo_context_color
            pat.add_color_stop_rgba(off, bb, g, r, op * a)
        pat.set_matrix(cairo.Matrix(1 / rx, 0, 0, 1 / ry, -cx / rx, -cy / ry))
        ctx.set_source(pat)
        ctx.fill_preserve()
        return self

    def apply_stroke(self, ctx, vmobject, background: bool = False):
        width = vmobject.get_stroke_width(background)
        if width == 0:
            return self
        A = self._get(vmobject)[0]
        k = math.sqrt(abs(np.linalg.det(A))) if A is not _ID else 1.0
        self.set_cairo_context_color(ctx, self.get_stroke_rgbas(vmobject, background=background), vmobject)
        ctx.set_line_width(width * self.cairo_line_width_multiple * k)
        from manim.camera.camera import CAP_STYLE_MAP, LINE_JOIN_MAP
        ctx.set_line_join(LINE_JOIN_MAP[vmobject.joint_type])
        ctx.set_line_cap(CAP_STYLE_MAP[vmobject.cap_style])
        ctx.stroke_preserve()
        return self

    def screen_box(self, m):
        """(x0, y0, x1, y1) of a mobject on screen now (frame units)."""
        self.prepare()
        boxes = []
        for f in m.family_members_with_points():
            A, b, _, _ = self._get(f)
            P = f.points[:, :2] @ A.T + b
            boxes.append((P.min(axis=0), P.max(axis=0)))
        if not boxes:
            c = m.get_center()
            return float(c[0]), float(c[1]), float(c[0]), float(c[1])
        lo = np.min([b[0] for b in boxes], axis=0)
        hi = np.max([b[1] for b in boxes], axis=0)
        return float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])


class _Rig(Mobject):
    """The camera's state (x, y, zoom) as a mobject, so camera moves are ordinary animations."""

    def __init__(self, x: float, y: float, z: float = 1.0, **kw):
        super().__init__(**kw)
        self.points = np.array([[x, y, z]], dtype=float)

    def interpolate_color(self, mobject1, mobject2, alpha):  # no colour: a camera state
        return self


class _CamMove(Animation):
    ww_cam = True

    def __init__(self, rig: _Rig, to, run_time: float = 1.4, ease=None, **kw):
        self.to = np.array(to, dtype=float)
        self.ease = ease or ease_io
        super().__init__(rig, run_time=run_time, **kw)

    def begin(self):
        self.start = np.array(self.mobject.points[0], dtype=float)
        super().begin()

    def interpolate_mobject(self, alpha: float) -> None:
        a = self.ease(_clamp01(alpha))
        s, e = self.start, self.to
        x = s[0] + (e[0] - s[0]) * a
        y = s[1] + (e[1] - s[1]) * a
        # zoom in log space: a push-in feels even
        z = math.exp(math.log(s[2]) + (math.log(e[2]) - math.log(s[2])) * a)
        self.mobject.points[0] = [x, y, z]


# --------------------------------------------------------------------------- motion presets

class _Morph(Animation):
    """Scale / offset / rotate / fade a mobject relative to its current (final) state, about an
    anchor. The family keeps its own colours: only alpha is multiplied."""

    ww_kind: str | None = None

    def __init__(self, mob, fn, anchor="center", introducer: bool = False, remover: bool = False,
                 kind: str | None = None, **kw):
        self.fn = fn
        self.anchor_kind = anchor
        if kind:
            self.ww_kind = kind
        kw.setdefault("rate_func", lambda t: t)
        super().__init__(mob, introducer=introducer, remover=remover, **kw)

    def begin(self):
        m = self.mobject
        a = self.anchor_kind
        if isinstance(a, str):
            self._anchor = {"center": m.get_center(), "bottom": m.get_bottom(), "top": m.get_top(),
                            "left": m.get_left(), "right": m.get_right()}[a]
        else:
            self._anchor = np.array(a, dtype=float)
        super().begin()

    def interpolate_mobject(self, alpha: float) -> None:
        sx, sy, off, rot, op = self.fn(_clamp01(alpha))
        c = self._anchor
        cs, sn = math.cos(rot), math.sin(rot)
        for m, s in zip(self.mobject.family_members_with_points(), self.starting_mobject.family_members_with_points()):
            p = s.points - c
            x, y = p[:, 0] * sx, p[:, 1] * sy
            q = np.empty_like(s.points)
            q[:, 0] = c[0] + x * cs - y * sn + off[0]
            q[:, 1] = c[1] + x * sn + y * cs + off[1]
            q[:, 2] = s.points[:, 2]
            m.points = q
            if hasattr(m, "fill_rgbas") and hasattr(s, "fill_rgbas"):
                if m.fill_rgbas.shape == s.fill_rgbas.shape:
                    m.fill_rgbas[:, 3] = s.fill_rgbas[:, 3] * op
                if m.stroke_rgbas.shape == s.stroke_rgbas.shape:
                    m.stroke_rgbas[:, 3] = s.stroke_rgbas[:, 3] * op
                bs = getattr(m, "background_stroke_rgbas", None)
                if bs is not None and bs.shape == s.background_stroke_rgbas.shape:
                    m.background_stroke_rgbas[:, 3] = s.background_stroke_rgbas[:, 3] * op

    def clean_up_from_scene(self, scene):
        super().clean_up_from_scene(scene)
        if self.remover:  # leave the mobject as it was, so it can be shown again later
            for m, s in zip(self.mobject.family_members_with_points(), self.starting_mobject.family_members_with_points()):
                m.points = s.points.copy()
                if hasattr(m, "fill_rgbas") and m.fill_rgbas.shape == s.fill_rgbas.shape:
                    m.fill_rgbas[:, 3] = s.fill_rgbas[:, 3]
                    m.stroke_rgbas[:, 3] = s.stroke_rgbas[:, 3]


def _group(mobs):
    return mobs[0] if len(mobs) == 1 else None


def _stag(anims, gap: float):
    if len(anims) == 1:
        return anims[0]
    rt = max(a.run_time for a in anims)
    return LaggedStart(*anims, lag_ratio=min(1.0, gap / max(rt, 1e-3)), run_time=rt + gap * (len(anims) - 1))


def pop_in(*mobs, run_time: float = 0.5, overshoot: float = 1.25, start: float = 0.25, anchor="bottom",
           gap: float = 0.07, rise: float = 0.0):
    """Pop in from small with a small overshoot (back-out); opacity leads, so it reads at once.
    anchor="bottom" grows things that stand on something from their base; "center" for floating
    things (icons, bubbles, coins). Several mobjects: staggered by `gap` seconds."""
    def fn(t):
        s = start + (1 - start) * back_out(t, overshoot)
        o = glide(_clamp01(t / 0.4))
        return s, s, (0.0, -rise * (1 - glide(t))), 0.0, o
    anims = [_Morph(m, fn, anchor=anchor, introducer=True, kind="appear", run_time=run_time) for m in mobs]
    return _stag(anims, gap)


def pop_out(*mobs, run_time: float = 0.28, to: float = 0.6, anchor="center", gap: float = 0.04):
    """Exit: shrink a little and fade, quicker than the entrance."""
    def fn(t):
        e = leave_ease(t)
        s = 1 + (to - 1) * e
        return s, s, (0.0, 0.0), 0.0, 1 - _clamp01(t / 0.85)
    anims = [_Morph(m, fn, anchor=anchor, remover=True, run_time=run_time) for m in mobs]
    return _stag(anims, gap)


def slide_in(*mobs, frm=LEFT, distance: float = 1.2, run_time: float = 0.55, gap: float = 0.07,
             scale: float = 0.96):
    """Slide in from a side (frm=LEFT means it arrives from the left) on the glide curve."""
    d = np.array(frm, dtype=float)[:2] * distance

    def fn(t):
        e = glide(t)
        s = scale + (1 - scale) * e
        return s, s, (d[0] * (1 - e), d[1] * (1 - e)), 0.0, glide(_clamp01(t / 0.45))
    anims = [_Morph(m, fn, anchor="center", introducer=True, kind="slide", run_time=run_time) for m in mobs]
    return _stag(anims, gap)


def slide_out(*mobs, to=RIGHT, distance: float = 1.0, run_time: float = 0.32, gap: float = 0.04):
    d = np.array(to, dtype=float)[:2] * distance

    def fn(t):
        e = leave_ease(t)
        return 1.0, 1.0, (d[0] * e, d[1] * e), 0.0, 1 - _clamp01(t / 0.9)
    anims = [_Morph(m, fn, anchor="center", remover=True, run_time=run_time) for m in mobs]
    return _stag(anims, gap)


def stagger(*anims, gap: float = 0.08):
    """Start animations one after another, `gap` seconds apart (a beat every few frames)."""
    return _stag(list(anims), gap)


def after(delay: float, anim):
    """Start an animation `delay` seconds into a play (to time a pop to the moment a camera move
    brings its object into view: pan_to(..., added_anims=[after(0.8, pop_in(sign))]))."""
    from manim import Succession, Wait
    return Succession(Wait(run_time=delay), anim)


def nudge(mob, scale: float = 1.1, run_time: float = 0.4):
    """A quick swell-and-settle on the stressed word's object (the 2.5D beat)."""
    def fn(t):
        k = math.sin(PI * min(1.0, t * 1.15)) * (1 - t) ** 0.5
        s = 1 + (scale - 1) * k
        return s, s, (0.0, 0.0), 0.0, 1.0
    return _Morph(mob, fn, anchor="bottom" if mob.height > 0.6 else "center", run_time=run_time)


def hop(mob, height: float = 0.5, run_time: float = 0.55, times: int = 1):
    """Jump with squash and stretch (a character's joy, a box landing)."""
    def fn(t):
        n = times
        u = (t * n) % 1.0 if t < 1 else 1.0
        y = height * 4 * u * (1 - u)
        squash = 1.0
        if u < 0.12:
            squash = 1 - 0.12 * math.sin(PI * u / 0.12)
        elif u > 0.88:
            squash = 1 - 0.1 * math.sin(PI * (u - 0.88) / 0.12)
        stretch = 1 + 0.06 * math.sin(PI * u) if 0.12 <= u <= 0.88 else 1.0
        return 2 - squash if u < 0.12 or u > 0.88 else 1 / stretch, squash * stretch, (0.0, y), 0.0, 1.0
    return _Morph(mob, fn, anchor="bottom", run_time=run_time)


def travel(mob, to, arc: float = 0.8, run_time: float = 1.0, spin: float = 0.0, ease=None):
    """Fly from where it is to `to` (a point or mobject) along an arc: a payment, a message, a
    parcel. arc = height of the curve (negative dips); spin = turns along the way."""
    end = to.get_center() if isinstance(to, Mobject) else np.array(to, dtype=float)
    start = mob.get_center().copy()
    e_ = ease or ease_io

    def fn(t):
        e = e_(t)
        p = start + (end - start) * e
        p = p + np.array([0, arc * 4 * e * (1 - e), 0])
        off = p - start
        return 1.0, 1.0, (off[0], off[1]), -TAU * spin * e, 1.0
    return _Morph(mob, fn, anchor="center", run_time=run_time, kind="move")


def walk(char, to_x: float, run_time: float = 1.2, step: float = 0.07):
    """Walk sideways to x with a step bounce (characters)."""
    start = char.get_center()[0]
    n = max(2, int(abs(to_x - start) / 0.55))

    def fn(t):
        e = ease_io(t)
        dx = (to_x - start) * e
        y = step * abs(math.sin(PI * n * t))
        tilt = 0.025 * math.sin(TAU * n * t / 2) * (1 - abs(2 * t - 1))
        return 1.0, 1.0, (dx, y), tilt, 1.0
    return _Morph(char, fn, anchor="bottom", run_time=run_time, kind="move")


def swap(old, new, run_time: float = 0.45):
    """Replace one thing with another in place: the old pops out as the new pops in."""
    new.move_to(old.get_center())
    return AnimationGroup(pop_out(old, run_time=run_time * 0.55), pop_in(new, run_time=run_time, anchor="center"),
                          lag_ratio=0.25)


class _Burst(Animation):
    def __init__(self, group, center, rng, run_time=0.9, spread=1.6, gravity=3.2, **kw):
        self.center = np.array(center, dtype=float)
        n = len(group.submobjects)
        ang = rng.uniform(0, TAU, n)
        sp = rng.uniform(0.55, 1.0, n) * spread
        self.vel = np.stack([np.cos(ang) * sp, np.abs(np.sin(ang)) * sp * 1.25 + 0.6, np.zeros(n)], axis=1)
        self.spin = rng.uniform(-2.5, 2.5, n)
        self.g = gravity
        super().__init__(group, run_time=run_time, remover=True, introducer=True, **kw)
        self.ww_kind = "burst"

    def interpolate_mobject(self, alpha):
        t = alpha * self.run_time
        for i, (m, s) in enumerate(zip(self.mobject.submobjects, self.starting_mobject.submobjects)):
            p = self.vel[i] * t + np.array([0, -0.5 * self.g * t * t, 0])
            c = s.get_center()
            m.points = s.points + (self.center + p - c)
            m.rotate(self.spin[i] * t)
            o = 1 - _clamp01((alpha - 0.55) / 0.45)
            m.set_fill(opacity=o * 0.95)


def burst(at, n: int = 14, colors=("YELLOW", "PINK", "BLUE", "GREEN", "ORANGE"), run_time: float = 0.9,
          spread: float = 1.6, size: float = 0.12, seed: int = 4):
    """Confetti: little shapes fly out of a point and fall (success, a celebration, a reveal)."""
    rng = np.random.default_rng(seed)
    center = at.get_center() if isinstance(at, Mobject) else np.array(at, dtype=float)
    bits = VGroup()
    for i in range(n):
        col = _c(colors[i % len(colors)])
        if i % 3 == 0:
            b = Circle(size * 0.55, stroke_width=0, fill_color=col, fill_opacity=0.95)
        elif i % 3 == 1:
            b = RoundedRectangle(corner_radius=size * 0.2, width=size * 1.6, height=size * 0.7,
                                 stroke_width=0, fill_color=col, fill_opacity=0.95)
        else:
            b = Polygon([0, size, 0], [-size * 0.85, -size * 0.55, 0], [size * 0.85, -size * 0.55, 0],
                        stroke_width=0, fill_color=col, fill_opacity=0.95)
        bits.add(b.move_to(center))
    layer(bits, "main")
    return _Burst(bits, center, rng, run_time=run_time, spread=spread)


def ping(target, color="YELLOW", run_time: float = 0.8, rings: int = 2):
    """Attention: soft rings swell out of a thing and fade (the 2.5D 'look here')."""
    c = target.get_center() if isinstance(target, Mobject) else np.array(target, dtype=float)
    r0 = (max(target.width, target.height) / 2 + 0.15) if isinstance(target, Mobject) else 0.4
    ring_list = []
    for i in range(rings):
        ring = Circle(r0, stroke_color=_c(color), stroke_width=7, fill_opacity=0).move_to(c)
        layer(ring, getattr(target, "ww_layer", "main") if isinstance(target, Mobject) else "main")

        def fn(t, i=i):
            e = expo_out(t)
            s = 1 + 0.55 * e
            return s, s, (0.0, 0.0), 0.0, (1 - t) ** 1.5
        ring_list.append(_Morph(ring, fn, anchor="center", introducer=True, remover=True, run_time=run_time))
    return _stag(ring_list, 0.18)


# --------------------------------------------------------------------------- shapes

def _ccw(m: VMobject) -> VMobject:
    """Counter-clockwise outline: boolean ops use the non-zero winding rule, so a clockwise
    polygon unioned with a circle would leave a hole where they overlap."""
    try:
        a = m.get_anchors()[:, :2]
        if len(a) > 2:
            area = 0.5 * float(np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1]))
            if area < 0:
                m.reverse_direction()
    except Exception:
        pass
    return m


def _U(*ms):
    return Union(*[_ccw(m) for m in ms])


def _D(a, b):
    return Difference(_ccw(a), _ccw(b))


def _I(a, b):
    return Intersection(_ccw(a), _ccw(b))


def _filled(m: VMobject, color, opacity: float = 1.0) -> VMobject:
    m.set_fill(_c(color), opacity=opacity)
    m.set_stroke(width=0)
    return m


def rrect(w: float, h: float, r: float | None = None, color="#FFFFFF", opacity: float = 1.0, at=ORIGIN) -> VMobject:
    """Filled rounded rectangle (r defaults to a friendly 18 % of the short side)."""
    r = min(w, h) * 0.18 if r is None else min(r, w / 2 - 1e-3, h / 2 - 1e-3)
    if r <= 0.005:
        from manim import Rectangle
        m = Rectangle(width=w, height=h)
    else:
        m = RoundedRectangle(corner_radius=r, width=w, height=h)
    return _filled(m, color, opacity).move_to(at)


def capsule(p0, p1, r0: float, r1: float | None = None, color="#FFFFFF", n: int = 10) -> VMobject:
    """A rounded limb from p0 to p1 (radius r0 → r1): arms, legs, strokes of icons. Fixed point
    count, so two capsules always interpolate cleanly."""
    m = VMobject()
    m.set_points_as_corners(_capsule_pts(p0, p1, r0, r1 if r1 is not None else r0, n))
    return _filled(m, color)


def _capsule_pts(p0, p1, r0, r1, n=10):
    p0 = np.array(p0, dtype=float)[:2]
    p1 = np.array(p1, dtype=float)[:2]
    d = p1 - p0
    L = float(np.hypot(*d)) or 1e-4
    ang = math.atan2(d[1], d[0])
    pts = []
    for i in range(n + 1):  # cap at p1: from +90° to -90°
        a = ang + PI / 2 - PI * i / n
        pts.append(p1 + r1 * np.array([math.cos(a), math.sin(a)]))
    for i in range(n + 1):  # cap at p0: from -90° to -270°
        a = ang - PI / 2 - PI * i / n
        pts.append(p0 + r0 * np.array([math.cos(a), math.sin(a)]))
    pts.append(pts[0])
    out = np.zeros((len(pts), 3))
    out[:, :2] = pts
    return out


def blob(points, color="#FFFFFF", opacity: float = 1.0) -> VMobject:
    """A smooth closed shape through points (organic shapes: bushes, hair, puddles)."""
    pts = [np.array([p[0], p[1], 0.0]) for p in points]
    m = VMobject()
    m.set_points_smoothly([*pts, pts[0]])
    return _filled(m, color, opacity)


def soft_shadow(width: float = 1.6, height: float | None = None, opacity: float = 0.22, at=ORIGIN,
                color=_SHADOW) -> VMobject:
    """A blurred-looking contact shadow (radial gradient, one shape). Put it under feet and props."""
    h = height if height is not None else width * 0.16
    e = Ellipse(width=width, height=h)
    _filled(e, color, opacity)
    e.ww_radial = [(0.0, _c(color), opacity), (0.55, _c(color), opacity * 0.6), (1.0, _c(color), 0.0)]
    return e.move_to(at)


def glow(radius: float = 1.0, color="YELLOW", opacity: float = 0.5, at=ORIGIN) -> VMobject:
    """A soft radial glow (sun halo, a lit bulb, a screen, a highlight behind the key object)."""
    e = Circle(radius)
    _filled(e, color, opacity)
    e.ww_radial = [(0.0, _c(color), opacity), (0.45, _c(color), opacity * 0.45), (1.0, _c(color), 0.0)]
    return e.move_to(at)


def _offset_diff(shape: VMobject, by, color, opacity: float = 1.0) -> VMobject | None:
    try:
        d = _D(shape, shape.copy().shift(np.array([by[0], by[1], 0])))
        _filled(d, color, opacity)
        return d
    except Exception as e:  # boolean ops can fail on degenerate shapes; the look degrades gracefully
        logger.debug(f"25d: boolean op failed: {e}")
        return None


def rim_light(shape: VMobject, color=None, amount: float = 0.09, opacity: float = 1.0) -> VMobject | None:
    """The light rim on the upper-left edge of a shape (light comes from the upper left)."""
    base = color or tint(shape.get_fill_color().to_hex(), 0.35)
    return _offset_diff(shape, (amount, -amount), base, opacity)


def side_shade(shape: VMobject, color=None, amount: float = 0.18, opacity: float = 1.0) -> VMobject | None:
    """The shaded band on the right side of a shape (the side away from the light)."""
    base = color or shade(shape.get_fill_color().to_hex(), 0.18)
    return _offset_diff(shape, (-amount, amount * 0.25), base, opacity)


def extrude(front: VMobject, depth=(0.28, 0.16), side_color=None, top_color=None) -> VGroup:
    """2.5D box: a front face plus a darker side face (right) and a lighter top face, so flat
    buildings, boxes and screens read as objects with thickness. Returns VGroup(side, top, front)."""
    x0, y0 = front.get_corner(DL)[:2]
    x1, y1 = front.get_corner(UR)[:2]
    dx, dy = depth
    col = front.get_fill_color().to_hex()
    side = _filled(Polygon([x1, y0, 0], [x1 + dx, y0 + dy, 0], [x1 + dx, y1 + dy, 0], [x1, y1, 0]),
                   side_color or shade(col, 0.25))
    top = _filled(Polygon([x0, y1, 0], [x1, y1, 0], [x1 + dx, y1 + dy, 0], [x0 + dx, y1 + dy, 0]),
                  top_color or tint(col, 0.25))
    return VGroup(side, top, front)


# --------------------------------------------------------------------------- icons

def _poly(pts, color):
    return _filled(Polygon(*[np.array([p[0], p[1], 0.0]) for p in pts]), color)


def icon(name: str, size: float = 0.6, color="#FFFFFF") -> VGroup:
    """Simple filled glyphs: check, cross, heart, star, lock, pin, bell, chat, user, bolt, cart,
    search, arrow, plus, dollar, wifi, shield, home, globe. size = its height."""
    c = _c(color)
    s = size
    g = VGroup()
    w = s * 0.13
    if name == "check":
        g.add(capsule([-0.32 * s, 0.0], [-0.08 * s, -0.25 * s], w, color=c),
              capsule([-0.08 * s, -0.25 * s], [0.36 * s, 0.28 * s], w, color=c))
    elif name == "cross":
        g.add(capsule([-0.3 * s, -0.3 * s], [0.3 * s, 0.3 * s], w, color=c),
              capsule([-0.3 * s, 0.3 * s], [0.3 * s, -0.3 * s], w, color=c))
    elif name == "plus":
        g.add(capsule([-0.32 * s, 0], [0.32 * s, 0], w, color=c), capsule([0, -0.32 * s], [0, 0.32 * s], w, color=c))
    elif name == "heart":
        ts = np.linspace(0, TAU, 48, endpoint=False)
        pts = [np.array([16 * math.sin(t) ** 3, 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t), 0]) for t in ts]
        h = VMobject()
        h.set_points_smoothly([*pts, pts[0]])
        h.scale_to_fit_height(s * 0.9)
        g.add(_filled(h, c))
    elif name == "star":
        from manim import Star
        st = Star(5, outer_radius=s * 0.52, inner_radius=s * 0.24).round_corners(s * 0.06)
        g.add(_filled(st, c))
    elif name == "lock":
        body = rrect(s * 0.72, s * 0.52, s * 0.1, c).move_to([0, -s * 0.2, 0])
        sh = _D(RoundedRectangle(corner_radius=s * 0.24, width=s * 0.52, height=s * 0.62),
                        RoundedRectangle(corner_radius=s * 0.15, width=s * 0.3, height=s * 0.42))
        sh.move_to([0, s * 0.2, 0])
        hole = _filled(Circle(s * 0.07), shade(c, 0.6)).move_to(body)
        g.add(_filled(sh, c), body, hole)
    elif name == "pin":
        r = s * 0.3
        p = _U(Circle(r).move_to([0, s * 0.18, 0]), Polygon([-r * 0.92, s * 0.06, 0], [r * 0.92, s * 0.06, 0], [0, -s * 0.5, 0]))
        p = _D(p, Circle(r * 0.42).move_to([0, s * 0.18, 0]))
        g.add(_filled(p, c))
    elif name == "bell":
        b = _U(Circle(s * 0.28).move_to([0, s * 0.08, 0]),
                  Polygon([-s * 0.28, s * 0.08, 0], [s * 0.28, s * 0.08, 0], [s * 0.38, -s * 0.28, 0], [-s * 0.38, -s * 0.28, 0]))
        g.add(_filled(b, c), _filled(Circle(s * 0.09), c).move_to([0, -s * 0.38, 0]),
              _filled(Circle(s * 0.06), c).move_to([0, s * 0.42, 0]))
    elif name == "chat":
        b = _U(RoundedRectangle(corner_radius=s * 0.2, width=s * 1.0, height=s * 0.7).move_to([0, s * 0.08, 0]),
                  Polygon([-s * 0.3, -s * 0.2, 0], [-s * 0.05, -s * 0.2, 0], [-s * 0.36, -s * 0.48, 0]))
        g.add(_filled(b, c))
        for x in (-0.24, 0, 0.24):
            g.add(_filled(Circle(s * 0.06), shade(c, 0.5) if _lum(c) > 0.5 else "#FFFFFF").move_to([x * s, s * 0.08, 0]))
    elif name == "user":
        g.add(_filled(Circle(s * 0.22), c).move_to([0, s * 0.22, 0]),
              _filled(_I(Circle(s * 0.4).move_to([0, -s * 0.42, 0]),
                                   RoundedRectangle(corner_radius=0.01, width=s, height=s * 0.42).move_to([0, -s * 0.3, 0])), c))
    elif name == "bolt":
        g.add(_poly([[0.12, 0.5], [-0.28, -0.04], [-0.02, -0.04], [-0.12, -0.5], [0.3, 0.08], [0.04, 0.08]], c).scale(s))
    elif name == "cart":
        g.add(_poly([[-0.42, 0.28], [0.42, 0.28], [0.32, -0.12], [-0.3, -0.12]], c).scale(s),
              _filled(Circle(s * 0.08), c).move_to([-0.2 * s, -0.32 * s, 0]),
              _filled(Circle(s * 0.08), c).move_to([0.2 * s, -0.32 * s, 0]),
              capsule([-0.5 * s, 0.42 * s], [-0.4 * s, 0.28 * s], s * 0.05, color=c))
    elif name == "search":
        ring = _D(Circle(s * 0.3), Circle(s * 0.19))
        g.add(_filled(ring, c).move_to([-0.08 * s, 0.08 * s, 0]),
              capsule([0.12 * s, -0.12 * s], [0.38 * s, -0.38 * s], s * 0.08, color=c))
    elif name == "arrow":
        g.add(capsule([-0.4 * s, 0], [0.25 * s, 0], w, color=c),
              _poly([[0.12, 0.28], [0.48, 0.0], [0.12, -0.28]], c).scale(s, about_point=ORIGIN).round_corners(s * 0.04))
    elif name == "dollar":
        g.add(T("$", size=s * 100 / TYPE_SCALE, color=c, weight="BOLD"))
        g[0].scale_to_fit_height(s * 0.9)
    elif name == "wifi":
        for i, r in enumerate((0.5, 0.33, 0.16)):
            a = _D(Circle(r * s), Circle((r - 0.09) * s)) if i < 2 else Circle(0.08 * s)
            if i < 2:
                a = _I(a, Polygon([0, 0, 0], [-s, s, 0], [s, s, 0]))
            g.add(_filled(a, c).shift(DOWN * s * 0.2))
    elif name == "shield":
        sh = Polygon([0, 0.5, 0], [0.42, 0.34, 0], [0.38, -0.08, 0], [0, -0.5, 0], [-0.38, -0.08, 0], [-0.42, 0.34, 0])
        g.add(_filled(sh.scale(s, about_point=ORIGIN).round_corners(s * 0.08), c))
    elif name == "home":
        g.add(_poly([[0, 0.48], [0.48, 0.06], [-0.48, 0.06]], c).scale(s, about_point=ORIGIN).round_corners(s * 0.05),
              rrect(s * 0.66, s * 0.5, s * 0.06, c).move_to([0, -0.18 * s, 0]))
    elif name == "globe":
        g.add(_filled(Circle(s * 0.46), c))
        inner = shade(c, 0.5) if _lum(c) > 0.5 else tint(c, 0.6)
        g.add(_filled(_D(Ellipse(width=s * 0.42, height=s * 0.92), Ellipse(width=s * 0.3, height=s * 0.8)), inner))
        g.add(_bar(-0.46 * s, 0.46 * s, 0, inner), _bar(-0.4 * s, 0.4 * s, 0.22 * s, inner), _bar(-0.4 * s, 0.4 * s, -0.22 * s, inner))
    else:
        raise ValueError(f"unknown icon '{name}'")
    return g.move_to(ORIGIN)


def _bar(x0, x1, y, color):
    return rrect(x1 - x0, 0.035, 0.017, color).move_to([(x0 + x1) / 2, y, 0])


def badge(name: str, color="BLUE", size: float = 0.9, ring: bool = True) -> VGroup:
    """A round coloured badge with a white glyph and a soft shadow (features, steps, ticks)."""
    col = _c(color)
    disc = _filled(Circle(size / 2), col)
    g = VGroup(soft_shadow(size * 0.95, size * 0.2, 0.18).move_to([0, -size * 0.55, 0]), disc)
    r = rim_light(disc, amount=size * 0.06)
    if r is not None:
        g.add(r)
    g.add(icon(name, size * 0.5, "#FFFFFF" if _lum(col) < 0.62 else PILL_INK).move_to(disc))
    if ring:
        g.add(Circle(size / 2 + 0.05, stroke_color="#FFFFFF", stroke_width=5, fill_opacity=0))
    return g


# --------------------------------------------------------------------------- props

def phone(screen: str = "app", color=None, height: float = 1.3, accent="BLUE") -> VGroup:
    """A phone (front view). screen: app | pay | chat | check | chart | map | blank."""
    h, w = height, height * 0.52
    body_col = _c(color) if color else "#2F3654"
    body = rrect(w, h, w * 0.22, body_col)
    scr = rrect(w * 0.86, h * 0.88, w * 0.16, "#F6F8FF").move_to(body)
    g = VGroup(soft_shadow(w * 1.3, h * 0.09, 0.2).move_to(body.get_bottom() + DOWN * h * 0.03), body,
               rim_light(body, amount=w * 0.04) or VGroup(), scr)
    g.add(rrect(w * 0.26, h * 0.025, h * 0.012, shade(body_col, 0.1)).move_to(scr.get_top() + DOWN * h * 0.04))
    g.screen = scr
    g.ui = _screen_ui(screen, scr, accent)
    g.add(g.ui)
    return g


def _screen_ui(kind: str, scr: VMobject, accent="BLUE") -> VGroup:
    w, h = scr.width, scr.height
    c = scr.get_center()
    ac = _c(accent)
    ui = VGroup()
    line_c = "#D7DDF0"
    if kind == "pay":
        ui.add(rrect(w * 0.78, h * 0.2, w * 0.1, tint(ac, 0.75)).move_to(c + UP * h * 0.2))
        ui.add(rrect(w * 0.4, h * 0.05, h * 0.025, ac).move_to(c + UP * h * 0.2))
        ui.add(rrect(w * 0.6, h * 0.035, h * 0.017, line_c).move_to(c + DOWN * h * 0.0))
        ui.add(rrect(w * 0.45, h * 0.035, h * 0.017, line_c).move_to(c + DOWN * h * 0.08 + LEFT * w * 0.075))
        btn = rrect(w * 0.72, h * 0.12, h * 0.06, _c("GREEN")).move_to(c + DOWN * h * 0.3)
        ui.add(btn, rrect(w * 0.3, h * 0.03, h * 0.015, "#FFFFFF").move_to(btn))
        idle(btn, "pulse", 0.22, 1.3)
        ui.button = btn
    elif kind == "chat":
        ui.add(rrect(w * 0.6, h * 0.1, h * 0.05, "#E4E8F7").move_to(c + UP * h * 0.28 + LEFT * w * 0.1))
        ui.add(rrect(w * 0.55, h * 0.1, h * 0.05, ac).move_to(c + UP * h * 0.12 + RIGHT * w * 0.12))
        ui.add(rrect(w * 0.48, h * 0.1, h * 0.05, "#E4E8F7").move_to(c + DOWN * h * 0.04 + LEFT * w * 0.14))
        ui.add(rrect(w * 0.6, h * 0.1, h * 0.05, ac).move_to(c + DOWN * h * 0.2 + RIGHT * w * 0.1))
    elif kind == "check":
        d = _filled(Circle(w * 0.26), _c("GREEN")).move_to(c + UP * h * 0.06)
        ui.add(glow(w * 0.45, "GREEN", 0.25, at=d.get_center()), d, icon("check", w * 0.3, "#FFFFFF").move_to(d))
        ui.add(rrect(w * 0.5, h * 0.035, h * 0.017, line_c).move_to(c + DOWN * h * 0.24))
    elif kind == "chart":
        for i, hh in enumerate((0.18, 0.3, 0.24, 0.42)):
            ui.add(rrect(w * 0.13, h * hh, w * 0.04, ac if i == 3 else tint(ac, 0.5)).move_to(
                c + LEFT * w * 0.27 + RIGHT * w * 0.18 * i + DOWN * h * 0.3, aligned_edge=DOWN))
    elif kind == "map":
        ui.add(rrect(w * 0.8, h * 0.8, w * 0.1, "#DCEFE0").move_to(c))
        ui.add(capsule(c + LEFT * w * 0.3 + DOWN * h * 0.25, c + RIGHT * w * 0.25 + UP * h * 0.2, w * 0.035, color="#FFFFFF"))
        ui.add(icon("pin", w * 0.32, _c("RED")).move_to(c + RIGHT * w * 0.22 + UP * h * 0.27))
    elif kind == "app":
        for i in range(3):
            for j in range(3):
                col = [_c("BLUE"), _c("PINK"), _c("GOLD"), _c("TEAL"), _c("PURPLE"), _c("ORANGE"), _c("GREEN"), _c("RED"), _c("BLUE")][i * 3 + j]
                ui.add(rrect(w * 0.2, w * 0.2, w * 0.06, tint(col, 0.15)).move_to(
                    c + RIGHT * w * 0.27 * (j - 1) + UP * h * (0.22 - 0.16 * i)))
    return ui


def laptop(screen: str = "chart", color=None, width: float = 2.0, accent="BLUE", back: bool = False) -> VGroup:
    """An open laptop, front view (screen + keyboard deck; screen: as phone()), or back=True: the
    lid seen from behind, for a character working at it and facing the viewer."""
    w = width
    body_col = _c(color) if color else "#3A4163"
    if back:
        lid_c = _c(color) if color else "#C9D1E6"
        lid = rrect(w * 0.82, w * 0.55, w * 0.05, lid_c)
        base = rrect(w * 0.9, w * 0.05, w * 0.02, shade(lid_c, 0.2)).next_to(lid, DOWN, buff=-0.01)
        logo = _filled(Circle(w * 0.055), tint(lid_c, 0.5)).move_to(lid)
        g = VGroup(soft_shadow(w * 1.1, w * 0.08, 0.2).move_to(base.get_bottom()), lid, base, logo)
        r = rim_light(lid, amount=w * 0.02)
        if r is not None:
            g.insert(2, r)
        idle(logo, "pulse", 0.25, 2.6)
        g.screen = None
        return g
    lid = rrect(w * 0.82, w * 0.55, w * 0.04, body_col)
    scr = rrect(w * 0.74, w * 0.47, w * 0.02, "#F6F8FF").move_to(lid)
    deck = _filled(Polygon([-w * 0.46, 0, 0], [w * 0.46, 0, 0], [w * 0.5, -w * 0.06, 0], [-w * 0.5, -w * 0.06, 0]),
                   tint(body_col, 0.55)).round_corners(w * 0.012)
    deck.next_to(lid, DOWN, buff=0)
    g = VGroup(soft_shadow(w * 1.15, w * 0.09, 0.2).move_to(deck.get_bottom() + DOWN * 0.02), lid, scr, deck,
               rrect(w * 0.16, w * 0.016, w * 0.008, shade(tint(body_col, 0.55), 0.15)).move_to(deck.get_top() + DOWN * w * 0.02))
    g.screen = scr
    g.ui = _screen_ui(screen, scr, accent)
    g.add(g.ui)
    return g


def desk(width: float = 3.2, height: float | None = None, color="#F2C79B") -> VGroup:
    """A desk, front view, top surface at its top edge (stand a character behind it)."""
    hgt = height if height is not None else CHAR_H * 0.36
    col = _c(color)
    top = rrect(width, 0.16, 0.06, tint(col, 0.15))
    front = rrect(width * 0.94, 0.22, 0.04, col).next_to(top, DOWN, buff=-0.02)
    legl = rrect(0.16, hgt - 0.3, 0.05, shade(col, 0.25)).next_to(front, DOWN, buff=-0.02).align_to(front, LEFT).shift(RIGHT * 0.15)
    legr = legl.copy().align_to(front, RIGHT).shift(LEFT * 0.15)
    drawer = rrect(width * 0.3, (hgt - 0.3) * 0.55, 0.06, col).next_to(front, DOWN, buff=-0.02).align_to(front, RIGHT).shift(LEFT * 0.08)
    knob = rrect(0.26, 0.06, 0.03, shade(col, 0.3)).move_to(drawer).shift(UP * drawer.height * 0.22)
    g = VGroup(soft_shadow(width * 1.05, 0.22, 0.2).move_to(legl.get_bottom() * [0, 1, 0] + [top.get_x(), 0, 0]),
               legl, legr, drawer, knob, front, top)
    g.shift(-g.get_bottom() * [0, 1, 0])
    g.top_y = lambda: top.get_top()[1]
    return g


def sofa(width: float = 3.4, color="PURPLE") -> VGroup:
    col = tint(_c(color), 0.25)
    back = rrect(width * 0.84, 0.95, 0.28, shade(col, 0.08)).shift(UP * 0.85)
    seat = rrect(width * 0.82, 0.5, 0.16, col).shift(UP * 0.38)
    arml = rrect(0.42, 0.95, 0.2, shade(col, 0.15)).move_to([-width / 2 + 0.21, 0.55, 0])
    armr = arml.copy().move_to([width / 2 - 0.21, 0.55, 0])
    cush = VGroup(*[rrect(width * 0.36, 0.7, 0.2, tint(col, 0.12)).move_to([x * width * 0.2, 0.95, 0]) for x in (-1, 1)])
    legs = VGroup(*[rrect(0.12, 0.18, 0.04, "#7A5A46").move_to([x * (width / 2 - 0.3), 0.05, 0]) for x in (-1, 1)])
    g = VGroup(soft_shadow(width * 1.05, 0.3, 0.22).move_to([0, 0.02, 0]), legs, back, cush, seat, arml, armr)
    g.shift(-g.get_bottom() * [0, 1, 0])
    return g


def house(width: float = 2.6, color="ORANGE", roof="RED") -> VGroup:
    """A small house with a side face, a rounded roof, a door and lit windows."""
    col = tint(_c(color), 0.4)
    front = rrect(width, width * 0.7, 0.05, col).shift(UP * width * 0.35)
    box = extrude(front, (width * 0.16, width * 0.08))
    rc = _c(roof)
    rf = _filled(Polygon([-width * 0.62, width * 0.68, 0], [width * 0.62, width * 0.68, 0], [0, width * 1.12, 0]), rc).round_corners(width * 0.05)
    rf_side = _filled(Polygon([width * 0.62, width * 0.68, 0], [width * 0.78, width * 0.76, 0], [width * 0.16, width * 1.2, 0], [0, width * 1.12, 0]), shade(rc, 0.25))
    door = rrect(width * 0.24, width * 0.4, width * 0.06, shade(_c(roof), 0.1)).move_to([width * 0.12, width * 0.2, 0])
    wins = VGroup(*[rrect(width * 0.24, width * 0.22, width * 0.04, WORLD["lit"]).move_to([-width * 0.26, width * 0.44, 0])])
    chimney = rrect(width * 0.13, width * 0.3, 0.03, shade(col, 0.2)).move_to([-width * 0.3, width * 1.0, 0])
    g = VGroup(soft_shadow(width * 1.4, width * 0.16, 0.22).move_to([width * 0.08, 0, 0]), chimney, rf_side, box, rf, door, wins)
    g.shift(-g.get_bottom() * [0, 1, 0])
    return g


def _awning(width, y, colors, n=7, drop=0.32):
    g = VGroup()
    sw = width / n
    for i in range(n):
        x0 = -width / 2 + i * sw
        col = colors[i % 2]
        stripe = _filled(Polygon([x0, y, 0], [x0 + sw, y, 0], [x0 + sw * 1.06, y - drop, 0], [x0 - sw * 0.06, y - drop, 0]), col)
        scallop = _filled(Circle(sw * 0.55), col).move_to([x0 + sw / 2, y - drop, 0])
        g.add(stripe, scallop)
    return g


def shop(width: float = 3.2, color="PINK", sign: str | None = "SHOP", awning=("RED", "#FFFFFF")) -> VGroup:
    """A storefront: side face, striped awning with a scalloped edge, a big window, a door, a sign."""
    col = tint(_c(color), 0.45)
    hgt = width * 0.82
    front = rrect(width, hgt, 0.05, col).shift(UP * hgt / 2)
    box = extrude(front, (width * 0.12, width * 0.06))
    win = rrect(width * 0.5, hgt * 0.42, 0.06, WORLD["glass"]).move_to([-width * 0.18, hgt * 0.33, 0])
    shine = _filled(Polygon([-0.1, -0.2, 0], [0.05, -0.2, 0], [0.25, 0.2, 0], [0.1, 0.2, 0]), "#FFFFFF", 0.55).scale(hgt * 0.4).move_to(win).shift(LEFT * width * 0.08)
    door = rrect(width * 0.24, hgt * 0.52, 0.06, shade(col, 0.3)).move_to([width * 0.28, hgt * 0.26, 0])
    knob = _filled(Circle(0.035), "#FFFFFF").move_to(door.get_center() + LEFT * width * 0.07)
    aw = _awning(width * 1.04, hgt * 0.72, [_c(awning[0]), _c(awning[1])])
    g = VGroup(soft_shadow(width * 1.3, width * 0.14, 0.22).move_to([width * 0.06, 0, 0]), box, win, shine, door, knob, aw)
    if sign:
        board = rrect(width * 0.6, hgt * 0.16, 0.08, PILL_BG).move_to([0, hgt * 0.88, 0])
        txt = T(sign, size=SIZE_LABEL / TYPE_SCALE * 0.9, color=PILL_INK, weight="BOLD")
        fit(txt, board.width * 0.85, board.height * 0.7).move_to(board)
        g.add(board, txt)
        g.sign = txt
    g.shift(-g.get_bottom() * [0, 1, 0])
    return g


def bank(width: float = 3.4, color="BLUE", sign: str | None = "BANK") -> VGroup:
    """A bank: steps, columns, a pediment, a sign."""
    col = tint(_c(color), 0.62)
    dark = shade(col, 0.18)
    hgt = width * 0.9
    steps = VGroup(*[rrect(width * (1.06 - 0.05 * i), 0.12, 0.03, tint(col, 0.15) if i % 2 else dark).move_to([0, 0.06 + 0.12 * i, 0]) for i in range(3)])
    base_top = 0.36
    body = rrect(width * 0.9, hgt * 0.56, 0.03, col).move_to([0, base_top + hgt * 0.28, 0])
    cols = VGroup()
    for i in range(4):
        x = -width * 0.33 + i * width * 0.22
        cols.add(rrect(width * 0.11, hgt * 0.5, 0.03, "#FFFFFF").move_to([x, base_top + hgt * 0.27, 0]))
        cols.add(rrect(width * 0.03, hgt * 0.5, 0.01, tint(col, 0.4)).move_to([x + width * 0.03, base_top + hgt * 0.27, 0]))
    beam = rrect(width * 1.0, hgt * 0.1, 0.03, tint(col, 0.2)).move_to([0, base_top + hgt * 0.6, 0])
    ped = _filled(Polygon([-width * 0.54, base_top + hgt * 0.65, 0], [width * 0.54, base_top + hgt * 0.65, 0],
                          [0, base_top + hgt * 0.92, 0]), dark).round_corners(0.05)
    g = VGroup(soft_shadow(width * 1.3, width * 0.14, 0.22), steps, body, cols, beam, ped)
    if sign:
        txt = T(sign, size=SIZE_SMALL / TYPE_SCALE, color=PILL_INK, weight="BOLD")
        fit(txt, width * 0.5, hgt * 0.07).move_to(beam)
        g.add(txt)
        g.sign = txt
    g.add(_filled(Circle(width * 0.05), "#FFFFFF").move_to([0, base_top + hgt * 0.75, 0]))
    g.shift(-g.get_bottom() * [0, 1, 0])
    return g


def coin(radius: float = 0.32, color="GOLD", symbol: str = "$") -> VGroup:
    """A coin with an edge (it reads as a disc with thickness), a rim highlight and a symbol."""
    col = _c(color)
    edge = _filled(Circle(radius), shade(col, 0.28)).shift(DOWN * radius * 0.12)
    face = _filled(Circle(radius), col)
    inner = _filled(Circle(radius * 0.74), tint(col, 0.18))
    g = VGroup(edge, face, inner)
    r = rim_light(face, amount=radius * 0.1)
    if r is not None:
        g.add(r)
    if symbol:
        s = T(symbol, size=40, color=shade(col, 0.45), weight="BOLD")
        s.scale_to_fit_height(radius * 0.8).move_to(inner)
        g.add(s)
    return g


def card(width: float = 1.6, color="PURPLE", accent="GOLD") -> VGroup:
    """A payment card with a gentle gradient, a chip and number dots."""
    col = _c(color)
    body = rrect(width, width * 0.63, width * 0.08, col)
    body.set_fill([tint(col, 0.15), shade(col, 0.12)], opacity=1)
    body.set_sheen_direction(DR)
    chip = rrect(width * 0.17, width * 0.13, width * 0.03, _c(accent)).move_to(body.get_corner(UL) + [width * 0.2, -width * 0.24, 0])
    dots = VGroup(*[rrect(width * 0.16, width * 0.04, width * 0.02, tint(col, 0.6)).move_to(body.get_corner(DL) + [width * (0.18 + 0.2 * i), width * 0.17, 0]) for i in range(4)])
    circ = VGroup(_filled(Circle(width * 0.08), "#FF8A65", 0.9).move_to(body.get_corner(UR) + [-width * 0.24, -width * 0.18, 0]),
                  _filled(Circle(width * 0.08), "#FFD15C", 0.9).move_to(body.get_corner(UR) + [-width * 0.15, -width * 0.18, 0]))
    g = VGroup(soft_shadow(width * 1.0, width * 0.12, 0.18).move_to(body.get_bottom() + DOWN * 0.06), body)
    r = rim_light(body, amount=width * 0.03)
    if r is not None:
        g.add(r)
    g.add(chip, dots, circ)
    return g


def cash(width: float = 1.4, color="GREEN") -> VGroup:
    """A bank note."""
    col = tint(_c(color), 0.2)
    body = rrect(width, width * 0.5, width * 0.05, col)
    inner = rrect(width * 0.86, width * 0.36, width * 0.04, tint(col, 0.3))
    mid = _filled(Ellipse(width=width * 0.28, height=width * 0.28), col)
    s = T("$", size=40, color=shade(col, 0.35), weight="BOLD")
    s.scale_to_fit_height(width * 0.18).move_to(mid)
    return VGroup(body, inner, mid, s)


def chart(width: float = 2.6, values=(0.35, 0.55, 0.45, 0.8), color="BLUE", board: bool = True, arrow: bool = True) -> VGroup:
    """A bar chart on a board; .bars to animate (pop_in(*chart.bars, anchor="bottom"))."""
    col = _c(color)
    h = width * 0.66
    g = VGroup()
    if board:
        b = rrect(width, h, width * 0.06, PILL_BG)
        g.add(soft_shadow(width * 1.05, width * 0.12, 0.18).move_to(b.get_bottom() + DOWN * 0.08), b)
    bars = VGroup()
    n = len(values)
    bw = width * 0.7 / n
    for i, v in enumerate(values):
        bar = rrect(bw * 0.7, max(0.08, h * 0.7 * v), bw * 0.16, col if i == n - 1 else tint(col, 0.45))
        bar.move_to([-width * 0.35 + bw * (i + 0.5), -h * 0.36, 0], aligned_edge=DOWN)
        bars.add(bar)
    g.add(rrect(width * 0.78, 0.03, 0.015, "#DCE2F2").move_to([0, -h * 0.37, 0]), bars)
    if arrow:
        a = VGroup(capsule([-width * 0.32, -h * 0.05], [width * 0.24, h * 0.3], width * 0.018, color=_c("GREEN")),
                   _poly([[0, 0.1], [0.11, -0.05], [-0.08, -0.06]], _c("GREEN")).scale(width).move_to([width * 0.27, h * 0.32, 0]).rotate(-0.55))
        g.add(a)
    g.bars = bars
    return g


def envelope(width: float = 1.2, color="#FFFFFF", seal="RED") -> VGroup:
    col = _c(color)
    h = width * 0.66
    body = rrect(width, h, width * 0.06, col)
    flap = _filled(Polygon([-width / 2 + 0.03, h / 2 - 0.02, 0], [width / 2 - 0.03, h / 2 - 0.02, 0], [0, -h * 0.05, 0]), shade(col, 0.08)).round_corners(width * 0.03)
    lower = _filled(Polygon([-width / 2 + 0.02, -h / 2 + 0.03, 0], [width / 2 - 0.02, -h / 2 + 0.03, 0], [0, h * 0.08, 0]), shade(col, 0.04)).round_corners(width * 0.03)
    s = _filled(Circle(width * 0.08), _c(seal)).move_to([0, -h * 0.02, 0])
    return VGroup(soft_shadow(width * 1.0, width * 0.1, 0.18).move_to([0, -h / 2 - 0.06, 0]), body, lower, flap, s)


def cloud(width: float = 2.0, color=None, opacity: float = 1.0) -> VGroup:
    """A puffy cloud: one merged shape with a flat-ish base and a soft underside shade."""
    col = _c(color) if color else WORLD["cloud"]
    w = width
    parts = [Circle(w * 0.2).move_to([-w * 0.22, 0, 0]), Circle(w * 0.27).move_to([0.02 * w, w * 0.1, 0]),
             Circle(w * 0.18).move_to([w * 0.28, -0.02 * w, 0]),
             RoundedRectangle(corner_radius=w * 0.1, width=w * 0.95, height=w * 0.22).move_to([0, -w * 0.09, 0])]
    body = _filled(_U(*parts), col, opacity)
    g = VGroup(body)
    sh = _offset_diff(body, (0, w * 0.045), mix(col, WORLD["sky"][1], 0.55) if not IS_DUSK else shade(col, 0.12), opacity)
    if sh is not None:
        g.add(sh)
    return g


def tree(height: float = 2.2, color=None, trunk=None) -> VGroup:
    """A round tree with light and shade on its canopy."""
    col = _c(color) if color else WORLD["tree"]
    h = height
    tr = rrect(h * 0.1, h * 0.42, h * 0.04, _c(trunk) if trunk else WORLD["trunk"]).move_to([0, h * 0.21, 0])
    can = _filled(_U(Circle(h * 0.26).move_to([0, h * 0.68, 0]), Circle(h * 0.2).move_to([-h * 0.19, h * 0.52, 0]),
                        Circle(h * 0.21).move_to([h * 0.18, h * 0.5, 0])), col)
    g = VGroup(soft_shadow(h * 0.6, h * 0.08, 0.2), tr, can)
    for f in (side_shade(can, amount=h * 0.08), rim_light(can, amount=h * 0.05)):
        if f is not None:
            g.add(f)
    g.shift(-g.get_bottom() * [0, 1, 0])
    return g


def pine(height: float = 2.4, color=None) -> VGroup:
    col = _c(color) if color else shade(WORLD["tree"], 0.1)
    h = height
    tr = rrect(h * 0.09, h * 0.2, h * 0.03, WORLD["trunk"]).move_to([0, h * 0.1, 0])
    g = VGroup(soft_shadow(h * 0.5, h * 0.07, 0.2), tr)
    for i, (y, w) in enumerate(((0.2, 0.42), (0.45, 0.34), (0.68, 0.25))):
        tri = _filled(Polygon([-w * h, y * h, 0], [w * h, y * h, 0], [0, (y + 0.36) * h, 0]), col).round_corners(h * 0.04)
        g.add(tri)
        s = side_shade(tri, amount=h * 0.07)
        if s is not None:
            g.add(s)
    g.shift(-g.get_bottom() * [0, 1, 0])
    return g


def bush(width: float = 1.4, color=None) -> VGroup:
    col = _c(color) if color else WORLD["grass"]
    w = width
    b = _filled(_U(Circle(w * 0.26).move_to([-w * 0.22, w * 0.2, 0]), Circle(w * 0.32).move_to([w * 0.05, w * 0.28, 0]),
                      Circle(w * 0.24).move_to([w * 0.3, w * 0.18, 0]),
                      RoundedRectangle(corner_radius=w * 0.08, width=w, height=w * 0.24).move_to([0, w * 0.12, 0])), col)
    g = VGroup(b)
    r = rim_light(b, amount=w * 0.05)
    if r is not None:
        g.add(r)
    g.shift(-g.get_bottom() * [0, 1, 0])
    return g


def hill(width: float = 8.0, height: float = 2.0, color=None, at=ORIGIN, lip: bool = True) -> VGroup:
    """A soft rolling hill (wide, rounded), base at its bottom edge."""
    col = _c(color) if color else WORLD["hill_mid"]
    n = 28
    pts = []
    for i in range(n + 1):
        u = i / n
        x = -width / 2 + width * u
        y = height * (math.sin(PI * u) ** 1.4)
        pts.append([x, y, 0])
    pts += [[width / 2, -height * 0.6, 0], [-width / 2, -height * 0.6, 0]]
    m = VMobject()
    m.set_points_smoothly([np.array(p) for p in pts] + [np.array(pts[0])])
    _filled(m, col)
    g = VGroup(m)
    if lip:
        r = rim_light(m, tint(col, 0.22), amount=height * 0.05)
        if r is not None:
            g.add(r)
    return g.shift(np.array(at, dtype=float))


def building(width: float = 1.6, height: float = 3.0, color=None, windows: bool = True, lit: float = 0.25,
             seed: int = 1, depth: float = 0.22) -> VGroup:
    """A city building with a side face and a window grid (some windows lit)."""
    rng = np.random.default_rng(seed)
    col = _c(color) if color else WORLD["bld"][seed % len(WORLD["bld"])]
    front = rrect(width, height, 0.04, col).move_to([0, height / 2, 0])
    g = VGroup(extrude(front, (depth, depth * 0.5)))
    if windows:
        cols = max(2, int(width / 0.42))
        rows = max(2, int((height - 0.4) / 0.5))
        ww, wh = width / cols * 0.5, 0.26
        dark, bright = VMobject(), VMobject()   # all windows of one colour are ONE shape: cheap to draw
        for i in range(rows):
            for j in range(cols):
                x = -width / 2 + width / cols * (j + 0.5)
                y = height - 0.35 - i * (height - 0.5) / rows
                (bright if rng.random() < lit else dark).append_vectorized_mobject(RoundedRectangle(corner_radius=0.04, width=ww, height=wh).move_to([x, y, 0]))
        for m, cc in ((dark, shade(col, 0.08) if not IS_DUSK else shade(col, 0.3)), (bright, WORLD["lit"])):
            if len(m.points):
                g.add(_filled(m, cc))
    return g


def merge(*mobs, color=None) -> VMobject:
    """Many same-coloured shapes as ONE shape (one draw call): rows of windows, dots, dashes."""
    m = VMobject()
    for x in mobs:
        for f in x.family_members_with_points():
            m.append_vectorized_mobject(f)
    col = color or mobs[0].family_members_with_points()[0].get_fill_color().to_hex()
    return _filled(m, col)


def panel(width: float = 5.6, height: float = 4.2, kind: str = "room", tint_k: float = 0.0) -> VGroup:
    """A rounded card holding a little world of its own (sky or wall + floor): side-by-side
    comparisons, a 'meanwhile' inset, a phone-screen close-up. .floor_y is where feet stand
    inside it; .inner is the picture area. tint_k > 0 greys it (the 'before' side)."""
    sky = {"room": WORLD["wall"], "office": WORLD["owall"], "outdoors": (WORLD["sky"][0], WORLD["sky"][2]),
           "city": (WORLD["sky"][0], WORLD["sky"][2]), "plain": WORLD["plain"]}.get(kind, WORLD["wall"])
    floor_c = {"room": WORLD["floor"], "office": WORLD["ofloor"], "outdoors": WORLD["ground"], "city": WORLD["walk"]}.get(kind, WORLD["plain"][1])
    if tint_k:
        sky = tuple(mix(c, "#B9BFCF", tint_k) for c in sky)
        floor_c = mix(floor_c, "#9AA1B4", tint_k)
    r = min(width, height) * 0.09
    card_ = rrect(width, height, r, PILL_BG)
    inner = rrect(width - 0.24, height - 0.24, r * 0.75, sky[0])
    inner.set_fill([sky[0], sky[1]], opacity=1)
    inner.set_sheen_direction(DOWN)
    fh = (height - 0.24) * 0.3
    floor = _I(rrect(width - 0.24, height - 0.24, r * 0.75, floor_c),
               rrect(width, fh + 0.02, 0.01, floor_c).move_to([0, -(height - 0.24) / 2 + fh / 2, 0]))
    _filled(floor, floor_c)
    g = VGroup(rrect(width, height, r, _SHADOW, 0.14).shift(DOWN * 0.1), card_, inner, floor)
    if kind == "outdoors":
        g.add(cloud(width * 0.22).move_to([-width * 0.22, height * 0.28, 0]))
    elif kind in ("room", "office"):
        g.add(window(width * 0.26, height * 0.26).move_to([width * 0.24, height * 0.16, 0]))
    g.floor_y = lambda: floor.get_top()[1] - fh * 0.35
    g.inner = inner
    return g


def skyline(width: float = 16.0, height: float = 2.4, color=None, seed: int = 2, n: int | None = None) -> VMobject:
    """A distant city silhouette as ONE shape (cheap to draw, made for far layers)."""
    rng = np.random.default_rng(seed)
    col = _c(color) if color else WORLD["far_city"]
    n = n or int(width / 0.9)
    shapes = []
    x = -width / 2
    while x < width / 2:
        w = rng.uniform(0.5, 1.3)
        h = height * rng.uniform(0.35, 1.0)
        shapes.append(RoundedRectangle(corner_radius=0.06, width=w, height=h).move_to([x + w / 2, h / 2, 0]))
        if rng.random() < 0.25:
            shapes.append(RoundedRectangle(corner_radius=0.03, width=0.08, height=0.5).move_to([x + w / 2, h + 0.2, 0]))
        x += w * rng.uniform(0.75, 1.0)
    shapes.append(RoundedRectangle(corner_radius=0.01, width=width, height=0.3).move_to([0, 0.1, 0]))
    m = _filled(_U(*shapes), col)
    return m


def server(height: float = 2.2, color="#3A4163", units: int = 4) -> VGroup:
    """A server rack; its LEDs blink (idle pulse)."""
    col = _c(color)
    w = height * 0.5
    front = rrect(w, height, w * 0.08, col).move_to([0, height / 2, 0])
    g = VGroup(soft_shadow(w * 1.6, w * 0.25, 0.22), extrude(front, (w * 0.18, w * 0.1)))
    for i in range(units):
        y = height * (0.15 + 0.78 * (i + 0.5) / units)
        g.add(rrect(w * 0.8, height * 0.15, w * 0.04, tint(col, 0.12)).move_to([0, y, 0]))
        led = _filled(Circle(w * 0.045), _c("GREEN" if i % 3 else "BLUE")).move_to([w * 0.28, y, 0])
        idle(led, "flicker", 0.6, 0.7 + 0.37 * i)
        g.add(led, rrect(w * 0.35, height * 0.02, height * 0.01, shade(col, 0.2)).move_to([-w * 0.12, y, 0]))
    g.shift(-g.get_bottom() * [0, 1, 0])
    return g


def gear(radius: float = 0.7, color="ORANGE", teeth: int = 8, spin: bool = True) -> VGroup:
    """A gear (it turns slowly when spin=True)."""
    col = _c(color)
    r = radius
    pts = []
    for i in range(teeth * 4):
        a = TAU * i / (teeth * 4)
        rr = r if (i % 4) in (0, 1) else r * 0.78
        pts.append([rr * math.cos(a), rr * math.sin(a), 0])
    body = Polygon(*pts).round_corners(r * 0.06)
    g_ = _filled(_D(body, Circle(r * 0.3)), col)
    g = VGroup(g_)
    s = side_shade(g_, amount=r * 0.1)
    if s is not None:
        g.add(s)
    if spin:
        idle(g, "spin", 1.0, 7.0)
    return g


def bulb(height: float = 1.4, color="YELLOW", lit: bool = True) -> VGroup:
    """A light bulb (an idea); lit adds a soft glow that pulses."""
    h = height
    col = _c(color)
    glass = _filled(_U(Circle(h * 0.33).move_to([0, h * 0.62, 0]),
                          Polygon([-h * 0.18, h * 0.4, 0], [h * 0.18, h * 0.4, 0], [h * 0.12, h * 0.22, 0], [-h * 0.12, h * 0.22, 0])),
                    col if lit else "#E8ECF6")
    base = VGroup(*[rrect(h * 0.26, h * 0.07, h * 0.03, "#8E95B2" if i % 2 else "#B5BBD3").move_to([0, h * (0.18 - 0.07 * i), 0]) for i in range(3)])
    g = VGroup()
    if lit:
        gl = glow(h * 0.75, color, 0.45, at=[0, h * 0.6, 0])
        idle(gl, "pulse", 0.35, 1.8)
        g.add(gl)
    g.add(glass, base)
    r = rim_light(glass, "#FFFFFF", amount=h * 0.04, opacity=0.8)
    if r is not None:
        g.add(r)
    g.add(_filled(Ellipse(width=h * 0.09, height=h * 0.16), "#FFFFFF", 0.85).move_to([-h * 0.13, h * 0.72, 0]))
    return g


def clock(radius: float = 0.7, color="#FFFFFF", rim="BLUE", hour: float = 10.0, minute: float = 10.0,
          spin: bool = False) -> VGroup:
    """A wall clock; .minute and .hour hands (spin=True turns the minute hand)."""
    face = _filled(Circle(radius), _c(color))
    ring = _filled(_D(Circle(radius * 1.12), Circle(radius)), _c(rim))
    ticks = VGroup(*[rrect(radius * 0.06, radius * 0.16, radius * 0.03, "#B9C0D8").move_to(
        [radius * 0.8 * math.sin(TAU * i / 12), radius * 0.8 * math.cos(TAU * i / 12), 0]).rotate(-TAU * i / 12) for i in range(12)])
    am = TAU * minute / 60
    ah = TAU * (hour % 12) / 12 + am / 12
    mh = capsule([0, 0], [radius * 0.68 * math.sin(am), radius * 0.68 * math.cos(am)], radius * 0.05, color=PILL_INK)
    hh = capsule([0, 0], [radius * 0.45 * math.sin(ah), radius * 0.45 * math.cos(ah)], radius * 0.07, color=PILL_INK)
    pin_ = _filled(Circle(radius * 0.08), _c("RED"))
    g = VGroup(soft_shadow(radius * 1.8, radius * 0.3, 0.16).move_to([0, -radius * 1.25, 0]), ring, face, ticks, hh, mh, pin_)
    g.minute, g.hour = mh, hh
    if spin:
        holder = VGroup(mh)
        idle(holder, "spin", 1.0, 2.5)
    return g


def plant(height: float = 1.6, pot="ORANGE", color=None) -> VGroup:
    col = _c(color) if color else WORLD["tree"]
    h = height
    potm = _filled(Polygon([-h * 0.22, h * 0.36, 0], [h * 0.22, h * 0.36, 0], [h * 0.16, 0, 0], [-h * 0.16, 0, 0]), _c(pot)).round_corners(h * 0.03)
    rimp = rrect(h * 0.5, h * 0.08, h * 0.03, shade(_c(pot), 0.15)).move_to([0, h * 0.37, 0])
    leaves = VGroup()
    for i, (ang, ln) in enumerate(((-0.6, 0.55), (-0.25, 0.68), (0.1, 0.72), (0.45, 0.6), (0.8, 0.48))):
        p0 = np.array([0, h * 0.4])
        p1 = p0 + h * ln * np.array([math.sin(ang), math.cos(ang)])
        leaf = blob([p0 + [0.0, 0], (p0 + p1) / 2 + h * 0.09 * np.array([math.cos(ang), -math.sin(ang)]), p1,
                     (p0 + p1) / 2 - h * 0.09 * np.array([math.cos(ang), -math.sin(ang)])], col if i % 2 else tint(col, 0.18))
        leaves.add(leaf)
    g = VGroup(soft_shadow(h * 0.6, h * 0.08, 0.2), leaves, potm, rimp)
    idle(leaves, "sway", 0.03, 4.4)
    g.shift(-g.get_bottom() * [0, 1, 0])
    return g


def lamp(height: float = 2.6, color=None) -> VGroup:
    """A street lamp (city foreground)."""
    col = _c(color) if color else shade(WORLD["street"], 0.05)
    h = height
    pole = rrect(h * 0.05, h * 0.9, h * 0.02, col).move_to([0, h * 0.45, 0])
    head = rrect(h * 0.2, h * 0.09, h * 0.04, col).move_to([0, h * 0.92, 0])
    light = _filled(Ellipse(width=h * 0.14, height=h * 0.05), WORLD["lit"]).move_to([0, h * 0.875, 0])
    base = rrect(h * 0.12, h * 0.06, h * 0.02, col).move_to([0, h * 0.03, 0])
    return VGroup(pole, head, light, base)


def window(width: float = 2.2, height: float = 1.8, frame="#FFFFFF", sky=None) -> VGroup:
    """A window with sky and a cloud in it (indoor backdrops)."""
    s0, s1 = (sky or (WORLD["sky"][0], WORLD["sky"][1]))
    f = rrect(width, height, 0.08, _c(frame))
    glass = rrect(width * 0.88, height * 0.86, 0.05, s0)
    glass.set_fill([s0, s1], opacity=1)
    glass.set_sheen_direction(DOWN)
    cl = cloud(width * 0.4).move_to(glass.get_center() + [width * 0.12, height * 0.12, 0])
    bar_v = rrect(0.06, height * 0.86, 0.02, _c(frame)).move_to(glass)
    bar_h = rrect(width * 0.88, 0.06, 0.02, _c(frame)).move_to(glass)
    sill = rrect(width * 1.1, 0.12, 0.05, shade(_c(frame), 0.06)).next_to(f, DOWN, buff=-0.04)
    return VGroup(soft_shadow(width * 1.1, 0.16, 0.12).move_to(sill.get_bottom() + DOWN * 0.04), f, glass, cl, bar_v, bar_h, sill)


def route(a, b, color="INK_3", curve: float = 0.6, dash: float = 0.16, width: float = 0.05) -> VGroup:
    """A dashed rounded path between two things (how something travels). Draw it with
    pop_in(*route(...), gap=0.02, anchor="center") or stagger, travel a coin along it."""
    pa = a.get_center() if isinstance(a, Mobject) else np.array(a, dtype=float)
    pb = b.get_center() if isinstance(b, Mobject) else np.array(b, dtype=float)
    mid = (pa + pb) / 2 + np.array([0, curve, 0])
    pts = [(1 - u) ** 2 * pa + 2 * (1 - u) * u * mid + u * u * pb for u in np.linspace(0, 1, 120)]
    L = sum(np.linalg.norm(pts[i + 1] - pts[i]) for i in range(len(pts) - 1))
    n = max(2, int(L / (dash * 2)))
    g = VGroup()
    for i in range(n):
        u0, u1 = i / n, (i + 0.5) / n
        p0 = pts[int(u0 * 119)]
        p1 = pts[int(u1 * 119)]
        g.add(capsule(p0, p1, width / 2, color=_c(color), n=4))
    return g


# --------------------------------------------------------------------------- text

_LABEL_Z = 9   # labels sit this far above their layer: a world object never covers its own name


def _label(g, target=None):
    """Put a label group in its target's depth (main without a target), just above its z-order."""
    d = getattr(target, "ww_depth", 1.0) if target is not None else 1.0
    if d is None:
        return hud(g)
    g.ww_depth = d
    g.ww_layer = getattr(target, "ww_layer", "main") if target is not None else "main"
    z = (getattr(target, "ww_z", None) if target is not None else None) or _Z["main"]
    g.ww_z = z + _LABEL_Z
    g.set_z_index(g.ww_z, family=True)
    return g


def pill(text: str, color=None, size: float = SIZE_LABEL, icon_name: str | None = None, shadow: bool = True,
         max_w: float | None = None) -> VGroup:
    """A rounded label card: text that reads on any background (white card, dark ink; or a
    coloured card with white/dark text picked for contrast). The main text device in 2.5D."""
    bg = _c(color) if color else PILL_BG
    ink = on_color(bg)
    t = T(text, size=size, color=ink, weight="BOLD")
    if max_w:
        fit(t, max_w)
    parts = [t]
    if icon_name:
        if color:
            ic = icon(icon_name, t.height * 1.2, ink)
        else:
            disc = _filled(Circle(t.height * 0.8), _c("BLUE"))
            ic = VGroup(disc, icon(icon_name, t.height * 0.85, "#FFFFFF").move_to(disc))
        parts = [ic, t]
    row = VGroup(*parts).arrange(RIGHT, buff=t.height * 0.4)
    padx, pady = t.height * 0.7, t.height * 0.5
    box = rrect(row.width + 2 * padx, row.height + 2 * pady, (row.height + 2 * pady) / 2, bg).move_to(row)
    g = VGroup()
    if shadow:
        g.add(rrect(box.width, box.height, box.height / 2, _SHADOW, 0.13).move_to(box).shift(DOWN * 0.07))
    g.add(box, row)
    g.text, g.box = t, box
    return _label(g)


def tag(text: str, target: Mobject, direction=UP, buff: float = 0.2, color=None, size: float = SIZE_LABEL) -> VGroup:
    """A pill attached to a thing, with a little pointer toward it; same layer as the target."""
    p = pill(text, color, size)
    d = np.array(direction, dtype=float)
    p.next_to(target, d, buff=buff + 0.12)
    box = p.box
    tip_dir = -d / (np.linalg.norm(d) + 1e-9)
    base = box.get_center() + tip_dir * np.array([box.width / 2, box.height / 2, 0]) * np.abs(tip_dir)
    perp = np.array([-tip_dir[1], tip_dir[0], 0])
    k = min(box.height, 0.5) * 0.3
    tri = _filled(Polygon(base + perp * k - tip_dir * 0.02, base - perp * k - tip_dir * 0.02, base + tip_dir * 0.2),
                  box.get_fill_color().to_hex())
    p.add(tri)
    return _label(p, target)


def bubble(content, speaker: Mobject | None = None, side=UR, color=None, size: float = SIZE_LABEL,
           max_w: float | None = None) -> VGroup:
    """A speech bubble (text, an icon name or a mobject) with its tail toward the speaker's head."""
    bg = _c(color) if color else PILL_BG
    if isinstance(content, str) and content.startswith("icon:"):
        inner = icon(content[5:], 0.55, _c("BLUE") if not color else on_color(bg))
    elif isinstance(content, str):
        inner = T(content, size=size, color=on_color(bg), weight="BOLD")
        fit(inner, max_w or by_aspect(4.2, 4.6))
    else:
        inner = content
    pad = 0.3
    box = rrect(inner.width + 2 * pad, inner.height + 2 * pad, min(0.35, (inner.height + 2 * pad) / 2), bg).move_to(inner)
    sx = 1 if np.array(side)[0] >= 0 else -1
    bl = box.get_corner(DL if sx > 0 else DR)
    tail = _filled(Polygon(bl + [sx * 0.25, 0.05, 0], bl + [sx * 0.65, 0.05, 0], bl + [-sx * 0.05, -0.32, 0]), bg)
    g = VGroup(rrect(box.width, box.height, box.get_height() / 2.2, _SHADOW, 0.12).move_to(box).shift(DOWN * 0.07), box, tail, inner)
    g.inner = inner
    if speaker is not None:
        head = getattr(speaker, "head_point", None)
        anchor = head() if callable(head) else speaker.get_top()
        g.move_to(anchor + np.array([sx * (g.width / 2 + 0.1), g.height / 2 + 0.25, 0]))
    return _label(g, speaker)


def thought(content, speaker: Mobject | None = None, side=UR, color=None, size: float = SIZE_LABEL) -> VGroup:
    """A thought bubble (cloud-ish, little circles toward the head)."""
    b = bubble(content, None, side, color, size)
    sx = 1 if np.array(side)[0] >= 0 else -1
    b.remove(b[2])
    bg = b[1].get_fill_color().to_hex()
    dots = VGroup(*[_filled(Circle(r), bg) for r in (0.13, 0.085)])
    corner = b[1].get_corner(DL if sx > 0 else DR)
    dots[0].move_to(corner + [sx * 0.1, -0.22, 0])
    dots[1].move_to(corner + [-sx * 0.12, -0.5, 0])
    b.add(dots)
    if speaker is not None:
        head = getattr(speaker, "head_point", None)
        anchor = head() if callable(head) else speaker.get_top()
        b.move_to(anchor + np.array([sx * (b.width / 2 + 0.2), b.height / 2 + 0.45, 0]))
    return _label(b, speaker)


def headline(text: str, sub: str | None = None, color=None) -> VGroup:
    """A bold title at the top of the safe area (in the hud: it ignores the camera)."""
    ink = _c(color) if color else _ws.INK
    t = T(text, size=SIZE_TITLE * 0.85, color=ink, weight="BOLD")
    g = VGroup(t)
    if sub:
        s = T(sub, size=SIZE_BODY * 0.85, color=_ws.INK_2)
        g.add(s)
        g.arrange(DOWN, buff=0.18)
    _ws.place_title(g)
    return hud(g)


def big_number(text: str, color="BLUE", size: float = 96) -> VGroup:
    """A big punchy figure on a soft card (a price, a percentage, a count)."""
    col = _c(color)
    t = T(text, size=size, color=PILL_INK, weight="BOLD")
    box = rrect(t.width + 0.8, t.height + 0.6, 0.3, PILL_BG).move_to(t)
    bar = rrect(box.width * 0.5, 0.1, 0.05, col).next_to(box.get_bottom(), UP, buff=0.18)
    t.shift(UP * 0.06)
    return _label(VGroup(rrect(box.width, box.height, 0.3, _SHADOW, 0.13).move_to(box).shift(DOWN * 0.08), box, bar, t))


# --------------------------------------------------------------------------- characters

SKIN = {"light": "#FADCC6", "fair": "#F1C3A2", "tan": "#D9A27C", "brown": "#AF7350", "deep": "#6F4632"}
HAIR = {"black": "#2B2433", "dark": "#3F2D2A", "brown": "#7A4B32", "auburn": "#A6462B", "blonde": "#E9B651",
        "grey": "#BDB8C8", "pink": "#F08DB8", "blue": "#5978E8"}
#: ready-made people; the same name always gives the same person (use one as the story's protagonist)
CAST = {
    "maya": dict(skin="tan", hair="bun", hair_color="black", top="TEAL", style="tee", bottom="#2F3A66"),
    "leo": dict(skin="light", hair="short", hair_color="brown", top="ORANGE", style="hoodie", bottom="#34416E"),
    "sam": dict(skin="brown", hair="curly", hair_color="black", top="PURPLE", style="shirt", bottom="#5B6178"),
    "ana": dict(skin="fair", hair="long", hair_color="auburn", top="PINK", style="tee", bottom="#3D5A9E"),
    "kai": dict(skin="deep", hair="buzz", hair_color="black", top="GOLD", style="hoodie", bottom="#2D3352"),
    "zoe": dict(skin="light", hair="bob", hair_color="blonde", top="BLUE", style="jacket", bottom="#2E3557"),
    "ravi": dict(skin="tan", hair="side", hair_color="black", top="GREEN", style="shirt", bottom="#40465E", glasses=True),
    "nora": dict(skin="brown", hair="long", hair_color="dark", top="RED", style="jacket", bottom="#2F3A66"),
}

# The body is drawn at a nominal 3.3 units tall (feet at y = 0) and scaled to `height`. Agency
# proportions: a big friendly head (about a third of the height), short legs, round hands.
_H0 = 3.3
_HIP = 1.02        # top of the legs
_SH = 1.8          # shoulder height
_SX = 0.37         # shoulder x
_HEAD_Y = 2.47     # head centre
_HEAD_R = 0.52

# Arm poses: (elbow, hand) relative to each shoulder for the screen-left arm "L" and the
# screen-right arm "R"; "look" is where the eyes go; "finger" adds a pointing finger; "hold" is the
# hand a held prop sits in.
POSES = {
    "stand":     {"L": ((-0.09, -0.4), (-0.07, -0.8)), "R": ((0.09, -0.4), (0.07, -0.8)), "look": (0, 0)},
    "point":     {"L": ((-0.09, -0.4), (-0.07, -0.8)), "R": ((0.36, 0.12), (0.74, 0.3)), "look": (1, 0.3), "finger": "R"},
    "point_left": {"L": ((-0.36, 0.12), (-0.74, 0.3)), "R": ((0.09, -0.4), (0.07, -0.8)), "look": (-1, 0.3), "finger": "L"},
    "think":     {"L": ((0.04, -0.4), (0.68, -0.42)), "R": ((0.13, -0.4), (-0.24, 0.16)), "look": (0.6, 0.8)},
    "type":      {"L": ((-0.2, -0.36), (0.12, -0.54)), "R": ((0.2, -0.36), (-0.12, -0.54)), "look": (0, -0.6)},
    "phone":     {"L": ((-0.09, -0.4), (-0.07, -0.8)), "R": ((0.08, -0.4), (-0.2, -0.12)), "look": (0.2, -0.8), "hold": "R"},
    "celebrate": {"L": ((-0.32, 0.36), (-0.5, 0.78)), "R": ((0.32, 0.36), (0.5, 0.78)), "look": (0, 0.5)},
    "wave":      {"L": ((-0.09, -0.4), (-0.07, -0.8)), "R": ((0.42, 0.06), (0.47, 0.52)), "look": (0.3, 0.2)},
    "shrug":     {"L": ((-0.3, -0.34), (-0.56, -0.06)), "R": ((0.3, -0.34), (0.56, -0.06)), "look": (0, 0.2)},
    "hold":      {"L": ((-0.16, -0.4), (0.16, -0.5)), "R": ((0.16, -0.4), (-0.16, -0.5)), "look": (0, -0.4), "hold": "R"},
    "present":   {"L": ((-0.09, -0.4), (-0.07, -0.8)), "R": ((0.34, -0.22), (0.72, -0.08)), "look": (1, 0), "finger": None},
}
for _a, _b in (("standing", "stand"), ("pointing", "point"), ("thinking", "think"), ("laptop", "type"),
               ("typing", "type"), ("celebrating", "celebrate"), ("holding_phone", "phone"), ("waving", "wave")):
    POSES[_a] = POSES[_b]

# Faces: brows (angle, lift), eyes (height scale), mouth ((upper), (lower), half-width); each lip
# edge is y = o + k * (x/w)^2 + e * sqrt(1 - (x/w)^2), so every mouth has the same points and
# interpolates cleanly.
FACES = {
    "neutral":   {"brow": (0.0, 0.0), "eye": 1.0, "mouth": ((0.014, 0.0, 0.0), (-0.014, 0.0, 0.0), 0.08)},
    "happy":     {"brow": (0.08, 0.02), "eye": 1.0, "mouth": ((0.0, 0.035, 0.0), (-0.085, 0.12, 0.0), 0.12)},
    "joy":       {"brow": (0.12, 0.06), "eye": 0.55, "mouth": ((0.008, 0.035, 0.0), (-0.16, 0.19, 0.0), 0.145)},
    "worried":   {"brow": (-0.34, 0.03), "eye": 1.05, "mouth": ((-0.012, -0.045, 0.0), (-0.034, -0.04, 0.0), 0.085)},
    "sad":       {"brow": (-0.3, -0.01), "eye": 0.9, "mouth": ((-0.01, -0.06, 0.0), (-0.036, -0.055, 0.0), 0.09)},
    "surprised": {"brow": (0.05, 0.1), "eye": 1.25, "mouth": ((0.0, 0.0, 0.055), (0.0, 0.0, -0.065), 0.06)},
    "thinking":  {"brow": (0.2, 0.05), "eye": 0.9, "mouth": ((0.0, -0.012, 0.0), (-0.022, 0.0, 0.0), 0.07), "mouth_x": 0.06},
    "determined": {"brow": (-0.2, -0.02), "eye": 0.85, "mouth": ((0.0, 0.025, 0.0), (-0.045, 0.06, 0.0), 0.1)},
}
for _a, _b in (("smile", "happy"), ("worry", "worried"), ("think", "thinking"), ("excited", "joy"), ("confused", "thinking")):
    FACES[_a] = FACES[_b]


def _bez(corners: np.ndarray) -> np.ndarray:
    """Corner points → the bezier point array a polyline VMobject stores."""
    m = VMobject()
    m.set_points_as_corners(corners)
    return m.points


def _mouth_pts(spec, n: int = 14):
    (ou, ku, eu), (ol, kl, el), w = spec
    xs = np.linspace(-w, w, n)
    up = [(x, ou + ku * (x / w) ** 2 + eu * math.sqrt(max(0.0, 1 - (x / w) ** 2))) for x in xs]
    lo = [(x, ol + kl * (x / w) ** 2 + el * math.sqrt(max(0.0, 1 - (x / w) ** 2))) for x in xs[::-1]]
    pts = up + lo + [up[0]]
    out = np.zeros((len(pts), 3))
    out[:, :2] = pts
    return out


class Character(VGroup):
    """A flat illustrated person, front view, feet at the bottom. Build once (in shared.py) and use
    the same parameters in every scene, or use cast("maya"). Parts: .body, .head, .face, .eyes,
    .mouth, .arms; poses with .to_pose(name), faces with .to_face(name), glances with .look(dir);
    blinks and breathes by itself (idle life drawn by the camera)."""

    def __init__(self, skin: str = "tan", hair: str = "short", hair_color: str = "black", top="TEAL",
                 style: str = "tee", bottom="#2F3A66", shoes: str = "#FFFFFF", glasses: bool = False,
                 height: float | None = None, pose: str = "stand", face: str = "happy", name: str = "",
                 life: bool = True, **kw):
        super().__init__(**kw)
        self.ww_name = name
        self.skin = SKIN.get(skin, skin)
        self.skin_sh = shade(self.skin, 0.14)
        self.hair_col = HAIR.get(hair_color, hair_color)
        self.top_col = _c(top)
        self.bottom_col = _c(bottom)
        self.style_ = style
        self.hair_style = hair
        self._pose = pose if pose in POSES else "stand"
        self._face = face if face in FACES else "happy"
        self.held = None
        P = POSES[self._pose]
        self._joints = {k: [np.array(P[k][0], dtype=float), np.array(P[k][1], dtype=float)] for k in ("L", "R")}
        self._look = np.array(P["look"], dtype=float)
        self._eye_k = 1.0

        sk, top_c, bot, hc = self.skin, self.top_col, self.bottom_col, self.hair_col
        self.shadow = soft_shadow(1.45, 0.24, 0.28).move_to([0, 0.03, 0])
        # hair that sits behind the head and body
        self.back_hair = VGroup()
        if hair == "long":
            self.back_hair.add(_filled(_U(Circle(_HEAD_R * 1.08).move_to([0, _HEAD_Y + 0.04, 0]),
                                             RoundedRectangle(corner_radius=0.3, width=_HEAD_R * 2.2, height=1.05).move_to([0, _HEAD_Y - 0.42, 0])), hc))
        elif hair == "bob":
            self.back_hair.add(_filled(_U(Circle(_HEAD_R * 1.1).move_to([0, _HEAD_Y + 0.05, 0]),
                                             RoundedRectangle(corner_radius=0.22, width=_HEAD_R * 2.25, height=0.7).move_to([0, _HEAD_Y - 0.18, 0])), hc))
        elif hair == "curly":
            puffs = [Circle(0.25).move_to([_HEAD_R * 1.0 * math.cos(a), _HEAD_Y + 0.08 + _HEAD_R * 0.98 * math.sin(a), 0])
                     for a in np.linspace(-0.35, PI + 0.35, 9)]
            self.back_hair.add(_filled(_U(*puffs, Circle(_HEAD_R * 1.08).move_to([0, _HEAD_Y + 0.1, 0])), hc))
        elif hair == "bun":
            self.back_hair.add(_filled(Circle(0.23), hc).move_to([0.0, _HEAD_Y + _HEAD_R + 0.12, 0]))
        if style == "hoodie":  # the hood behind the neck
            self.back_hair.add(rrect(0.8, 0.34, 0.16, shade(top_c, 0.16)).move_to([0, _SH + 0.05, 0]))
        # legs + shoes
        self.legs = VGroup(capsule([-0.16, _HIP], [-0.165, 0.2], 0.155, 0.14, color=bot),
                           capsule([0.16, _HIP], [0.165, 0.2], 0.155, 0.14, color=bot))
        crotch = rrect(0.62, 0.3, 0.12, bot).move_to([0, _HIP - 0.05, 0])
        self.legs.add(crotch)
        sh_c = _c(shoes)
        self.shoes = VGroup()
        for x in (-0.18, 0.18):
            sgn = 1 if x > 0 else -1
            shoe = _filled(_U(Circle(0.15).move_to([x, 0.15, 0]),
                                 RoundedRectangle(corner_radius=0.08, width=0.4, height=0.17).move_to([x + 0.06 * sgn, 0.085, 0])), sh_c)
            sole = rrect(0.42, 0.05, 0.025, shade(sh_c, 0.22)).move_to([x + 0.06 * sgn, 0.025, 0])
            self.shoes.add(VGroup(shoe, sole))
        # torso
        tor = _filled(Polygon([-0.43, _SH + 0.06, 0], [0.43, _SH + 0.06, 0], [0.39, _HIP - 0.02, 0], [-0.39, _HIP - 0.02, 0]),
                      top_c).round_corners(0.2)
        self.torso = VGroup(tor)
        s = side_shade(tor, amount=0.15)
        if s is not None:
            self.torso.add(s)
        if style == "hoodie":
            self.torso.add(rrect(0.48, 0.2, 0.09, shade(top_c, 0.1)).move_to([0, _HIP + 0.22, 0]),
                           capsule([-0.08, _SH - 0.04], [-0.1, _SH - 0.32], 0.024, color=tint(top_c, 0.55)),
                           capsule([0.08, _SH - 0.04], [0.1, _SH - 0.32], 0.024, color=tint(top_c, 0.55)))
        elif style == "shirt":
            self.torso.add(_filled(Polygon([-0.17, _SH + 0.07, 0], [0.17, _SH + 0.07, 0], [0, _SH - 0.2, 0]), tint(top_c, 0.6)),
                           *[_filled(Circle(0.028), shade(top_c, 0.3)).move_to([0, y, 0]) for y in (_SH - 0.32, _SH - 0.5, _SH - 0.68)])
        elif style == "jacket":
            self.torso.add(_filled(Polygon([-0.19, _SH + 0.07, 0], [0.19, _SH + 0.07, 0], [0.12, _HIP + 0.02, 0], [-0.12, _HIP + 0.02, 0]), "#FFFFFF"),
                           _filled(Polygon([-0.19, _SH + 0.07, 0], [-0.03, _SH - 0.42, 0], [-0.15, _SH - 0.52, 0], [-0.3, _SH - 0.04, 0]), shade(top_c, 0.15)),
                           _filled(Polygon([0.19, _SH + 0.07, 0], [0.03, _SH - 0.42, 0], [0.15, _SH - 0.52, 0], [0.3, _SH - 0.04, 0]), shade(top_c, 0.15)))
        else:  # tee: a collar
            self.torso.add(_filled(Ellipse(width=0.3, height=0.13), shade(top_c, 0.16)).move_to([0, _SH + 0.04, 0]))
        # neck + head
        self.neck = VGroup(rrect(0.2, 0.32, 0.08, sk).move_to([0, _SH + 0.1, 0]),
                           _filled(Ellipse(width=0.24, height=0.1), self.skin_sh).move_to([0, _SH + 0.19, 0]))
        ears = VGroup(*[_filled(Circle(0.1), sk).move_to([x, _HEAD_Y - 0.04, 0]) for x in (-_HEAD_R + 0.02, _HEAD_R - 0.02)])
        skull = _filled(Ellipse(width=_HEAD_R * 2, height=_HEAD_R * 2.04), sk).move_to([0, _HEAD_Y, 0])
        self.head = VGroup(ears, skull)
        hs = side_shade(skull, self.skin_sh, amount=0.08)
        if hs is not None:
            self.head.add(hs)
        # face
        self.eyes = VGroup(*[VGroup(_filled(Ellipse(width=0.1, height=0.13), "#2A2236"),
                                    _filled(Circle(0.02), "#FFFFFF").shift([0.017, 0.026, 0])).move_to([x, _HEAD_Y + 0.0, 0])
                             for x in (-0.18, 0.18)])
        brow_c = shade(hc, 0.1) if hair not in ("buzz",) and _lum(hc) < 0.45 else shade(hc, 0.35)
        self.brows = VGroup(*[capsule([x - 0.075, _HEAD_Y + 0.19], [x + 0.075, _HEAD_Y + 0.19], 0.024, color=brow_c) for x in (-0.18, 0.18)])
        self.mouth = VMobject()
        self.mouth.set_points_as_corners(_mouth_pts(FACES[self._face]["mouth"]))
        _filled(self.mouth, "#5A2A3A")
        self.cheeks = VGroup(*[_filled(Circle(0.075), "#FF8FA0", 0.32).move_to([x, _HEAD_Y - 0.15, 0]) for x in (-0.3, 0.3)])
        self.nose = _filled(Ellipse(width=0.08, height=0.055), self.skin_sh).move_to([0, _HEAD_Y - 0.1, 0])
        self.face = VGroup(self.cheeks, self.nose, self.eyes, self.brows, self.mouth)
        if glasses:
            gl = VGroup(*[Circle(0.135, stroke_color="#2A2236", stroke_width=4, fill_color="#FFFFFF", fill_opacity=0.15).move_to([x, _HEAD_Y, 0]) for x in (-0.18, 0.18)],
                        rrect(0.1, 0.024, 0.012, "#2A2236").move_to([0, _HEAD_Y + 0.02, 0]))
            self.face.add(gl)
        self.hair = self._front_hair(hair, hc)
        # arms (rebuilt by poses)
        self.arms = VGroup(*[self._arm(side) for side in ("L", "R")])
        # three reference points inside the body: they ride along with any move/scale/flip, so the
        # pose builder can map nominal coordinates to wherever the character is now
        self._refs = VGroup(VectorizedPoint([0, 1.5, 0]), VectorizedPoint([0.3, 1.5, 0]), VectorizedPoint([0, 1.8, 0]))
        self.body = VGroup(self.legs, self.shoes, self.torso)
        self.add(self.shadow, self.back_hair, self.body, self.neck, self.head, self.face, self.hair, self.arms, self._refs)
        self._apply_face(self._face)
        self._apply_look(self._look)
        if height is None:
            height = CHAR_H
        self.scale(height / _H0, about_point=ORIGIN)
        if life:
            k = sum(map(ord, name or (str(skin) + str(hair))))
            idle(self.eyes, "blink", 0.13, 3.4 + (k % 7) * 0.31, phase=(k % 11) * 0.37)
            idle(self, "breathe", 0.008, 3.6, phase=(k % 5) * 0.9)

    # ---- geometry
    def _front_hair(self, hair, hc):
        g = VGroup()
        R, Y = _HEAD_R, _HEAD_Y
        top_arc = [np.array([R * 1.05 * math.cos(a), Y + 0.02 + R * 1.07 * math.sin(a), 0]) for a in np.linspace(0.08, PI - 0.08, 13)]
        fy = Y + 0.24
        shapes = {
            "short": [(-R * 1.0, Y + 0.08), (-0.26, fy + 0.02), (0.02, fy - 0.03), (0.22, fy + 0.04), (R * 1.0, Y + 0.08)],
            "side": [(-R * 0.98, Y + 0.12), (-0.2, fy - 0.03), (0.3, fy + 0.1), (R * 1.0, Y + 0.08)],
            "bun": [(-R * 1.0, Y + 0.12), (-0.15, fy + 0.03), (0.2, fy + 0.03), (R * 1.0, Y + 0.12)],
            "long": [(-R * 1.06, Y - 0.2), (-0.26, fy - 0.02), (0.06, fy + 0.08), (0.34, fy - 0.03), (R * 1.06, Y - 0.2)],
            "bob": [(-R * 1.08, Y - 0.12), (-0.3, fy - 0.06), (0.0, fy - 0.08), (0.3, fy - 0.06), (R * 1.08, Y - 0.12)],
        }
        if hair in shapes:
            fr = [np.array([x, y, 0]) for x, y in shapes[hair]]
            shape = VMobject()
            shape.set_points_smoothly([*top_arc, *fr, top_arc[0]])
            g.add(_filled(shape, hc))
            r = rim_light(g[0], tint(hc, 0.28), amount=0.05)
            if r is not None:
                g.add(r)
        elif hair == "buzz":
            cap = _I(Ellipse(width=R * 2.06, height=R * 2.1).move_to([0, Y + 0.01, 0]),
                               RoundedRectangle(corner_radius=0.01, width=1.4, height=0.55).move_to([0, Y + R - 0.02, 0]))
            g.add(_filled(cap, hc))
        elif hair == "curly":
            puffs = [Circle(0.17).move_to([x, Y + 0.38 + 0.05 * math.cos(x * 9), 0]) for x in np.linspace(-0.34, 0.34, 5)]
            g.add(_filled(_U(*puffs), hc))
        return g

    def _arm(self, side: str) -> VGroup:
        sgn = -1 if side == "L" else 1
        sh = np.array([sgn * _SX, _SH - 0.04])
        el, hd = self._joints[side]
        el = sh + el
        hd = sh + hd
        sleeve = shade(self.top_col, 0.12)
        fore = self.skin if self.style_ == "tee" else sleeve
        up = capsule(sh, el, 0.13, 0.115, color=sleeve)
        lo = capsule(el, hd, 0.11 if self.style_ == "tee" else 0.115, 0.095, color=fore)
        hand = _filled(Circle(0.11), self.skin).move_to([hd[0], hd[1], 0])
        g = VGroup(up, lo, hand)
        finger = POSES.get(self._pose, {}).get("finger")
        d = (hd - el) / (np.linalg.norm(hd - el) + 1e-6)
        fpts = _capsule_pts(hd, hd + 0.17 * d, 0.042, 0.036, 10) if finger == side else _capsule_pts(hd, hd + 0.001 * d, 0.001, 0.001, 10)
        f = VMobject()
        f.set_points_as_corners(fpts)
        g.add(_filled(f, self.skin))
        return g

    def _to_world(self):
        o = self._refs[0].get_center()[:2]
        ex = (self._refs[1].get_center()[:2] - o) / 0.3
        ey = (self._refs[2].get_center()[:2] - o) / 0.3
        M = np.stack([ex, ey], axis=1)
        o0 = o - M @ np.array([0, 1.5])
        return M, o0

    def _rebuild_arms(self):
        M, o = self._to_world()
        for i, side in enumerate(("L", "R")):
            new = self._arm(side)
            for dst, src in zip(self.arms[i], new):
                pts = src.points.copy()
                pts[:, :2] = pts[:, :2] @ M.T + o
                dst.points = pts
        if self.held is not None:
            self.held.move_to(self.hand_point(POSES[self._pose].get("hold") or "R") + UP * self.held.height * 0.22)

    def _apply_face(self, name):
        f = FACES[name] if isinstance(name, str) else name
        M, o = self._to_world()
        ang, lift = f["brow"]
        for k, b in enumerate(self.brows):
            sgn = -1 if k == 0 else 1
            c = np.array([sgn * 0.18, _HEAD_Y + 0.2 + lift])
            d = np.array([math.cos(ang * sgn), math.sin(ang * sgn)]) * 0.075
            pts = _capsule_pts(c - d, c + d, 0.024, 0.024, 10)
            pts[:, :2] = pts[:, :2] @ M.T + o
            b.points = _bez(pts)
        pts = _mouth_pts(f["mouth"])
        pts[:, 0] += f.get("mouth_x", 0.0)
        pts[:, 1] += _HEAD_Y - 0.26
        pts[:, :2] = pts[:, :2] @ M.T + o
        self.mouth.points = _bez(pts)
        self._eye_k = f["eye"]

    def _apply_look(self, look):
        M, o = self._to_world()
        sy = float(np.linalg.norm(M[:, 1]))
        for k, e in enumerate(self.eyes):
            x = (-0.18 if k == 0 else 0.18) + 0.04 * look[0]
            y = _HEAD_Y + 0.0 + 0.035 * look[1]
            target = M @ np.array([x, y]) + o
            want = 0.13 * self._eye_k * sy
            cur = e[0].height
            if cur > 1e-6 and abs(cur - want) > 1e-5:
                e[0].stretch(want / cur, 1)
            e.move_to([target[0], target[1], 0])

    # ---- helpers for placing things
    def stand(self, x: float = 0.0, y: float | None = None) -> "Character":
        """Put the feet on the ground line at x (returns self)."""
        y = GROUND_Y if y is None else y
        M, o = self._to_world()
        self.shift(np.array([x - o[0], y - o[1], 0]))
        return self

    def head_point(self):
        """The top of the head, on screen-free world coordinates (for bubbles)."""
        M, o = self._to_world()
        p = M @ np.array([0, _HEAD_Y + _HEAD_R]) + o
        return np.array([p[0], p[1], 0])

    def hand_point(self, side: str = "R"):
        M, o = self._to_world()
        sgn = -1 if side == "L" else 1
        sh = np.array([sgn * _SX, _SH - 0.04])
        p = M @ (sh + self._joints[side][1]) + o
        return np.array([p[0], p[1], 0])

    def _fit_held(self, mob: Mobject):
        M, _ = self._to_world()
        cap = 0.62 * float(np.linalg.norm(M[:, 1]))  # a phone is about a fifth of the body
        if mob.height > cap:
            mob.scale_to_fit_height(cap)

    def hold(self, mob: Mobject, side: str = "R") -> "Character":
        """Put a prop in a hand now; it follows the hand through pose changes."""
        self._fit_held(mob)
        self.held = mob
        mob.move_to(self.hand_point(side) + UP * mob.height * 0.22)
        self._insert_held(mob)
        return self

    def _insert_held(self, mob):
        # behind the arms, so the hand grips the prop instead of floating behind it
        if mob in self.submobjects:
            self.remove(mob)
        self.insert(self.submobjects.index(self.arms), mob)

    # ---- animations
    def to_pose(self, name: str, run_time: float = 0.45, hold: Mobject | None = None) -> Animation:
        """Animate to a pose: stand, point, point_left, think, type, phone, celebrate, wave, shrug,
        hold, present. hold=a prop puts it in the holding hand (a phone, a card, a coin)."""
        if name not in POSES:
            raise ValueError(f"unknown pose '{name}' (one of {', '.join(sorted(POSES))})")
        P = POSES[name]
        char = self
        start = {k: [v[0].copy(), v[1].copy()] for k, v in self._joints.items()}
        end = {k: [np.array(P[k][0], dtype=float), np.array(P[k][1], dtype=float)] for k in ("L", "R")}
        look0, look1 = self._look.copy(), np.array(P["look"], dtype=float)
        if hold is not None and char.held is not hold:
            char._fit_held(hold)
            char.held = hold
            char._insert_held(hold)

        class _Pose(Animation):
            def __init__(s, **kw):
                super().__init__(char, run_time=run_time, rate_func=lambda t: t, **kw)
                s.ww_kind = "pose"

            def begin(s):
                char._pose = name
                super().begin()

            def interpolate_mobject(s, alpha):
                e = back_out(_clamp01(alpha), 1.1)
                for k in ("L", "R"):
                    char._joints[k] = [start[k][j] + (end[k][j] - start[k][j]) * e for j in (0, 1)]
                char._look = look0 + (look1 - look0) * glide(_clamp01(alpha))
                char._rebuild_arms()
                char._apply_look(char._look)

            def create_starting_mobject(s):
                return VGroup()

            def get_all_families_zipped(s):
                return []

        return _Pose()

    def to_face(self, name: str, run_time: float = 0.3) -> Animation:
        """Animate to a face: neutral, happy, joy, worried, sad, surprised, thinking, determined."""
        if name not in FACES:
            raise ValueError(f"unknown face '{name}' (one of {', '.join(sorted(FACES))})")
        char = self
        f0, f1 = FACES[self._face], FACES[name]
        m0 = np.array(f0["mouth"][0] + f0["mouth"][1] + (f0["mouth"][2], f0.get("mouth_x", 0.0)), dtype=float)
        m1 = np.array(f1["mouth"][0] + f1["mouth"][1] + (f1["mouth"][2], f1.get("mouth_x", 0.0)), dtype=float)
        b0, b1 = np.array(f0["brow"]), np.array(f1["brow"])
        e0, e1 = f0["eye"], f1["eye"]

        class _Face(Animation):
            def __init__(s, **kw):
                super().__init__(char, run_time=run_time, rate_func=lambda t: t, **kw)
                s.ww_kind = "pose"

            def begin(s):
                char._face = name
                super().begin()

            def interpolate_mobject(s, alpha):
                e = glide(_clamp01(alpha))
                m = m0 + (m1 - m0) * e
                char._apply_face({"brow": tuple(b0 + (b1 - b0) * e), "eye": e0 + (e1 - e0) * e,
                                  "mouth": (tuple(m[0:3]), tuple(m[3:6]), m[6]), "mouth_x": m[7]})
                char._apply_look(char._look)

            def create_starting_mobject(s):
                return VGroup()

            def get_all_families_zipped(s):
                return []

        return _Face()

    def look(self, direction=(1, 0), run_time: float = 0.3) -> Animation:
        """Glance (the eyes move): (1, 0) right, (-1, 0) left, (0, 1) up, (0, -1) down."""
        char = self
        l0, l1 = self._look.copy(), np.array(direction, dtype=float)[:2]

        class _Look(Animation):
            def __init__(s, **kw):
                super().__init__(char, run_time=run_time, rate_func=lambda t: t, **kw)
                s.ww_kind = "pose"

            def interpolate_mobject(s, alpha):
                char._look = l0 + (l1 - l0) * glide(_clamp01(alpha))
                char._apply_look(char._look)

            def create_starting_mobject(s):
                return VGroup()

            def get_all_families_zipped(s):
                return []

        return _Look()


def cast(name: str, **overrides) -> Character:
    """A ready-made person from CAST (maya, leo, sam, ana, kai, zoe, ravi, nora): the same name gives
    the same look in every scene, so a protagonist stays recognisable. Overrides: pose, face,
    height, top, ..."""
    spec = dict(CAST.get(name.lower(), CAST["maya"]))
    spec.update(overrides)
    return Character(name=name.lower(), **spec)


# --------------------------------------------------------------------------- backdrops

BACKDROPS = ("outdoors", "city", "room", "office", "plain")


class Stage(dict):
    """What a backdrop put on screen, by name (stage["far"], stage["clouds"], ...)."""

    def all(self):
        return [m for v in self.values() for m in (v if isinstance(v, list) else [v])]


def _grain(h, w, rng, amt=1.4):
    return (rng.random((h, w, 1)).astype(np.float32) - 0.5) * amt


def paint_backdrop(kind: str, w: int, h: int, frame_w: float, seed: int = 3) -> np.ndarray:
    """The static far-away part (sky, or the room's wall), painted once into the camera's
    background: RGBA uint8 (h, w, 4)."""
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]

    def rgb(hx):
        hx = hx.lstrip("#")
        return np.array([int(hx[i:i + 2], 16) for i in (0, 2, 4)], np.float32)

    if kind in ("outdoors", "city"):
        top, mid, hor = (rgb(c) for c in WORLD["sky"])
        hy = 0.5 - (HORIZON_Y / FRAME_H)  # horizon position from the top, 0..1
        k = np.clip(y / max(hy, 0.05), 0, 1)
        img = np.where(k < 0.6, top + (mid - top) * (k / 0.6), mid + (hor - mid) * ((k - 0.6) / 0.4))
        img = np.broadcast_to(img, (h, w, 3)).copy()
        # warm glow around the sun (upper right)
        sx, sy = 0.5 + SUN_POS[0] / FRAME_W, 0.5 - SUN_POS[1] / FRAME_H
        aspect = w / h
        d = np.sqrt(((x - sx) * aspect) ** 2 + (y - sy) ** 2)
        g = np.exp(-(d / 0.35) ** 2)
        img += (rgb(WORLD["sun"]) - img) * (g * 0.35)
    elif kind in ("room", "office"):
        a, b = (rgb(c) for c in (WORLD["wall"] if kind == "room" else WORLD["owall"]))
        img = np.broadcast_to(a + (b - a) * y, (h, w, 3)).copy()
        aspect = w / h
        d = np.sqrt(((x - 0.5) * aspect) ** 2 + (y - 0.42) ** 2)
        img += (np.array([255, 255, 255], np.float32) - img) * (np.exp(-(d / 0.55) ** 2) * 0.18)
    else:
        a, b = (rgb(c) for c in WORLD["plain"])
        aspect = w / h
        d = np.sqrt(((x - 0.5) * aspect) ** 2 + (y - 0.45) ** 2)
        img = a + (b - a) * np.clip(d / 0.9, 0, 1)
        img = np.broadcast_to(img, (h, w, 3)).copy()
    img += _grain(h, w, rng)
    out = np.empty((h, w, 4), np.uint8)
    out[..., :3] = np.clip(img + 0.5, 0, 255).astype(np.uint8)
    out[..., 3] = 255
    return out


def _ground(gw: float, gy: float, seed: int = 5) -> VGroup:
    """The ground the characters stand on: a wide, gently curved plane with a soft gradient (lighter
    toward the horizon), a light lip, and a few grass tufts merged into one shape."""
    rng = np.random.default_rng(seed + 11)
    top = gy + 0.3
    n = 24
    pts = [[-gw / 2 + gw * i / n, top + 0.18 * math.sin(PI * i / n) + 0.05 * math.sin(i * 1.7), 0] for i in range(n + 1)]
    bottom = -FRAME_H / 2 - 2.0
    pts += [[gw / 2, bottom, 0], [-gw / 2, bottom, 0]]
    m = VMobject()
    m.set_points_as_corners([np.array(p) for p in pts] + [np.array(pts[0])])
    _filled(m, WORLD["ground"])
    m.set_fill([WORLD["ground_lip"], WORLD["ground"], shade(WORLD["ground"], 0.08)], opacity=1)
    m.set_sheen_direction(DOWN)
    g = VGroup(m)
    lip = _offset_diff(m, (0, -0.1), tint(WORLD["ground_lip"], 0.25))
    if lip is not None:
        g.add(lip)
    tufts = []
    for k in range(9):
        x = rng.uniform(-FRAME_W * 0.55, FRAME_W * 0.55)
        y = rng.uniform(bottom * 0.0 + gy - by_aspect(1.6, 2.6), gy - 0.25)
        s = rng.uniform(0.14, 0.24)
        for a, l in ((-0.5, 0.8), (0.0, 1.0), (0.5, 0.75)):
            tufts.append(Polygon([x - s * 0.18, y, 0], [x + s * 0.18, y, 0],
                                 [x + s * l * math.sin(a), y + s * l * 1.6 * math.cos(a), 0]))
    try:
        g.add(_filled(_U(*tufts), shade(WORLD["ground"], 0.14)))
    except Exception:
        pass
    return g


def _hedge(width: float, seed: int, planters: bool) -> VGroup:
    """Foreground for the near layer: LOW things along the bottom edge (bushes, planters), so a
    camera move sweeps them past without ever covering the characters and props."""
    rng = np.random.default_rng(seed + 3)
    g = VGroup()
    x = -width / 2 + rng.uniform(0, 2)
    bottom = -FRAME_H / 2
    while x < width / 2:
        b = bush(rng.uniform(1.5, 2.2) * by_aspect(1.0, 0.9))
        if planters:
            box = rrect(b.width * 0.9, 0.5, 0.08, shade(WORLD["walk"], 0.18))
            b.next_to(box, UP, buff=-0.25)
            item = VGroup(b, box).move_to([x, bottom - 0.12, 0], aligned_edge=DOWN)
        else:
            item = b.move_to([x, bottom - 0.3, 0], aligned_edge=DOWN)
        idle(item, "sway", 0.012, 4.5 + rng.uniform(0, 2))
        g.add(item)
        x += rng.uniform(5.5, 8.5)
    return g


def _bleed_w(depth: float, pan: float = 6.0) -> float:
    return FRAME_W + 2 * (pan * depth + 2.0)


def backdrop(kind: str = "outdoors", sun: bool = True, clouds: int = 3, foreground: bool = True,
             seed: int = 5, pan: float = 6.0) -> Stage:
    """The scenery for a backdrop (everything but the painted sky/wall), already in its layers.
    WaitwhatScene25D.set_backdrop() adds it; call this directly only to build a custom stage."""
    rng = np.random.default_rng(seed)
    st = Stage()
    W = FRAME_W
    gy = GROUND_Y
    if kind in ("outdoors", "city"):
        if sun and not (kind == "city" and IS_DUSK):
            sx, sy = SUN_POS
            s = VGroup(glow(1.7, WORLD["sun"], 0.5 if not IS_DUSK else 0.6), _filled(Circle(0.6), WORLD["sun"]),
                       _filled(Circle(0.6), tint(WORLD["sun"], 0.35)).scale(0.72).shift(UL * 0.06))
            s.move_to([sx, sy, 0])
            st["sun"] = layer(s, "sky", depth=0.03)
        cl = []
        spots_ = by_aspect([(-0.36, 0.95), (-0.04, 1.75), (0.42, 2.3)], [(-0.28, 1.1), (0.05, 3.2), (0.4, 4.6)])
        for i in range(clouds):
            fx, fy = spots_[i % len(spots_)]
            c = cloud(rng.uniform(1.7, 2.5) * by_aspect(1.0, 0.85), opacity=0.96 if not IS_DUSK else 0.55)
            c.move_to([fx * W + rng.uniform(-0.3, 0.3), _ws.SAFE_TOP - fy + rng.uniform(-0.2, 0.2), 0])
            layer(c, "far", depth=0.08 + 0.05 * i)
            idle(c, "drift", 0.35, 11 + 3 * i)
            cl.append(c)
        st["clouds"] = cl
    if kind == "outdoors":
        bw = _bleed_w(0.2, pan)
        far = VGroup(hill(bw * 0.55, 1.5, haze(WORLD["hill_far"], 0.25), at=[-bw * 0.22, HORIZON_Y - 0.5, 0], lip=False),
                     hill(bw * 0.6, 1.9, haze(WORLD["hill_far"], 0.1), at=[bw * 0.2, HORIZON_Y - 0.55, 0], lip=False))
        st["far"] = layer(far, "far")
        bw = _bleed_w(0.5, pan)
        midh = hill(bw * 0.7, 1.55, WORLD["hill_mid"], at=[-bw * 0.12, (HORIZON_Y + gy) / 2 - 0.7, 0])
        midh2 = hill(bw * 0.55, 1.2, shade(WORLD["hill_mid"], 0.06), at=[bw * 0.3, (HORIZON_Y + gy) / 2 - 0.75, 0])
        trees = VGroup()
        for i, x in enumerate(np.linspace(-W * 0.62, W * 0.62, 6 if not IS_VERTICAL else 4)):
            t = (tree if i % 2 else pine)(rng.uniform(1.0, 1.5), color=haze(WORLD["tree"], 0.12))
            t.move_to([x + rng.uniform(-0.5, 0.5), (HORIZON_Y + gy) / 2 + 0.2 + rng.uniform(-0.15, 0.25), 0], aligned_edge=DOWN)
            idle(t, "sway", 0.012, 5 + i)
            trees.add(t)
        st["mid"] = layer(VGroup(midh2, midh, trees), "mid")
        gw = _bleed_w(1.0, pan)
        st["ground"] = layer(_ground(gw, gy, seed), "main")
        st["ground"].set_z_index(_Z["main"] - 5, family=True)
        st["ground"].ww_z = _Z["main"] - 5
        if foreground:
            st["near"] = layer(_hedge(_bleed_w(1.5, pan), seed, planters=False), "near")
    elif kind == "city":
        bw = _bleed_w(0.18, pan)
        far = VGroup(skyline(bw, by_aspect(2.6, 3.4), haze(WORLD["far_city"], 0.2), seed=seed),
                     skyline(bw, by_aspect(1.8, 2.4), WORLD["far_city"], seed=seed + 1))
        far[0].move_to([0, HORIZON_Y - 0.3, 0], aligned_edge=DOWN)
        far[1].move_to([0.7, HORIZON_Y - 0.5, 0], aligned_edge=DOWN)
        st["far"] = layer(far, "far")
        bw = _bleed_w(0.5, pan)
        blds = VGroup()
        x = -bw / 2
        i = 0
        while x < bw / 2:
            wdt = rng.uniform(1.3, 2.1)
            hgt = rng.uniform(1.8, by_aspect(3.4, 4.4))
            b = building(wdt, hgt, color=haze(WORLD["bld"][(seed + i) % len(WORLD["bld"])], 0.3), seed=seed + i,
                         lit=0.18 if not IS_DUSK else 0.45)
            b.move_to([x + wdt / 2, gy + 0.65, 0], aligned_edge=DOWN)
            blds.add(b)
            x += wdt + rng.uniform(0.15, 0.5)
            i += 1
        st["mid"] = layer(blds, "mid")
        gw = _bleed_w(1.0, pan)
        walk_ = rrect(gw, 1.25, 0.02, WORLD["walk"]).move_to([0, gy + 0.1, 0])
        walk_.set_fill([tint(WORLD["walk"], 0.2), WORLD["walk"]], opacity=1)
        walk_.set_sheen_direction(DOWN)
        curb = rrect(gw, 0.14, 0.02, shade(WORLD["walk"], 0.12)).move_to([0, gy - 0.55, 0])
        road = rrect(gw, FRAME_H, 0.02, WORLD["street"]).move_to([0, gy - 0.6 - FRAME_H / 2, 0])
        lanes = merge(*[RoundedRectangle(corner_radius=0.04, width=0.9, height=0.08).move_to([x, gy - by_aspect(1.4, 1.9), 0])
                        for x in np.arange(-gw / 2, gw / 2, 2.0)], color=tint(WORLD["street"], 0.5))
        st["ground"] = layer(VGroup(road, lanes, curb, walk_), "main")
        st["ground"].set_z_index(_Z["main"] - 5, family=True)
        st["ground"].ww_z = _Z["main"] - 5
        if foreground:
            st["near"] = layer(_hedge(_bleed_w(1.5, pan), seed, planters=True), "near")
    elif kind in ("room", "office"):
        fy = gy + by_aspect(0.95, 1.4)          # where the back wall meets the floor
        gw = _bleed_w(0.75, pan)
        fl_col = WORLD["floor"] if kind == "room" else WORLD["ofloor"]
        floor = rrect(gw, FRAME_H, 0.02, fl_col).move_to([0, fy - FRAME_H / 2, 0])
        floor.set_fill([fl_col, shade(fl_col, 0.1)], opacity=1)
        floor.set_sheen_direction(DOWN)
        base = rrect(gw, 0.14, 0.02, WORLD["trim"]).move_to([0, fy + 0.07, 0])
        st["floor"] = layer(VGroup(floor, base), "mid", depth=0.75)
        st["floor"].ww_z = _Z["mid"] + 2          # under the rug and everything standing on the floor
        st["floor"].set_z_index(st["floor"].ww_z, family=True)
        decor = VGroup()
        wy = (fy + _ws.SAFE_TOP) / 2 + by_aspect(0.15, 0.4)
        if kind == "room":
            win = window(by_aspect(2.6, 2.4), by_aspect(2.1, 2.4)).move_to([-W * 0.24, wy, 0])
            frame_ = VGroup(rrect(1.3, 1.0, 0.06, "#FFFFFF"), rrect(1.1, 0.8, 0.04, tint(_c("TEAL"), 0.5)),
                            hill(1.0, 0.35, _c("GREEN"), at=[0, -0.4, 0], lip=False)).move_to([W * 0.2, wy + 0.25, 0])
            shelf = VGroup(rrect(2.0, 0.1, 0.03, WORLD["trim"]),
                           plant(0.75).move_to([-0.55, 0.05, 0], aligned_edge=DOWN),
                           VGroup(*[rrect(0.16, 0.5 - 0.06 * i, 0.03, _c(c_)).move_to([0.2 + 0.18 * i, 0.05, 0], aligned_edge=DOWN)
                                    for i, c_ in enumerate(("BLUE", "PINK", "GOLD", "TEAL"))])).move_to([W * 0.22, wy - by_aspect(1.1, 1.5), 0])
            decor.add(win, frame_, shelf)
        else:
            win = window(by_aspect(5.0, 3.6), by_aspect(1.9, 2.3)).move_to([-W * 0.12, wy - 0.1, 0])
            glass = win[2]
            sk = skyline(glass.width * 0.98, glass.height * 0.42, shade(WORLD["far_city"], 0.12), seed=seed + 7)
            sk.stretch_to_fit_width(glass.width * 0.97).move_to(glass.get_bottom() + UP * 0.03, aligned_edge=DOWN)
            win.remove(win[3])
            win.insert(3, sk)
            board = VGroup(rrect(1.7, 1.25, 0.08, "#C99A6E"), rrect(1.55, 1.1, 0.05, "#E2B98F"),
                           *[rrect(0.36, 0.34, 0.04, _c(c_)).move_to([-0.45 + 0.45 * (i % 3), 0.2 - 0.42 * (i // 3), 0]).rotate(0.06 * (i - 2))
                             for i, c_ in enumerate(("YELLOW_SOFT", "PINK", "TEAL", "GOLD", "BLUE"))]).move_to([W * 0.33, wy + 0.1, 0])
            clk = clock(0.42, spin=False).move_to([W * 0.33, wy + by_aspect(1.35, 1.7), 0])
            cab_c = tint(_c("BLUE"), 0.55)
            cab = VGroup(rrect(1.0, 1.5, 0.08, cab_c),
                         *[rrect(0.8, 0.38, 0.05, tint(cab_c, 0.25)).move_to([0, 0.45 - 0.46 * i, 0]) for i in range(3)],
                         *[rrect(0.3, 0.06, 0.03, shade(cab_c, 0.3)).move_to([0, 0.55 - 0.46 * i, 0]) for i in range(3)])
            cab.move_to([-W * 0.42, fy - 0.08, 0], aligned_edge=DOWN)
            decor.add(win, board, clk, cab)
        st["mid"] = layer(decor, "mid", depth=0.6)
        if kind == "room":
            rug = _filled(Ellipse(width=by_aspect(7.0, 6.0), height=by_aspect(1.1, 1.3)), tint(_c("TEAL"), 0.45)).move_to([W * 0.04, gy - 0.15, 0])
            rug_in = _filled(Ellipse(width=rug.width * 0.82, height=rug.height * 0.66), tint(_c("TEAL"), 0.62)).move_to(rug)
            st["rug"] = layer(VGroup(rug, rug_in), "main", depth=0.9)
            st["rug"].ww_z = _Z["main"] - 3
            st["rug"].set_z_index(st["rug"].ww_z, family=True)
            fl = VGroup(rrect(0.08, by_aspect(2.6, 3.2), 0.04, "#7C6A8A"),
                        _filled(Polygon([-0.45, 0, 0], [0.45, 0, 0], [0.28, 0.6, 0], [-0.28, 0.6, 0]), _c("GOLD")).round_corners(0.06))
            fl[1].next_to(fl[0], UP, buff=-0.05)
            fl.add(rrect(0.6, 0.08, 0.04, "#7C6A8A").next_to(fl[0], DOWN, buff=-0.04),
                   glow(0.9, "YELLOW_SOFT", 0.35, at=fl[1].get_center()))
            fl.move_to([W * 0.4, fy - 0.15, 0], aligned_edge=DOWN)
            st["lamp"] = layer(fl, "mid", depth=0.72)
        if foreground:
            p = plant(by_aspect(2.2, 2.6), pot="BLUE" if kind == "office" else "ORANGE").move_to([-W / 2 + 0.35, -FRAME_H / 2 + by_aspect(0.2, 0.6), 0], aligned_edge=DOWN)
            st["near"] = layer(VGroup(p), "near")
    elif kind == "plain":
        blobs = VGroup()
        for i, (fx, fy, r, col) in enumerate(((-0.38, 0.28, 3.2, "BLUE"), (0.36, -0.12, 3.6, "PINK"), (0.05, 0.42, 2.4, "TEAL"))):
            gl = glow(r * by_aspect(1.0, 1.1), col, 0.16 if not IS_DUSK else 0.22, at=[fx * W, fy * FRAME_H, 0])
            idle(gl, "drift", 0.4, 13 + 4 * i)
            blobs.add(gl)
        st["far"] = layer(blobs, "far", depth=0.12)
        dots = VGroup()
        for i in range(10):
            d = _filled(Circle(rng.uniform(0.04, 0.09)), _c(("BLUE", "PINK", "GOLD", "TEAL")[i % 4]), 0.5)
            d.move_to([rng.uniform(-0.48, 0.48) * W, rng.uniform(-0.4, 0.45) * FRAME_H, 0])
            idle(d, "float", 0.06, 3 + i * 0.4)
            dots.add(d)
        st["mid"] = layer(dots, "mid", depth=0.45)
        sh = soft_shadow(by_aspect(9.0, 6.5), 1.0, 0.1).move_to([0, gy, 0])
        st["ground"] = layer(sh, "main")
        st["ground"].set_z_index(_Z["main"] - 5, family=True)
        st["ground"].ww_z = _Z["main"] - 5
    else:
        raise ValueError(f"unknown backdrop '{kind}' (one of {', '.join(BACKDROPS)})")
    return st


# --------------------------------------------------------------------------- the scene

def _kind25(anim) -> str | None:
    k = getattr(anim, "ww_kind", None)
    if k:
        return k
    if isinstance(anim, AnimationGroup):
        kinds = [_kind25(a) for a in anim.animations]
        for want in ("appear", "slide", "burst", "move", "pose"):
            if want in kinds:
                return want
    return None


class WaitwhatScene25D(WaitwhatScene):
    """WaitwhatScene in 2.5D: flat illustrated layers seen through a parallax camera. Narration
    timing, sound cues, aspect and lint as usual; the backdrop is painted and staged in setup."""

    #: the scenery: outdoors | city | room | office | plain (plan scenes[].backdrop overrides it)
    backdrop: str | None = None
    #: draw the backdrop's scenery (hills, buildings, decor) automatically
    auto_backdrop: bool = True
    #: options for the scenery, e.g. {"pan": 12} when the camera will travel 12 units sideways
    #: (the layers are built wide enough), {"clouds": 2}, {"foreground": False}, {"sun": False}
    backdrop_opts: dict = {}
    #: the camera's start zoom (1 = the layout as written)
    start_zoom: float = 1.0

    def __init__(self, **kwargs):
        kwargs.setdefault("camera_class", Camera25D)
        super().__init__(**kwargs)

    def setup(self):
        super().setup()
        cam = self.camera
        self.rig = _Rig(float(SAFE_CENTER[0]), float(SAFE_CENTER[1]), self.start_zoom)
        cam.rig = self.rig
        renderer = self.renderer
        cam.clock = lambda: float(renderer.time)
        cam.roots = lambda: self.mobjects
        self.add(self.rig)
        self.stage = Stage()
        self._fx_on = False
        self._drift_v = None
        self._perf = {"shapes_max": 0, "redraw_s": 0.0, "work": 0.0, "layers": 0}
        sc = next((s for s in (_ws.load_plan(self.ws).get("scenes") or []) if s.get("id") == self.scene_id), None) or {}
        kind = sc.get("backdrop") or self.backdrop or "outdoors"
        self._backdrop_kind = None
        self.set_backdrop(kind, scenery=self.auto_backdrop, **dict(self.backdrop_opts or {}))

    # ---- background + scenery
    def _install_background(self):
        pass  # set_backdrop paints the sky / wall

    def set_backdrop(self, kind: str = "outdoors", scenery: bool = True, **opts) -> Stage:
        """Paint the backdrop's sky or wall and (scenery=True) add its layered scenery. Calling it
        again switches the place (the old scenery is removed). Returns the Stage."""
        if kind not in BACKDROPS:
            logger.warning(f"waitwhat 25d: unknown backdrop '{kind}', using outdoors")
            kind = "outdoors"
        cam = self.camera
        try:
            import hashlib
            seed = int(hashlib.md5(str(_ws.load_plan(self.ws).get("title", "waitwhat")).encode()).hexdigest()[:6], 16) % 1000
            bg = paint_backdrop(kind, cam.pixel_width, cam.pixel_height, cam.frame_width, seed=seed)
            if bg.shape == cam.pixel_array.shape:
                cam.background = bg
                cam.set_pixel_array(bg)
        except Exception as e:  # never let a backdrop break a render
            logger.warning(f"waitwhat 25d: backdrop paint failed: {e}")
        for m in self.stage.all():
            if m in self.mobjects:
                self.remove(m)
        self.stage = Stage()
        if scenery:
            try:
                self.stage = backdrop(kind, **opts)
                self.add(*self.stage.all())
            except Exception as e:
                logger.warning(f"waitwhat 25d: scenery failed ({kind}): {e}")
        self._backdrop_kind = kind
        return self.stage

    def finish(self, tail: float = 0.8, fade: bool = False):
        """Hold until the narration has finished (+tail). fade=True (a cut follows) pops the
        scene's characters, props and labels out over the last 0.5 s and keeps the backdrop."""
        dt = self.narration_end + tail - self.now
        if fade:
            keep = set(map(id, self.stage.all())) | {id(self.rig)}
            out = [m for m in self.mobjects if id(m) not in keep]
            if dt > 0.55:
                self.wait(dt - 0.5)
            if out:
                self.play(*[FadeOut(m) for m in out], run_time=0.5, sfx=False)
        elif dt > 0.02:
            self.wait(dt)
        self._write_report()

    # ---- layers
    def put(self, *mobs, layer_name: str = "main", depth: float | None = None):
        """Tag mobjects with a layer without adding them (pop_in/slide_in add them)."""
        for m in mobs:
            layer(m, layer_name, depth)
        return mobs[0] if len(mobs) == 1 else VGroup(*mobs)

    def place(self, *mobs, layer_name: str = "main", depth: float | None = None):
        """Tag and add at once (things already there when the scene starts)."""
        self.put(*mobs, layer_name=layer_name, depth=depth)
        self.add(*mobs)
        return mobs[0] if len(mobs) == 1 else VGroup(*mobs)

    def hud(self, *mobs):
        """Fixed on the screen and added now (titles, counters)."""
        for m in mobs:
            hud(m)
        self.add(*mobs)
        return mobs[0] if len(mobs) == 1 else VGroup(*mobs)

    # ---- camera
    @property
    def cam_state(self):
        x, y, z = self.rig.points[0]
        return float(x), float(y), float(z)

    def _target(self, to):
        if to is None:
            return None
        if isinstance(to, Mobject):
            c = to.get_center()
            if isinstance(to, Character):
                c = to.get_center() + UP * to.height * 0.12
            return np.array([c[0], c[1]])
        a = np.array(to, dtype=float).reshape(-1)
        return a[:2]

    def camera_move(self, to=None, zoom: float | None = None, by=None, run_time: float = 1.4, ease=None) -> Animation:
        """The camera move as an animation (to combine in one self.play with other things):
        to = a point or mobject the screen centres on; zoom = absolute zoom; by = a relative pan."""
        x, y, z = self.cam_state
        p = np.array([x, y])
        t = self._target(to)
        if t is not None:
            p = t
        if by is not None:
            p = p + np.array(by, dtype=float).reshape(-1)[:2]
        return _CamMove(self.rig, [p[0], p[1], zoom if zoom is not None else z], run_time=run_time, ease=ease)

    def set_camera(self, to=None, zoom: float | None = None):
        """Put the camera somewhere at once (no move): the scene's opening framing."""
        x, y, z = self.cam_state
        t = self._target(to)
        if t is not None:
            x, y = float(t[0]), float(t[1])
        self.rig.points[0] = [x, y, z if zoom is None else float(zoom)]

    def _cam_play(self, anim, added_anims=(), whoosh: bool = True):
        dist = np.linalg.norm(anim.to[:2] - self.rig.points[0][:2]) + abs(math.log(max(anim.to[2], 0.05)) - math.log(max(self.rig.points[0][2], 0.05))) * 4
        sfx = None
        if whoosh and dist > 0.8 and anim.run_time >= 0.6:
            sfx = [{"name": "whoosh" if dist > 2.5 else "swish", "at": "0.05", "gain": -7.0 if dist > 2.5 else -6.0}]
        self.play(anim, *added_anims, sfx=sfx if sfx else None)

    def pan_to(self, to, run_time: float = 1.4, zoom: float | None = None, added_anims=()):
        """Pan so `to` (a point or a mobject) sits at the screen focus; far layers move less."""
        self._cam_play(self.camera_move(to=to, zoom=zoom, run_time=run_time), added_anims)

    def push_in(self, zoom: float = 1.3, to=None, run_time: float = 1.5, added_anims=()):
        """Move the camera forward (zoom > current) toward `to`: near layers grow faster than far
        ones, so the flat art opens up in depth. Keep zoom between 1 and ~1.8."""
        self._cam_play(self.camera_move(to=to, zoom=zoom, run_time=run_time), added_anims)

    def pull_out(self, zoom: float = 1.0, to=None, run_time: float = 1.5, added_anims=()):
        """Move back (to zoom 1 by default), optionally re-centring on `to`."""
        self._cam_play(self.camera_move(to=to if to is not None else SAFE_CENTER, zoom=zoom, run_time=run_time), added_anims)

    def dolly(self, by=RIGHT * 3, run_time: float = 2.0, zoom: float | None = None, added_anims=()):
        """A tracking move sideways (and/or up) by a vector: the parallax shot, near layers sweep
        past, far ones barely move. Pair it with a character walking (walk())."""
        self._cam_play(self.camera_move(by=by, zoom=zoom, run_time=run_time), added_anims)

    def drift(self, velocity=RIGHT * 0.12, zoom_rate: float = 0.0, ramp: float = 0.8):
        """A slow continuous creep (units/s, zoom/s) that keeps the frame alive under narration;
        runs through waits until stop_drift()."""
        v = np.array(velocity, dtype=float).reshape(-1)[:2]
        st = {"t": 0.0, "v": v, "z": float(zoom_rate), "ramp": ramp, "stop": None}
        self._drift_v = st

        def upd(m, dt):
            st["t"] += dt
            k = min(1.0, st["t"] / max(st["ramp"], 1e-3))
            if st["stop"] is not None:
                st["stop"] += dt
                k *= max(0.0, 1 - st["stop"] / max(st["ramp"], 1e-3))
                if k <= 0:
                    m.clear_updaters()
                    return
            k = k * k * (3 - 2 * k)
            m.points[0][0] += st["v"][0] * dt * k
            m.points[0][1] += st["v"][1] * dt * k
            m.points[0][2] *= math.exp(st["z"] * dt * k)

        self.rig.clear_updaters()
        self.rig.add_updater(upd)

    def stop_drift(self, ramp: float = 0.6):
        if self._drift_v is not None:
            self._drift_v["stop"] = 0.0
            self._drift_v["ramp"] = ramp

    def shake(self, amount: float = 0.08, run_time: float = 0.35):
        """A short camera shake (an impact, a 'thud')."""
        cam = self.camera
        rng = np.random.default_rng(7)
        ph = rng.uniform(0, TAU, 2)

        class _Shake(Animation):
            ww_cam = True

            def __init__(s, **kw):
                super().__init__(VectorizedPoint(), run_time=run_time, **kw)

            def interpolate_mobject(s, a):
                k = (1 - a) ** 2
                cam.shake = amount * k * np.array([math.sin(60 * a + ph[0]), math.sin(47 * a + ph[1])])

        self.play(_Shake(), sfx=[{"name": "thud", "at": "start", "gain": -3}])
        cam.shake = np.zeros(2)

    def to_screen(self, point) -> np.ndarray:
        """Where a main-layer point is on screen now."""
        A, b = self.camera.layer_affine(1.0)
        p = np.array(point, dtype=float).reshape(-1)
        q = A @ p[:2] + b
        return np.array([q[0], q[1], 0.0])

    # ---- frame bookkeeping
    def _sync(self):
        """Carry each layer's z-order down its family and switch on per-frame drawing when idle
        life exists (waits then render frame by frame)."""
        fx = [False]

        def walk(m, z):
            own = getattr(m, "ww_z", None)
            if own is not None:
                z = own
            if z is not None and m.z_index != z:
                m.z_index = z
            if getattr(m, "ww_fx", None):
                fx[0] = True
            for s in m.submobjects:
                walk(s, z)

        for m in self.mobjects:
            if m is self.rig:
                continue
            if getattr(m, "ww_z", None) is None and not hasattr(m, "ww_depth"):
                m.ww_z = _Z["main"]
            walk(m, None)
        if fx[0] and not self._fx_on:
            self._fx_on = True
            self.add_updater(lambda dt: None)  # keeps waits rendering frame by frame
        return fx[0]

    def add(self, *mobjects):
        super().add(*mobjects)
        try:
            for m in mobjects:
                if getattr(m, "ww_z", None) is None and m is not getattr(self, "rig", None) and not hasattr(m, "ww_depth"):
                    m.ww_z = _Z["main"]
                    m.set_z_index(_Z["main"], family=True)
        except Exception:
            pass
        return self

    def _cam_moving(self, animations) -> bool:
        rig = getattr(self, "rig", None)
        if rig is None:
            return False
        if rig.updaters:
            return True
        for a in animations:
            if getattr(a, "mobject", None) is rig or getattr(a, "ww_cam", False):
                return True
            if isinstance(a, AnimationGroup) and self._cam_moving(a.animations):
                return True
        return any(getattr(self.camera, "shake", np.zeros(2)).tolist())

    def get_moving_mobjects(self, *animations):
        if self._cam_moving(animations) or self._fx_on:
            fam = self.get_mobject_family_members()
            if self._cam_moving(animations):
                return fam
            # idle life only: everything from the first member with an effect upward in z-order
            # (plus whatever the animations move, which the base rule would also catch)
            base = super().get_moving_mobjects(*animations)
            for i, m in enumerate(fam):
                if getattr(m, "ww_fx", None):
                    return fam[i:] if not base or len(base) <= len(fam) - i else base
            return base
        return super().get_moving_mobjects(*animations)

    def get_moving_and_static_mobjects(self, animations):
        if self._cam_moving(animations):
            return list(self.mobjects), []
        return super().get_moving_and_static_mobjects(animations)

    def play(self, *args, **kwargs):
        try:
            self._sync()
        except Exception as e:
            logger.debug(f"25d sync failed: {e}")
        t0 = self.now
        moving_cam = False
        try:
            from manim.animation.animation import prepare_animation
            anims = [prepare_animation(a) for a in args]
            moving_cam = self._cam_moving(anims)
            args = tuple(anims)
        except Exception:
            pass
        super().play(*args, **kwargs)
        dt = self.now - t0
        try:
            shapes = sum(1 for m in self.get_mobject_family_members()
                         if isinstance(m, VMobject) and len(m.points) > 0)
            self._perf["shapes_max"] = max(self._perf["shapes_max"], shapes)
            full = moving_cam or self._fx_on
            self._perf["redraw_s"] = round(self._perf["redraw_s"] + (dt if full else 0.0), 2)
            self._perf["work"] += shapes * dt * (1.0 if full else 0.35)
        except Exception:
            pass


    def _auto_cues(self, anims, t0: float, t1: float):
        kinds = [_kind25(a) for a in anims]
        if not any(kinds):
            return super()._auto_cues(anims, t0, t1)
        if t1 - t0 < 0.15:
            return
        if "appear" in kinds or "burst" in kinds:
            n = 0
            for a in anims:
                if isinstance(a, AnimationGroup):
                    n += sum(1 for s in a.animations if getattr(s, "ww_kind", None) == "appear")
                elif getattr(a, "ww_kind", None) == "appear":
                    n += 1
            if "burst" in kinds:
                self._cue("shimmer", t0 + 0.02, -6.0, auto=True, kind="appear")
            k = max(1, min(n, 3))
            for i in range(k):
                self._cue("pop", t0 + (t1 - t0) * 0.7 * i / k + 0.02, -3.0 - i, auto=True, kind="appear")
        elif "slide" in kinds:
            self._cue("swish", t0 + 0.02, -8.0, auto=True, kind="appear")

    def in_view(self, mob: Mobject, margin: float = 0.2) -> Mobject:
        """Shift a label or bubble (in world units) so that, from where the camera is now, it sits
        inside the safe area. Call it after a camera move, before showing the thing."""
        x0, y0, x1, y1 = self.camera.screen_box(mob)
        dx = max(0.0, SAFE_LEFT + margin - x0) - max(0.0, x1 - (SAFE_RIGHT - margin))
        dy = max(0.0, SAFE_BOTTOM + margin - y0) - max(0.0, y1 - (SAFE_TOP - margin))
        if dx or dy:
            A = self.camera._get(mob)[0]
            k = math.sqrt(abs(np.linalg.det(A))) or 1.0
            mob.shift(np.array([dx / k, dy / k, 0]))
        return mob

    # ---- lint
    def _check_layout(self):
        n = len(self._lint)
        super()._check_layout()
        hw, hh = FRAME_W / 2, FRAME_H / 2
        keep = []
        for item in self._lint[n:]:
            b = item.get("box")
            # a label the camera simply isn't looking at (panned away) is not a defect
            if item.get("issue") == "off-frame" and b and (b[2] < -hw or b[0] > hw or b[3] < -hh or b[1] > hh):
                continue
            keep.append(item)
        self._lint[n:] = keep

    def _screen_box(self, m):
        try:
            return self.camera.screen_box(m)
        except Exception:
            return super()._screen_box(m)

    def _write_report(self):
        p = getattr(self, "_perf", None)
        if p is not None:
            # measured on Cairo at 1080p30 (this machine): ~15 µs per filled shape per redrawn frame,
            # plus ~0.2 s per second of video for everything else (encoding, start-up)
            p["est_render_s"] = round(p["work"] * 30 * 15e-6 + self.now * 0.2 + 1.5, 1)
            heavy = []
            if p["shapes_max"] > SHAPE_BUDGET:
                heavy.append(f"{p['shapes_max']} shapes on screen (budget {SHAPE_BUDGET}): fewer props, "
                             "simpler backdrop (scenery=False on busy scenes), or pop old things out")
            if p["est_render_s"] > RENDER_BUDGET_25D:
                heavy.append(f"about {p['est_render_s']:.0f} s to render (budget {RENDER_BUDGET_25D:.0f} s): "
                             f"{p['redraw_s']:.0f} s redrawn with up to {p['shapes_max']} shapes")
            for h in heavy:
                if not any(i.get("issue") == "render budget" and i.get("what") == h for i in self._lint):
                    self._lint.append({"t": round(self.now, 2), "issue": "render budget", "what": h})
        super()._write_report()
