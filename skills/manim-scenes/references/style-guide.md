# waitwhat house style

Opacity layers, the safe-area and edge-buffer rules and semantic colour come from the visual
design rules in AmitSubhash/3brown1blue and the Hermes Agent manim-video skill (both MIT);
see THIRD_PARTY.md.

Everything here is implemented in `lib/waitwhat_style.py`; use the helpers rather than
re-deriving values, so all scenes match.

## Frame
- 16:9, 14.22 × 8 units, origin at centre. Safe area: |x| ≤ 6.5, |y| ≤ 3.5. Keep text ≥ 0.5 units
  from every edge (the lib's layout lint flags anything closer).
- The background is the video's **theme** (`plan.theme`), painted by `WaitwhatScene` behind
  everything; it is not a mobject, so fades and `self.clear()` never touch it. Never draw your
  own full-frame background. `grid_paper()` is still allowed as a faint "workbench" backdrop on
  `classic`.

## Themes (worlds)

One theme per video, chosen by the director for the topic; a scene may override it only when the
story moves to another place (`scenes[].theme`). The palette constants (`INK`, `INK_2`, `BLUE`,
`YELLOW`, ...) and `color_of()` already hold the current theme's values, with contrast checked
against its background, so **use names, never hex**. Plain `Text`, `MathTex`, `Line`, `Square`
etc. default to the theme's ink. `IS_DARK`, `THEME` and `FLOOR_Y` tell you where you are.

| Theme | World | Good for |
| --- | --- | --- |
| `classic` | pure black, the 3b1b look (default) | math, proofs, abstract ideas |
| `studio` | warm charcoal, soft spotlight | products, companies, modern tech |
| `chalkboard` | green slate, chalk dust; pen sound is chalk | derivations, lessons, history of science |
| `blueprint` | blue drafting sheet with a grid | machines, systems, architecture, how things are built |
| `space` | night sky, faint nebula, twinkling stars | astronomy, physics, scale, big ideas |
| `ocean` | deep water, light rays, drifting particles | biology, oceans, flows, calm deep dives |
| `city` | night skyline along the bottom | startups, economics, people and places |
| `whiteboard` | clean board, marker colours; pen sound is marker | business, product walkthroughs |
| `graph_paper` | light grid on whole/half units | data, measurement, geometry |
| `paper` | warm notebook, ruled lines | stories, biographies, history, gentle intros |
| `hills` | illustrated daytime sky, clouds, hills | nature, everyday life, stories for everyone |

- `city` and `hills` draw scenery along the bottom: keep content above `FLOOR_Y` (−2.6).
- On light themes (`whiteboard`, `graph_paper`, `paper`, `hills`) the attention colour `YELLOW`
  is a deep amber and concept colours are marker-dark; fills at 0.3–0.5 read well.
- `plan.theme` may also be `{"name": "space", "ambient": false}` (no background motion), or
  carry a `backdrop` image under the theme, cover-fitted, blurred and dimmed
  (`{"name": "studio", "backdrop": "backdrop.png", "backdrop_dim": 0.72}`, path relative to
  `workspace/`). The director can paint one with `ww backdrop "<a place or era, no text>"`
  (one OpenRouter image, a few cents). Use it rarely: only when a real place or era carries the
  story and no procedural theme fits; procedural themes are the default.

## Colour

Values below are `classic`; other themes adapt them (same names, same meanings), so write names
(`"BLUE"`) in `plan.palette`, not hex.

| Name | Hex | Default meaning |
| --- | --- | --- |
| `INK` | #FFFFFF | primary text, neutral strokes |
| `INK_2` | #BBBBBB | secondary text, arrows |
| `INK_3` / `INK_4` | #777777 / #333333 | axes, guides, grids, dimmed structure |
| `YELLOW` | #FFFF00 | attention: pencil circle, highlight, "this one" |
| `BLUE` | #58C4DD | first concept |
| `TEAL` | #5CD0B3 | second concept |
| `PINK` | #D147BD | third concept |
| `GOLD` | #F0AC5F | fourth concept / money / energy |
| `GREEN` / `RED` | #83C167 / #FC6255 | good/bad, gain/loss, correct/wrong (only with that meaning) |
| `PURPLE`, `ORANGE`, `YELLOW_SOFT` | | extra concepts |

- Assign concepts in `plan.palette` and read them with `color_of("name")`. If a concept is
  blue in scene 2, it is blue in scene 9, in formulas, labels and shapes alike.
- Regions you talk about get `fill_opacity` 0.45–0.6 with a full-strength stroke of the same
  colour (below ~0.4 most colours turn muddy brown on black). Background regions 0.15–0.3.
- Opacity layers: `PRIMARY` 1.0 (what we talk about now), `CONTEXT` 0.35 (still relevant),
  `SCAFFOLD` 0.15 (grids, guides). `dim(*mobs)` pushes things back; don't delete context.

## Type
- Words: `T(text, size=…)` in CMU Serif. Sizes: `SIZE_TITLE` 64, `SIZE_HEAD` 48, `SIZE_BODY` 38,
  `SIZE_LABEL` 32, `SIZE_SMALL` 26 (minimum). Sentence case. No full stops on labels.
- Math: `M(r"…")` (LaTeX, Computer Modern, matches CMU Serif). Colour parts with
  `M(r"{{a}}^2 + {{b}}^2 = {{c}}^2", colors={"a": color_of("a"), …})`.
- Handwriting: `hand("wait, what?")` in yellow, only for asides and arrows-with-notes.
- Code: `code_block(src)` (Menlo, monokai on a near-black panel).
- At most ~12 words on screen at once. Never paragraphs. Titles are rare: the hook should be
  a picture, not a title card.

## Layout
- One focal object per scene, centred or slightly left, 50–70 % of frame width.
- Labels sit on or right next to their objects (`label(...)`, `next_to(buff=0.2)`), never in a
  legend far away.
- Two-panel layouts: left/right halves centred at x = ±3.4, a faint divider if needed.
- A formula that summarises a picture goes above or below it, not on top of it.
- Before adding something, ask what already occupies that region; move or dim it first.

## Motion
- Entrances: `enter(m)` (fade up from 94 % scale, strong ease-out, ~0.7 s; staggers groups).
  Draw strokes with `Create`, text with `Write` or `enter`, shapes from their origin with
  `GrowFromEdge`, `GrowFromPoint`, `GrowArrow`. Never pop things in with `self.add` mid-scene
  unless it is a deliberate cut.
- On-screen moves: `.animate` with the default smooth ease-in-out; 1–2 s for normal moves,
  2–4 s for the transformation that *is* the explanation.
- Transform, don't swap: `ReplacementTransform`, `TransformMatchingTex`,
  `TransformMatchingShapes`, `FadeTransform`. Identity should be trackable by eye.
- Exits: `leave(m)` (0.4 s) or dim. Exits are faster than entrances.
- Emphasis: `pencil_circle(m)` + `Create` for the key thing; `pulse(shape)` (fill brightens and
  settles) for regions; `focus(m)` (Circumscribe) only for text or compact groups, since it draws
  an axis-aligned box. One emphasis at a time.
- Rhythm: after a reveal, hold (`self.wait(1–2)`) while the narration lands. Silence with a strong
  picture is part of the style.

## Alive, not busy

- **See, then hear.** The visual for a word lands on its bookmark or a beat before it, never
  after. Mark the stressed word of each key sentence and give it a visual beat: something
  appears, moves, changes colour, or `beat(mob)` (a quick swell). Roughly every 3–5 s of
  narration something on screen should change in a way that means something.
- **No dead frames.** Under narration, never hold a completely still frame for more than ~3 s;
  move the story forward (stage a reveal, tick a number, draw the next arrow). Ambient themes
  (`space`, `ocean`, `city`, `hills`) keep the background breathing on their own. Don't add
  meaningless wobble or floating to objects: motion should explain.
- **Tempo follows energy** (`scenes[].energy` in the plan): `high` scenes use snappier
  entrances (0.4–0.8 s) and more beats; `low`/`close` scenes use slower moves and longer holds;
  `reveal` gets the longest build and a held picture afterwards.
- **Vary the entrances** between scenes (grow from a point, draw on, slide in from where it
  comes from, transform from the previous object) so the video doesn't fall into one rhythm.

## Sound cues

Sound is logged from the animations themselves (`ww stitch` mixes it under the voice):
- automatic: appear → soft pop (a staggered group → ticks), `Write` → the theme's pen,
  `Create` → a quieter stroke, `erase(...)`/`Uncreate` → eraser, typing → keys. Moves, fades
  out and highlights are silent.
- chosen: `self.play(anim, sfx="coin")`, `sfx="chime@end"`, `sfx="swish@mid"`,
  `sfx="rise@reveal"` (a bookmark), a list of those, or `sfx=False` for silence;
  `self.sfx("stamp", at="approved")` for a moment between plays.
- Names: `SFX` in the lib (pop tick click pencil chalk marker eraser whoosh swish rise chime
  shimmer coin register keys paper thud stamp notify wrong). Give meaning, not decoration: a coin
  when money moves, a chime once at the aha, keys when code runs. One chosen sound per beat.

- Live numbers: `ValueTracker` + `always_redraw` / `DecimalNumber` updaters for anything that
  changes continuously. Show real values, not placeholders.

## Brand stings
`ww render --stings` renders the ~1.7 s intro (the hand-lettered wordmark from `brand/wordmark.svg`
drawing itself on in chalk, blue question mark) and the 2.4 s outro. `ww stitch` adds them automatically (turn off with `plan.sound.intro/outro = false`).
Don't add another title card after the intro; go straight into the hook.
