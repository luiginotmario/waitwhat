# Briefing a scene subagent

Subagents keep render logs and tracebacks out of the director's context and let scenes render in
parallel. They start with no memory of this conversation, so the brief must stand on its own.

Before fanning out, make sure these exist: `workspace/plan.json` (with palette), narration audio
for every scene (`ww tts`), `workspace/scenes/shared.py` for anything two scenes share, and one
finished scene (usually the hook) whose frames you have looked at. That first scene is the
style reference the others must match.

Give each subagent one scene (or two or three very short ones). A good brief:

```
You are animating ONE scene of a waitwhat explainer video (3Blue1Brown style, Manim CE).

Job dir: /abs/path/to/job        (your shell's cwd resets between commands: run each as
                                  `cd /abs/path/to/job && …`)
Scene id: squares                (write workspace/scenes/squares.py, class name anything)
Tools: /abs/plugin/scripts/ww    (ww render squares; ww manim … for experiments)

Read first:
- /abs/plugin/skills/manim-scenes/SKILL.md and its references/style-guide.md
- workspace/plan.json (your scene's narration, visual, transition; the palette)
- workspace/audio/squares.json (bookmark times; the scene must last until narration ends)
- workspace/scenes/shared.py and workspace/scenes/hook.py (match this look exactly)

What this scene must do: <the scene's goal + storyboard, in your words, including what is on
screen at the start (handoff from the previous scene) and what must be on screen at the end
(handoff to the next)>.

Loop: write → `ww render squares` → if it fails, read the traceback and fix (max 3 attempts,
then simplify the visual) → look at workspace/frames/squares_sheet.jpg → fix overlaps, clipping,
tiny text, dead time, anything off-style → re-render. Stop when the frames look finished.

Reply in at most 8 lines: status (done/failed), duration vs narration, what the viewer sees,
any deviation from the storyboard and why, any issue you could not fix. No code, no logs.
```

Then review each sheet yourself. Common cross-scene problems only you can see: colours drifting
from the palette, a handoff that jumps (end of A ≠ start of B), text sizes that differ, one scene
far busier than its neighbours. Send fixes back to the same subagent if it is still alive
(SendMessage), otherwise brief a new one with the specific fix.
