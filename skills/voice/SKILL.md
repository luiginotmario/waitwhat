---
name: voice
description: Narration for waitwhat videos - choosing an ElevenLabs voice (via OpenRouter) for the topic and tone, directing an expressive delivery (emphasis, energy arc, pace, pauses), bookmarks and pronunciation, then generating per-scene audio with word-level timings (scripts/tts.py; direct ElevenLabs or macOS say as fallbacks). Use after the script is written and before any scene is animated, and whenever narration changes.
---

# Voice

Narration is recorded per scene **before** animation, because the audio's length and word
timings drive every scene's timing. The tool is `ww tts`; it reads `workspace/plan.json`, writes
`workspace/audio/<id>.wav` + `<id>.json` (duration, word times, bookmark times), and skips
scenes whose narration and voice settings are unchanged. Scenes are voiced in parallel (about 5
at a time, retrying OpenRouter rate limits). `ww tts --background` returns at once and voices
in a detached process, so scene code can be written meanwhile (`ww render` waits for a scene's
audio); `ww tts --wait` waits for it and prints the result.

## Providers

`tts.py` uses the first one available, in this order (override with `--backend`, or
`WAITWHAT_TTS_PROVIDER=openrouter|elevenlabs|say`, or a comma list such as `elevenlabs,say`):

