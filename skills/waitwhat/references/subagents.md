# Scene subagents: the default production flow

For any video with **3 or more scenes**, scenes are built by subagents in parallel, one per
scene. This is not an optimisation to consider; it is how a waitwhat video is made. It keeps
render logs and tracebacks out of your context, and it turns minutes per scene into minutes per
video. (Fewer than 3 scenes, or no Agent/Task tool at all: see "Serial fallback" below.)

What the clock looks like: the subagents start one after another as you write their Agent calls,
and the video waits for the slowest one. So the hand-off is two messages, the briefs are short
(the plan carries the direction), and each builder needs as few turns as possible.

## The hand-off: two messages

**Message 1** (one assistant message, three tool calls):
1. Write `workspace/plan.json`, final: every scene's `narration` (with bookmarks), `goal`,
   `visual`, `build`, `transition`, `covers`, `energy`, plus `palette`, `theme`, `voice`, `sound`.
   `visual` and `build` are the builder's brief, so make them concrete: what appears where and on
   which word, the `shared.py` objects to use, what is on screen at the start and the end (for
   `continuous` handoffs), the beats, the chosen sound moments, what to watch out for.
2. Write `workspace/scenes/shared.py`: every constructor two scenes share (the objects a
   `continuous` handoff passes on, layout constants, a scene's end state the next one starts
   from). Together with the style lib it is the style reference. Don't render a reference scene.
3. Bash: `ww render --check && ww progress plan && ww tts --background && ww progress stage animating "<message>"`.
   `--check` imports `shared.py` with the toolchain (about a second); if it fails, fix
   `shared.py` before fanning out. `ww tts --background` returns at once; every final render of a
   scene waits for that scene's audio, so the builders write code meanwhile.

**Message 2**: one `scene-builder` Agent call per scene, all in this one message (consecutive
Agent calls run together; set `run_in_background: false` where the tool offers it: you need every
result before the review). At most `WAITWHAT_RENDER_JOBS` at once (the run context gives the
number); with more scenes, launch the first batch in outline order and the next when it returns.
Two very short scenes that share objects may go to one subagent.

- **`scene-builder` agent type available** (the waitwhat worker defines it): it already knows
  the loop, the house style and the lib API (`references/scene-builder.md` plus the
  manim-scenes skill).
- **Otherwise** (e.g. Claude Code without the worker): use a general-purpose subagent and start
  the brief with: "First read `<plugin>/skills/waitwhat/references/scene-builder.md`,
  `<plugin>/skills/manim-scenes/SKILL.md` and its `references/style-guide.md`, and follow them."

The brief is three lines. Everything else is in the scene's `plan.json` entry, which the builder
reads; don't repeat the narration, storyboard or palette here:

```
Job dir: /abs/path/to/job   ww: /abs/plugin/scripts/ww
Scene: squares (2 of 6) → workspace/scenes/squares.py. Your brief is its entry in workspace/plan.json.
<optional: one line the plan doesn't say, e.g. "keep the triangle exactly where hook leaves it">
```

Each subagent writes its scene, renders the final 1080p (`ww render <id>`, a few seconds; it
marks the scene's progress), looks at the 2x2 sheet, fixes only real problems, and replies in
one or two lines (scene, duration vs narration, status, deviations).

## After the batch returns: one review turn

1. One Bash: `ww tts --wait && ww review` (instant if the voice finished). `tts --wait` confirms
   every scene was voiced (if one failed: `ww tts --scene <id>`, then re-render it). `ww review`
   writes `workspace/frames/_review_<n>.jpg`: one row per scene in plan order, first frame |
   middle | last frame, so the end of each row sits above the start of the next (the handoff).
2. Read every `_review_*.jpg` in ONE message. Look for what only you can see across scenes:
   colours drifting from the palette, a `continuous` handoff that jumps (end of A ≠ start of B),
   text sizes that differ, one scene far busier than its neighbours, a scene that ignores the
   theme, a flat run of scenes with the same rhythm. A cut scene's first frame is often empty;
   that is fine. Open a scene's own sheet (`frames/<id>_sheet.jpg`) only if a row looks wrong.
3. Fix only what matters, all fixes in one message so they run in parallel: SendMessage to the
   same subagent if it can still be messaged, otherwise a new `scene-builder` with the specific
   change, or a one-line fix yourself and `ww render <id>`. Nothing to fix: go straight to stitch.
4. `ww stitch` (see the waitwhat skill, step 7).

## Serial fallback

With no Agent/Task tool, or for a video of 1–2 scenes, run the same loop yourself, one scene
after another: write → `ww render <id>` (final, marks progress) → look at the sheet → fix only if
needed. Still start the voice with `ww tts --background` first.
