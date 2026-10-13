"""Template (3D): a solid turns into view, a wedge lifts out, and the inside is named and set moving.

Narration bookmarks used: "cell", "open", "cathode", "separator", "anode", "flow".
For "what is inside": a battery cell, a cable, a pipe, a tree trunk, an earbud driver
(kind="cylinder"), or a planet, an eye, a fruit (kind="sphere").
Pattern: whole object (rotate_reveal) → open (the wedge slides out while the camera eases a little
lower) → a label per layer on its word, in a column beside the cut → the invisible process on the
cut face (here: lithium ions drifting from anode to cathode) with a slow drift of the camera.
Both aspects: the object stands upright, so 9:16 zooms in further (it is tall and narrow already). Budget: ~250 faces.
"""
from waitwhat_style import *

STEEL = "GREY" if IS_DARK else "INK_3"      # a neutral that stays light-ish on light themes
LAYERS = [  # (name, palette colour, outer radius); concentric bands, outermost first
    ("steel can", STEEL, 1.25),
    ("cathode", "RED", 1.12),
    ("separator", "TEAL", 0.86),
    ("anode", "BLUE", 0.74),
    ("core", STEEL, 0.3),
]
HEIGHT = 4.0


class CellInside(WaitwhatScene3D):
    def construct(self):
        cell = cutaway(LAYERS, kind="cylinder", height=HEIGHT, cut=PI / 2)
        self.view(zoom=by_aspect(1.2, 1.55), shift=SAFE_CENTER + by_aspect(LEFT * 1.4, LEFT * 1.05))

        self.play(rotate_reveal(cell, angle=-PI / 2), run_time=self.until("cell", minimum=1.2))
        self.wait_until("open")
        self.camera_to(phi=self.camera.get_phi() + 6 * DEGREES, added_anims=[cell.open()], run_time=1.8)

        names = ["cathode", "separator", "anode"]
        labels = self.label_layers(cell, names=names)               # on the right-hand cut face
        for c, mark in zip(labels, names):
            self.wait_until(mark)
            self.play(c.enter())

        # what happens inside: ions cross the separator, anode → cathode, on the cut face
        self.wait_until("flow")
        a = cell.start + cell.cut                                    # the right-hand cut face's angle
        r0, r1 = 0.5, 1.0                                            # mid-anode → mid-cathode
        streams = VGroup(*[
            self.particles(lambda s, z=z: [(r0 + (r1 - r0) * s) * np.cos(a), (r0 + (r1 - r0) * s) * np.sin(a), z],
                           n=3, speed=0.45, color="GOLD", radius=0.05)
            for z in np.linspace(-HEIGHT * 0.35, HEIGHT * 0.35, 5)])
        self.play(FadeIn(streams), run_time=0.6)
        self.drift(0.05)
        self.finish()
