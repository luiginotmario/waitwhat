# Render loop and visual check

The frames-first verification loop is adapted from iart-ai/manim-skills (MIT). See THIRD_PARTY.md.

## Commands
- `ww render <id> [<id>…]` renders at 1080p30, skips scenes whose code, shared code, style lib
  and narration timing are unchanged. `--force` to re-render anyway, `--draft` for 480p,
  `-j 3` for parallel scenes, `--all` for every scene in the plan.
- Output per scene (one JSON line): `ok`, `duration`, `layout_issues`, `missing_marks`,
  `warning` (e.g. video shorter than narration), `sheet` (contact sheet path).
- Full logs: `workspace/logs/<id>.render.log`. Lint: `workspace/logs/<id>.layout.json`.

## When it fails (max 3 attempts per scene)
1. Read the last exception line first, then the deepest frame that points into *your* file.
2. Fix the cause. Typical: wrong kwarg for this Manim version, LaTeX error (unescaped `%`, `&`,
   `#`, `_` in `Tex`, or `$` inside `MathTex`), indexing a submobject that doesn't exist,
   animating something not on screen, `Transform` chains (see gotchas).
3. If attempt 3 fails, simplify: drop the updater, replace the tricky LaTeX with `T(...)`, use
   fewer objects. Note the simplification in your report.
4. Quick experiments: `ww manim -ql -s --media_dir /tmp/ww scratch.py Test` renders only the last
   frame as PNG, in a second or two.

## Visual check (always, after every successful render)
Open the sheet (`Read workspace/frames/<id>_sheet.jpg`); individual frames are next to it. For
moments that matter (the aha), extract an exact frame:
`ffmpeg -ss 7.5 -i workspace/renders/<id>.mp4 -frames:v 1 /tmp/f.png`.

Ask of every frame, and fix any "yes":
1. Is anything cut off at an edge, or closer than ~0.5 units to it?
2. Does any text overlap other text, a shape's stroke, or an arrow?
3. Is any text too small to read on a phone (below ~26 pt equivalent) or low-contrast?
4. Is a label far from what it labels?
5. Is the frame nearly empty (a lone small object) or cluttered (more than ~4 things competing)?
6. Is a colour used for something other than its palette meaning?
7. Does the frame show the moment the narration is describing (is the bookmark timing right)?
8. Does it look like 3Blue1Brown, or like a slide deck? (Slides: bullet text, boxes of prose,
   centred titles over static content. Fix by turning words into pictures.)
9. Does the last frame match the next scene's first frame (continuous transitions)?

The automatic lint catches overlap between text objects and off-frame text, but not text over
shapes, ugly composition or wrong timing. Your eyes are the real check.
