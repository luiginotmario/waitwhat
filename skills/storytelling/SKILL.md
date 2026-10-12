---
name: storytelling
description: Story and script rules for waitwhat explainer videos, distilled from how 3Blue1Brown builds explanations: hook in the first seconds, one concrete question, intuition before formalism, one idea per scene, continuity, consistent concept colours, pauses. Use when planning or rewriting the scene list and narration of a waitwhat video, or when judging whether a script is good enough to animate.
---

# Storytelling for explainers

A waitwhat video is a guided rediscovery: the viewer should feel they could almost have found the
idea themselves. Everything below serves that.

## The non-negotiables

1. **Hook in the first 5 seconds.** Open on the most surprising true thing, a puzzle, or a
   picture that begs a question. Never open with a definition, an agenda or "In this video".
   - Weak: "The Pythagorean theorem states that a² + b² = c²."
   - Strong: "Draw any right triangle you like. Build a square on each side. The two small
     squares *always* hold exactly as much as the big one. Why on earth would that be?"
2. **One concrete question** carries the whole video, stated early in the viewer's words. Every
   scene either sharpens it, gathers what is needed to answer it, or answers it.
3. **Intuition before formalism.** Show the picture, let the viewer notice the pattern, *then*
   name it. Notation arrives as a summary of something already understood. Concrete numbers
   before variables; a specific example before the general case.
4. **One idea per scene.** If a scene needs "and also", split it. Each scene answers one small
   question (write it in `plan.scenes[].goal`).
5. **Continuity: transform, don't cut.** Objects persist and morph between scenes; the last
   frame of one scene is the first frame of the next (`"transition": "continuous"`). Cut only
   for a true change of subject.
6. **A colour means one thing for the whole video.** Assign concept colours once in
   `plan.palette` and never reuse a colour for something else. Yellow is reserved for "look here".
7. **Pauses come from punctuation, plus one real beat where it counts.** Flowing sentences
   already breathe at commas and full stops, so don't sprinkle `<break>` tags between beats. Save
   a deliberate pause (at most about one per minute, ≤ `<break time="1.2s"/>`) for a real reveal
   or the key question; for longer silence, hold a strong picture on screen instead.
8. **Cover everything the request needs, and nothing it doesn't.** The coverage plan
   (`plan.outline` in request.json, see the waitwhat skill) is the checklist: every item gets
   at least one scene, in order, and nothing outside it gets screen time. Length follows from
   that (about 190 spoken words per minute; scenes are typically 10–25 s), so a narrow question
   is a short video and a broad one is a long one. Tight beats padded at every length: cut
   tangents and repetition, never a needed step.

## Shape of a good video

Hook (puzzle or surprising claim) → the question in plain words → build the minimum intuition
with one rich example → the aha (a single visual moment where it clicks) → name it, generalise,
maybe one formula → why it matters / a surprising application → a closing line that echoes the
hook. Not every topic fits; pick an arc from `references/arcs.md` that suits it.

**Long videos are chapters, not lists.** When the outline has many items, group them into a few
chapters, each a small arc of its own (a sub-question, the build-up, its own little aha), all
serving the one big question. Open each chapter by saying why we need this piece now ("To see
why order matters, we first need..."), close it by handing the result to the next one, and
briefly recap the thread before the final payoff. A viewer twenty minutes in should still know
where they are and why.

## Writing narration that sounds human

Write how a curious person talks, not how a lecture reads: mostly flowing, conversational
sentences joined with "and", "so", "but", "now", with a short punchy line only for emphasis or a
reveal (about one in five). Concrete nouns, "you" and "we", contractions. Use the narrator moves:
name the viewer's likely question or objection and answer it, an occasional honest first-person
aside, flag when something will feel strange or hard, and signpost where we are ("Now...", "So if
we step back..."). Keep questions rare (hook and turning points, not every scene). Point at the
screen ("this blue square", "watch the gap") because the picture is doing half the work. Never
read on-screen text aloud word for word, and never put full narration sentences on screen. More,
with examples, in `references/narration.md`.

## Depth adapts to the audience

Same structure, different floor. For "like I'm 10": no unexplained terms, analogies from daily
life, numbers small enough to picture. For experts: still intuition first, but you may move
faster, use notation, and add the subtle case at the end. Never condescend; assume curiosity.

## Before you hand the plan to animation, check

- Is every outline item covered by a scene (`covers`), in order, and nothing the person asked
  for missing? Is there anything on screen the request didn't need?
- Could a viewer state the question after scene 2? Would they care about the answer?
- Is there one moment that is clearly *the* aha, and does it get time and silence?
- Is every term defined before use, with a picture? Any "obviously" or "simply"? Delete them.
- Is each scene's visual something only animation can show (motion, transformation,
  accumulation, comparison), rather than slides with words?
- Does the ending pay off the hook?

Deeper material, loaded on demand:
- `references/principles.md`: Grant Sanderson's design principles, the pedagogy checklist,
  and what research says about engaging educational video.
- `references/arcs.md`: story arcs with worked outlines (math, history, science, tech, company).
- `references/narration.md`: narration craft, examples of weak vs strong lines, pacing math.
