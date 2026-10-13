"""Template: A vs B with real numbers that grow into bars, then the takeaway.

Narration bookmarks used: "left", "right", "ratio". Replace DATA with sourced numbers only.
Pattern: counters tick up while bars grow (accumulation); the ratio is the aha, circled.
Both aspects: tall bars stay side by side in 9:16 too (they are narrow); they just get taller.
"""
from waitwhat_style import *

DATA = [("Walking", 5, "km/h"), ("Cycling", 15, "km/h")]


class Compare(WaitwhatScene):
    def construct(self):
        base = by_aspect(DOWN * 2.4, UP * (SAFE_BOTTOM + 1.0))   # the bars' floor
        tall = by_aspect(4.2, 6.2)                                  # the biggest bar's height
        gap = by_aspect(4.8, 3.6)
        cols = [color_of(DATA[0][0].lower(), BLUE), color_of(DATA[1][0].lower(), TEAL)]
        top = max(v for _, v, _ in DATA)
        groups = []
        for i, ((name, val, unit), col) in enumerate(zip(DATA, cols)):
            x = -gap / 2 + gap * i
            h = ValueTracker(0.0)
            bar = always_redraw(lambda h=h, x=x, col=col: Rectangle(
                width=1.8, height=max(0.001, h.get_value() / top * tall), stroke_color=col, stroke_width=3,
                fill_color=col, fill_opacity=0.55).move_to(np.array([x, base[1], 0]), aligned_edge=DOWN))
            num = DecimalNumber(0, num_decimal_places=0, font_size=56, color=col)
            num.add_updater(lambda m, h=h, x=x, col=col: m.set_value(h.get_value()).next_to(
                np.array([x, base[1] + h.get_value() / top * tall, 0]), UP, buff=0.18))
            unit_t = T(unit, size=SIZE_SMALL, color=INK_2)
            unit_t.add_updater(lambda m, num=num: m.next_to(num, RIGHT, buff=0.12, aligned_edge=DOWN))
            name_t = T(name, size=SIZE_LABEL).next_to(np.array([x, base[1], 0]), DOWN, buff=0.25)
            groups.append((h, val, bar, num, unit_t, name_t))
        half = min(4.5, SAFE_W / 2)
        floor = Line(LEFT * half + base, RIGHT * half + base, color=INK_3, stroke_width=2)
        self.play(Create(floor), *[enter(g[5]) for g in groups], run_time=1.0)
        for (h, val, bar, num, unit_t, _), mark in zip(groups, ["left", "right"]):
            self.wait_until(mark)
            self.add(bar, num, unit_t)
            self.play(h.animate.set_value(val), run_time=1.6, rate_func=ease_out)
        ratio = M(rf"{DATA[1][1] / DATA[0][1]:g}\times", size=96, color=YELLOW).move_to(UP * by_aspect(2.6, SAFE_TOP - 0.9))
        self.wait_until("ratio")
        self.play(Write(ratio), run_time=0.9)
        self.play(Create(pencil_circle(ratio, buff=0.25, seed=8)), run_time=0.6)
        self.finish()
