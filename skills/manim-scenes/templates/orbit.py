"""Template (3D): an orbit seen flat from above, then tilted to show what the flat view hides.

Narration bookmarks used: "sun", "earth", "tilt", "summer", "winter".
For anything that moves around something: planets and moons, satellites, electrons in the
classic picture, a pendulum seen from above, a spinning top's axis.
Pattern: start as a plain 2D diagram (FLAT view) → tilt the camera on the word that needs depth
(the axis tilt) → the motion continues while one consequence is named (summer / winter). Light
comes from the Sun (light_from), so the planet has a day and a night side. Labels are pinned:
they follow their objects, flat on the screen.
Both aspects: the orbit is a circle; 9:16 zooms out so it spans the width. Budget: ~420 faces,
the Earth moves the whole scene (an updater): keep such scenes ≤ ~25 s.
"""
from waitwhat_style import *

R_ORBIT, TILT = 4.2, 23.4 * DEGREES


class Seasons(WaitwhatScene3D):
    view_phi, view_theta = FLAT_PHI, FLAT_THETA

    def construct(self):
        sun = depth_sorted(ball(0.75, "GOLD", resolution=(16, 10), checker=False))   # unlit: it is the light
        self.light_from(ORIGIN, ambient=0.35)                        # day and night sides
        path = glow_path(orbit_path(R_ORBIT), color="INK_2", width=2, glow=0.6, depth=True)
        self.view(zoom=self.fit_zoom(path, fill=by_aspect(0.85, 0.7)))   # room for the labels

        earth = ball(0.42, "BLUE", resolution=(16, 10))
        axis = depth_sorted(Line(IN * 0.75, OUT * 0.75, stroke_width=4, color=INK).rotate(TILT, axis=UP))
        planet = VGroup(earth, axis)
        angle = ValueTracker(-PI / 2)                                # where the Earth is on its orbit
        planet.add_updater(lambda m: m.move_to(R_ORBIT * np.array([np.cos(angle.get_value()),
                                                                   np.sin(angle.get_value()), 0])))
        planet.update()

        sun_lab = self.tag(T("Sun", size=SIZE_LABEL, color=INK_2), sun, LEFT)      # beside it at any zoom
        earth_lab = self.tag(T("Earth", size=SIZE_LABEL, color=INK_2), earth, UP)

        self.play(GrowFromCenter(sun), run_time=self.until("sun", minimum=0.8))
        self.play(enter(sun_lab))
        self.wait_until("earth")
        # timed so the Earth is on the far side (north pole leaning to the Sun) on "summer" and half
        # an orbit later on "winter": the picture must agree with the words
        t_s, t_w = self.mark_time("summer"), self.mark_time("winter")
        rate = PI / max(4.0, t_w - t_s)
        angle.set_value(PI - rate * (t_s - self.now - 1.5))
        planet.update()
        self.play(Create(path), FadeIn(planet), enter(earth_lab), run_time=1.5)
        angle.add_updater(lambda m, dt: m.increment_value(rate * dt))   # keeps orbiting from now on
        self.add(angle)

        self.wait_until("tilt")
        tilt_lab = self.pin(M(r"23.4^\circ", size=40, color=YELLOW), lambda: axis.get_end(), offset=UR * 0.4)
        phi = by_aspect(72, 50) * DEGREES                            # 9:16: from higher, a taller ellipse
        zoom = self.fit_zoom(path, fill=by_aspect(0.75, 0.75), phi=phi, theta=-70 * DEGREES)
        self.camera_to(phi=phi, theta=-70 * DEGREES, zoom=zoom, run_time=2.5, added_anims=[enter(tilt_lab), FadeOut(earth_lab)])

        self.wait_until("summer")
        season = self.tag(hand("summer", size=SIZE_LABEL), earth, RIGHT)          # one label per object at a time
        self.play(enter(season), FadeOut(tilt_lab))
        self.wait_until("winter")
        winter = self.tag(hand("winter", size=SIZE_LABEL), earth, RIGHT)
        self.play(FadeOut(season), enter(winter))
        self.finish()
