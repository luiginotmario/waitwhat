"""Template (3D): an exploded stack, layer by layer, then the one layer that matters lights up.

Narration bookmarks used: "stack", "explode", "glass", "sensor", "display", "touch".
For "what is this made of": a touchscreen, a solar cell, skin, a road, the atmosphere, a PCB.
Pattern: the object turns into view whole → the layers pull apart → each gets a label on its word
(a tidy column at the side, leader lines that follow the layers) → the camera settles lower while
the key layer is singled out → the physics (here: a touch spreading through the sensor grid).
Both aspects: labels take a column on the right; the picture shifts left to make room (in 9:16
it also sits higher and pulls further apart, since the frame is tall). Budget: 4 slabs + 16 grid
lines, two short camera moves.
"""
from waitwhat_style import *

LAYERS = [  # top to bottom: (name, palette colour[, thickness])
    ("cover glass", "BLUE"),
    ("touch sensor", "TEAL"),
    ("display", "PINK"),
    ("backlight", "GOLD"),
]


class ScreenStack(WaitwhatScene3D):
    def construct(self):
        stack = exploded_layers(LAYERS, width=4.6, depth=3.0, thickness=0.14)
        stack["cover glass"].plate.set_fill(opacity=0.3)            # glass reads as glass
        sensor = stack["touch sensor"]
        top = sensor.plate.get_zenith()[2] + 0.01                     # a fine wire grid on the sensor
        rows = VGroup(*[Line([-2.1, y, top], [2.1, y, top]) for y in np.linspace(-1.2, 1.2, 7)])
        cols = VGroup(*[Line([x, -1.35, top], [x, 1.35, top]) for x in np.linspace(-1.9, 1.9, 9)])
        grid = VGroup(rows, cols).set_stroke(INK, 1.5, 0.55)
        sensor.add(depth_sorted(grid))

        gap = by_aspect(0.95, 1.8)                                   # 9:16 is tall: pull further apart
        self.view(zoom=by_aspect(0.95, 0.78), shift=SAFE_CENTER + by_aspect(LEFT * 1.6, LEFT * 1.0))

        self.play(rotate_reveal(stack, angle=-PI / 3), run_time=self.until("stack", minimum=1.2))
        self.wait_until("explode")
        self.camera_to(phi=70 * DEGREES, added_anims=[stack.explode(gap)], run_time=2.2)

        texts = [by_aspect(n, n.replace(" ", "\n")) for n in stack.names]   # 9:16: short lines
        labels = self.label_layers(stack, texts=texts)               # one per layer, top to bottom
        for c, mark in zip(labels, ["glass", "sensor", "display"]):
            self.wait_until(mark)
            self.play(c.enter())
        self.play(labels[-1].enter(), run_time=0.6)

        # the point: dim the rest, the sensor's grid lights up where the finger lands
        self.wait_until("touch")
        others = [l for l in stack.layers if l is not sensor]
        hit = [0.6, 0.2, top]
        self.play(*[l.animate.set_opacity(0.18) for l in others],
                  rows[4].animate.set_stroke(YELLOW, 4, 1), cols[5].animate.set_stroke(YELLOW, 4, 1),
                  run_time=1.0)
        rings = self.ripples(hit, n=3, max_radius=1.4, period=1.6, color="YELLOW")
        self.add(rings)
        self.orbit(by=PI / 10, dphi=-6 * DEGREES, run_time=2.5, sfx="swish")
        self.finish()
