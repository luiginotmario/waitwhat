"""waitwhat 3D: the 3Blue1Brown look in depth, for the few scenes where depth explains something.

Loaded by waitwhat_style (scene files keep `from waitwhat_style import *`; never import this module
first, the two import each other):

    class Stack(WaitwhatScene3D):
        def construct(self):
            stack = exploded_layers([("cover glass", "BLUE"), ("touch sensor", "TEAL"), ("display", "PINK")])
            self.play(rotate_reveal(stack), run_time=self.until("layers"))
            self.play(stack.explode(0.8), run_time=2)
            labels = self.label_layers(stack)
            self.play(*[c.enter() for c in labels])
            self.orbit(PI / 5, run_time=self.until("touch"))
            self.finish()

What you get, on top of everything WaitwhatScene gives (bookmark timing, sound cues, themes, both
aspects, the layout lint):
  * WaitwhatScene3D: Manim CE's ThreeDScene on a faster Cairo camera (vectorized projection, depth
    sort and soft shading: 3-5x faster than the stock one, same look), framed on the safe area
    (in 9:16 the world origin sits on SAFE_CENTER), house default view
  * camera grammar: view(), camera_to(), orbit(), dolly(), drift()/stop_drift(), fit_zoom()
  * text stays flat on the screen: fixed()/hud() for screen text, pin() for a label that follows a 3D
    point, callout() for a label with a leader line to a 3D point, all in sync while the camera moves
  * constructors in the house palette: surface(), graph_surface(), ball(), slab(), cylinder(),
    axes3d(), exploded_layers(), cutaway(), glow_path(), orbit_path(); animations rotate_reveal();
    "invisible physics": particles() and ripples()
  * the 3D lint: text left in 3D space, 3D objects leaving the frame, and the render budget
    (faces on screen x seconds of camera motion) go into layout_issues

Every 3D object here is light on faces on purpose: a Cairo 3D frame costs roughly 25 µs per face,
so keep a scene under ~1500 faces and its camera motion short (the budget in references/3d.md).
All code here is original to waitwhat (MIT).
"""
from __future__ import annotations

import math

import numpy as np
from manim import (
    DEGREES, DOWN, IN, LEFT, ORIGIN, OUT, PI, RIGHT, TAU, UP,
    AnimationGroup, Camera, Circle, Dot, FadeIn, FadeOut, Line, Mobject, Prism, Sphere, Surface,
    ThreeDAxes, ThreeDScene, ThreeDVMobject, UpdateFromAlphaFunc, ValueTracker, VectorizedPoint,
    VGroup, VMobject, interpolate_color, rate_functions, smooth,
)
from manim.camera.three_d_camera import ThreeDCamera
from manim.mobject.types.point_cloud_mobject import Point
from manim.utils.family import extract_mobject_family_members

import waitwhat_style as _ws
from waitwhat_style import (
    BG, CONTEXT, FRAME_H, FRAME_W, INK, INK_2, INK_3, INK_4, IS_DARK, IS_VERTICAL, SAFE_BOTTOM,
    SAFE_CENTER, SAFE_LEFT, SAFE_RIGHT, SAFE_TOP, SAFE_W, SIZE_LABEL, T, YELLOW, WaitwhatScene,
    by_aspect, color_of, ease_out,
)

__all__ = [
    "WaitwhatScene3D", "WaitwhatCamera3D", "Callout", "Layers", "Cutaway",
    "VIEW_PHI", "VIEW_THETA", "FLAT_PHI", "FLAT_THETA", "FACE_BUDGET", "MOTION_BUDGET", "RENDER_BUDGET",
    "SURFACE_RES", "SPHERE_RES", "ROUND_RES",
    "surface", "graph_surface", "ball", "slab", "cylinder", "axes3d", "exploded_layers", "cutaway",
    "glow_path", "orbit_path", "rotate_reveal", "depth_sorted", "bleed", "tone", "keep_safe",
]

# --------------------------------------------------------------------------- budget + defaults

#: the house angled view (radians, Manim's convention): above and a little to the right-front
VIEW_PHI, VIEW_THETA = 64 * DEGREES, -58 * DEGREES
#: the flat view: identical to a 2D scene, so a 3D scene can start where a 2D one ended, then tilt
FLAT_PHI, FLAT_THETA = 0.0, -90 * DEGREES
#: faces on screen at once (each shaded polygon of a surface or solid). Above it renders slow down.
FACE_BUDGET = 1500
#: seconds of 3D motion (camera moves, drift, solids moving) per scene at ~600 faces. A still
#: camera with still solids costs ~nothing: Manim draws them once and reuses the frame.
MOTION_BUDGET = 12.0
#: estimated seconds to render the scene (a 2D scene takes 2-7 s); above it the lint says so
RENDER_BUDGET = 15.0
#: default resolutions, chosen for 1080p: smooth enough, cheap enough
SURFACE_RES = 18          # surface(): 18 x 18 = 324 faces
SPHERE_RES = (20, 12)     # ball(): 240 faces
ROUND_RES = 20            # cylinder(), cutaway(): segments around


def _pt(p) -> np.ndarray:
    if isinstance(p, Mobject):
        return p.get_center()
    a = np.array(p, dtype=float).reshape(-1)
    return np.array([a[0], a[1], a[2] if len(a) > 2 else 0.0])


def _anchor_fn(anchor):
    """A 3D anchor as a function returning the current point: a Mobject (its centre, so it follows
    the object), a callable, or a fixed point."""
    if callable(anchor) and not isinstance(anchor, Mobject):
        return lambda: _pt(anchor())
    if isinstance(anchor, Mobject):
        return anchor.get_center
    p = _pt(anchor)
    return lambda: p


def keep_safe(m: Mobject) -> Mobject:
    """Shift a flat (screen) mobject back inside the safe area if it pokes out (labels that follow
    moving 3D things use this every frame)."""
    x0, y0 = m.get_corner(DOWN + LEFT)[:2]
    x1, y1 = m.get_corner(UP + RIGHT)[:2]
    dx = max(0.0, SAFE_LEFT - x0) - max(0.0, x1 - SAFE_RIGHT)
    dy = max(0.0, SAFE_BOTTOM - y0) - max(0.0, y1 - SAFE_TOP)
    if dx or dy:
        m.shift([dx, dy, 0])
    return m


def tone(color, k: float = 0.22) -> str:
    """A darker (dark themes) or lighter (light themes) cousin of a colour: the checkerboard's second tone."""
    from manim import ManimColor
    return interpolate_color(ManimColor(color), ManimColor("#000000" if IS_DARK else "#FFFFFF"), k).to_hex()


def _named(c):
    """Accept palette names ("BLUE"), concept names (color_of) or colour values."""
    if isinstance(c, str) and not c.startswith("#"):
        inks = {"INK": INK, "INK_2": INK_2, "INK_3": INK_3, "INK_4": INK_4}
        if c.upper() in inks:
            return inks[c.upper()]
        if c.upper() in _ws.NAMED:
            return _ws.NAMED[c.upper()]
        return color_of(c)
    return c


# --------------------------------------------------------------------------- the camera

_FAST = None


def _fast_types():
    global _FAST
    if _FAST is None:
        import manim as _m
        _FAST = tuple(getattr(_m, n) for n in ("ThreeDVMobject", "Square", "Rectangle", "Polygon",
                                               "RegularPolygon", "Triangle", "Circle"))
    return _FAST


