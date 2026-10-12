# waitwhat house style

Opacity layers, the safe-area and edge-buffer rules and semantic colour come from the visual
design rules in AmitSubhash/3brown1blue and the Hermes Agent manim-video skill (both MIT);
see THIRD_PARTY.md.

Everything here is implemented in `lib/waitwhat_style.py`; use the helpers rather than
re-deriving values, so all scenes match.

## Frame
- 16:9, 14.22 × 8 units, origin at centre. Safe area: |x| ≤ 6.5, |y| ≤ 3.5. Keep text ≥ 0.5 units
  from every edge (the lib's layout lint flags anything closer).
- Background `#000000` (set by `WaitwhatScene`). No vignettes, gradients or textures.
  `grid_paper()` is allowed as a very faint backdrop for "workbench" scenes.

## Colour

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
- Live numbers: `ValueTracker` + `always_redraw` / `DecimalNumber` updaters for anything that
  changes continuously. Show real values, not placeholders.

## Brand stings
`ww render --stings` renders the ~1.7 s intro (the hand-lettered wordmark from `brand/wordmark.svg`
drawing itself on in chalk, blue question mark) and the 2.4 s outro. `ww stitch` adds them automatically (turn off with `plan.sound.intro/outro = false`).
Don't add another title card after the intro; go straight into the hook.
