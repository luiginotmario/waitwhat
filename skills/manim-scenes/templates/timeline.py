"""Template: events on a persistent timeline (history, product evolution, any sequence).

Narration bookmarks used: "e1" … "e4". Replace EVENTS with researched facts only.
Pattern: one axis stays on screen (the scene's skeleton); a marker walks along it;
each event is a dot + year + 2-4 word label, alternating above/below so nothing collides.
"""
from waitwhat_style import *

EVENTS = [  # (year, label)  ← fill from research; keep labels short
    (1837, "telegraph"),
    (1876, "telephone"),
    (1969, "ARPANET"),
    (1991, "the web"),
]


class Timeline(WaitwhatScene):
    def construct(self):
        y0, y1 = EVENTS[0][0] - 10, EVENTS[-1][0] + 10
        line = NumberLine(x_range=[y0, y1, 10], length=12, color=INK_3, include_ticks=True,
                          tick_size=0.05, stroke_width=3).shift(DOWN * 0.3)
        self.play(Create(line), run_time=1.2)
        marker = Triangle(color=YELLOW, fill_opacity=1).scale(0.12).rotate(PI)
        marker.next_to(line.n2p(y0), UP, buff=0.05)
        self.play(FadeIn(marker))
        for i, (year, text) in enumerate(EVENTS):
            col = CONCEPT_CYCLE[i % len(CONCEPT_CYCLE)]
            p = line.n2p(year)
            dot = Dot(p, radius=0.11, color=col)
            up = i % 2 == 0
            stem = Line(p, p + (UP if up else DOWN) * 1.1, color=col, stroke_width=2)
            yr = M(str(year), size=40, color=col).next_to(stem, UP if up else DOWN, buff=0.12)
            lab = T(text, size=SIZE_LABEL).next_to(yr, UP if up else DOWN, buff=0.12)
            self.play(marker.animate.next_to(p, UP, buff=0.05), run_time=self.until(f"e{i + 1}", minimum=0.6))
            self.play(GrowFromCenter(dot), Create(stem), enter(yr, lab), run_time=0.9)
        self.play(FadeOut(marker))
        self.finish()
