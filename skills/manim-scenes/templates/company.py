"""Template: company explainer beat - problem → product → concrete example → how they make money.

Narration bookmarks used: "problem", "product", "example", "money".
EVERY string below must come from research (their site, docs, pricing page). Never invent
customers, numbers or features; if pricing is not public, say "subscription" only if stated.
"""
from waitwhat_style import *

PERSON = "A shop owner"                     # the everyday person with the problem
PAIN = ["invoice", "invoice", "invoice", "receipt", "invoice"]
PRODUCT = "The product"                     # company / product name from research
OUTCOME = "Paid in 2 days"                  # the concrete result from a real example
REVENUE = "monthly subscription"            # from the pricing page


def person_icon(color=INK):
    head = Circle(0.32, color=color, stroke_width=4)
    body = Arc(radius=0.62, start_angle=PI * 0.1, angle=PI * 0.8, color=color, stroke_width=4)
    body.next_to(head, DOWN, buff=0.08)
    return VGroup(head, body)


class CompanyBeat(WaitwhatScene):
    def construct(self):
        who = person_icon().move_to(LEFT * 5 + UP * 0.3)
        who_l = T(PERSON, size=SIZE_SMALL, color=INK_2).next_to(who, DOWN, buff=0.25)
        papers = VGroup(*[VGroup(RoundedRectangle(corner_radius=0.05, width=0.9, height=1.15, stroke_width=2,
                                                  color=INK_3, fill_color="#16181c", fill_opacity=1),
                                 T(p if i == len(PAIN) - 1 else "", size=18, color=INK_2))
                        for i, p in enumerate(PAIN)])
        for i, p in enumerate(papers):
            p[1].move_to(p[0]).shift(UP * 0.3)
            p.move_to(LEFT * 2.9 + UP * (0.9 - 0.12 * i) + RIGHT * 0.12 * i).rotate(0.08 * (i - 2))

        self.play(enter(who, who_l), run_time=0.9)
        self.wait_until("problem")
        self.play(LaggedStart(*[FadeIn(p, shift=DOWN * 0.3, rate_func=ease_out) for p in papers], lag_ratio=0.15),
                  run_time=1.4)
        stress = hand("hours every week", size=32, color=RED).next_to(papers, UP, buff=0.35)
        self.play(FadeIn(stress), run_time=0.5)

        prod = node(PRODUCT, color=color_of("product", BLUE), width=3.0, height=1.3, size=SIZE_LABEL).move_to(RIGHT * 0.9)
        self.wait_until("product")
        self.play(GrowFromCenter(prod), run_time=0.9)

        self.wait_until("example")
        flow = link(papers, prod, color=INK_2)
        self.play(GrowArrow(flow), FadeOut(stress), run_time=0.7)
        self.play(LaggedStart(*[p.animate.move_to(prod).scale(0.2).set_opacity(0) for p in papers], lag_ratio=0.1),
                  FadeOut(flow), run_time=1.4)
        done = VGroup(Circle(0.45, color=GREEN, stroke_width=5),
                      VMobject(stroke_color=GREEN, stroke_width=6).set_points_as_corners(
                          [LEFT * 0.2 + UP * 0.02, DOWN * 0.18, RIGHT * 0.25 + UP * 0.22])).move_to(RIGHT * 4.6 + UP * 0.3)
        out = T(OUTCOME, size=SIZE_LABEL, color=GREEN).next_to(done, DOWN, buff=0.3)
        self.play(GrowArrow(link(prod, done, color=INK_2)), Create(done), enter(out), run_time=1.2)

        self.wait_until("money")
        coin = lambda: VGroup(Circle(0.16, color=GOLD, fill_color=GOLD, fill_opacity=0.8),
                              T("$", size=18, color=BLACK))
        path = ArcBetweenPoints(who.get_center() + DOWN * 1.8, prod.get_bottom() + DOWN * 0.1, angle=0.6)
        coins = [coin().move_to(path.get_start()) for _ in range(4)]
        self.play(LaggedStart(*[MoveAlongPath(c, path) for c in coins], lag_ratio=0.25), run_time=1.8)
        rev = T(REVENUE, size=SIZE_SMALL, color=GOLD).next_to(prod, DOWN, buff=0.7)
        self.play(*[FadeOut(c) for c in coins], enter(rev), run_time=0.7)
        self.finish()
