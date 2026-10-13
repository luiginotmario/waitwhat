# Scene subagents: the default production flow

For any video with **3 or more scenes**, scenes are built by subagents in parallel, one per
scene. This is not an optimisation to consider; it is how a waitwhat video is made. It keeps
render logs and tracebacks out of your context, and it turns minutes per scene into minutes per
video. (Fewer than 3 scenes, or no Agent/Task tool at all: see "Serial fallback" below.)

## Before fanning out (one or two turns)

1. `workspace/plan.json` is final: every scene's `narration` (with bookmarks), `goal`, `visual`,
   `transition`, `covers`, plus `palette`, `voice` and `sound`. Then `ww progress plan`.
2. `workspace/scenes/shared.py` holds every constructor two scenes share (the objects a
   `continuous` handoff passes on, layout constants, a scene's end state that the next one
   starts from). Together with the style lib it is the style reference. Do not render a
   reference scene first: all scenes start at once.
3. Start the voice without waiting for it: `ww tts --background && ww progress stage animating "<message>"`.
   It returns immediately and marks each scene it voices as pending; every `ww render` of a
   pending scene waits for that scene's audio, so the subagents can write code meanwhile.

## Fan out (the same turn, or the very next)

Launch one subagent per scene **as several Agent tool calls in one message**, so they run in
parallel. The whole hand-off can be a single message, in this order: Write `plan.json`, Write
`shared.py`, Bash `ww progress plan && ww tts --background && ww progress stage animating "…"`,
then the Agent calls (tool calls in one message run in order; consecutive Agent calls run
together). Set `run_in_background: false` on each Agent call where the tool offers it: you need
every result before the review, and they still run in parallel with each other. At most `WAITWHAT_RENDER_JOBS` at once (the run context gives the number; default
`max(2, cores - 2)`). With more scenes than that, launch the first batch in outline order, then
the next batch when it returns. Two very short scenes that share objects may go to one subagent.

- **`scene-builder` agent type available** (the waitwhat worker defines it): it already knows
  the loop, the house style and the lib API (`references/scene-builder.md` plus the
  manim-scenes skill). The brief only needs what is specific to the scene.
- **Otherwise** (e.g. Claude Code without the worker): use a general-purpose subagent and start
  the brief with: "First read `<plugin>/skills/waitwhat/references/scene-builder.md`,
  `<plugin>/skills/manim-scenes/SKILL.md` and its `references/style-guide.md`, and follow them."

The brief (keep it short; the subagent reads plan.json itself):

```
Job dir: /abs/path/to/job          ww: /abs/plugin/scripts/ww
Scene: squares (2 of 6)            write workspace/scenes/squares.py

What it must do: <the scene's job and storyboard in your words>.
Starts on: <what is on screen at the start: the previous scene's end state, built by
           shared.make_triangle(), or "a cut: empty frame">.
Ends on:   <what must be on screen at the end, for the next scene's handoff>.
Use: shared.make_triangle(), shared.SQUARE_STYLE; palette a=BLUE, b=TEAL, c=YELLOW_SOFT.
Watch out for: <anything you already know is tricky, e.g. long labels near the right edge>.
```

Each subagent writes its scene, previews it (`ww render <id> --preview`), looks at the frames,
fixes (max 3 attempts per error), renders the final 1080p once, marks `ww progress scene <id>
done`, and replies in one or two lines (scene, duration vs narration, status, deviations).

## After the batch returns

1. `ww tts --wait` (instant if the voice finished): confirm every scene was voiced. If one
   failed, `ww tts --scene <id>` and re-render that scene.
2. Review every contact sheet in ONE turn (parallel Reads of `workspace/frames/<id>_sheet.jpg`).
   Look for what only you can see across scenes: colours drifting from the palette, a handoff
   that jumps (end of A ≠ start of B), text sizes that differ, one scene far busier than its
   neighbours.
3. Fix only what matters. Send the fix to the same subagent if it can still be messaged
   (SendMessage), otherwise brief a new `scene-builder` with the specific change, or make a
   one-line fix yourself and `ww render <id>`. Several fixes go out in parallel, like the first
   batch.
4. `ww stitch`.

## Serial fallback

With no Agent/Task tool, or for a video of 1–2 scenes, run the same loop yourself, one scene
after another: write → `ww render <id> --preview` → look → fix → `ww render <id>` → `ww progress
scene <id> done`. Still start the voice with `ww tts --background` first, and still do only one
final render per scene (or `ww render --all` once at the end, which renders in parallel).
