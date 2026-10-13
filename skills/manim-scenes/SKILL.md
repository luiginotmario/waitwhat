---
name: manim-scenes
description: Write, render and visually check Manim Community Edition scenes in the waitwhat house style (3Blue1Brown look - CMU Serif, semantic colour palette, smooth transforms - on the video's theme, from classic black to chalkboard, blueprint, paper or night sky, with sound cues tied to the animations). One file per scene, timed to narration bookmarks, render → traceback → fix loop, contact-sheet review for overlapping or off-screen text. Includes templates for math proofs, timelines, flow/causal diagrams, maps, molecules, code walkthroughs, comparisons and company explainers. Use whenever animating scenes for a waitwhat video.
---

# Manim scenes, waitwhat style

Each scene is `workspace/scenes/<id>.py` containing one `WaitwhatScene` subclass. Start every
file with `from waitwhat_style import *` (the lib is `lib/waitwhat_style.py` in this skill; it is
on `PYTHONPATH` whenever you use `ww`). Shared constructors live in `workspace/scenes/shared.py`.

```python
from waitwhat_style import *
from shared import make_triangle          # same object in every scene that shows it

class Squares(WaitwhatScene):
    def construct(self):
        tri = make_triangle()
        self.add(tri)                        # continuous handoff: start exactly where the last scene ended
        sq_a = Square(3, color=color_of("a"), fill_opacity=0.35).next_to(tri.leg_a, LEFT, buff=0)
        self.wait_until("squares")           # narration: "<bookmark mark="squares"/>Build a square…"
        self.play(GrowFromEdge(sq_a, RIGHT), run_time=1.6)
        self.play(Circumscribe(sq_a, color=YELLOW), run_time=self.until("compare"))
        self.finish()                        # hold until the narration ends (+0.8 s)
```

## The look (details in `references/style-guide.md`)

- The video's theme (`plan.theme`: classic black by default; chalkboard, blueprint, paper,
  space... see the style guide) is painted behind everything. Ink-coloured primary text, CMU
  Serif for words (`T("…")`), LaTeX for math (`M(r"a^2+b^2=c^2", colors={...})`), handwritten
  attention colour only for "look here" asides (`hand`).
- Colours carry meaning: `color_of("concept")` reads `plan.palette`, so every scene agrees.
  `YELLOW` means attention. Greys are structure. Never decorate with colour, and never write hex:
  the named colours adapt to the theme.
- Few words on screen: labels, a formula, a key number. The narration carries sentences.
- Big and calm: one focal object filling 50–70 % of the frame, generous margins, nothing within
  0.5 units of the edge, text never below `SIZE_SMALL`.
- Motion explains: things grow from where they come from, transform into what they become, and
  dim (`dim(...)`) rather than vanish when they become context. Entrances ease out (`enter`),
  exits are quicker (`leave`). Typical run_time 1–3 s; the big reveal gets more, plus silence.
- Signature move: the yellow pencil circle (`pencil_circle(target)`) to point at the thing
  that matters. Use it at most once or twice per scene.
- Alive, not busy: the visual lands on (or just before) its word, the stressed word of a key
  sentence gets a visual beat, and the frame never sits completely still for more than ~3 s
  under narration. Tempo follows the scene's `energy`.
- Sound comes from the animations: appear, write, draw and erase get quiet cues automatically;
  add meaning with `self.play(..., sfx="coin")` or `self.sfx("chime", at="reveal")`. Details in
  the style guide ("Sound cues").

## Timing comes from the voice

`ww tts` writes `workspace/audio/<id>.json` (it may still be voicing while you write the code:
`ww render` waits for the scene's audio, and without audio the lib estimates timings from the
narration text). Use `self.until("mark")` as a
`run_time` (or `self.play_until("mark", ...)`, `self.wait_until("mark")`, `self.until("word:square")`)
so visuals land on the words that describe them, and end every scene with `self.finish()`.
If the scene is longer than its narration, that is fine (silent beats are good); if it is shorter,
`finish()` pads it. Don't hard-code long sequences of `self.wait(3)` that ignore the audio.

## Continuity between scenes

Scenes are separate files, so continuity is designed: scene B starts by `self.add(...)`-ing
exactly what scene A ended with (built by the same function in `shared.py`), then transforms it.
Mark such boundaries `"transition": "continuous"` in the plan. For a real change of subject,
end with `self.finish(fade=True)` and mark `"cut"`. Patterns in `references/patterns.md`.

## Render → fix → look

1. `ww render <id> --preview` for every look while iterating (480p15, about 2-3x faster), then
   `ww render <id>` once for the final 1080p30. Unchanged scenes are skipped.
2. On failure the traceback is printed. Fix the cause, not the symptom. **Max 3 attempts**; then
   simplify the visual (fewer objects, no LaTeX trick, no updater) and say so.
   Common errors and fixes: `references/gotchas.md`.
3. On success, **look** at `workspace/frames/<id>_sheet.jpg` (3 frames, top to bottom in time;
   from the latest render, preview or final).
   Also read `layout_issues` in the JSON line (overlapping or off-frame text found by the lib).
   Fix: overlapping or clipped text, labels far from their objects, tiny text, empty or
   cluttered frames, colour drift, things that should have been dimmed. Checklist in
   `references/render-loop.md`.
4. Preview again after fixes. A scene is done when you would be happy to pause on any frame;
   then render the final once.

For videos of 3+ scenes the orchestrator runs this loop in parallel subagents, one per scene
(the waitwhat skill's `references/subagents.md` and `references/scene-builder.md`); they report
back in a line or two.

## Templates for any topic

`templates/` holds complete, rendering scenes to copy and adapt (each uses bookmarks and
`finish()`):

| Template | For |
| --- | --- |
| `math_proof.py` | geometry + algebra, rearrangement proofs, formulas built from pictures |
| `graph_sweep.py` | functions, parameters, a value swept with live numbers |
| `timeline.py` | history, biographies, product evolution, any sequence in time |
| `flow_causal.py` | pipelines, causal chains, feedback loops, how systems work |
| `map_geo.py` | places, routes, spread, anything on a map (lat/lon; GeoJSON optional) |
| `molecule.py` | chemistry, biology structures, ball-and-stick, reactions |
| `code_walkthrough.py` | algorithms, code, with a live variable panel |
| `comparison.py` | A vs B, before/after, numbers that grow into bars |
| `company.py` | company explainers: problem → product → example → money → users |

Read only the template you need. Adapt freely; they show the style, not the only way.
