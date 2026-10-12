"""Template: a visual proof that builds a formula from a picture.

Example: 1 + 3 + 5 + ... + (2n-1) = n^2, shown as L-shaped layers that grow a square.
Narration bookmarks used: "first", "grow", "formula".
Pattern: concrete case first (dots you can count), then the general rule as a summary.
"""
from waitwhat_style import *

N = 5


class OddSquares(WaitwhatScene):
    def construct(self):
        cell = 0.62
        layers = VGroup()
        colors = [color_of("layer1", BLUE), color_of("layer2", TEAL), color_of("layer3", PINK),
                  color_of("layer4", GOLD), color_of("layer5", GREEN)]
        for k in range(N):  # layer k is an L of 2k+1 squares around the k x k block
            cells = [(i, k) for i in range(k + 1)] + [(k, j) for j in range(k)]
            L = VGroup(*[Square(cell * 0.92, stroke_width=2, color=colors[k]).set_fill(colors[k], 0.55)
                         .move_to(np.array([i * cell, j * cell, 0])) for i, j in cells])
            layers.add(L)
        layers.move_to(LEFT * 3)

        counts = VGroup(*[M(str(2 * k + 1), size=48, color=colors[k]) for k in range(N)])
        plus = [M("+", size=48) for _ in range(N - 1)]
        sum_row = VGroup(*[x for pair in zip(counts, plus + [VMobject()]) for x in pair])
        sum_row.arrange(RIGHT, buff=0.25).move_to(RIGHT * 3.3 + UP * 1.2)

        # concrete first: one square, then three, then five...
        self.play(enter(layers[0]), FadeIn(counts[0], shift=UP * 0.1))
        self.wait_until("first")
        for k in range(1, N):
            self.play(
                LaggedStart(*[GrowFromCenter(c) for c in layers[k]], lag_ratio=0.08),
                FadeIn(plus[k - 1]), FadeIn(counts[k], shift=UP * 0.1),
                run_time=1.0 if k < N - 1 else 1.4,
            )
        self.wait_until("grow")
        frame = SurroundingRectangle(layers, color=YELLOW, buff=0.08, stroke_width=3)
        side = M(f"{N}", size=48, color=INK).next_to(frame, DOWN, buff=0.2)
        self.play(Create(frame), FadeIn(side), run_time=1.0)

        # the general rule, as a summary of what we can already see
        rule = M(r"1 + 3 + 5 + \cdots + (2n-1) = n^2", size=54).move_to(RIGHT * 3.3 + DOWN * 0.6)
        fit(rule, 6.4)
        self.wait_until("formula")
        self.play(Write(rule), run_time=1.6)
        self.play(Create(pencil_circle(rule[0][-2:], buff=0.22, seed=3)), run_time=0.6)
        self.finish()