1. **OpenRouter** (`OPENROUTER_API_KEY`): ElevenLabs models through OpenRouter, so the whole
   product runs on one key and one bill. It is the same ElevenLabs engine with the same controls
   (voice settings, previous/next-text stitching, seed, mp3 at 44.1 kHz), and with the same seed
   it produces the same audio as the direct API. The speech endpoint returns audio only, so
   `tts.py` transcribes each take with ElevenLabs Scribe and aligns the transcript to the script
   for word timings (within ~50 ms of ElevenLabs' native timestamps).
2. **ElevenLabs direct** (`ELEVENLABS_API_KEY`): native character timestamps. Use it for cloned
   or designed voices (OpenRouter serves those only with BYOK).
3. **macOS `say`**: free, offline, fine for drafts. Word timing inside a sentence is estimated.

Cost: about $0.04 per 1,000 characters of speech, plus about $0.11 per hour of audio for the
transcription (~4% on top). A 2-minute video (~2,300 characters) costs about $0.10. The real
cost of every call is written to `.waitwhat/usage.json`. Iterate with `--backend say`; run the
real voice once the script is final. Never re-synthesise unchanged scenes; use `--force` only
when needed. `ww tts --voices` lists models, prices and voices without spending anything.

## Model

Default: **`elevenlabs/eleven-multilingual-v2`** at `speed` 1.12, the long-form narration model.
It honours `<break>`, `style` and `speed`, and the default voice lands at ~190–205 wpm. Use it.

`elevenlabs/eleven-v4` is more emotive and takes inline audio tags, but it has no speed control
and reads at ~150–165 wpm with every voice we measured, well below the pace target. Pick it only
for a deliberately slow, intimate piece, and direct it with tags (below), since it ignores
`style` and `speed`.

## Choosing a voice

Match the topic and the person asking, not a default. Settle it in one pass and write it into
`plan.voice.voice_id` as one of OpenRouter's premade names (an ElevenLabs voice id also works):

**Default to American voices.** A clear US accent is the easiest for the widest audience to follow.
Use a British or other accent only when the person asks for it or the subject clearly calls for it
(e.g. a video in British English about British history).

| Content | Voice qualities | Voices (American first) |
| --- | --- | --- |
| Math, physics, "why is this true" | warm, curious, unhurried | `brian` (deep, resonant US, **default**), `eric` (smooth US), `matilda` (clear, knowledgeable US) |
| Science, history, explainers for everyone | clear, friendly | `matilda`, `eric`, `sarah` (warm, reassuring US), `bella` (bright US) |
| Tech, product, company explainers | confident, modern, conversational | `eric`, `chris` (down-to-earth US, speed 1.05), `roger` (laid-back US, speed 1.05), `sarah` |
| "Like I'm 10", playful topics | bright, warm | `jessica`, `will`, `laura` (all US) |
| Serious subjects (health, conflict, loss) | calm, low-key, no hype | `sarah`, `river` (neutral, relaxed), `brian` |
| Only when asked for a British/other accent | | `george`, `alice`, `daniel`, `lily` (British), `charlie` (Australian) |

Measured on multilingual-v2 at speed 1.12 with the same flowing script: brian ~203 wpm, eric ~209,
matilda ~206, sarah ~200, chris ~224 and roger ~216 (use speed 1.05 for those two).

Skip the character voices (`callum`, `harry`) for narration. Respect explicit requests (gender,
accent, language, a named voice). For non-English videos, set `plan.voice.language` (ISO-639-1)
and write the narration in that language.

`plan.voice` defaults: `voice_id` `brian`, `model_id` as above, `stability` 0.45,
`similarity_boost` 0.8, `style` 0.15, `speed` 1.12, `max_pause` 0.7. Add `seed` (an integer)
for repeatable takes.

## Delivery direction

The target is a curious friend thinking out loud: wonder, not hype. A flat, even read is the
usual failure, so direct it.

- **One stressed word per sentence.** Put it where speech stresses naturally: last in a short
  clause, or set off by a comma or a full stop ("they hold as much area. Exactly as much.").
  Don't use capitals or asterisks; they leak into the on-screen text and the manifest.
- **Energy follows the arc.** The hook is curious and bright. The scene before the insight is
  slower and softer. The reveal lifts. The close is calm. Set this per scene with
  `scenes[].voice` overrides:

  | Beat | `scenes[].voice` |
  | --- | --- |
  | hook | `{"stability": 0.4, "style": 0.25}` |
  | just before the insight | `{"stability": 0.55, "speed": 1.04}` |
  | reveal | `{"stability": 0.35, "style": 0.3}` |
  | close | `{"stability": 0.55, "style": 0.1, "speed": 1.06}` |

  Inside a scene, slow down only the one key sentence: keep it short and give it its own full
  stop. Let the connective sentences around it run on with commas.
- **Think aloud, sparingly**: one or two lines per video ("Wait, why would that be true?", "Hm.
  That can't be a coincidence."), never more than one per scene.
- **Audio tags (v4 only).** Put a tag in a bookmark, so it reaches the audio but never the
  screen: `<bookmark tag="curious"/>`, `<bookmark mark="reveal" tag="excited"/>`. Use at most 1–2
  per scene, never on every line. `curious`, `thoughtful`, `excited` and `whispers` are acted,
  not read out. Other models ignore tags.

Hook, multilingual-v2, with `"voice": {"stability": 0.4, "style": 0.25}`:

```
Draw any right triangle, and build a square on each side. Here is the strange part:
the two small squares, together, hold exactly as much area as the big one. Every single time.
Wait, why would that be true?
```

The reveal, with the scene's one long pause:

```
Take four copies of the triangle, <break time="0.9s"/> <bookmark mark="reveal"/>and the answer falls right out.
```

## Pace and pauses

- **Target 185–205 wpm**, about **3.2 words per second**: a 15 s scene holds ~48 words, a
  2-minute video ~380. Move quickly through connective sentences; slow down only for the key one.
- **Let punctuation make the pauses.** Don't put a `<break>` between ordinary beats. `tts.py`
  also compresses the long pauses the model leaves at sentence ends: anything over 0.3 s is
  shortened and capped at `max_pause` (0.7 s).
- **At most one pause over 0.8 s per minute**, written as `<break time="0.8s"/>` to `"1.2s"` and
  used only before a real reveal. Explicit breaks are kept exactly. Never stack breaks. Long
  silences belong to the picture (`self.wait`), not the voice track.
- `<bookmark mark="name"/>` goes just before the word a visual must land on, 1–4 per scene. A
  bookmark directly before a `<break>` lands at the *start* of the pause (good for "watch this:").

## Pronunciation

Use `plan.pronunciations` (`{"written": "spoken"}`). It applies only to the audio, so on-screen
text and the manifest keep the real spelling. Examples: `"Euler": "Oiler"`, `"SQL": "sequel"`,
`"km/h": "kilometres per hour"`, `"10^9": "ten to the nine"`, `"API": "A P I"`. Spell out
symbols and numbers the way a person says them.

## Check the result

After `ww tts` (or `ww tts --wait` for a background run), read the printed lines. A scene far longer than planned means the narration is
too long for its idea: trim words, not pauses. An `align=stt:…%` below ~90% means the voice said
something other than the script (an odd number, a misread name); fix it with a pronunciation.
Below 60%, `tts.py` falls back to proportional timing. Listen to one scene if you can (`afplay
workspace/audio/<id>.wav`) before rendering everything.