class WaitwhatCamera3D(ThreeDCamera):
    """ThreeDCamera with the waitwhat framing and a fast path for shaded faces.

    * `look` (a Point) is the world point the camera looks at; `shift` (a Point) moves the projected
      picture on screen (in 9:16 it starts at SAFE_CENTER, above the phone's bottom UI). Both are
      animatable, and replace ThreeDCamera's frame_center (keep that at ORIGIN).
    * soft, hue-keeping shading: colour x (ambient + diffuse) plus a faint highlight, lit from the
      viewer's upper left by default (`headlight`), or from a world point (`light_point`).
    * shaded faces are projected, depth-sorted and lit in one numpy pass per frame and drawn with
      flat colours; everything else takes Manim's usual path.
    * fixed-in-frame mobjects are re-collected from their roots every frame, so text transformed or
      rebuilt on screen stays flat.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.look = Point(ORIGIN, stroke_width=0)
        self.shift = Point(np.array([SAFE_CENTER[0], SAFE_CENTER[1], 0.0]), stroke_width=0)
        self.headlight = True
        self.light_dir = np.array([-0.45, 0.6, 1.0]) / np.linalg.norm([-0.45, 0.6, 1.0])
        self.light_point = None
        self.ambient = 0.6 if IS_DARK else 0.78   # light themes: keep the marker colours true
        self.highlight = 0.1
        self.fixed_roots: list[Mobject] = []

    # ---- fixed in frame, by root
    def add_fixed_in_frame_mobjects(self, *mobjects):
        for m in mobjects:
            if m not in self.fixed_roots:
                self.fixed_roots.append(m)
        super().add_fixed_in_frame_mobjects(*mobjects)

    def remove_fixed_in_frame_mobjects(self, *mobjects):
        self.fixed_roots = [m for m in self.fixed_roots if m not in mobjects]
        self.refresh_fixed()

    def refresh_fixed(self):
        self.fixed_in_frame_mobjects = set(extract_mobject_family_members(self.fixed_roots))

    def is_fixed(self, m) -> bool:
        return m in self.fixed_in_frame_mobjects

    def capture_mobjects(self, mobjects, **kwargs):
        self.refresh_fixed()
        super().capture_mobjects(mobjects, **kwargs)

    # ---- projection
    def project_points(self, points):
        rot = self.get_rotation_matrix()
        pts = np.dot(np.asarray(points, dtype=float) - self.look.points[0], rot.T)
        d = self.get_focal_distance()
        zs = pts[:, 2]
        with np.errstate(divide="ignore"):
            factor = d / (d - zs)
        factor[(d - zs) <= 0] = 10 ** 6
        factor *= self.get_zoom()
        pts[:, 0] *= factor
        pts[:, 1] *= factor
        s = self.shift.points[0]
        pts[:, 0] += s[0]
        pts[:, 1] += s[1]
        return pts

    def fresh(self):
        """Recompute the rotation from the angle trackers now (updaters run before the frame's capture)."""
        self.reset_rotation_matrix()
        return self

    def view_dir(self) -> np.ndarray:
        """Unit vector from the scene towards the viewer, in world space."""
        return self.get_rotation_matrix()[2]

    # ---- shading
    def _light_vectors(self, P: np.ndarray) -> np.ndarray:
        if self.light_point is not None and not self.headlight:
            L = np.asarray(self.light_point, dtype=float) - P
            n = np.linalg.norm(L, axis=1, keepdims=True)
            return L / np.where(n == 0, 1, n)
        rot = self.get_rotation_matrix()
        return np.broadcast_to(rot.T @ self.light_dir, P.shape)

    def _shade(self, rgb: np.ndarray, P: np.ndarray, N: np.ndarray) -> np.ndarray:
        """rgb (k,3), points (k,3), normals (k,3) → shaded rgb. Normals are flipped to face the viewer."""
        V = self.view_dir()
        s = np.sign(N @ V)
        s[s == 0] = 1
        N = N * s[:, None]
        d = np.clip(np.sum(N * self._light_vectors(P), axis=1), 0, 1)
        f = self.ambient + (1 - self.ambient) * d
        return np.clip(rgb * f[:, None] + (self.highlight * d ** 16)[:, None], 0, 1)

    def modified_rgbas(self, vmobject, rgbas):
        if not self.should_apply_shading or not getattr(vmobject, "shade_in_3d", False) \
                or getattr(vmobject, "ww_flat", False) or vmobject.get_num_points() == 0:
            return rgbas
        pts = vmobject.points
        n = len(pts)
        i1, i2 = (3, n - 4) if n >= 8 else (1, n - 1)
        N = np.cross(pts[i1] - pts[0], pts[i2] - pts[0])
        ln = np.linalg.norm(N)
        N = N / ln if ln > 0 else np.array(UP, dtype=float)
        out = np.array(rgbas[:1] if len(rgbas) else rgbas, dtype=float)
        if len(out):
            out[:, :3] = self._shade(out[:, :3], pts[:1], N[None, :].repeat(len(out), 0))
        return out

    # ---- depth sort (vectorized, same rule as ThreeDCamera: shaded mobjects by depth, others on top)
    def get_mobjects_to_display(self, *args, **kwargs):
        mobjects = Camera.get_mobjects_to_display(self, *args, **kwargs)
        z = self.get_rotation_matrix()[2]
        keys = np.full(len(mobjects), np.inf)
        groups = {}
        for i, m in enumerate(mobjects):
            if not getattr(m, "shade_in_3d", False):
                continue
            g = getattr(m, "z_index_group", None)
            if g is not None:
                c = groups.get(id(g))
                if c is None:
                    c = groups[id(g)] = g.get_center()
            else:
                p = m.points
                c = (p.min(axis=0) + p.max(axis=0)) / 2 if len(p) else ORIGIN
            keys[i] = z @ c
        order = np.argsort(keys, kind="stable")
        return [mobjects[i] for i in order]

    # ---- fast drawing of shaded faces
    def display_multiple_non_background_colored_vmobjects(self, vmobjects, pixel_array):
        vmobjects = list(vmobjects)
        ctx = self.get_cairo_context(pixel_array)
        fast_t = _fast_types()
        fast = [v for v in vmobjects
                if getattr(v, "shade_in_3d", False) and type(v) in fast_t and len(v.points) >= 8
                and v not in self.fixed_in_frame_mobjects and v not in self.fixed_orientation_mobjects
                and v.get_stroke_width(background=True) == 0]
        pre = self._prepare_fast(fast) if fast else {}
        for v in vmobjects:
            job = pre.get(id(v))
            if job is None:
                self.display_vectorized(v, ctx)
                continue
            xy, fill, stroke, width = job
            ctx.new_path()
            ctx.move_to(xy[0][0], xy[0][1])
            for k in range(1, len(xy) - 2, 4):
                a, b, c = xy[k], xy[k + 1], xy[k + 2]
                ctx.curve_to(a[0], a[1], b[0], b[1], c[0], c[1])
            if abs(xy[0][0] - xy[-1][0]) < 1e-6 and abs(xy[0][1] - xy[-1][1]) < 1e-6:
                ctx.close_path()
            if fill[3] > 0:
                ctx.set_source_rgba(fill[2], fill[1], fill[0], fill[3])
                ctx.fill_preserve()
            if width > 0 and stroke[3] > 0:
                ctx.set_source_rgba(stroke[2], stroke[1], stroke[0], stroke[3])
                ctx.set_line_width(width * self.cairo_line_width_multiple)
                ctx.stroke_preserve()
        return self

    def _prepare_fast(self, faces):
        lens = np.array([len(v.points) for v in faces])
        starts = np.concatenate([[0], np.cumsum(lens)[:-1]])
        P = np.concatenate([v.points for v in faces])
        if not np.all(np.isfinite(P)):
            return {}
        proj = self.project_points(P)
        a, b, c = P[starts], P[starts + 3], P[starts + lens - 4]
        N = np.cross(b - a, c - a)
        ln = np.linalg.norm(N, axis=1)
        bad = ln == 0
        N[bad] = UP
        ln[bad] = 1
        N = N / ln[:, None]
        fills = np.array([v.get_fill_rgbas()[0] for v in faces], dtype=float)
        strokes = np.array([v.get_stroke_rgbas()[0] for v in faces], dtype=float)
        widths = [v.get_stroke_width() for v in faces]
        if self.should_apply_shading:
            lit = np.array([not getattr(v, "ww_flat", False) for v in faces])
            if lit.any():
                fills[lit, :3] = self._shade(fills[lit, :3], a[lit], N[lit])
                strokes[lit, :3] = self._shade(strokes[lit, :3], a[lit], N[lit])
        xy_all = proj[:, :2].tolist()
        out = {}
        for i, v in enumerate(faces):
            s = starts[i]
            out[id(v)] = (xy_all[s:s + lens[i]], fills[i].tolist(), strokes[i].tolist(), widths[i])
        return out


# --------------------------------------------------------------------------- styling helpers

def _style_faces(mob: Mobject, color, opacity: float, stroke_color=None, stroke_width: float = 0.6,
                 checker: bool = True):
    """House look for a surface or solid: fill in the concept colour (checkerboard with a darker
    cousin), thin stroke of the same hue."""
    color = _named(color)
    sc = stroke_color or tone(color, 0.45)
    if isinstance(mob, Surface) and checker:
        mob.set_fill_by_checkerboard(color, tone(color), opacity=opacity)
    else:
        mob.set_fill(color, opacity=opacity)
    mob.set_stroke(sc, width=stroke_width, opacity=min(1.0, opacity + 0.2))
    return mob


def depth_sorted(mob: Mobject, shaded: bool = False) -> Mobject:
    """Let a flat thing (a line, a path, a label plate) take part in the depth sort, so a solid in
    front of it hides it. shaded=False keeps its colour unlit. Long paths: build them from short
    pieces (glow_path(..., depth=True) does), since each piece is sorted by its centre."""
    for m in mob.family_members_with_points():
        m.shade_in_3d = True
        m.ww_flat = not shaded
    return mob


def bleed(mob: Mobject) -> Mobject:
    """Mark something that may run off the frame on purpose (a ground plane, long axes) so the
    3D lint doesn't flag it."""
    mob.ww_bleed = True
    return mob


def surface(func, u_range=(-3, 3), v_range=(-3, 3), color="BLUE", resolution=SURFACE_RES,
            opacity: float = 0.85, checker: bool = True, stroke_width: float = 0.5) -> Surface:
    """A parametric surface func(u, v) -> [x, y, z] in the house look (checkerboard of the concept
    colour and its darker cousin, thin same-hue stroke). resolution ≤ 24 (faces = res²)."""
    res = resolution if isinstance(resolution, (tuple, list)) else (resolution, resolution)
    s = Surface(lambda u, v: np.asarray(func(u, v), dtype=float), u_range=u_range, v_range=v_range,
                resolution=tuple(int(r) for r in res), checkerboard_colors=False)
    return _style_faces(s, color, opacity, stroke_width=stroke_width, checker=checker)


def graph_surface(f, x_range=(-3, 3), y_range=(-3, 3), color="BLUE", resolution=SURFACE_RES,
                  opacity: float = 0.85, live: bool = False, **kw) -> Surface:
    """The surface z = f(x, y) (or f(x, y, t) with live=True: then call
    `s.set_time(t)`, or `self.animate_surface(s, seconds)`, to move it in place without rebuilding)."""
    if live:
        s = surface(lambda u, v: [u, v, f(u, v, 0.0)], x_range, y_range, color, resolution, opacity, **kw)
        _make_live(s, lambda u, v, t: np.stack([u, v, f(u, v, t)], axis=-1))
        return s
    return surface(lambda u, v: [u, v, f(u, v)], x_range, y_range, color, resolution, opacity, **kw)


def _make_live(s: Surface, func_t):
    """Give a Surface .set_time(t): re-evaluates func_t(U, V, t) on the uv grid (vectorized) and
    rewrites every face's points in place. ~1 ms for 324 faces, so a surface can move every frame."""
    faces = s.list_of_faces
    uv = np.array([[f.u1, f.u2, f.v1, f.v2] for f in faces])
    U = np.stack([uv[:, 0], uv[:, 1], uv[:, 1], uv[:, 0], uv[:, 0]], axis=1)
    V = np.stack([uv[:, 2], uv[:, 2], uv[:, 3], uv[:, 3], uv[:, 2]], axis=1)
    w = np.array([0, 1 / 3, 2 / 3, 1.0])

    def set_time(t: float):
        C = np.asarray(func_t(U, V, t), dtype=float)            # (faces, 5, 3) corners
        A, B = C[:, :-1, :], C[:, 1:, :]                        # 4 straight segments per face
        pts = A[:, :, None, :] + (B - A)[:, :, None, :] * w[None, None, :, None]
        pts = pts.reshape(len(faces), 16, 3)
        for f, p in zip(faces, pts):
            f.points = p
        s.time = t
        return s

    s.set_time = set_time
    s.time = 0.0
    set_time(0.0)
    return s


def ball(radius: float = 1.0, color="BLUE", at=ORIGIN, resolution=SPHERE_RES, opacity: float = 1.0,
         checker: bool = True) -> Surface:
    """A sphere in the house look (planet, atom, ball). Default 20 x 12 = 240 faces; a small ball
    (radius < 0.4) needs only (10, 6)."""
    s = Sphere(radius=radius, resolution=resolution, checkerboard_colors=False)
    _style_faces(s, color, opacity, checker=checker)
    return s.move_to(_pt(at))


def slab(width: float = 4.0, depth: float = 3.0, height: float = 0.2, color="BLUE", at=ORIGIN,
         opacity: float = 0.8, stroke_width: float = 1.5) -> Prism:
    """A box (plate, layer, chip, block): 6 shaded faces, the cheapest solid there is."""
    p = Prism(dimensions=[width, depth, height])
    c = _named(color)
    p.set_fill(c, opacity=opacity).set_stroke(c, width=stroke_width, opacity=min(1.0, opacity + 0.15))
    return p.move_to(_pt(at))


def cylinder(radius: float = 1.0, height: float = 2.0, color="BLUE", at=ORIGIN, direction=OUT,
             resolution: int = ROUND_RES, opacity: float = 1.0, ends: bool = True) -> Surface:
    """A cylinder (rod, can, cell, wire) along `direction`: one band around, `resolution` sides."""
    from manim import Cylinder
    c = Cylinder(radius=radius, height=height, direction=np.array(direction, dtype=float),
                 resolution=(1, int(resolution)), show_ends=ends, checkerboard_colors=False)
    _style_faces(c, color, opacity, checker=False)
    return c.move_to(_pt(at))


def axes3d(x_range=(-4, 4, 1), y_range=(-4, 4, 1), z_range=(-2.5, 2.5, 1), x_length=None, y_length=None,
           z_length=None, color=None, ticks: bool = False) -> ThreeDAxes:
    """3D axes in the house style: thin grey structure, small tips, no numbers (label with
    self.axis_labels(ax, "x", "y", "z") so the letters stay flat on the screen)."""
    col = color or INK_3
    cfg = {"color": col, "stroke_width": 2, "include_tip": True, "tip_width": 0.18, "tip_height": 0.18,
           "include_ticks": ticks, "tick_size": 0.05}
    ax = ThreeDAxes(x_range=list(x_range), y_range=list(y_range), z_range=list(z_range),
                    x_length=x_length or (x_range[1] - x_range[0]), y_length=y_length or (y_range[1] - y_range[0]),
                    z_length=z_length or (z_range[1] - z_range[0]), axis_config=cfg, z_axis_config=cfg)
    return ax


# --------------------------------------------------------------------------- glowing paths

def _as_path(path) -> VMobject:
    if isinstance(path, VMobject):
        return path
    pts = np.array([_pt(p) for p in path])
    m = VMobject()
    m.set_points_smoothly(pts) if len(pts) > 2 else m.set_points_as_corners(pts)
    return m


def glow_path(path, color="YELLOW", width: float = 4, glow: float = 1.0, depth: bool = False,
              pieces: int = 24) -> VGroup:
    """A path drawn the 3b1b way for things you can't see (current, a signal, a trajectory): a
    bright core over two soft, wider strokes of the same colour. `path` is a VMobject (e.g.
    orbit_path, ParametricFunction) or a list of 3D points. depth=True cuts it into `pieces` so solids
    in front of it hide it (otherwise it is drawn over solids, like an x-ray overlay)."""
    color = _named(color)
    base = _as_path(path)
    if depth:
        segs = []
        for i in range(pieces):
            seg = VMobject()
            seg.pointwise_become_partial(base, i / pieces, (i + 1) / pieces)
            segs.append(seg)
        layers = []
        for w, o in ((width * 5, 0.10 * glow), (width * 2.4, 0.22 * glow), (width, 1.0)):
            g = VGroup(*[s.copy().set_stroke(color, w, min(1.0, o)).set_fill(opacity=0) for s in segs])
            layers.append(depth_sorted(g))
        return VGroup(*layers)
    out = VGroup()
    for w, o in ((width * 5, 0.10 * glow), (width * 2.4, 0.22 * glow), (width, 1.0)):
        out.add(base.copy().set_stroke(color, w, min(1.0, o)).set_fill(opacity=0))
    return out


def orbit_path(radius: float = 3.0, center=ORIGIN, ecc: float = 0.0, tilt: float = 0.0,
               color="INK_3", width: float = 2, samples: int = 96) -> VMobject:
    """A closed orbit (circle or ellipse of eccentricity `ecc`, focus at `center`) in the xy plane,
    tilted by `tilt` radians about the x axis. A plain thin path; wrap it in glow_path() to make it glow."""
    a = radius
    b = a * math.sqrt(max(0.0, 1 - ecc ** 2))
    c = a * ecc
    ts = np.linspace(0, TAU, samples + 1)
    pts = np.stack([a * np.cos(ts) - c, b * np.sin(ts), np.zeros_like(ts)], axis=1)
    if tilt:
        ct, st = math.cos(tilt), math.sin(tilt)
        pts = pts @ np.array([[1, 0, 0], [0, ct, st], [0, -st, ct]])
    m = VMobject()
    m.set_points_smoothly(pts + _pt(center))
    return m.set_stroke(_named(color), width).set_fill(opacity=0)


# --------------------------------------------------------------------------- rotate_reveal

def rotate_reveal(mob: Mobject, angle: float = -PI / 2, axis=OUT, about=None, fade: bool = True,
                  rate_func=ease_out, **kw) -> UpdateFromAlphaFunc:
    """Bring a 3D object in by turning it into place (from `angle` away about `axis`) while it fades
    up: the 3b1b entrance for solids. fade=False turns an object that is already on screen from
    angle away into its rest pose (add it rotated first). Use as self.play(rotate_reveal(m), run_time=...)."""
    fam = mob.family_members_with_points()
    pts0 = [m.points.copy() for m in fam]
    fills0 = [m.get_fill_opacities().copy() if hasattr(m, "get_fill_opacities") else None for m in fam]
    strokes0 = [m.get_stroke_opacities().copy() if hasattr(m, "get_stroke_opacities") else None for m in fam]
    center = _pt(about) if about is not None else mob.get_center()
    ax = np.array(axis, dtype=float)
    ax = ax / (np.linalg.norm(ax) or 1)

    def rot(theta):
        K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
        return np.eye(3) + math.sin(theta) * K + (1 - math.cos(theta)) * K @ K

    def update(m, a):
        R = rot(angle * (1 - a))
        for f, p in zip(fam, pts0):
            f.points = (p - center) @ R.T + center
        if fade:
            for f, fo, so in zip(fam, fills0, strokes0):
                if fo is not None and len(f.fill_rgbas):
                    f.fill_rgbas[:, 3] = np.resize(fo, len(f.fill_rgbas)) * a
                if so is not None and len(f.stroke_rgbas):
                    f.stroke_rgbas[:, 3] = np.resize(so, len(f.stroke_rgbas)) * a
        return m

    update(mob, 0.0)
    return UpdateFromAlphaFunc(mob, update, rate_func=rate_func, introducer=True, **kw)


# --------------------------------------------------------------------------- exploded layers

class Layers(VGroup):
    """A stack of plates (top to bottom as given), assembled and centred on the origin.
    `stack.layers` (one VGroup per layer: the plate, plus anything you .add() to it, e.g. a grid
    drawn on it), `stack["display"]`, `stack.explode(gap)`, `stack.assemble()`, `stack.anchors`."""

    def __init__(self, layers, width: float = 4.6, depth: float = 3.0, thickness: float = 0.14,
                 opacity: float = 0.82):
        super().__init__()
        specs = []
        for spec in layers:
            if isinstance(spec, dict):
                specs.append(dict(spec))
            elif isinstance(spec, (tuple, list)):
                d = {"name": spec[0], "color": spec[1] if len(spec) > 1 else "BLUE"}
                if len(spec) > 2:
                    d["thickness"] = spec[2]
                specs.append(d)
            else:
                specs.append({"name": str(spec), "color": "BLUE"})
        ts = [float(s.get("thickness", thickness)) for s in specs]
        total = sum(ts)
        z = total / 2
        self.layers, self.names, self.anchors = [], [], {}
        self.plate_size = (width, depth)
        for s, t in zip(specs, ts):
            zc = z - t / 2
            col = _named(s.get("color", "BLUE"))
            plate = slab(width, depth, t, col, at=[0, 0, zc], opacity=float(s.get("opacity", opacity)))
            anchor = VectorizedPoint([width / 2, -depth / 2 + 0.25, zc + t / 2])
            layer = VGroup(plate, anchor)
            layer.name, layer.hue, layer.plate, layer.anchor, layer.home_z = s["name"], col, plate, anchor, zc
            self.layers.append(layer)
            self.names.append(s["name"])
            self.anchors[s["name"]] = anchor
            self.add(layer)
            z -= t
        self.gap = 0.0

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.layers[self.names.index(key)]
        return super().__getitem__(key)

    def _targets(self, gap: float):
        n = len(self.layers)
        return [((n - 1) / 2 - i) * gap for i in range(n)]

    def explode(self, gap: float = 0.9, lag: float = 0.0) -> AnimationGroup:
        """Pull the layers apart vertically (top one up, bottom one down), `gap` units between them."""
        old, new = self._targets(self.gap), self._targets(gap)
        self.gap = gap
        return AnimationGroup(*[l.animate.shift(OUT * (b - a)) for l, a, b in zip(self.layers, old, new)],
                              lag_ratio=lag)

    def assemble(self) -> AnimationGroup:
        """Close the stack again."""
        return self.explode(0.0)


def exploded_layers(layers, width: float = 4.6, depth: float = 3.0, thickness: float = 0.14,
                    opacity: float = 0.82) -> Layers:
    """A stack of thin plates for "what is this made of" (a touchscreen, a solar cell, skin, the
    atmosphere, a PCB). layers: top to bottom, each "name", ("name", "COLOR"[, thickness]) or
    {"name", "color", "thickness", "opacity"}. Then: self.play(stack.explode(0.9)),
    self.label_layers(stack). A glass layer reads well at opacity 0.3."""
    return Layers(layers, width, depth, thickness, opacity)


# --------------------------------------------------------------------------- cutaway

class Cutaway(VGroup):
    """A layered solid with a wedge that lifts out: `cut.open()` reveals the cross-section.
    Parts: `body` (outer shell minus the wedge), `wedge`, `faces` (the cut faces, one band per layer,
    hidden until open()), `anchors[name]` (a point on that layer's band of the cut face, for callouts)."""

    def __init__(self, layers, kind: str = "cylinder", height: float = 4.0, cut: float = PI / 2,
                 resolution: int = ROUND_RES, start: float = 0.0, opacity: float = 1.0):
        super().__init__()
        specs = []
        for s in layers:
            if isinstance(s, dict):
                specs.append((s["name"], _named(s.get("color", "BLUE")), float(s["radius"])))
            else:
                specs.append((s[0], _named(s[1]), float(s[2])))
        specs.sort(key=lambda x: -x[2])
        self.kind, self.cut, self.start, self.length = kind, cut, start, height
        R = specs[0][2]
        self.radius = R
        a0, a1 = start, start + cut                      # the wedge spans [a0, a1]
        n_rest = max(6, int(round(resolution * (TAU - cut) / TAU)))
        n_wedge = max(2, int(round(resolution * cut / TAU)))
        outer = specs[0][1]
        if kind == "sphere":
            def shell(u0, u1, n):
                return Sphere(radius=R, u_range=(u0, u1), v_range=(0, PI), resolution=(n, max(8, resolution // 2)),
                              checkerboard_colors=False)
            self.body = _style_faces(shell(a1, a0 + TAU, n_rest), outer, opacity, checker=False)
            self.wedge = _style_faces(shell(a0, a1, n_wedge), outer, opacity, checker=False)
        else:
            h = height / 2

            def can(u0, u1, n, caps: bool):
                side = Surface(lambda z, a: np.array([R * math.cos(a), R * math.sin(a), z]), u_range=(-h, h),
                               v_range=(u0, u1), resolution=(1, n), checkerboard_colors=False)
                _style_faces(side, outer, opacity, checker=False)
                g = VGroup(side)
                if caps:
                    for name, col, r in specs:
                        r_in = next((x[2] for x in specs if x[2] < r), 0.0)
                        cap = Surface(lambda rho, a: np.array([rho * math.cos(a), rho * math.sin(a), h]),
                                      u_range=(r_in, r), v_range=(u0, u1), resolution=(1, n), checkerboard_colors=False)
                        g.add(_style_faces(cap, col, opacity, stroke_color=col, stroke_width=0.5, checker=False))
                return g

            self.body = can(a1, a0 + TAU, n_rest, True)
            self.wedge = can(a0, a1, n_wedge, True)
        # cut faces: one band per layer on each of the two cut planes
        self.faces = VGroup()
        self.anchors, self.anchors_left = {}, {}
        self.layer_names = [s[0] for s in specs]
        for k, (name, col, r) in enumerate(specs):
            r_in = specs[k + 1][2] if k + 1 < len(specs) else 0.0
            for j, ang in enumerate((a0, a1)):
                ca, sa = math.cos(ang), math.sin(ang)
                if kind == "sphere":
                    band = Surface(lambda rho, al, ca=ca, sa=sa: rho * np.array([math.sin(al) * ca, math.sin(al) * sa, math.cos(al)]),
                                   u_range=(r_in, r), v_range=(0, PI), resolution=(1, 10), checkerboard_colors=False)
                else:
                    band = Surface(lambda rho, z, ca=ca, sa=sa: np.array([rho * ca, rho * sa, z]),
                                   u_range=(r_in, r), v_range=(-height / 2, height / 2), resolution=(1, 3),
                                   checkerboard_colors=False)
                band.set_fill(col, opacity=0).set_stroke(tone(col, 0.4), width=0.8, opacity=0)
                band.ww_open = (1.0, 1.0)
                self.faces.add(band)
            mid = (r + r_in) / 2
            for store, ang in ((self.anchors, a1), (self.anchors_left, a0)):   # a1's face is right of the opening
                # staggered heights (outer layers higher), so a column of labels keeps their order
                if kind == "sphere":
                    al = PI / 2 - 0.5 + 0.28 * k               # polar angle on the half-disc
                    p = mid * np.array([math.sin(al) * math.cos(ang), math.sin(al) * math.sin(ang), math.cos(al)])
                else:
                    p = np.array([mid * math.cos(ang), mid * math.sin(ang), height * (0.38 - 0.13 * k)])
                store[name] = VectorizedPoint(p)
        self.names = self.layer_names
        self.add(self.body, self.faces, self.wedge, *self.anchors.values(), *self.anchors_left.values())
        self.bisector = np.array([math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0.0])

    def open(self, distance: float | None = None) -> AnimationGroup:
        """Lift the wedge out (along the cut's bisector, fading) and show the cut faces."""
        d = distance if distance is not None else self.radius * 1.4
        shift = self.bisector * d + (OUT * 0.3 if self.kind != "sphere" else ORIGIN)
        return AnimationGroup(
            self.wedge.animate.shift(shift).set_opacity(0),
            *[f.animate.set_fill(opacity=1.0).set_stroke(opacity=0.9) for f in self.faces],
        )

    def close(self) -> AnimationGroup:
        d = self.radius * 1.4
        shift = self.bisector * d + (OUT * 0.3 if self.kind != "sphere" else ORIGIN)
        return AnimationGroup(self.wedge.animate.shift(-shift).set_opacity(1.0),
                              *[f.animate.set_fill(opacity=0).set_stroke(opacity=0) for f in self.faces])


def cutaway(layers, kind: str = "cylinder", height: float = 4.0, cut: float = PI / 2, start: float | None = None,
            resolution: int = ROUND_RES, opacity: float = 1.0) -> Cutaway:
    """A layered solid you can open: a cell, a cable, a pipe, an earbud driver (kind="cylinder",
    axis = z) or a planet, a fruit, an eye (kind="sphere"). layers: (name, COLOR, radius), outer
    first or in any order. The wedge [start, start + cut] lifts out with self.play(cut.open());
    callouts attach to cut.anchors[name] (on the cut face to the right of the opening; anchors_left
    for the other one). The opening faces the camera's azimuth (theta): by default the house view
    turned so the labelled right-hand face is seen nearly face-on (start = VIEW_THETA - cut / 2 + 25°);
    for another view pass start = theta - cut / 2 + 25°."""
    if start is None:
        start = VIEW_THETA - cut / 2 + 25 * DEGREES
    return Cutaway(layers, kind, height, cut, resolution, start, opacity)


# --------------------------------------------------------------------------- callouts

class Callout(VGroup):
    """A screen-flat label tied to a 3D point by a thin leader line (+ a dot on the point), kept in
    sync with the camera every frame. Make with self.callout(...); animate with .enter()/.leave()."""

    def __init__(self, scene, label, anchor, at=None, side=RIGHT, dist: float = 1.3, color=None,
                 dot: bool = True, buff: float = 0.12):
        lab = T(label, size=SIZE_LABEL, color=INK) if isinstance(label, str) else label
        col = _named(color) if color is not None else INK_2
        self.label = lab
        self.line = VMobject().set_stroke(col, 2.5).set_fill(opacity=0)
        self.dot = Dot(radius=0.055, color=col) if dot else VectorizedPoint()
        super().__init__(self.line, self.dot, lab)
        # a plain closure, never the scene itself: mobjects get deep-copied by animations
        self.to_screen = (lambda p, _s=scene: _s.to_screen(p))
        self.anchor_fn, self.at, self.side, self.dist, self.buff = _anchor_fn(anchor), at, \
            np.array(side, dtype=float), dist, buff
        self.grow = ValueTracker(1.0)
        self.add_updater(lambda m: m.sync())
        self.sync()

    def _place(self, a: np.ndarray) -> np.ndarray:
        if self.at is None:
            return a + self.side * (self.dist + self.label.width / 2 * abs(self.side[0])
                                    + self.label.height / 2 * abs(self.side[1]))
        at = self.at(a) if callable(self.at) else _pt(self.at)
        return at

    def sync(self):
        a = self.to_screen(self.anchor_fn())
        keep_safe(self.label.move_to(self._place(a)))
        c = self.label.get_center()
        e = _ws._exit_point(self.label, a - c) if np.linalg.norm(a - c) > 1e-6 else c
        u = (a - e) / (np.linalg.norm(a - e) or 1)
        e = e + u * self.buff
        g = float(self.grow.get_value())
        end = a + (e - a) * max(g, 0.001)
        self.line.set_points_as_corners([a, end])
        self.dot.move_to(a)
        return self

    def enter(self, run_time: float = 0.8):
        self.grow.set_value(0.0)
        self.sync()
        return AnimationGroup(FadeIn(self, suspend_mobject_updating=False, rate_func=ease_out),
                              self.grow.animate(rate_func=ease_out).set_value(1.0), run_time=run_time)

    def leave(self, run_time: float = 0.4):
        return FadeOut(self, run_time=run_time)


# --------------------------------------------------------------------------- the scene

class WaitwhatScene3D(WaitwhatScene, ThreeDScene):
    """WaitwhatScene in 3D: ThreeDScene on the fast waitwhat camera, framed on the safe area, house
    view (VIEW_PHI, VIEW_THETA). Narration timing, sound cues, themes, aspect and lint as usual."""

    #: the view a scene starts from (radians); FLAT_PHI/FLAT_THETA starts as a 2D picture
    view_phi: float = VIEW_PHI
    view_theta: float = VIEW_THETA
    view_zoom: float = 1.0

    def __init__(self, **kwargs):
        kwargs.setdefault("camera_class", WaitwhatCamera3D)
        super().__init__(**kwargs)

    def setup(self):
        super().setup()
        self._drift: dict = {}
        self._perf = {"faces_max": 0, "motion_s": 0.0, "work": 0.0}
        self._full_redraw = False
        self.set_camera_orientation(phi=self.view_phi, theta=self.view_theta, zoom=self.view_zoom)

    # ---- screen space
    def to_screen(self, point) -> np.ndarray:
        """Where a 3D point is on screen right now (frame units, z = 0): for placing flat things."""
        cam = self.camera.fresh()
        p = cam.project_points(np.array([_pt(point)]))[0]
        return np.array([p[0], p[1], 0.0])

    def fixed(self, *mobs):
        """Keep mobjects flat on the screen (they ignore the camera), without adding them yet, so
        they can enter with an animation: self.play(Write(self.fixed(title)))."""
        self.camera.add_fixed_in_frame_mobjects(*mobs)
        return mobs[0] if len(mobs) == 1 else VGroup(*mobs)

    def hud(self, *mobs):
        """fixed(...) and add them now."""
        self.fixed(*mobs)
        self.add(*mobs)
        return mobs[0] if len(mobs) == 1 else VGroup(*mobs)

    def pin(self, mob: Mobject, anchor, offset=UP * 0.45) -> Mobject:
        """A flat label that follows a 3D point (a Mobject's centre, a point, or a function) at a
        screen offset, upright and the same size whatever the camera does. Returns mob (not added)."""
        get = _anchor_fn(anchor)
        off = np.array(offset, dtype=float)
        self.fixed(mob)
        mob.add_updater(lambda m: keep_safe(m.move_to(self.to_screen(get()) + off)))
        keep_safe(mob.move_to(self.to_screen(get()) + off))
        return mob

    def tag(self, mob: Mobject, target: Mobject, direction=DOWN, buff: float = 0.2) -> Mobject:
        """A flat label next to a 3D object's outline on screen (next_to, projected): it clears the
        object at any zoom or angle and follows it. Use for names of things (Sun, Earth, the cell);
        pin() for a point, callout() when the label sits away from what it names. Returns mob."""
        d = np.array(direction, dtype=float)
        self.fixed(mob)

        def place(m):
            x0, y0, x1, y1 = self._screen_box(target)
            c = np.array([(x0 + x1) / 2, (y0 + y1) / 2, 0.0])
            edge = c + np.array([d[0] * (x1 - x0) / 2, d[1] * (y1 - y0) / 2, 0.0])
            m.move_to(edge + d * (buff + abs(d[0]) * m.width / 2 + abs(d[1]) * m.height / 2))
            return keep_safe(m)

        mob.add_updater(place)
        return place(mob)

    def callout(self, label, anchor, at=None, side=RIGHT, dist: float = 1.3, color=None, dot: bool = True) -> Callout:
        """A flat label + leader line to a 3D anchor (Mobject, point or function). The label sits at
        `side` of the anchor's screen point (dist units away), or at `at` (a fixed screen point, or a
        function of the anchor's screen point). self.play(c.enter()) / c.leave()."""
        c = Callout(self, label, anchor, at=at, side=side, dist=dist, color=color, dot=dot)
        self.fixed(c)
        return c

    def label_layers(self, stack, names=None, side=None, x: float | None = None, color=None,
                     gap: float = 0.16, texts=None) -> list[Callout]:
        """Callouts for the layers of an exploded stack or a cutaway (its .names and .anchors), in a
        column at the side (right by default) that keeps them apart however close the layers come on
        screen. Returns the callouts in stack order: self.play(*[c.enter() for c in labels]), or one
        per bookmark. A cutaway labelled on the left uses its anchors_left. texts: what the labels
        say, if not the names (e.g. two-line versions in 9:16: by_aspect(n, n.replace(" ", "\\n")))."""
        names = names or stack.names
        side = np.array(side if side is not None else RIGHT, dtype=float)
        anchors = stack.anchors
        if side[0] < 0 and getattr(stack, "anchors_left", None):
            anchors = stack.anchors_left
        texts = texts or names
        return self.label_column([(t, anchors[n]) for t, n in zip(texts, names)], side=side, x=x, color=color, gap=gap,
                                 clear=stack)

    def label_column(self, items, side=RIGHT, x: float | None = None, color=None, gap: float = 0.16,
                     reach: float = 0.6, clear: Mobject | None = None) -> list[Callout]:
        """Callouts for several 3D points as one tidy column of labels at the side of the frame:
        items = [(text or mobject, anchor), ...]. Each label follows its anchor's height on screen,
        pushed apart so they never overlap, and kept inside the safe area. The column stands `reach`
        units beside the outermost anchor, or beside the whole of `clear` (the object, as seen now),
        or at screen x = `x`; never past the safe area."""
        side = np.array(side, dtype=float)
        labs = [T(t, size=SIZE_LABEL, color=INK) if isinstance(t, str) else t for t, _ in items]
        anchors = [_anchor_fn(a) for _, a in items]
        wmax = max(l.width for l in labs)
        if x is not None:
            col_x = x
        else:
            xs = [self.to_screen(f())[0] for f in anchors]
            box = self._seen_box(clear) if clear is not None else None
            if box is not None:
                xs += [box[0], box[2]]
            if side[0] >= 0:
                col_x = min(SAFE_RIGHT - wmax / 2, max(xs) + reach + wmax / 2)
            else:
                col_x = max(SAFE_LEFT + wmax / 2, min(xs) - reach - wmax / 2)
        cache = {"key": None, "ys": None}

        def ys_now():
            cam = self.camera
            key = (round(self.renderer.time, 4), cam.get_theta(), cam.get_phi(), cam.get_zoom(),
                   tuple(np.round([f()[2] for f in anchors], 4)))
            if cache["key"] != key:
                raw = np.array([self.to_screen(f())[1] for f in anchors], dtype=float)
                order = np.argsort(-raw, kind="stable")
                hs = [l.height for l in labs]
                ys = raw.copy()
                prev = None
                for i in order:                      # top to bottom, pushed down to keep a gap
                    lim = SAFE_TOP - hs[i] / 2 if prev is None else ys[prev] - (hs[prev] + hs[i]) / 2 - gap
                    ys[i] = min(raw[i], lim)
                    prev = i
                low = SAFE_BOTTOM + hs[order[-1]] / 2   # lift the column if it fell off the bottom
                if ys[order[-1]] < low:
                    ys += low - ys[order[-1]]
                cache["key"], cache["ys"] = key, ys
            return cache["ys"]

        return [self.callout(lab, f, at=(lambda a, i=i: np.array([col_x, ys_now()[i], 0.0])), color=color)
                for i, (lab, f) in enumerate(zip(labs, anchors))]

    def axis_labels(self, axes: ThreeDAxes, x: str = "x", y: str = "y", z: str = "z", size: float = 40):
        """Flat x / y / z letters pinned just past the axes' tips. Returns a VGroup (not added)."""
        out = VGroup()
        for name, ax, off in ((x, axes.x_axis, RIGHT * 0.35 + DOWN * 0.2), (y, axes.y_axis, RIGHT * 0.3),
                              (z, axes.z_axis, UP * 0.35)):
            if name:
                out.add(self.pin(_ws.M(name, size=size, color=INK_2), ax.get_end(), offset=off))
        return out

    # ---- camera grammar
    def view(self, phi=None, theta=None, zoom=None, look_at=None, shift=None, gamma=None):
        """Set the camera now (radians): view(phi=70*DEGREES, theta=-40*DEGREES, zoom=1.2,
        look_at=point, shift=screen offset)."""
        self.set_camera_orientation(phi=phi, theta=theta, zoom=zoom, gamma=gamma)
        if look_at is not None:
            self.camera.look.move_to(_pt(look_at))
        if shift is not None:
            self.camera.shift.move_to(_pt(shift))

    def camera_to(self, phi=None, theta=None, zoom=None, look_at=None, shift=None, gamma=None,
                  run_time: float = 2.5, rate_func=smooth, added_anims=(), **kw):
        """Move the camera (smooth ease-in-out, the house easing for moves). Other animations can
        ride along in added_anims; play() kwargs such as sfx pass through."""
        cam = self.camera
        anims = [tr.animate.set_value(v) for v, tr in ((phi, cam.phi_tracker), (theta, cam.theta_tracker),
                                                        (zoom, cam.zoom_tracker), (gamma, cam.gamma_tracker))
                 if v is not None]
        if look_at is not None:
            anims.append(cam.look.animate.move_to(_pt(look_at)))
        if shift is not None:
            anims.append(cam.shift.animate.move_to(_pt(shift)))
        self.play(*anims, *added_anims, run_time=run_time, rate_func=rate_func, **kw)

    def move_camera(self, phi=None, theta=None, gamma=None, zoom=None, focal_distance=None,
                    frame_center=None, added_anims=(), **kwargs):
        """Manim's move_camera, routed through camera_to (frame_center becomes look_at)."""
        kwargs.setdefault("rate_func", smooth)
        if focal_distance is not None:
            self.camera.set_focal_distance(focal_distance)
        self.camera_to(phi=phi, theta=theta, zoom=zoom, gamma=gamma, look_at=frame_center,
                       added_anims=added_anims, **kwargs)

    def orbit(self, by: float = PI / 4, run_time: float = 4.0, dphi: float = 0.0, zoom=None, **kw):
        """Swing the camera around the vertical axis by `by` radians (plus tilt dphi) in one eased move."""
        cam = self.camera
        self.camera_to(theta=cam.get_theta() + by, phi=cam.get_phi() + dphi if dphi else None, zoom=zoom,
                       run_time=run_time, **kw)

    def dolly(self, zoom: float = 1.4, run_time: float = 2.0, look_at=None, **kw):
        """Push in (zoom > current) or pull out, optionally re-aiming at look_at."""
        self.camera_to(zoom=zoom, look_at=look_at, run_time=run_time, **kw)

    def drift(self, rate: float = 0.06, about: str = "theta", ramp: float = 1.0):
        """Slow ambient camera rotation (rad/s) that eases in over `ramp` s and keeps going through
        waits and other animations, until stop_drift() eases it out. Costs a full redraw every frame:
        keep drifting stretches short (MOTION_BUDGET)."""
        cam = self.camera
        tr = {"theta": cam.theta_tracker, "phi": cam.phi_tracker, "gamma": cam.gamma_tracker}[about]
        st = self._drift.get(about)
        if st is None:
            st = self._drift[about] = {"rate": 0.0, "target": rate, "ramp": max(ramp, 0.05)}

            def upd(m, dt, st=st, about=about):
                k = min(1.0, dt * 4.0 / st["ramp"])
                st["rate"] += (st["target"] - st["rate"]) * k
                if st["target"] == 0 and abs(st["rate"]) < 2e-3:
                    m.remove_updater(st["fn"])
                    self._drift.pop(about, None)
                    return
                m.increment_value(st["rate"] * dt)

            st["fn"] = upd
            tr.add_updater(upd)
            self.add(tr)
        st["target"], st["ramp"] = rate, max(ramp, 0.05)

    def stop_drift(self, about: str = "theta", ramp: float = 0.8):
        """Ease the drift out over the next `ramp` seconds (it stops itself)."""
        st = self._drift.get(about)
        if st:
            st["target"], st["ramp"] = 0.0, max(ramp, 0.05)

    def fit_zoom(self, mob: Mobject, fill: float = 0.8, phi=None, theta=None, below: Mobject | None = None) -> float:
        """The zoom at which mob fills `fill` of the free safe area (under `below`, e.g. a title) seen
        from phi/theta (default: the current angles). Use: self.view(zoom=self.fit_zoom(stack))."""
        cam = self.camera
        keep = (cam.get_phi(), cam.get_theta(), cam.get_zoom())
        cam.set_phi(keep[0] if phi is None else phi)
        cam.set_theta(keep[1] if theta is None else theta)
        cam.set_zoom(1.0)
        cam.fresh()
        P = cam.project_points(mob.get_all_points())
        cam.set_phi(keep[0]); cam.set_theta(keep[1]); cam.set_zoom(keep[2]); cam.fresh()
        w = max(P[:, 0].max() - P[:, 0].min(), 1e-3)
        h = max(P[:, 1].max() - P[:, 1].min(), 1e-3)
        x0, y0, x1, y1 = _ws.content_box(below)
        return float(min(fill * (x1 - x0) / w, fill * (y1 - y0) / h))

    def light_from(self, point=None, ambient: float | None = None):
        """Light the scene from a world point (a sun, a lamp) instead of the viewer's upper left;
        lower ambient (e.g. 0.25) gives a real night side (lifted a little on light themes).
        light_from() restores the headlight."""
        if ambient is None:
            ambient = 0.6
        cam = self.camera
        cam.headlight = point is None
        cam.light_point = None if point is None else _pt(point)
        cam.ambient = ambient if IS_DARK else 1 - (1 - ambient) * 0.6   # light themes: softer night side

    def animate_surface(self, s: Surface, run_time: float, speed: float = 1.0, **kw):
        """Run a live surface (graph_surface(..., live=True)) forward in time for run_time seconds."""
        t0 = s.time
        self.play(UpdateFromAlphaFunc(s, lambda m, a: m.set_time(t0 + speed * run_time * a)),
                  run_time=run_time, rate_func=rate_functions.linear, **kw)

    def keep_surface_moving(self, s: Surface, speed: float = 1.0):
        """Let a live surface keep moving through waits and other animations (an updater). Every
        frame becomes a full redraw while it moves: s.clear_updaters() when the point is made."""
        s.add_updater(lambda m, dt: m.set_time(m.time + speed * dt))

    # ---- invisible physics
    def particles(self, path, n: int = 16, speed: float = 0.25, color="YELLOW", radius: float = 0.06,
                  glow: bool = True, follow: bool = False, fade_ends: bool = True) -> VGroup:
        """Dots streaming along a 3D path (a VMobject or a function s∈[0,1] -> point): charge in a
        wire, blood in a vessel, a signal on a nerve, air through a pipe. They are drawn flat and
        round on the screen (over solids, like an x-ray), move by themselves (an updater: `speed`
        laps per second), and appear/disappear at open ends. follow=True re-reads a path that moves.
        Returns the group (not added): self.add(p) or self.play(FadeIn(p)); p.clear_updaters() to stop."""
        col = _named(color)
        if callable(path) and not isinstance(path, Mobject):
            fn = lambda s: _pt(path(s))
            closed = np.linalg.norm(fn(0.0) - fn(1.0)) < 1e-3
        else:
            fn, closed = None, None

        def sample():
            if fn is not None:
                return np.array([fn(s) for s in np.linspace(0, 1, 241)])
            return np.array([path.point_from_proportion(s) for s in np.linspace(0, 1, 241)])

        state = {"pts": sample(), "phase": 0.0}
        if closed is None:
            closed = np.linalg.norm(state["pts"][0] - state["pts"][-1]) < 1e-3
        seg = np.linalg.norm(np.diff(state["pts"], axis=0), axis=1)
        state["cum"] = np.concatenate([[0], np.cumsum(seg)]) / max(seg.sum(), 1e-9)
        dots = VGroup()
        for _ in range(n):
            d = VGroup()
            if glow:
                d.add(Dot(radius=radius * 3.2, color=col, fill_opacity=0.12),
                      Dot(radius=radius * 1.9, color=col, fill_opacity=0.25))
            d.add(Dot(radius=radius, color=col, fill_opacity=1.0))
            d.base = [m.get_fill_opacity() for m in d]
            dots.add(d)

        def place(group, dt=0.0):
            state["phase"] = (state["phase"] + speed * dt) % 1.0
            if follow:
                state["pts"] = sample()
            s = (np.arange(n) / n + state["phase"]) % 1.0
            idx = np.interp(s, state["cum"], np.arange(len(state["cum"])))
            i0 = np.clip(np.floor(idx).astype(int), 0, len(state["pts"]) - 2)
            f = (idx - i0)[:, None]
            P = state["pts"][i0] * (1 - f) + state["pts"][i0 + 1] * f
            cam = self.camera.fresh()
            Q = cam.project_points(P)
            for k, d in enumerate(group):
                d.move_to([Q[k, 0], Q[k, 1], 0])
                a = 1.0
                if fade_ends and not closed:
                    a = min(1.0, s[k] / 0.08, (1 - s[k]) / 0.08)
                for m, b in zip(d, d.base):
                    m.set_fill(opacity=b * a)
            return group

        self.fixed(dots)
        dots.add_updater(place)
        place(dots)
        return dots

    def ripples(self, center=ORIGIN, normal=OUT, n: int = 3, max_radius: float = 3.0, period: float = 1.8,
                color="BLUE", width: float = 3) -> VGroup:
        """Expanding rings in the plane facing `normal` (sound from a speaker, a wave from a touch, a
        field spreading): each ring grows from the centre to max_radius and fades, n at a time, one
        every period/n seconds. Moves by itself (an updater); r.clear_updaters() and fade it to stop."""
        col = _named(color)
        c0 = _pt(center)
        nv = np.array(normal, dtype=float)
        nv = nv / (np.linalg.norm(nv) or 1)
        u = np.cross(nv, RIGHT if abs(nv[0]) < 0.9 else UP)
        u = u / np.linalg.norm(u)
        v = np.cross(nv, u)
        ang = np.linspace(0, TAU, 49)
        unit = np.outer(np.cos(ang), u) + np.outer(np.sin(ang), v)
        rings = VGroup(*[VMobject().set_stroke(col, width).set_fill(opacity=0) for _ in range(n)])
        state = {"t": 0.0}

        def upd(g, dt=0.0):
            state["t"] += dt
            for k, ring in enumerate(g):
                ph = ((state["t"] / period) + k / n) % 1.0
                r = max(0.02, ph * max_radius)
                ring.set_points_as_corners(c0 + unit * r)
                ring.set_stroke(opacity=(1 - ph) ** 1.5)
            return g

        rings.add_updater(upd)
        upd(rings)
        return rings

    # ---- perf + 3D lint
    def get_moving_mobjects(self, *animations):
        cam = self.camera
        moving = super().get_moving_mobjects(*animations)
        if moving is self.mobjects or len(moving) == len(self.mobjects):
            self._full_redraw = True
            return moving
        if any(m in moving for m in (cam.look, cam.shift)):
            self._full_redraw = True
            return self.mobjects
        # a shaded thing moving among static solids must be depth-sorted with them: redraw all
        for m in moving:
            for f in m.family_members_with_points():
                if getattr(f, "shade_in_3d", False):
                    self._full_redraw = True
                    return self.mobjects
        return moving

    def play(self, *args, **kwargs):
        cam = self.camera
        before = (cam.get_phi(), cam.get_theta(), cam.get_zoom(), tuple(cam.look.points[0]), tuple(cam.shift.points[0]))
        t0 = self.now
        self._full_redraw = False
        super().play(*args, **kwargs)
        dt = self.now - t0
        after = (cam.get_phi(), cam.get_theta(), cam.get_zoom(), tuple(cam.look.points[0]), tuple(cam.shift.points[0]))
        try:
            faces = sum(1 for m in extract_mobject_family_members(self.mobjects, only_those_with_points=True)
                        if getattr(m, "shade_in_3d", False))
            self._perf["faces_max"] = max(self._perf["faces_max"], faces)
            if before != after or self._drift or self._full_redraw:
                self._perf["motion_s"] = round(self._perf["motion_s"] + dt, 2)
                self._perf["work"] += faces * dt
        except Exception:
            pass

    def _screen_box(self, m):
        cam = self.camera
        cam.refresh_fixed()
        if cam.is_fixed(m):
            return super()._screen_box(m)
        pts = m.get_all_points()
        if len(pts) == 0:
            return super()._screen_box(m)
        P = cam.fresh().project_points(pts)
        return float(P[:, 0].min()), float(P[:, 1].min()), float(P[:, 0].max()), float(P[:, 1].max())

    def _seen_box(self, m):
        """Screen box of the visible parts of m (anything faded out is ignored), or None."""
        seen = [f.points for f in m.family_members_with_points()
                if max(float(np.max(f.get_fill_opacities(), initial=0)),
                       float(np.max(f.get_stroke_opacities(), initial=0))) > 0.05]
        if not seen:
            return None
        P = self.camera.fresh().project_points(np.concatenate(seen))
        return float(P[:, 0].min()), float(P[:, 1].min()), float(P[:, 0].max()), float(P[:, 1].max())

    def _check_layout(self):
        super()._check_layout()
        cam = self.camera
        hw, hh = FRAME_W / 2, FRAME_H / 2
        for t in self._texts():
            if self._visible(t) and not cam.is_fixed(t) and t not in cam.fixed_orientation_mobjects:
                name = str(getattr(t, "original_text", None) or getattr(t, "tex_string", None) or type(t).__name__)[:40]
                self._lint.append({"t": round(self.now, 2), "issue": "text in 3D space (it skews and hides behind "
                                   "solids): use self.fixed(), self.pin() or self.callout()", "what": name})
        for m in self.mobjects:
            if (isinstance(m, (ValueTracker, Point)) or cam.is_fixed(m) or getattr(m, "ww_bleed", False)
                    or not isinstance(m, VMobject)):
                continue
            box = self._seen_box(m)
            if box is None:
                continue
            x0, y0, x1, y1 = box
            if x1 - x0 < 1e-3 and y1 - y0 < 1e-3:
                continue
            if x0 < -hw + 0.1 or x1 > hw - 0.1 or y0 < -hh + 0.1 or y1 > hh - 0.1:
                self._lint.append({"t": round(self.now, 2), "issue": "3D object runs off the frame (zoom out, "
                                   "self.fit_zoom(), or bleed(mob) if intended)", "what": type(m).__name__,
                                   "box": [round(v, 2) for v in (x0, y0, x1, y1)]})

    def _write_report(self):
        p = getattr(self, "_perf", None)
        if p is not None:
            # measured on Cairo at 1080p30: ~25 µs per face per redrawn frame, plus ~0.25 s per second of
            # video for everything else (text, encoding, start-up)
            p["est_render_s"] = round(p["work"] * 30 * 25e-6 + self.now * 0.25, 1)
            heavy = []
            if p["faces_max"] > FACE_BUDGET:
                heavy.append(f"{p['faces_max']} faces on screen (budget {FACE_BUDGET}): lower the resolutions")
            if p["est_render_s"] > RENDER_BUDGET:
                heavy.append(f"about {p['est_render_s']:.0f} s to render (budget {RENDER_BUDGET:.0f} s): "
                             f"{p['motion_s']:.0f} s of 3D motion with up to {p['faces_max']} faces; hold the "
                             "camera still while the narration explains, or use fewer faces")
            for h in heavy:
                if not any(i.get("issue") == "render budget" and i.get("what") == h for i in self._lint):
                    self._lint.append({"t": round(self.now, 2), "issue": "render budget", "what": h})
        super()._write_report()
