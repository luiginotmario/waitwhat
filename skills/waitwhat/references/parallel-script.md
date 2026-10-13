# Parallel script: you direct, each scene builder writes its own words

Use this flow when the run context says **script mode: parallel**. You write the skeleton of the
story; each `scene-builder` writes its scene's narration and code together and voices its own
scene, all at once; you then read the whole script once and smooth the seams. Your first turn is
short, and the narration is written in parallel.

## 1. The skeleton (your one big message)

Write `workspace/plan.json` with everything the normal plan has (title, question, audience,
aha, `duration_target`, outline/asked/deferred, theme, palette, voice, pronunciations, sound,
thumbnail) and, per scene, everything except the final words:

- `id`, `title`, `goal`, `covers`, `energy`, `transition`, `visual`, `build` (as usual).
- `say`: what the narration must get across, in order: 2–4 short bullets (strings). Facts,
  numbers and terms go here exactly as they must be said; the builder adds nothing factual.
- `hands_off`: one line: the thought this scene ends on and how the next scene picks it up
  (e.g. `"ends on 'a quarter of a day, every year' → next opens on what that adds up to"`).
  The first scene's `hands_off` also says what the hook is; the last scene's says how it closes
  the question.
- `seconds`: its share of `duration_target` (≈190 words per minute).
- `narration`: `""` (the builder fills it).

Write `shared.py` in the same message, and one Bash:
`ww render --check && ww progress plan && ww progress stage animating "<message>"` (no
`ww tts` here: each builder voices its own scene). Then, in the next message, the Agent calls
with the usual three-line briefs, adding: `Write this scene's narration first (parallel script).`

Think about the arc (the hook, the order of ideas, where the insight lands, how each scene hands
to the next), not the sentences: the builders write the sentences.

## 2. What each builder does

It reads `ww brief <id>` (its entry, its neighbours, and the whole arc), writes its narration
to the voice and storytelling rules (spoken English, bookmarks on the words its visuals land
on, about `seconds` long), runs `ww narrate <id>` (saves it into plan.json under a lock and
voices it), then writes and renders the scene against that audio.

## 3. The read-through (one turn, then fixes in parallel)

After the batch returns: one Bash `ww review && ww script`, then Read the `_review_*.jpg` images
in the same message as you read the script printed by `ww script`. Read the script as one piece,
aloud in your head:
- Does each scene pick up where the last one left off? Repeated openings ("So...", "Now..."),
  a term explained twice or never, a jump in the logic, a missing transition sentence.
- One voice: same register and person throughout; the hook earns the question; the close
  answers it.
- Length near `duration_target` (the script prints the voiced total).

Fix only real seams, and keep every edit small: rewrite a sentence or two, **keep the scene's
bookmark names**, then re-voice and re-render that scene in one chain:
`ww narrate <id> <<'EOF' … EOF` `&& ww render <id>` (bookmarks unchanged, so the code retimes by
itself). Several scenes: one Bash with the chains joined by `&`, then `wait`. Visual fixes go to
builders as usual. Then `ww stitch` (step 7 of the waitwhat skill).
