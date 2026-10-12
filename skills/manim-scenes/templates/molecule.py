"""Template: a molecule built atom by atom, then one property annotated.

Narration bookmarks used: "atoms", "angle", "polar".
Pattern: build → measure (angle, length) → explain the consequence (here: polarity).
"""
from waitwhat_style import *


class Water(WaitwhatScene):
    def construct(self):
        ang = np.radians(104.5)
        r = 2.0
        h1 = (r * np.cos(PI / 2 + ang / 2), r * np.sin(PI / 2 + ang / 2) - 1.0)
        h2 = (r * np.cos(PI / 2 - ang / 2), r * np.sin(PI / 2 - ang / 2) - 1.0)
        mol = molecule([("O", (0, -1.0)), ("H", h1), ("H", h2)], [(0, 1, 1), (0, 2, 1)], scale=1.6)
        mol.move_to(LEFT * 2.2)
        sticks, balls = mol

        self.wait_until("atoms")
        self.play(GrowFromCenter(balls[0]), run_time=0.8)
        self.play(LaggedStart(*[AnimationGroup(Create(s), GrowFromCenter(b))
                                for s, b in zip(sticks, balls[1:])], lag_ratio=0.4), run_time=1.6)

        o = balls[0].get_center()
        arc = Angle(Line(o, balls[1].get_center()), Line(o, balls[2].get_center()), radius=0.9,
                    other_angle=True, color=YELLOW, stroke_width=4)
        deg = M(r"104.5^\circ", size=44, color=YELLOW).next_to(arc, UP, buff=0.15)
        self.wait_until("angle")
        self.play(Create(arc), Write(deg), run_time=1.2)

        self.wait_until("polar")
        minus = M(r"\delta^-", size=52, color=color_of("negative", BLUE)).next_to(balls[0], DOWN, buff=0.25)
        plus1 = M(r"\delta^+", size=52, color=color_of("positive", RED)).next_to(balls[1], UP, buff=0.2)
        plus2 = M(r"\delta^+", size=52, color=color_of("positive", RED)).next_to(balls[2], UP, buff=0.2)
        self.play(enter(minus, plus1, plus2), run_time=1.0)
        dipole = Arrow(o + DOWN * 0.1, o + UP * 2.3, color=INK_2, stroke_width=5, buff=0)
        dipole.move_to(RIGHT * 2.4)
        lab = T("polar", size=SIZE_LABEL, color=INK_2).next_to(dipole, RIGHT, buff=0.3)
        self.play(GrowArrow(dipole), enter(lab), run_time=1.2)
        self.finish()
