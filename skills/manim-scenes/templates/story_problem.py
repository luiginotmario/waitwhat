"""Template (2.5D): a character with a problem, in a place. The story's protagonist meets the
problem the video is about: who they are, what goes wrong, what it costs, the question.

Narration bookmarks used: "who", "problem", "cost", "question" (a beat every 2-3 s).
Backdrop: room (set scenes[].backdrop in plan.json, or the class attribute). Every name and
number comes from research; the protagonist is the same cast() member in every scene (shared.py).
Works in 16:9 and 9:16 (by_aspect, GROUND_Y and CHAR_H adapt).
"""
from waitwhat_style import *

WHO = "Maya runs a bakery"          # who they are, in a few words
PAIN = "6 hours a week"             # what the problem costs (from research)


class StoryProblem(WaitwhatScene25D):
    backdrop = "room"

    def construct(self):
        x0 = by_aspect(-0.6, 0.6)
        maya = cast("maya", pose="type", face="happy").stand(x=x0)
        table = desk(by_aspect(3.4, 3.6)).move_to([x0, GROUND_Y - 0.35, 0], aligned_edge=DOWN)
        layer(table, "main", depth=1.05)            # a touch nearer than Maya: drawn in front of her
        lap = laptop(back=True, width=by_aspect(1.5, 1.9)).next_to(table.top_y() * UP + x0 * RIGHT, UP, buff=0)
        layer(lap, "main", depth=1.05)

        # the place and the person arrive at once: things pop in from their base, staggered
        self.play(pop_in(maya, table, lap, gap=0.09), run_time=0.7)
        self.wait_until("who")
        who = tag(WHO, maya, UP, buff=0.15)
        self.play(pop_in(who, anchor="bottom"), nudge(maya))

        # the problem piles up: letters fly in one after another and land on the desk
        self.wait_until("problem")
        pile = VGroup(*[envelope(by_aspect(0.95, 1.1)).rotate(0.12 * (i - 2)) for i in range(5)])
        top_y = table.top_y()
        for i, e in enumerate(pile):
            e.move_to([x0 + by_aspect(1.1, 1.0) + 0.06 * i, top_y + 0.2 + 0.16 * i, 0])
        layer(pile, "main", depth=1.08)
        self.play(FadeOut(who), slide_in(*pile, frm=RIGHT + UP * 0.4, distance=2.5, gap=0.12),
                  maya.to_face("worried"), maya.look((1, -0.3)), run_time=1.1, sfx="paper")

        # what it costs: a clock and the number, and the camera leans in on Maya
        self.wait_until("cost")
        clk = clock(by_aspect(0.6, 0.62), spin=True).move_to([x0 + by_aspect(-3.3, -1.9), maya.head_point()[1] + by_aspect(-0.1, 1.7), 0])
        cost = self.in_view(pill(PAIN, "RED", icon_name="cross").next_to(clk, DOWN, buff=0.3), margin=0.3)
        self.play(pop_in(clk, anchor="center"), pop_in(cost, anchor="top"), maya.look((-1, 0.4)), run_time=0.6)
        self.push_in(by_aspect(1.22, 1.15), to=maya.get_center() + by_aspect(LEFT * 0.4 + UP * 0.6, LEFT * 1.0 + UP * 1.2), run_time=1.4)

        # the question the video answers
        self.wait_until("question")
        q = self.in_view(thought(T("?", size=SIZE_HEAD, color=PILL_INK, weight="BOLD"), maya, side=UR))
        self.play(maya.to_pose("think"), maya.to_face("thinking"), pop_in(q, anchor="bottom"), run_time=0.55)
        self.drift(RIGHT * 0.05, zoom_rate=0.01)
        self.finish()
