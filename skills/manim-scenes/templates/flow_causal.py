"""Template: a causal chain that closes into a feedback loop, with a pulse travelling the arrows.

Narration bookmarks used: "a", "b", "c", "loop".
Pattern: the diagram grows one link per narrated step; a moving dot shows causation;
the closing arrow is the aha (feedback). Works for pipelines and systems too.
"""
from waitwhat_style import *

STEPS = ["Warmer air", "More evaporation", "More water vapour", "More heat trapped"]


class FeedbackLoop(WaitwhatScene):
    def construct(self):
        cols = [color_of("heat", RED), color_of("water", BLUE), color_of("vapour", TEAL), color_of("heat", RED)]
        pos = [UP * 2.2, RIGHT * 3.6, DOWN * 2.2, LEFT * 3.6]
        nodes = [node(s, color=c, width=3.6).move_to(p) for s, c, p in zip(STEPS, cols, pos)]
        arrows = [link(nodes[i], nodes[(i + 1) % 4], curved=-PI / 3, color=INK_2) for i in range(4)]

        self.play(enter(nodes[0]))
        for i, mark in enumerate(["a", "b", "c"]):
            self.wait_until(mark)
            self.play(Create(arrows[i]), run_time=0.7)   # curved arrows: Create, not GrowArrow
            pulse = Dot(color=YELLOW, radius=0.09)
            path = arrows[i].copy()
            path.pop_tips()                                # pop_tips() returns the tips, not the path
            self.play(MoveAlongPath(pulse, path),
                      enter(nodes[i + 1]), run_time=0.9)
            self.remove(pulse)

        # the loop closes: this is the point of the scene
        self.wait_until("loop")
        self.play(Create(arrows[3]), run_time=0.9)
        self.play(LaggedStart(*[a.animate.set_color(YELLOW) for a in arrows], lag_ratio=0.25),
                  rate_func=there_and_back, run_time=2.0)
        label = hand("feedback!", size=40).move_to(ORIGIN)
        self.play(FadeIn(label, scale=0.9, rate_func=ease_out))
        self.finish()
