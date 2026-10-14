"""Template (2.5D): a city / system overview, then a parallax push-in on the part that matters.
The parts of a system stand in two depth rows (a back row a little smaller and higher, a front
row on the street), get their names, get connected, and the camera pushes in on one of them:
near things grow faster than far ones, so the picture opens up in depth.

Narration bookmarks used: "parts", "connect", "closer".
Backdrop: city. Labels and parts come from the plan (here: homes, a shop, a bank, the cloud).
Works in 16:9 and 9:16.
"""
from waitwhat_style import *

TITLE = "Where the money goes"
PARTS = [("You", "house"), ("The shop", "shop"), ("The bank", "bank"), ("The cloud", "server")]
FOCUS = 1                    # which part the camera pushes in on


def make_part(kind: str):
    return {"house": lambda: house(by_aspect(2.0, 1.9)), "shop": lambda: shop(by_aspect(2.3, 2.3), sign=None),
            "bank": lambda: bank(by_aspect(2.4, 2.4), sign=None), "server": lambda: server(by_aspect(1.9, 1.9))}[kind]()


class CityOverview(WaitwhatScene25D):
    backdrop = "city"

    def construct(self):
        title = headline(TITLE)
        self.play(slide_in(title, frm=UP, distance=0.6), run_time=0.5)

        # two rows in depth: the back row (depth 0.8) stands higher and smaller, the front row (1.0)
        # on the street; in 9:16 that is also how four things fit across a narrow frame
        parts = [make_part(k) for _, k in PARTS]
        back_y = GROUND_Y + by_aspect(0.45, 0.5)
        spots_back = [by_aspect(-4.6, -2.3), by_aspect(1.4, 1.0)]     # in 9:16 the rows overlap a little:
        spots_front = [by_aspect(-1.6, -0.9), by_aspect(4.4, 2.1)]    # the back row peeks out behind
        for p, x in zip(parts[0::2], spots_back):
            p.scale(0.82).move_to([x, back_y, 0], aligned_edge=DOWN)
            layer(p, "main", depth=0.8)
        for p, x in zip(parts[1::2], spots_front):
            p.move_to([x, GROUND_Y - by_aspect(0.3, 0.05), 0], aligned_edge=DOWN)
        # names at the same depth as their part; in 9:16 the front row's names go below it, so a
        # back-row name is never hidden behind a front-row one
        tags = [tag(name, p, UP if (i % 2 == 0 or not IS_VERTICAL) else DOWN, buff=0.1)
                for i, ((name, _), p) in enumerate(zip(PARTS, parts))]

        self.wait_until("parts")
        self.play(pop_in(*parts, gap=0.18), run_time=0.6)
        self.play(pop_in(*tags, gap=0.12, anchor="bottom"), run_time=0.5)

        # how they connect: dashed routes draw in, and a letter runs along one
        self.wait_until("connect")
        links = [route(parts[i].get_top(), parts[j].get_top(), curve=0.9, color="INK_3")
                 for i, j in ((0, 1), (1, 2), (2, 3))]
        self.play(*[pop_in(*l, gap=0.01, anchor="center") for l in links], run_time=0.7, sfx="swish")
        msg = envelope(0.6).move_to(parts[0].get_top())
        self.play(pop_in(msg, anchor="center"), run_time=0.3)
        self.play(travel(msg, parts[1].get_top(), arc=0.9, run_time=1.0), sfx="message@end")

        # the push-in: the focus part fills the frame, the skyline barely moves
        self.wait_until("closer")
        focus = parts[FOCUS]
        self.play(pop_out(title, msg, *[t_ for i, t_ in enumerate(tags) if i != FOCUS]),
                  *[pop_out(*l, gap=0.0) for l in links], run_time=0.4)
        self.push_in(by_aspect(1.75, 1.6), to=focus.get_center() + UP * 0.3, run_time=1.8)
        self.play(ping(focus, "YELLOW"), nudge(tags[FOCUS]))
        self.finish()
