# Manim CE gotchas (verified on Manim 0.22)

Partly adapted from the gotcha lists in AmitSubhash/3brown1blue (MIT) and the Hermes Agent
manim-video skill (MIT); each item was re-checked against the version `ww setup` installs.

## Objects and transforms
- `Transform(a, b)` morphs `a` into `b`'s shape but keeps `a` on screen; `b` is never added.
  Animating `b` afterwards does nothing visible. Use `ReplacementTransform(a, b)` when you will
  keep working with `b`. Chained `Transform(a, b)` then `Transform(a, c)` is fine; chaining
  `Transform(a, b)` then `Transform(b, c)` is the bug.
- `x = mob` is not a copy; use `mob.copy()`.
- Never put the same mobject in two animations of one `play()`; chain instead:
  `mob.animate.shift(R).set_color(C)`. Order matters after scaling.
- `.animate` returns a builder: only use it inside `self.play()`.
- Animating something not yet on screen (`self.play(m.animate…)`) makes it pop in at the end
  state. Add it (`enter`, `Create`, `self.add`) first.
- `always_redraw` / updaters keep running; `mob.clear_updaters()` when done, or they fight
  later animations. `self.wait()` with only updaters may freeze: use
  `self.wait(t, frozen_frame=False)`.

- `GrowArrow` works only on straight `Arrow`s; use `Create` for `CurvedArrow`. `arrow.pop_tips()`
  returns the removed tips (not the arrow), so copy first: `p = arrow.copy(); p.pop_tips()`.
- Never name a scene class after a Manim class (`Angle`, `Circle`, `Text`, `Graph`…): it shadows
  the import and fails with confusing errors like `Scene.__init__() got an unexpected keyword`.

## Text and LaTeX
- Always raw strings: `M(r"\frac{a}{b}")`.
- `MathTex` is already math mode: no `$…$`. Use `Tex` for mixed text and math.
- In `Tex`, escape `% & # _ $`. In `T()` (Pango) anything goes, but `<` `>` `&` in
  `MarkupText` need escaping.
- `Brace.get_text("…", font_size=…)` crashes; build the label yourself:
  `lab = T("width", size=SIZE_LABEL).next_to(brace, DOWN, buff=0.1)`.
- `set_color_by_tex("a", …)` colours every submobject *containing* "a" (e.g. also `\cdot a b`).
  Isolate parts with `{{a}}` in the string or with `substrings_to_isolate=["a"]`.
- `get_part_by_tex("x")` returns `None` if not isolated; check before using.
- `TransformMatchingTex` needs matching isolated parts in both formulas; otherwise use
  `TransformMatchingShapes` or `ReplacementTransform`.
- `Text` has no `letter_spacing` kwarg.
- Text in CE is a `VMobject`, so `VGroup(circle, T("x"))` is fine. `Group` is for images.

## Layout
- `to_edge(…, buff=0.5)` minimum. Scale long things with `fit(m, max_w, max_h)`.
- `next_to(target, direction, buff=0.2)` for labels; `arrange(DOWN, buff=0.3)` for stacks;
  `arrange_in_grid` for grids. Avoid raw coordinates beyond |x| 5.5, |y| 3.2.
- `group.move_to(p)` centres the group's *bounding box*, labels included. To line up two
  diagrams, position them by their anchor object: `g.shift(target - g.frame.get_center())`.
- `Arrow` shrinks its tip on short arrows; for very short ones use `max_tip_length_to_length_ratio`.
- 3D: only when the plan marks the scene `"dim": "3d"`. Subclass `WaitwhatScene3D` (never mix
  `WaitwhatScene` with `ThreeDScene` by hand) and follow `references/3d.md`: text flat on the
  screen (`tag`, `pin`, `callout`), house constructors sized for the render budget.

## Rendering
- A scene id that equals a Python module name (`wave`, `math`, `random`, `types`, `code`, `string`)
  shadows it: scene files are on the import path, so Manim itself fails to import. Pick another id.
- Each file must define its scene class in that file (subclassing an imported scene class is
  fine; importing one is not enough).
- `--disable_caching` is on (`ww render`), so stale partial movies are never reused.
- A scene that ends before its narration is padded with its last frame by stitch, but it reads
  as dead air; call `self.finish()` and design for the full length.
