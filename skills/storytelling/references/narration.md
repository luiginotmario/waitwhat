# Narration craft

## Sound like a curious person talking, not a lecture
- Write how a curious person actually *talks* to a friend: mostly flowing sentences (often 20 to
  30 words) that carry one thought through to its end, joined with "and", "so", "but", "now",
  "which means". Clipped one-clause sentences in a row sound like a slide deck read aloud.
- Keep a short, punchy line for emphasis or a reveal, roughly one sentence in five: "Always."
  "That's the whole trick." It only lands because the sentences around it breathe.
- "You" and "we". Contractions. Talk *with* the viewer about what you're both looking at.
- Concrete before abstract: "a 3 by 4 triangle" before "legs a and b".
- Point at the picture: "this blue square", "watch the gap", "notice the four corners".
- Name things once, then keep the name. Don't call it "the hypotenuse", then "the long side",
  then "c" unless you are deliberately teaching that they are the same.
- Numbers: say them the way people say them ("two and a half thousand years", not "2,500 yrs").
  Write out symbols you want spoken: "a squared plus b squared", not "a^2 + b^2".

## Narrator moves
These are what make an explanation feel like a person thinking alongside you. Use them on
purpose, not as tics.

- **Name the viewer's question or objection, then answer it.** You're anticipating the exact
  moment they'd raise a hand.
  - "At this point you might reasonably ask why we'd ever square the sides instead of just
    adding them, and the answer is that areas, unlike lengths, can be cut up and rearranged."
  - "If you're thinking this only works because I picked friendly numbers, that's fair, so let's
    break it with an ugly triangle and watch it survive anyway."
- **Honest first-person asides, sparingly** (a few per video, not per scene). They build trust
  and tell the viewer where effort is needed.
  - "I'll be honest, the next step is the one I found hardest to see the first time, so let's go
    slowly."
  - "There's a cleaner algebraic proof, but I've never found it tells you *why*, which is what
    we're after here."
- **Flag difficulty and feelings.** Saying that something feels strange makes the viewer feel
  normal for feeling it, and keeps them watching.
  - "This might feel like cheating, since we never measured a single angle, but stick with it."
  - "If this is the point where your eyes start to glaze, that's completely normal, so here's
    the one picture to hold on to."
- **Signpost transitions.** Tell the viewer where you are in the argument, especially in long
  videos: "Now...", "So if we step back for a second...", "As I said earlier...", "Here's where
  it gets interesting...", "Okay, so far we have two pieces; the third is where they meet."
- **Questions in moderation.** Only about one sentence in sixteen should be a question. Use
  them at the hook and at real turning points ("So why should the leftover space be a square?"),
  not as a reflex at the start of every scene. A string of rhetorical questions sounds like a
  sales pitch.
- **Hook with concrete stakes, never a definition.** Open on a real number, a surprising claim,
  or a tension the viewer can feel.
  - Weak: "A hash function is a function that maps data to a fixed-size value."
  - Strong: "Your password probably isn't stored anywhere on the sites you use, and yet they can
    tell, instantly, whether you typed it right, which sounds impossible until you see the trick."

## Weak → strong

| Weak | Strong |
| --- | --- |
| "In this video we will explore the concept of entropy." | "Shuffle a deck of cards and it never, in your whole life, shuffles itself back into order, even though nothing in the physics forbids it, so what exactly is stopping it?" |
| "It is obvious that the areas are equal." | "Look at what we've got: the same four triangles sitting in the same big square, so whatever space they leave over has to be the same too." |
| "The algorithm utilizes a heuristic function to estimate costs." | "Instead of exploring everything, it makes a guess about how far is left, and the clever part is that the guess only has to be optimistic, never accurate." |
| "Company X is a leading provider of innovative payroll solutions." | "Paying twelve people in four countries used to take Maria two full days every month, and most of that time went into one spreadsheet nobody trusted." |
| "Attention. Queries. Keys. Values. Let's define each." | "Each word gets to ask a question of every other word, and how well their answers match decides how much each one gets listened to." |

## Terms: name it, then say what it is
Introduce a technical term and explain it in the same sentence, the first time it's spoken:
"the card network, the system Visa and Mastercard run that connects every bank to every other",
"an idempotency key, a label that makes sure a retried request is only charged once". Put the
term on screen as a label on its picture; let the voice carry the meaning. For an expert
audience the explanation can be a short clause; for a newcomer it can be a picture and a
sentence. Never stack two new terms in one sentence.

## Pace and pauses
- Narrate at about **190 words per minute**, a lively conversational pace (the voice skill's
  default speed of 1.12 lands here; 1.0 is noticeably slower). A 20 s scene holds about 60 to 65 words.
- Pauses come from punctuation: commas, full stops and paragraph breaks already give the voice
  natural breath. Don't put `<break>` tags between ordinary beats.
- Use at most about one deliberate long pause per minute, at a real reveal or right after the
  key question, and keep it at or under `<break time="1.2s"/>`. If a moment needs more silence
  than that, hold the picture instead (`self.wait`) rather than stretching the audio.
- Put a `<bookmark mark="…"/>` right before the word a visual must land on. Keep 1–4 per scene;
  too many makes animation choppy.

## Bookmarks example
```
Take any right triangle you like and <bookmark mark="squares"/>build a square on each of its
sides, and now here's the strange part: <bookmark mark="compare"/>the two smaller squares,
together, always hold exactly as much area as the big one. <break time="1.0s"/> Always.
```

## Endings
End on the idea, not on a summary list. Echo the hook's image, add one line of perspective
("Two and a half thousand years later, it still comes down to four triangles."), stop.
