"""Template (2.5D): a product or service flow across a place, followed by the camera. Here: a card
payment travels from a shop, through the product in the middle, to the bank; the camera dollies
along with the coin, so the city's layers slide past at different speeds (the parallax shot).

Narration bookmarks used: "tap", "send", "check", "bank", "done".
Backdrop: city, built wide enough for the camera's travel (backdrop_opts pan). Names and numbers
come from research. Works in 16:9 and 9:16 (in 9:16 the stops sit further apart in world units
and the camera ends on the bank instead of pulling out).
"""
from waitwhat_style import *

PRODUCT = "Your product"        # the company / product in the middle of the flow
DONE = "Paid in 2 seconds"      # the outcome, from research


class ServiceFlow(WaitwhatScene25D):
    backdrop = "city"
    backdrop_opts = {"pan": by_aspect(13, 15)}

    def construct(self):
        gap = by_aspect(8.5, 7.5)                       # distance between the stops (world units)
        xs, xp, xb = by_aspect(-3.2, 0.0), by_aspect(-3.2, 0.0) + gap, by_aspect(-3.2, 0.0) + 2 * gap
        store = shop(by_aspect(2.8, 3.0), sign="CAFE").move_to([xs - by_aspect(0.8, 0.9), GROUND_Y - 0.1, 0], aligned_edge=DOWN)
        leo = cast("leo", pose="phone", face="happy").stand(x=xs + by_aspect(1.4, 1.5))
        ph = phone(screen="pay")
        leo.hold(ph)
        hub = server(by_aspect(2.0, 2.4)).move_to([xp, GROUND_Y - 0.1, 0], aligned_edge=DOWN)
        hub_tag = tag(PRODUCT, hub, UP, buff=0.3)
        stop = hub.get_corner(UL) + np.array([-0.35, -0.2, 0])      # where the coin waits beside the hub
        vault = bank(by_aspect(3.0, 3.3)).move_to([xb, GROUND_Y - 0.1, 0], aligned_edge=DOWN)
        self.add(store, leo)                            # the opening frame: Leo at the cafe
        self.set_camera(to=[xs + 0.4, SAFE_CENTER[1], 0])

        self.wait_until("tap")
        c = coin(by_aspect(0.3, 0.36)).move_to(ph.get_center() + UP * 0.1)
        self.play(nudge(ph.ui.button, 1.25), ping(ph, "GREEN"), sfx="click")
        self.play(pop_in(c, anchor="center"), run_time=0.4, sfx="coin")

        # the money leaves: the camera travels with it, near layers sweep past, far ones barely move
        self.wait_until("send")
        path_a = route(c, stop, curve=1.6)
        self.play(pop_in(*path_a, gap=0.012, anchor="center"), run_time=0.5, sfx=False)
        self.pan_to([xp, SAFE_CENTER[1], 0], run_time=1.6,
                    added_anims=[travel(c, stop, arc=0.0, run_time=1.6), after(0.7, pop_in(hub, hub_tag, gap=0.25, run_time=0.55))])

        self.wait_until("check")
        ok = badge("shield", "GREEN", by_aspect(0.8, 0.95)).next_to(c, UP, buff=0.2)
        self.play(pop_in(ok, anchor="center"), nudge(hub), sfx="approve")

        self.wait_until("bank")
        path_b = route(c, vault.get_top() + UP * 0.2, curve=1.4)
        self.play(pop_out(ok), pop_in(*path_b, gap=0.012, anchor="center"), run_time=0.5, sfx=False)
        self.pan_to([xb, SAFE_CENTER[1], 0], run_time=1.6,
                    added_anims=[travel(c, vault.get_top() + UP * 0.2, arc=0.0, run_time=1.6, spin=1), after(0.7, pop_in(vault, run_time=0.55))])

        self.wait_until("done")
        paid = pill(DONE, "GREEN", icon_name="check").next_to(vault, UP, buff=0.35).shift(by_aspect(LEFT * 0.9, ORIGIN))
        self.play(pop_out(c), pop_in(paid, anchor="bottom"), burst(vault.get_top() + UP * 0.2), sfx="payment")
        if not IS_VERTICAL:   # the whole chain in one look
            lo, hi = xs - 1.5, xb + 1.3
            self.pull_out(min(1.0, SAFE_W / (hi - lo)), to=[(lo + hi) / 2, SAFE_CENTER[1] + 0.9, 0], run_time=1.6)
        self.finish()
