"""Template: code on the left, its live state on the right, a highlight walking the lines.

Narration bookmarks used: "code", "step1", "step2", "found".
Pattern: show the data, not just the code; every highlighted line changes something visible.
"""
from waitwhat_style import *

SRC = '''
def search(xs, target):
    lo, hi = 0, len(xs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if xs[mid] == target:
            return mid
        if xs[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
'''
XS = [3, 8, 12, 17, 23, 38, 56, 72]
TARGET = 23


class BinarySearch(WaitwhatScene):
    def construct(self):
        code = code_block(SRC, size=22).scale_to_fit_width(6.0).to_edge(LEFT, buff=0.55).shift(UP * 0.4)
        lines = code.code_lines  # one submobject per source line

        cells = VGroup(*[VGroup(Square(0.62, stroke_width=2, color=INK_3),
                                T(str(v), size=SIZE_SMALL)) for v in XS]).arrange(RIGHT, buff=0.05)
        for c in cells:
            c[1].move_to(c[0])
        cells.move_to(RIGHT * 3.5 + DOWN * 0.2)
        target = VGroup(T("target", size=SIZE_SMALL, color=INK_2), M(str(TARGET), size=40, color=YELLOW)) \
            .arrange(RIGHT, buff=0.2).next_to(cells, UP, buff=1.2)

        def ptr(name, color, above=False):
            arrow = Arrow(UP * 0.6 if above else DOWN * 0.6, ORIGIN, buff=0, color=color, stroke_width=4)
            lab = T(name, size=SIZE_SMALL, color=color)
            return VGroup(lab, arrow).arrange(DOWN, buff=0.05) if above else VGroup(arrow, lab).arrange(DOWN, buff=0.05)

        lo_p, hi_p, mid_p = ptr("lo", BLUE), ptr("hi", PINK), ptr("mid", YELLOW, above=True)

        nudge = {id(lo_p): LEFT * 0.17, id(hi_p): RIGHT * 0.17}  # lo and hi can share a cell

        def place(p, i):  # mid points down from above; lo/hi point up from below
            return p.animate.next_to(cells[i], UP if p is mid_p else DOWN, buff=0.08).shift(nudge.get(id(p), ORIGIN))

        bar = SurroundingRectangle(lines[0], color=YELLOW, buff=0.06, stroke_width=0).set_fill(YELLOW, 0.15)

        self.wait_until("code")
        self.play(FadeIn(code, shift=RIGHT * 0.2, rate_func=ease_out), enter(cells, target), run_time=1.2)
        lo_p.next_to(cells[0], DOWN, buff=0.08).shift(LEFT * 0.17)
        hi_p.next_to(cells[-1], DOWN, buff=0.08).shift(RIGHT * 0.17)
        self.play(FadeIn(bar), enter(lo_p, hi_p), run_time=0.8)
        lo, hi = 0, len(XS) - 1
        step = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            step += 1
            mark = "step1" if step == 1 else "step2" if step == 2 else None
            if mark:
                self.wait_until(mark)
            if step == 1:
                mid_p.next_to(cells[mid], UP, buff=0.08)
                show_mid = FadeIn(mid_p)
            else:
                show_mid = place(mid_p, mid)
            self.play(bar.animate.move_to(lines[3]).stretch_to_fit_width(lines[3].width + 0.12),
                      show_mid, run_time=0.8)
            if XS[mid] == TARGET:
                break
            if XS[mid] < TARGET:
                lo = mid + 1
                self.play(bar.animate.move_to(lines[7]), place(lo_p, lo),
                          *[cells[i].animate.set_opacity(0.25) for i in range(0, lo)], run_time=0.9)
            else:
                hi = mid - 1
                self.play(bar.animate.move_to(lines[9]), place(hi_p, hi),
                          *[cells[i].animate.set_opacity(0.25) for i in range(hi + 1, len(XS))], run_time=0.9)
        self.wait_until("found")
        self.play(bar.animate.move_to(lines[5]), cells[mid][0].animate.set_fill(GREEN, 0.6), run_time=0.8)
        self.play(Create(pencil_circle(cells[mid], buff=0.2, seed=6)), run_time=0.6)
        self.finish()
