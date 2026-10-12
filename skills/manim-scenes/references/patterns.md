# Scene patterns

## Continuity handoff (the default between scenes)

```python
# workspace/scenes/shared.py
from waitwhat_style import *

A, B = 3.0, 4.0  # concrete numbers, reused everywhere

def make_triangle():
    tri = Polygon(ORIGIN, RIGHT * B, UP * A, color=INK, stroke_width=4)
    tri.set_fill(INK_4, 0.6)
    return tri.move_to(ORIGIN)

def end_state_of_hook():
    """Exactly what the hook scene leaves on screen; the next scene starts from this."""
    tri = make_triangle()
    return VGroup(tri)
```

Scene A ends with that state on screen (no fade). Scene B begins with
`self.add(end_state_of_hook())` and transforms from there. The cut between them is invisible.
If B needs A's objects in a new place, *move them on screen in B*, never between files.

## Representation patterns (pick the one that answers this scene's question)

- **Build on screen**: objects appear in the order the narration introduces them.
- **Rearrange to prove**: the same pieces in two arrangements; what's left over must match.
  Animate pieces sliding with `.animate.move_to` / `Rotate` in 1.5–2.5 s each.
- **Morph between views**: picture → formula with `TransformMatchingShapes`/`ReplacementTransform`
  (e.g., a square's area becomes the `a^2` term in the same colour).
- **Sweep a parameter**: `ValueTracker` drives a shape, a graph and a number together; the viewer
  sees cause and effect (template `graph_sweep.py`).
- **Zoom into a part**: keep the whole visible, dimmed and small, while a detail is expanded
  beside it, with a dashed line linking the two.
- **Flow of something**: a dot or packet travels along arrows (`MoveAlongPath`) to show
  causation, data flow or money flow (template `flow_causal.py`, `company.py`).
- **Accumulate**: counters (`DecimalNumber`) and bars grow while the narration gives the number.
- **Question frame**: ask (narration), show the setup, pause with `<break time="1.2s"/>`, then answer
  visually. Don't print the question as a sentence on screen; a "?" or circled gap is enough.

## Per-scene skeleton
Within one scene keep one anchor object on screen the whole time (the triangle, the map, the
diagram). Add to it, highlight within it, dim parts of it, but don't remove it until the end.

## Endings
- Continuous: leave the final state on screen; the next scene adds it back.
- Cut: `self.finish(fade=True)` fades everything during the tail.
- Last scene: leave a clean, centred final picture (it is also a good thumbnail candidate).

## Thumbnails
Set `plan.thumbnail = {"scene": id, "t": seconds}` on the most striking frame (usually the aha).
Or render a still: write `workspace/scenes/thumbnail.py` with a big, simple composition (the key
picture + at most 3 large words) and run
`ww manim -qh -s --media_dir workspace/.media workspace/scenes/thumbnail.py Thumbnail` then copy
the PNG to `workspace/thumbnail.png`.
