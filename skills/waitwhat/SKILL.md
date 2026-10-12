---
name: waitwhat
description: Turn any prompt, attached files, or a company URL into a narrated explainer video in the visual style of 3Blue1Brown (Manim + voice + music → out/video.mp4). Use for "make me a waitwhat video on X", "explain X as a video", "animate an explainer of this paper/company", or whenever the working directory holds a waitwhat job (request.json). Also handles refine requests ("wait, what?" on a paused frame). This is the orchestrator; it calls the storytelling, research, voice, manim-scenes, sound and refine skills.
---

# waitwhat: prompt → explainer video

You are the director. You decide what the video should teach, who it is for, and how it should
feel; the other waitwhat skills hold the craft. The bar is a video a curious, smart person would
happily watch to the end and come away actually understanding something.

Tools live in `${CLAUDE_PLUGIN_ROOT}/scripts/` (if that path did not expand, use
`$WAITWHAT_PLUGIN_DIR/scripts/`). Call them through the wrapper, below written as `ww`:
`${CLAUDE_PLUGIN_ROOT}/scripts/ww <cmd>`. `ww help` lists commands. The first run of any render
installs the toolchain (`ww setup`, idempotent, a few minutes).

## 1. Find the job

- **Worker / Mac app**: the cwd contains `request.json`. That is the job dir. Do not move it.
- **Someone asks in chat** ("make me a waitwhat video on X"): run `ww new "<their prompt>"
  [--attach files]`, which creates `./waitwhat-videos/<slug>/` with a contract-shaped
  `request.json`, then work inside that dir. At the end, `open out/video.mp4`.
- **A refine** (`request.json` has `refine`, or the user says "wait, what?" about a video):
  load the `waitwhat:refine` skill and follow it instead of planning from scratch.

The job I/O contract is not negotiable: read `references/job-contract.md` once per job. Outputs
are `out/video.mp4` (1080p h264+aac), `out/thumbnail.jpg`, `out/manifest.json`; everything you
make lives in `workspace/` (it is archived and becomes the base of future refines).

## 2. Report progress as you go

The person is watching a progress bar. Update it at every stage change and per scene:
`ww progress stage <understanding|research|script|voice|animating|stitching|done> "<short human message>"`,
`ww progress plan` after writing plan.json (and whenever the scene list changes), and
`ww progress scene <id> <rendering|done|failed>`. `ww progress plan` also reports progress against
the outline (each outline item is done when every scene that `covers` it is done), so the person
sees their checklist fill in.
Messages are for a person: "Sketching the visual proof", not "running render.py".

## 3. Understand the request: the coverage plan is the checklist

Every video is built against a **coverage plan**: every topic the person asked for, the
prerequisites they need but didn't say, the order of the explanation, a title and an estimated
duration. The one principle: **cover everything the request needs, and nothing it doesn't.**
There is no default length; a narrow question makes a short video and a broad one a long video.

- **`request.json` has `plan`** (the web app plans before the job starts, with
  `references/planning.md`): that is your checklist. `plan.outline` is the ordered list of what
  the video must cover, `plan.asked` is what the person explicitly asked for, `plan.est_minutes`
  the length it was scoped to, `plan.note`/`plan.deferred` what a free preview left out, and
  `request.answers` any clarifying answers the person gave. You may refine it (split an item,
  reorder, merge two items into one scene, add a missing prerequisite you discover while
  researching), but you may **not silently drop** anything: if an item truly cannot be covered,
  record it in `plan.json` `dropped` with the reason and say so in your final message.
- **No `plan`** (older clients, local runs): read `references/planning.md` and do that planning
  step yourself first (headless: never ask questions).

Write into `workspace/plan.json` (schema in `references/job-contract.md`):

- `outline`, `asked`, `deferred` copied from the request plan (or from your own planning), and
  `duration_target` = `est_minutes` × 60. Keep `duration_target` honest if your scene plan grows:
  the worker sizes its time limit from it.
- **Mode**: topic (just a prompt), attachments (explain *this* paper/deck/data), company (the
  prompt is or contains a company URL), refine. A prompt can mix them.
- **The one question** the video answers, phrased the way a curious viewer would ask it
  (`plan.question` if present). Pick the most interesting honest version of the request.
  "Explain transformers" becomes "How can predicting the next word produce something that seems
  to reason?"
