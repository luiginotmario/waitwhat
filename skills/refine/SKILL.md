---
name: refine
description: Handle a waitwhat "wait, what?" refine - the viewer paused the video, circled something on the frame in pencil and typed what confused them. Work out which scene and element they mean and what kind of change helps (insert a scene before, expand, replace the visual, or re-explain with a different analogy), then re-voice and re-render only the affected scenes, re-stitch, and keep continuity. Use when request.json has a "refine" field or a user asks to change part of an existing waitwhat video.
---

# Refine: "wait, what?"

A refine is a conversation with one confused viewer. They told you three things: **when**
(`at_seconds`), **where** (the pencil circle on `frame_path`) and **what** (their words). Your job
is to answer that confusion inside the video, building on what exists, so the new version feels
like the same video, just clearer at that moment.

## Inputs
- `request.json` → `refine: {text, at_seconds, frame_path}` (frame relative to the job dir).
- `workspace/` = the previous version: `plan.json`, `scenes/`, `audio/`, `renders/`,
  `timeline.json`, `versions.md`. Everything not touched is reused as-is (render and TTS caches
  are keyed by content, so unchanged scenes cost nothing).
- Locally, `ww refine <job> "<text>" --at <s> [--frame f.png]` creates the new version dir with
  the previous workspace copied in; then work there.

## 1. Locate
`ww render --probe <at_seconds>` maps the moment to a scene id and local time, prints the
narration around it, and lists what was on screen with bounding boxes (in frame units and in
1080p pixels). Look at the frame image: the pencil circle's position (scale pixel coordinates if
the frame isn't 1920×1080) tells you which object(s) they mean. Then read that scene's narration
and code. If the circle is ambiguous, the words decide; if the words are vague ("huh?"), the
circle and the narration at that moment decide.

## 2. Diagnose: what kind of confusion is it?

| Signal | Likely gap | Change |
| --- | --- | --- |
| "what is X?", circled a term/symbol | a prerequisite was assumed | **insert before**: a short scene (8–20 s) that builds X with a picture, then hands off to the existing scene |
| "why?", "how did we get here?", circled a step or arrow | a step went by too fast or was skipped | **expand**: slow that scene down, add the missing intermediate step (split into two scenes if needed) |
| "what am I looking at?", circled a cluttered region | the visual doesn't show what the narration says | **replace** the visual for that beat; keep the narration's idea |
| "still don't get it", "explain differently" | the framing didn't land | **re-explain** with a different representation or analogy (see storytelling: what/why/how views) |
| a factual or pronunciation complaint | an error | **fix** narration/visual/pronunciation; verify with research first |

Pick the smallest change that would satisfy that viewer, but don't be timid: if a new scene is
what's needed, add it. Usually one or two scenes change.

## 3. Edit the plan, then the pieces
- Edit `workspace/plan.json`: insert or modify scenes. Keep existing ids; give new scenes new ids
  (`squares-why`), and keep the palette (new concepts get new colours, old ones keep theirs).
- Write the new narration so it flows from the previous scene's last sentence and into the next
  scene's first one. Read the three in sequence.
- `ww progress plan` (scene list changed), `ww tts` (only changed narration is re-voiced, with
  the same voice as before), then write/modify scene files and `ww render <ids>`.
- Continuity: an inserted scene starts from the previous scene's end state and ends in the next
  scene's start state (use `shared.py`), or set `"transition": "cut"` on both sides deliberately.
  If you changed a scene's end state, re-render the next scene too.
- Look at the contact sheets of every changed scene *and* its neighbours' boundaries.

## 4. Stitch and report
`ww stitch` → `out/`, `ww check`, `ww progress stage done "…"`. Append one line to
`workspace/versions.md`: what the viewer asked, what you changed, which scenes. In the final
message, tell the viewer what changed and where it is now (e.g. "new 15 s scene at 0:41 that
builds the tilted square before we use it").

## Examples
- *"wait what, why is the middle a square?"*, circled the tilted gap at 0:24 → expand `copies`:
  add a beat showing the four right angles (each corner = 180° − the two acute angles = 90°)
  before naming c².
- *"what's a hypotenuse"*, circled the long side at 0:08 → fix vocabulary: the video should say
  "the long side" first and only then name it; re-voice `hook`, add a label on screen.
- *"I don't get why they're equal"*, circled the equation at 0:50 → re-explain in `aha`: animate
  both pictures losing their triangles at the same time (subtracting equals from equals) instead
  of only stating it.
