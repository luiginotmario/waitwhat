"""Template (3D): a surface that starts flat (a 2D picture), tilts to show depth, then moves.

Narration bookmarks used: "plane", "drop", "ring", "height", "fade".
For a field or a quantity over a plane: a ripple on water, a sound wave, a membrane, a potential
well, a probability density, elevation, heat on a plate.
Pattern: flat view (phi = 0, identical to a 2D scene: it can continue from one) → tilt to the house
view → the cause (a stone drops) → the surface moves in place (graph_surface(live=True): faces are
rewritten, not rebuilt, so it is cheap) → one point is tracked with a flat marker and a callout,
so "each point moves up and down" is seen, not just said.
Both aspects: fit_zoom() frames the plane for the aspect and the view (flat, then tilted); 9:16
looks from higher (phi 48°) so the flat plane projects taller in the tall frame. Budget: 24 x 24 =
576 faces moving for ~10 s (the heaviest template: about 2x a 2D scene's render time).
"""
from waitwhat_style import *

SPEED, K, AMP = 1.0, 3.0, 0.55        # ring speed (units per unit of surface time), wavenumber, dip depth


def height(x, y, t):
    """The water surface: a ring-shaped dip travelling outwards, smaller as it spreads."""
    r = np.sqrt(x ** 2 + y ** 2)
    front = SPEED * np.maximum(t, 0)
    on = np.clip(t * 4, 0, 1)                                       # flat before the stone lands
    packet = np.exp(-((r - front) / 1.3) ** 2) * np.cos(K * (r - front))       # a short train of rings
    return -AMP * on * packet / (1 + 0.45 * front)


class Ripple(WaitwhatScene3D):
    view_phi, view_theta = FLAT_PHI, FLAT_THETA                     # starts as a flat, 2D-looking grid

    def construct(self):
        water = graph_surface(height, x_range=(-4, 4), y_range=(-4, 4), color="BLUE", resolution=24,
                              opacity=0.9, live=True)
        water.set_time(-1.0)                                         # flat
        self.view(zoom=self.fit_zoom(water, fill=0.85))              # framed for this aspect
        self.play(FadeIn(water), run_time=self.until("plane", minimum=0.8))
        phi = by_aspect(VIEW_PHI, 48 * DEGREES)                       # 9:16: from higher, so the plane is taller
        tilted = self.fit_zoom(water, fill=by_aspect(0.8, 0.95), phi=phi, theta=VIEW_THETA)
        self.camera_to(phi=phi, theta=VIEW_THETA, zoom=tilted, run_time=2.0)

        self.wait_until("drop")
        stone = ball(0.22, "GREY", at=OUT * 3.5, resolution=(10, 6))
        self.play(FadeIn(stone), run_time=0.3)
        self.play(stone.animate.move_to(ORIGIN), run_time=0.6, rate_func=rate_functions.ease_in_quad)
        self.remove(stone)
        self.sfx("thud", gain=-3)
        # one point on the surface, tracked: a flat marker that rides the surface + a callout.
        # The wave's pace is set from the voice, so the rings reach that point on "height".
        px, py = 2.4, 0.0
        pace = (px / SPEED) / max(2.0, self.mark_time("height") + 0.4 - self.now)
        water.set_time(0.0)
        self.keep_surface_moving(water, speed=pace)                  # moves through everything below

        point = lambda: [px, py, float(height(px, py, water.time))]
        marker = self.pin(Dot(radius=0.09, color=YELLOW), point, offset=ORIGIN)
        self.wait_until("ring")
        tag = self.callout("one point", point, side=by_aspect(UR, UP), dist=1.1)
        self.wait_until("height")
        self.play(FadeIn(marker, scale=0.5), tag.enter())
        self.wait_until("fade")
        self.wait(2.0)
        water.clear_updaters()                                       # stop the motion (and the cost)
        self.finish()
