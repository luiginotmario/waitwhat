"""Template (2.5D): before / after with the same character. Two little worlds in cards (panel()),
side by side in 16:9 and stacked in 9:16: the old way (greyed, worried, a pile of paper and a
clock) and the new way (bright, happy, one tap). The camera visits each, then steps back.

Narration bookmarks used: "before", "after", "difference".
Backdrop: plain (the cards carry their own places). The before/after facts come from research.
"""
from waitwhat_style import *

BEFORE, AFTER = "Before", "After"
BEFORE_COST = "2 days"          # how long / how much it took before (research)
AFTER_COST = "2 minutes"        # and after (research)


class BeforeAfter(WaitwhatScene25D):
    backdrop = "plain"

    def construct(self):
        pw, ph = by_aspect((5.7, 4.6), (6.0, 4.6))
        left = panel(pw, ph, "office", tint_k=0.55)
        right = panel(pw, ph, "room")
        side_by_side(left, right, buff=by_aspect(1.1, 0.9))

        h = ph * 0.62
        sad = cast("leo", face="worried", pose="shrug", height=h)
        happy = cast("leo", face="joy", pose="phone", height=h)
        sad.stand(x=left.get_x() - pw * 0.12, y=left.floor_y())
        happy.stand(x=right.get_x() - pw * 0.08, y=right.floor_y())
        happy.hold(phone(screen="check"))
        papers = VGroup(*[envelope(0.62).rotate(0.15 * (i - 2)).move_to(
            [left.get_x() + pw * 0.22 + 0.05 * i, left.floor_y() + 0.75 + 0.17 * i, 0]) for i in range(5)])
        clk = clock(0.38).move_to([left.get_x() + pw * 0.3, left.get_top()[1] - ph * 0.26, 0])
        lab_b = pill(BEFORE, "#8E95B2").move_to(left.get_corner(UL) + [0.95, -0.55, 0])
        lab_a = pill(AFTER, "GREEN").move_to(right.get_corner(UL) + [0.85, -0.55, 0])
        cost_b = pill(BEFORE_COST, "RED", icon_name="cross")
        cost_a = pill(AFTER_COST, "GREEN", icon_name="check")
        for c_, p_ in ((cost_b, left), (cost_a, right)):   # inside the card's lower right corner
            c_.move_to(p_.get_corner(DR) + [-c_.width / 2 - 0.25, c_.height / 2 + 0.25, 0])

        self.play(pop_in(left, right, anchor="center", gap=0.12), run_time=0.6)

        # before: lean in on the left card; the problem piles up
        self.wait_until("before")
        self.push_in(by_aspect(1.18, 1.08), to=left, run_time=1.0,
                     added_anims=[pop_in(sad, anchor="bottom"), pop_in(lab_b, anchor="center")])
        self.play(pop_in(*papers, gap=0.08, anchor="center"), pop_in(clk, anchor="center"), run_time=0.6)
        self.play(pop_in(cost_b, anchor="center"), nudge(sad))

        # after: swing over to the right card; one tap and it's done
        self.wait_until("after")
        self.pan_to(right, zoom=by_aspect(1.18, 1.08), run_time=1.1,
                    added_anims=[pop_in(happy, anchor="bottom"), pop_in(lab_a, anchor="center")])
        self.play(pop_in(cost_a, anchor="center"), burst(happy.held, n=10, spread=1.1), sfx="chime")

        # the difference: step back, the old way fades into context, the new way gets the beat
        self.wait_until("difference")
        self.pull_out(1.0, run_time=1.0)
        old = VGroup(left, sad, papers, clk, lab_b, cost_b)
        self.play(old.animate.set_opacity(0.35), nudge(right, 1.04), hop(happy, 0.35), run_time=0.6)
        self.finish()
