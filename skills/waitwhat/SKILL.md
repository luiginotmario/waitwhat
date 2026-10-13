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

If this skill and its companions (storytelling, voice, manim-scenes and its style guide, sound,
the job contract, the subagent flow) are already in your system prompt, as the waitwhat worker
preloads them, don't invoke or re-read them: start working. Read other references only when
the step that needs them comes up.

**Pace.** The person is waiting: wall-clock time matters as much as cost, and almost all of it
is model turns (a 1080p scene renders in seconds, the voice in ~25 s in the background, stitching
in ~10 s). Every turn you take is on the critical path, and so is every token you write. So:
- Batch independent tool calls into one message (parallel Reads, a Write plus a Bash).
- Write `plan.json` in ONE Write with everything in it (scenes, narration, per-scene direction);
  never build it with a string of Edits.
- Write each thing once: what a scene builder needs goes in its `plan.json` entry, and the Agent
  brief only points at it (references/subagents.md). Don't restate the plan in briefs.
- Research is bounded (step 3). No test renders, no reading the style lib's source, no
  `ww help`: everything you need is in your context.
- The finish is two turns (step 7), and the final reply is a few lines.

## 1. Find the job

- **Worker / Mac app**: the cwd contains `request.json`. That is the job dir. Do not move it.
- **Someone asks in chat** ("make me a waitwhat video on X"): run `ww new "<their prompt>"
  [--attach files]`, which creates `./waitwhat-videos/<slug>/` with a contract-shaped
  `request.json`, then work inside that dir. At the end, `open out/video.mp4`.
- **A refine** (`request.json` has `refine`, or the user says "wait, what?" about a video):
  load the `waitwhat:refine` skill and follow it instead of planning from scratch.

The job I/O contract is not negotiable: read `references/job-contract.md` once per job (unless
it is already in your context). Outputs
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
  `references/planning.md`): that is your checklist. **Do not re-plan from scratch** and don't
  read `planning.md`: the scope, order and length are decided. Go straight to the scene plan
  (step 4) and refine the outline only where the story needs it. `plan.outline` is the ordered list of what
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
- **A chosen depth wins**: `request.level` other than `auto` is a hard override of any inferred
  audience: `eli10` = define every term, analogies first; `expert` = assume the fundamentals, go
  deep; `jargon` = precise technical terminology throughout, defining only rare terms.
- **Audience and depth** (`plan.audience` if present; it starts with the level: `newcomer`,
  `intermediate` or `expert`). If you plan yourself, read the asker's vocabulary
  (`references/planning.md`, "Read the asker"): precise jargon ("idempotency keys", "PSP", "KV
  cache") means an expert who wants depth and pace, so skip the basics they already used in
  their question; vague, everyday wording means a newcomer, so start high-level and intuitive
  and go progressively deeper. "Like I'm 10" means no jargon, every term earned (same respect,
  simpler words). Either way every technical term is explained in place, the first time it's said.
- **Length**: what the outline needs, about `est_minutes`. Respect explicit asks. If the job
  prompt states a **free preview limit**, stay within it (it is a soft ceiling: ±15%), and keep
  the plan's focus; don't quietly add deferred material back.

For attachments, read them fully first (PDFs and images with Read). For company URLs and for any
topic where facts matter, load `waitwhat:research`. Never invent facts, numbers, quotes or
customers; if you cannot verify something, leave it out.

**Research is bounded.** `request.research` (when present) lists pages the web app already
fetched while planning, saved in `workspace/research/`: use them, don't fetch them again. Then
at most two rounds: ONE `ww fetch URL URL ... [--search "..."]` call with every page you need (they
download in parallel; `--search` only works when `JINA_API_KEY` is set), then ONE Bash that pulls
the relevant passages out of all of them (a `grep -n -i -E` over the files, or `sed -n` ranges),
and only if a needed fact is still missing, one more targeted round. Write `research/notes.md`
in the same message as `plan.json`. For timeless topics (math, classic physics, how the calendar
works) your own knowledge plus one reference page is enough.

## 4. Plan the story, then the pictures

Load `waitwhat:storytelling` and write the scene plan from the outline: walk the outline in
order and give each item as many scenes as it needs (usually one to three; a prerequisite can be
a single short scene). When the subject has a real story (a company, a discovery, an invention,
a historical turn), tell it as one: a real protagonist with a problem, what was at stake, the
turning point, then the idea, all from verified sources.

Each scene has one job, its narration, a storyboard (`visual`: what appears, where, on which word;
concrete enough for a builder to draw it), how it hands off to the next scene, `covers` (the
1-based outline items it serves), and `build`: the builder's notes in a line or two (the
`shared.py` objects it uses, what is on screen at its start and end, the 1–3 beats, the chosen
sound moments, anything tricky). The scene builder works from this entry alone.
Every outline item must be covered by at least one scene; `ww progress plan` warns about any that
aren't. Give every scene an `energy` (`high`, `medium`, `low`, `reveal`, `close`) so the video has
an arc instead of one flat level: a bright hook, steady build-up, a hush before the insight, a
lift at the reveal, a calm close.

