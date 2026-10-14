---
name: manim-scenes
description: Write, render and visually check Manim Community Edition scenes in the waitwhat styles - classic (3Blue1Brown look - CMU Serif, semantic colour palette, smooth transforms - on the video's theme, from classic black to chalkboard, blueprint, paper or night sky, with sound cues tied to the animations). One file per scene, timed to narration bookmarks, render → traceback → fix loop, contact-sheet review for overlapping or off-screen text. Includes templates for math proofs, timelines, flow/causal diagrams, maps, molecules, code walkthroughs, comparisons and company explainers, plus 3D scenes in the same look (exploded layers, cutaways, surfaces, orbits) for the few physical ideas that need depth - and 2.5D (flat illustrated explainer-agency art in depth layers with a parallax camera, a consistent character kit, props and snappy pop-in motion) for companies, products, everyday questions, history and stories. Use whenever animating scenes for a waitwhat video.
---

# Manim scenes, waitwhat style

**Two styles, chosen per video in `plan.style`:** `"classic"` (everything below: the 3b1b look,
for maths, science and education) and `"25d"` (flat illustrated layers with a parallax camera,
for everything else). In a 2.5D video, read **`references/25d.md`** first (`ww brief` prints it as
`read_first`) and use `WaitwhatScene25D`; the timing, sound, aspect and render loop below are the
same, the look rules are in that reference.

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
- Two aspects, one render each: 16:9 (default) or vertical 9:16 (`plan.aspect`; `ww render`
  prints `"aspect": "9:16"`). Lay scenes out with the adaptive helpers (`place_title`,
  `side_by_side`, `flow`, `spots`, `fit_safe`, `by_aspect`, `MAIN`) instead of hard-coded
  x positions, and in 9:16 follow the vertical rules (below).
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

## Vertical 9:16 in one breath

When `plan.aspect` is `"9:16"` (`IS_VERTICAL`), the frame is 8 × 14.22 units and is watched on a
phone: **stack, don't spread** (side by side becomes one above the other, sequences run top to
bottom); **larger type** (the lib scales it by 1.3; keep labels to 1–3 words); **one central
focus** at `SAFE_CENTER`; **thumb-safe margins** (|x| ≤ 3.45, nothing in the top 0.9 units); and
**nothing to read in the bottom ~15 %** (below `SAFE_BOTTOM`), where the platform's captions and
buttons sit. Details and the helper table: `references/style-guide.md`, "Layout" and
"Vertical 9:16". The templates `comparison.py`, `flow_causal.py` and `timeline.py` adapt to both
aspects; adapt the others with the same helpers.

## 3D scenes (only where depth explains something)

A scene marked `"dim": "3d"` in the plan is a `WaitwhatScene3D` (same import, same timing, sound,
themes, aspects and lint): shaded solids and surfaces in the palette colours, a camera that
tilts, orbits and dollies, and every label flat on the screen (`tag`, `pin`, `callout`,
`label_layers`, never text in 3D space). Helpers for the house 3D look: `exploded_layers()`,
`cutaway()`, `graph_surface(live=True)`, `ball()`/`slab()`/`cylinder()`, `rotate_reveal()`,
`particles()`/`ripples()`/`glow_path()` for invisible physics. Keep it rare (one or two scenes in a
video) and within the render budget (≤ 1500 faces, surfaces ≤ 24 × 24, camera moves of 1.5–3 s,
then hold still): then a 3D scene renders in 4–10 s, the same class as 2D. **Read
`references/3d.md` before writing one** (camera grammar, labels, patterns, budget, 9:16 framing,
pitfalls), and start from a 3D template.

## 2.5D scenes (only in a `"style": "25d"` video)

Every scene of a 2.5D video is a `WaitwhatScene25D` (same import, timing, sound, aspects, lint):
flat rounded vector art with soft shadows and rim light, in depth layers (`far`, `mid`, `main`,
`near`, `hud`) that a parallax camera moves at different speeds (`pan_to`, `push_in`, `dolly`,
`drift`); a backdrop per scene (`outdoors`, `city`, `room`, `office`, `plain`); a cast of
consistent characters (`cast("maya")`, poses, faces, blink); props (`phone`, `laptop`, `shop`,
`bank`, `coin`, `chart`...); text on pills (`pill`, `tag`, `bubble`, `headline`); and snappy motion
(`pop_in` with a small overshoot, `slide_in`, `travel`, `nudge`, `burst`), a new beat every
2-3 s. Read `references/25d.md` (API, layering rules, catalogue, pacing, 9:16, budget, pitfalls)
and start from a 2.5D template. A 2.5D scene renders in 4-10 s.

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

1. `ww render <id>` renders the final 1080p30 in a few seconds: render the final directly and look
   at it (it also marks the scene's progress). Unchanged scenes are skipped. `--preview` (480p15,
   about 2x faster) is only worth it for very heavy scenes.
2. On failure the traceback is printed. Fix the cause, not the symptom. **Max 3 attempts**; then
   simplify the visual (fewer objects, no LaTeX trick, no updater) and say so.
   Common errors and fixes: `references/gotchas.md`.
3. On success, **look** at `workspace/frames/<id>_sheet.jpg` (a 2x2 grid in time order: the
   first frame, ~40 %, ~75 %, the last frame before any fade-out; from the latest render).
   Also read `layout_issues` in the JSON line (overlapping or off-frame text found by the lib).
   Fix: overlapping or clipped text, labels far from their objects, tiny text, empty or
   cluttered frames, colour drift, things that should have been dimmed. Checklist in
   `references/render-loop.md`.
4. Render again after fixes and look once more. Fix only real defects; a clean sheet is done.
   A scene is done when you would be happy to pause on any frame.

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
| `exploded_layers.py` | 3D: what something is made of (a touchscreen stack, a solar cell, skin, a road) |
| `cutaway.py` | 3D: what is inside (a battery cell, a cable, a planet, an eye), and what flows in it |
| `surface_wave.py` | 3D: a quantity over a plane that moves (ripples, sound, a membrane, a field) |
| `orbit.py` | 3D: things going around things (planets, moons, satellites, a tilted axis) |
| `story_problem.py` | 2.5D: the protagonist with a problem in a place (who, problem, cost, the question) |
| `service_flow.py` | 2.5D: a product/service flow across a place, the camera travelling with it (shop → product → bank) |
| `city_overview.py` | 2.5D: a system's parts in two depth rows, connected, then a parallax push-in |
| `before_after.py` | 2.5D: before/after with the same character in two little worlds |

Read only the template you need. Adapt freely; they show the style, not the only way. The
comparison, flow and timeline templates, the four 3D templates and the four 2.5D templates are
written once for both aspects (`by_aspect`, `MAIN`, `SAFE_CENTER`, `fit_zoom`); the others are laid out for 16:9, so
re-place their objects with the layout helpers in a 9:16 video.
