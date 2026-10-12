# Narration craft

## Sound like a person talking to one friend
- Short sentences. One clause where possible. Vary rhythm: a long sentence, then a short one.
- "You" and "we". Contractions. Questions the viewer is already asking.
- Concrete before abstract: "a 3 by 4 triangle" before "legs a and b".
- Point at the picture: "this blue square", "watch the gap", "notice the four corners".
- Name things once, then keep the name. Don't call it "the hypotenuse", then "the long side",
  then "c" unless you are deliberately teaching that they are the same.
- Numbers: say them the way people say them ("two and a half thousand years", not "2,500 yrs").
  Write out symbols you want spoken: "a squared plus b squared", not "a^2 + b^2".

## Weak → strong

| Weak | Strong |
| --- | --- |
| "In this video we will explore the concept of entropy." | "Shuffle a deck of cards. Why does it never shuffle itself back into order?" |
| "It is obvious that the areas are equal." | "Look: the same four triangles, the same big square. What's left over has to match." |
| "The algorithm utilizes a heuristic function to estimate costs." | "It makes a guess. A cheap, optimistic guess about how far is left." |
| "Company X is a leading provider of innovative payroll solutions." | "Paying twelve people in four countries used to take Maria two days a month." |

## Pauses and pacing
- ~150 words per minute is a comfortable explainer pace (ElevenLabs at speed 1.0 is close).
  A 20 s scene holds about 45–50 words.
- `<break time="0.6s"/>` between beats, `1.0–1.5s` after a question or before a reveal.
  Don't exceed ~2 s; hold longer silence with the picture instead (`self.wait`).
- Put a `<bookmark mark="…"/>` right before the word a visual must land on. Keep 1–4 per scene;
  too many makes animation choppy.

## Bookmarks example
```
Take any right triangle. <bookmark mark="squares"/>Build a square on each of its sides.
<break time="0.8s"/> Now here's the strange part: <bookmark mark="compare"/>the two smaller
squares, together, hold exactly as much area as the big one. <break time="1.2s"/> Always.
```

## Endings
End on the idea, not on a summary list. Echo the hook's image, add one line of perspective
("Two and a half thousand years later, it still comes down to four triangles."), stop.
