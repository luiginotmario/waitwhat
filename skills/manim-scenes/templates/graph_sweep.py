"""Template: a function whose parameter is swept, with a live readout.

Narration bookmarks used: "curve", "sweep", "flip".
Pattern: ValueTracker drives the curve, a dot and the number together (cause → effect).
"""
from waitwhat_style import *


class ParabolaSweep(WaitwhatScene):
    def construct(self):
        ax = Axes(x_range=[-3, 3, 1], y_range=[-4, 4, 2], x_length=7.5, y_length=6,
                  axis_config={"color": INK_3, "stroke_width": 2, "include_ticks": True,
                               "tick_size": 0.06}).shift(LEFT * 2.2)
        a = ValueTracker(1.0)
        col = color_of("curve", BLUE)
        def xmax():  # keep the curve inside the axes (|y| <= 4)
            return min(3.0, (4.0 / max(abs(a.get_value()), 1e-3)) ** 0.5)

        curve = always_redraw(lambda: ax.plot(lambda x: a.get_value() * x ** 2, x_range=[-xmax(), xmax()],
                                              color=col, stroke_width=5).set_z_index(1))
        dot = always_redraw(lambda: Dot(ax.c2p(min(1.2, xmax()), a.get_value() * min(1.2, xmax()) ** 2),
                                         color=YELLOW, radius=0.09))
        readout = VGroup(M(r"y = a\,x^2", size=56, colors={"a": col}),
                         VGroup(M("a =", size=52), DecimalNumber(1.0, num_decimal_places=2, font_size=52, color=col))
                         .arrange(RIGHT, buff=0.2)).arrange(DOWN, buff=0.5, aligned_edge=LEFT)
        readout.move_to(RIGHT * 4.3 + UP * 1.0)
        readout[1][1].add_updater(lambda m: m.set_value(a.get_value()))

        self.play(Create(ax), run_time=1.2)
        self.wait_until("curve")
        self.play(Create(curve), enter(readout), run_time=1.5)
        self.add(dot)
        self.wait_until("sweep")
        self.play(a.animate.set_value(2.5), run_time=2.0)
        self.play(a.animate.set_value(0.3), run_time=2.0)
        self.wait_until("flip")
        self.play(a.animate.set_value(-1.0), run_time=2.2)
        self.finish()
