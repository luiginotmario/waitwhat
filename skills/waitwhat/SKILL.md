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
`ww progress plan` after writing plan.json, `ww progress scene <id> <rendering|done|failed>`.
Messages are for a person: "Sketching the visual proof", not "running render.py".

## 3. Understand the request

Work out, and write into `workspace/plan.json` (schema in `references/job-contract.md`):

- **Mode**: topic (just a prompt), attachments (explain *this* paper/deck/data), company (the
  prompt is or contains a company URL), refine. A prompt can mix them.
- **The one question** the video answers, phrased the way a curious viewer would ask it. Pick
  the most interesting honest version of the request. "Explain transformers" becomes "How can
  predicting the next word produce something that seems to reason?"
- **Audience and depth**. Default: a smart adult with no special background. Read cues: "like
  I'm 10" means no jargon, every term earned (it is not a kids' show: same respect, simpler
  words); "for engineers" or a technical attachment means you can use notation, but you still
  build intuition first. When unsure, aim at the bright newcomer; experts enjoy clarity too.
- **Length**: 1–5 minutes, default about 2–3 (≈ 300–450 narrated words). Respect explicit asks.

For attachments, read them fully first (PDFs and images with Read). For company URLs and for any
topic where facts matter, load `waitwhat:research`. Never invent facts, numbers, quotes or
customers; if you cannot verify something, leave it out.

## 4. Plan the story, then the pictures

Load `waitwhat:storytelling` and write the scene plan: 6–12 scenes, each with one job, a
narration draft, a storyboard line, its concept colours and how it hands off to the next scene.
Narration comes first and drives everything else. Read the whole narration aloud in your head:
if a sentence would sound odd spoken by a person, rewrite it.

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

## 7. Sound, stitch, check

Load `waitwhat:sound` for the music mood and transitions (usually just `plan.sound`). Then
`ww stitch` → `out/`. Watch for problems: extract a few frames across the final video, check the
thumbnail, and run `ww check`. Then `ww progress stage done "Your video is ready"`.

## 8. Finish

Reply briefly: the title, length, what the video covers, and the path to `out/video.mp4`
(local runs: also `open` it). Mention anything you could not verify or had to simplify.

## Judgment calls

- If a scene keeps failing after 3 fix attempts, simplify the visual rather than dropping the
  idea; a clean simple picture beats a broken clever one.
- If the request is ambiguous and you are running headless (worker), choose the most useful
  interpretation and say which in the final message. In an interactive chat you may ask one
  short question first, but only if the answer would change the whole video.
- Cost matters: ElevenLabs characters are limited. Narrate once, re-narrate only scenes whose
  text changed (the cache does this for you).