- **Audience and depth** (`plan.audience` if present). Default: a smart adult with no special
  background. Read cues: "like I'm 10" means no jargon, every term earned (it is not a kids'
  show: same respect, simpler words); "for engineers" or a technical attachment means you can use
  notation, but you still build intuition first.
- **Length**: what the outline needs, about `est_minutes`. Respect explicit asks. If the job
  prompt states a **free preview limit**, stay within it (it is a soft ceiling: ±15%), and keep
  the plan's focus; don't quietly add deferred material back.

For attachments, read them fully first (PDFs and images with Read). For company URLs and for any
topic where facts matter, load `waitwhat:research`. Never invent facts, numbers, quotes or
customers; if you cannot verify something, leave it out.

## 4. Plan the story, then the pictures

Load `waitwhat:storytelling` and write the scene plan from the outline: walk the outline in
order and give each item as many scenes as it needs (usually one to three; a prerequisite can be
a single short scene). Each scene has one job, a narration draft, a storyboard line, its concept
colours, how it hands off to the next scene, and `covers`: the 1-based outline items it serves.
Every outline item must be covered by at least one scene; `ww progress plan` warns about any that
aren't. Narration comes first and drives everything else. Read the whole narration aloud in your
head: if a sentence would sound odd spoken by a person, rewrite it. Check the total narration
against `duration_target` (≈190 words per minute); if you are far off, revisit the scope, not the
speaking pace.

## 5. Voice before animation

Load `waitwhat:voice`. Choose the voice, set `plan.voice`, add bookmarks where visuals must land
on a word, then `ww tts`. Scene timing comes from these audio files, so narrate *before*
animating, and re-run `ww tts --scene <id>` whenever a scene's narration changes.

## 6. Animate scene by scene

Load `waitwhat:manim-scenes`. One Manim file per scene in `workspace/scenes/<id>.py`, shared
objects in `workspace/scenes/shared.py`. Render with `ww render <id>`, fix errors (max 3 tries),
then *look* at `workspace/frames/<id>_sheet.jpg` and fix anything overlapping, cut off,
unreadable or ugly.

Use subagents for scenes whenever you can: brief one per scene (or a few small scenes each) so
tracebacks and render logs stay out of your context. The briefing template is in
`references/subagents.md`. Write `shared.py`, the palette and the narration timings *before*
fanning out, render the hook yourself first to lock the look, then run the rest in parallel.
Review every returned contact sheet yourself; consistency across scenes is your job.

### Long videos (roughly 10+ scenes)

Length is not a reason to cut corners, but your own context is finite, so delegate harder:
- Plan, narrate and voice the whole video first (`ww tts` handles every scene in one call).
- Render the hook yourself to lock the look, then hand **every other scene** to a subagent,
  a few at a time (3 to 4 in parallel), working through the outline in order. Keep your own
  context for direction and review: look at contact sheets, not render logs.
- Keep `shared.py` and the palette stable once the fan-out starts; if you must change them,
  re-render the scenes that import what changed.
- `ww render --all -j 3` and `ww stitch` take longer on long videos: give those Bash calls the
  maximum timeout, or run them in the background and poll.
- Update progress per scene as subagents report back, so a long render never looks stuck.

## 7. Sound, stitch, check

Load `waitwhat:sound` for the music mood and transitions (usually just `plan.sound`). Then
`ww stitch` → `out/`. Watch for problems: extract a few frames across the final video, check the
thumbnail, and run `ww check`. Then `ww progress stage done "Your video is ready"`.

## 8. Finish

Reply briefly: the title, length, what the video covers, and the path to `out/video.mp4`
(local runs: also `open` it). Mention anything you could not verify or had to simplify, any
outline item you dropped and why, and (free previews) what was deferred.

## Judgment calls

- If a scene keeps failing after 3 fix attempts, simplify the visual rather than dropping the
  idea; a clean simple picture beats a broken clever one.
- If the request is ambiguous and you are running headless (worker), choose the most useful
  interpretation and say which in the final message. In an interactive chat you may ask 1 to 3
  short multiple-choice questions first (the rules are in `references/planning.md`), but only
  if the answers would change the whole video. Most requests need none.
- Cost matters: ElevenLabs characters are limited. Narrate once, re-narrate only scenes whose
  text changed (the cache does this for you).