**Choose the world** (`plan.theme`): one theme for the whole video, matched to the topic (the
table is in the style guide): `classic` black for math and abstract ideas (the default),
`chalkboard` for lessons and derivations, `blueprint` for machines and systems, `space` for
astronomy and scale, `ocean` for life and flows, `paper` or `hills` for stories and history,
`studio`, `city` or `whiteboard` for companies, products and business, `graph_paper` for data.
Switch per scene (`scenes[].theme`) only when the story itself moves to another place.

Narration comes first and drives everything else. Read the whole narration aloud in your
head: if a sentence would sound odd spoken by a person, rewrite it. Check the total narration
against `duration_target` (≈190 words per minute); if you are far off, revisit the scope, not the
speaking pace.

## 5. Voice: final words, then voice in the background

Load `waitwhat:voice`. Choose the voice, set `plan.voice`, add bookmarks where visuals must land
on a word. Scene timing comes from the audio, so the narration must be **final** before any
scene is animated; the audio itself doesn't have to exist yet. Start it with
`ww tts --background`: it voices every scene in parallel in a detached process and returns at
once, and `ww render` of a scene waits for that scene's audio. (`ww tts` without the flag does
the same in the foreground.) Re-run `ww tts --scene <id>` whenever a scene's narration changes.

## 6. Animate: one subagent per scene, in parallel

Load `waitwhat:manim-scenes`. One Manim file per scene in `workspace/scenes/<id>.py`, shared
objects in `workspace/scenes/shared.py`.

**For any video with 3 or more scenes, scenes are built by parallel subagents: this is the
default flow, not a suggestion.** Follow `references/subagents.md`:
1. One message: Write `plan.json` (every scene's narration, `visual`, `build` notes; see the job
   contract) + Write `shared.py` (the style reference; no reference render) + one Bash:
   `ww render --check && ww progress plan && ww tts --background && ww progress stage animating "…"`.
2. Next message: one `scene-builder` Agent call per scene, all in that ONE message (at most
   `WAITWHAT_RENDER_JOBS` at once; more scenes go in batches, in outline order). Each brief is
   three lines; the scene's `plan.json` entry is the real brief.
3. Each subagent writes its scene, renders the final 1080p (seconds), looks at its 2x2 sheet,
   fixes only real problems, and replies in a line or two. Progress updates itself.
4. You review the whole video in ONE turn (`ww tts --wait && ww review`, then Read the
   `_review_*.jpg` images) and send back only the fixes that matter, in parallel.

Fallback: with no Agent/Task tool, or 1–2 scenes, run the same loop yourself scene by scene
(write → `ww render <id>` → look at the sheet → fix only if needed).

### Long videos (roughly 10+ scenes)

Length is not a reason to cut corners, but your own context is finite, so delegate harder:
- Plan, narrate and start the voice for the whole video first (`ww tts --background` voices
  every scene).
- Hand every scene to a subagent, batch by batch in outline order. Keep your own context for
  direction and review: look at the `ww review` images, not render logs.
- Keep `shared.py` and the palette stable once the fan-out starts; if you must change them,
  re-render the scenes that import what changed.
- `ww render --all` and `ww stitch` take longer on long videos: give those Bash calls the
  maximum timeout, or run them in the background and poll.
- Progress is per scene (each final render reports it), so a long render never looks stuck.

## 7. Sound, stitch, check (two turns)

Load `waitwhat:sound` for the music mood and effects (usually just `plan.sound`, already in
plan.json; the scenes log their own sound cues). Then:
1. One Bash: `ww stitch && ww check; echo "v1 $(date +%F): <one line>" >> workspace/versions.md`
   (`ww check` only complains that the stage is not `done` yet; that is expected here).
2. One message: Read `workspace/frames/_final.jpg` (frames across the finished video plus the
   thumbnail) and, in the same message, Bash `ww progress stage done "Your video is ready"`. If
   the look shows a real problem (a black or broken frame, a wrong scene order, a bad
   thumbnail), fix it, stitch again, and set done again.

## 8. Finish

Reply in a few short lines: the title, the length, what it covers, and the path to
`out/video.mp4` (local runs: also `open` it). Mention anything you could not verify or had to
simplify, any outline item you dropped and why, and (free previews) what was deferred.

## Judgment calls

- If a scene keeps failing after 3 fix attempts, simplify the visual rather than dropping the
  idea; a clean simple picture beats a broken clever one.
- If the request is ambiguous and you are running headless (worker), choose the most useful
  interpretation and say which in the final message. In an interactive chat you may ask 1 to 3
  short multiple-choice questions first (the rules are in `references/planning.md`), but only
  if the answers would change the whole video. Most requests need none.
- Cost matters: ElevenLabs characters are limited. Narrate once, re-narrate only scenes whose
  text changed (the cache does this for you).
