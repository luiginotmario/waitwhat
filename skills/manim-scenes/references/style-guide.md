# waitwhat house style

Opacity layers, the safe-area and edge-buffer rules and semantic colour come from the visual
design rules in AmitSubhash/3brown1blue and the Hermes Agent manim-video skill (both MIT);
see THIRD_PARTY.md.

Everything here is implemented in `lib/waitwhat_style.py`; use the helpers rather than
re-deriving values, so all scenes match.

## Frame
- Two aspects, chosen by the person and written to `plan.aspect` (one render per video, laid out
  for its aspect from the start, never cropped). The lib reads it: `ASPECT`, `IS_VERTICAL`.
  - **16:9** (default): 1920×1080, 14.22 × 8 units, origin at centre. Safe area: |x| ≤ 6.5,
    |y| ≤ 3.5.
  - **9:16** (vertical): 1080×1920, 8 × 14.22 units (same 135 px per unit), origin at centre.
    Safe area: |x| ≤ 3.45, from `SAFE_TOP` (6.21) down to `SAFE_BOTTOM` (−4.98). See
    "Vertical 9:16" below.
- `SAFE_W`, `SAFE_H`, `SAFE_TOP`, `SAFE_BOTTOM`, `SAFE_LEFT`, `SAFE_RIGHT`, `SAFE_CENTER` hold the
  safe area for the current aspect; `FRAME_W`/`FRAME_H` the frame. Keep text ≥ 0.5 units from
  every edge (the lib's layout lint flags anything closer, and in 9:16 anything in the bottom band).
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

- `city` and `hills` draw scenery along the bottom: keep content above `FLOOR_Y` (−2.6 in 16:9;
  in 9:16 the scenery sits inside the bottom band, below `SAFE_BOTTOM`).
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
- These are nominal sizes: `T`, `M`, `hand`, `label`, `node` and `code_block` multiply them by
  `TYPE_SCALE` (1.0 in 16:9, 1.3 in 9:16, because a vertical video is watched full width on a
  phone). Raw `Text(...)`/`MathTex(...)` don't: pass `font_size=sz(40)`.
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
- Two-panel layouts: `side_by_side(a, b)` (16:9: left/right halves around x = ±3.4; 9:16: one
  above the other). A faint divider if needed.
- A formula that summarises a picture goes above or below it, not on top of it.
- Before adding something, ask what already occupies that region; move or dim it first.
- **Write layouts that adapt**, so a scene is right in either aspect without a second version:

  | Helper | Does |
  | --- | --- |
  | `place_title(mob)` | top of the safe area, centred, fitted to its width |
  | `side_by_side(a, b, below=title)` | compare: a row in 16:9, a stack in 9:16; fitted, centred in the free area |
  | `flow(*steps)` | a sequence or pipeline along `MAIN` (→ in 16:9, ↓ in 9:16); join with `link(a, b)` |
  | `spots(n)` | n anchor points along `MAIN`, for things placed by position |
  | `fit_safe(mob, below=title)` | shrink to the free safe area and centre there |
  | `content_box(below, above)` | the free safe area as (x0, y0, x1, y1) |
  | `safe_point(fx, fy)` | a point by fraction of the safe area (−1…1) |
  | `by_aspect(a, b)` | a value per aspect: `by_aspect(LEFT * 3.5, UP * 2.5)` |

  `MAIN` is the frame's long axis (`RIGHT` in 16:9, `DOWN` in 9:16), `CROSS` the short one. A
  hard-coded `LEFT * 5` or `move_to([6, 0, 0])` is off-frame in 9:16 (|x| ≤ 3.45): derive
  positions from these instead.

## Vertical 9:16

A vertical video is watched on a phone, full screen, often with the sound low and a thumb over
the screen. Compose for that from the start; never shrink a landscape layout into it.

- **Stack, don't spread.** Side by side becomes one above the other (`side_by_side`, `flow`,
  `spots`); sequences, timelines and pipelines run top to bottom; a wide object (a pair of
  molecules, a number line, a map) turns a quarter or is fitted to the width. At most two
  things side by side, and only when they are narrow (two bars, two numbers).
- **Larger type, fewer words.** `T`/`M` already scale by 1.3; keep labels to 1–3 words, break a
  long one onto two lines (`"hydrogen\nbond"`), and never go below `SIZE_SMALL`. A line of
  text should fit in ~6.9 units without shrinking; if `fit()` had to shrink it, shorten it.
- **One central focus.** One object, centred on `SAFE_CENTER` (slightly above the frame's
  middle), filling 60–80 % of the width. Context goes above or below it, never beside it.
- **Thumb-safe margins.** Nothing that must be read within 0.55 units of the sides or in the
  top 0.9 units (the feed's top bar).
- **Keep the bottom ~15 % clear** (y below `SAFE_BOTTOM` = −4.98): vertical players put the
  caption, the buttons and their progress bar there. Scenery (the `city` skyline, `hills`) may
  sit there; labels, numbers and formulas never. The lint flags text in that band.
- **Titles at the top.** `place_title(...)` puts them under the top bar; build the picture
  below with `below=title`.
- **Code** (`code_block`) only with short lines (≤ ~30 characters); split long lines.
- **Check the sheet as a phone**: hold the 2x2 sheet at arm's length; if a label is hard to read
  there, it is too small or too long.

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
They follow the video's aspect (the wordmark is fitted to the narrow frame in 9:16).
`ww render --stings` renders the ~1.7 s intro (the hand-lettered wordmark from `brand/wordmark.svg`
drawing itself on in chalk, blue question mark) and the 2.4 s outro. `ww stitch` adds them automatically (turn off with `plan.sound.intro/outro = false`).
Don't add another title card after the intro; go straight into the hook.
