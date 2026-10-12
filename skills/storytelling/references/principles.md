# Principles: what makes an explainer work

Parts of this file are adapted from the `explanation-design.md` and `pedagogy-checklist.md`
rules in AmitSubhash/3brown1blue (MIT, © 2026 Amit T Subhash), which distil Grant Sanderson's
talks. See THIRD_PARTY.md.

## Grant Sanderson's three design moves

From his talk "Designing Math": explaining one idea is a design problem with an abundance of
choice, and three decisions come first.

1. **Ask "what does it look like?"** For every abstract object, look for the picture. π is the
   distance halfway round a unit circle; *i* is a quarter turn. Give each symbol a picture
   before combining them. It is the difference between reading sheet music and hearing the song.
2. **Give your characters motivation.** "Before you try to prove something, it is a good idea
   to believe it is true." For each part of a formula or system, name its reason to exist and
   show it on screen (box it in its colour and label what it *does*). Motivation is the
   difference between a proof and an explanation.
3. **The most memorable application is the most surprising one.** Motivate with an application
   matched to the audience, then push past the obvious one.

One object, several representations, one question each: the same idea can be shown as *what*
(what does it look like), *why* (why must it be true) and *how it is used*. Pairing a "what"
view with a "why" view produces mystery and then resolution.

## The pedagogical checklist (rigor is not the same as done)

From his JMM 2023 lecture: rigor has a satisfying "done" test, clarity does not, so keep a second
checklist and take it as seriously.

1. Does every definition have a motivating example, given *before* it?
2. Does the derivation feel rediscoverable: could the viewer anticipate the next step?
3. Does it feel personal: a real voice with some warmth, not a neutral recitation?
4. Are the core ideas given diagrams?
5. Are abstractions preceded by concrete examples (one layer of abstraction below the target)?
6. Does it start with a problem before the instruction? (Problem-first learners understand and
   transfer better; in video, ask and genuinely pause.)
7. Is there a reason to care, early?

Useful techniques: *discovery fiction* (a plausible path of flawed attempts and fixes that leads
to the construct, flagged honestly as a story); *honest hand-waving* (say when you simplify, and
scope claims; never "obviously"); *inside-out unpacking* of the one formula that deserves it.

His contest rubric is a good final lens: **Motivation** (clear by the end of the intro why it
matters), **Clarity** (jargon explained, goals clear, care for newcomers), **Novelty** (feels
fresh), **Memorability** (something sticks months later: a picture, an aha, enthusiasm).

## How 3Blue1Brown scenes look and move (from the 3b1b/videos code, ideas only)

The channel's config renders on pure black (#000000) with CMU Serif text. Scene code leans on
a small palette used semantically (yellow, blue, red, teal, green, pink, greys), large text, and
unhurried animations: most `run_time`s are 2–3 s, with 4–10 s for the big transformations.
Objects are built once and transformed many times; very little appears without motion that
explains where it came from.

## What research says about engaging educational video

- **Short and segmented wins.** In a large edX study (Guo, Kim & Rubin, 2014) median engagement
  fell sharply after about 6 minutes, and enthusiastic, faster-paced speakers held attention
  better. Our 1–5 minute default fits this.
- **Mayer's multimedia principles** (decades of experiments):
  - *Coherence*: cut interesting-but-irrelevant extras. Decoration costs attention.
  - *Signalling*: highlight what matters (colour, a circle, dimming the rest).
  - *Redundancy*: narration + picture beats narration + picture + the same words on screen.
  - *Spatial and temporal contiguity*: labels sit on their objects, and the visual happens
    *while* the words describe it (bookmarks make this exact).
  - *Segmenting*: learner-paced chunks beat one long stream (scenes, pauses).
  - *Pre-training*: name the key parts before the process that uses them.
  - *Personalisation and voice*: conversational "you/we" style and a natural human-sounding
    voice improve learning.
- **Curiosity is a gap.** Interest peaks when people know enough to see what they don't know
  (Loewenstein's information-gap theory). Open the gap early; close it at the aha.
- **Generation effect.** Asking the viewer to predict, even briefly, makes the answer stick.
