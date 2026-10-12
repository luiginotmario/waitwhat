---
name: voice
description: Narration for waitwhat videos - choosing an ElevenLabs voice for the topic and tone, pacing, pauses, bookmarks and pronunciation, then generating per-scene audio with word-level timings (scripts/tts.py; falls back to macOS say without a key). Use after the script is written and before any scene is animated, and whenever narration changes.
---

# Voice

Narration is recorded per scene **before** animation, because the audio's length and word
timings drive every scene's timing. The tool is `ww tts`; it reads `workspace/plan.json`, writes
`workspace/audio/<id>.wav` + `<id>.json` (duration, word times, bookmark times), and skips
scenes whose narration and voice settings are unchanged.

## Backends

- **ElevenLabs** (when `ELEVENLABS_API_KEY` is set): `tts.py` calls the text-to-speech
  *with-timestamps* endpoint directly, because word timings are what sync needs and the MCP's
  `text_to_speech` tool doesn't return them. It passes neighbouring scenes' text as context so the
  intonation flows across scene boundaries.
- **The ElevenLabs MCP** (configured in this plugin's `.mcp.json`) is for *choosing*: use
  `search_voices` / `search_voice_library` / `get_voice` to find a voice, and `text_to_speech`
  only for a short audition when the user wants to hear options. Don't narrate scenes through it.
  `ww tts --voices` lists the account's voices without spending characters.
- **macOS `say`** is the free fallback (no key, offline, decent for drafts). Sentence timing and
  pauses are exact; word timing inside a sentence is estimated. Default voice `Daniel`.

Characters cost money. Budget roughly 1 character per character of narration; a 2-minute video
is ~1,800 characters. Iterate with `--backend say`, and synthesise with ElevenLabs once the script
is final. Never re-synthesise unchanged scenes (`--force` only when needed).

## Choosing a voice

Match the topic and the person asking, not a default. Settle it in one pass and write it into
`plan.voice` (`voice_id` beats `voice_name`; names can be ambiguous).

| Content | Voice qualities | Good premade starting points |
| --- | --- | --- |
| Math, physics, "why is this true" | warm, curious, unhurried; sounds like it is thinking with you | George (warm storyteller, British), Quentin (narrator/educator, US), Alice (clear educator, British) |
| Science, history, explainers for everyone | clear, friendly, mid-pace | Matilda, Daniel (steady broadcaster), Chris (down-to-earth) |
| Tech, product, company explainers | confident, modern, conversational | Eric, Roger, Sarah, River (neutral) |
| "Like I'm 10" / playful topics | bright, warm, a little faster | Jessica, Will, Laura |
| Serious subjects (health, conflict, loss) | calm, low-key, no "hype" | River, Daniel, Alice |

Respect explicit requests (gender, accent, language, a named voice). For non-English videos use
`eleven_multilingual_v2` and set `plan.voice.language`; write the narration in that language.

Settings (in `plan.voice`): `stability` 0.4–0.55 (lower = more expressive), `similarity_boost`
~0.8, `style` 0–0.3 (higher costs latency, can sound theatrical), `speed` 0.95–1.05. Default model
`eleven_multilingual_v2` (supports `<break>` tags). `eleven_v3` is more expressive but ignores
break tags (tts.py turns them into "…").

## Pacing, pauses, bookmarks

- About 150 words per minute. A 15 s scene ≈ 35–40 words.
- `<break time="0.6s"/>` between beats, up to ~1.5 s before a reveal. Long silences belong to the
  picture (`self.wait`), not the audio.
- `<bookmark mark="name"/>` just before the word a visual must land on. 1–4 per scene. A bookmark
  directly before a `<break>` lands at the *start* of the pause (good for "watch this:").
- Ending a scene on a question? Put a short break after it so the next scene doesn't rush in.

## Pronunciation

Use `plan.pronunciations` (`{"written": "spoken"}`), applied only to the audio, so on-screen
text and the manifest keep the real spelling. Examples: `"Euler": "Oiler"`, `"SQL": "sequel"`,
`"GIF": "jif"` (if the user prefers), `"km/h": "kilometres per hour"`, `"10^9": "ten to the nine"`.
Spell out symbols and numbers the way a person says them. Acronyms said as letters: `"API": "A P I"`.

## Check the result

After `ww tts`, read the printed durations: a scene far longer than planned means the narration
is too long for its idea (trim words, not pauses). Listen to one scene if you can (`afplay
workspace/audio/<id>.wav` on macOS) before rendering everything.
