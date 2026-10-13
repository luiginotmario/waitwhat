# Third-party sources and credits

waitwhat stands on other people's work. Everything we copied or adapted is listed here with its
licence; sources we only learned from are listed too. We copy or adapt only from permissively
licensed projects (MIT, Apache-2.0, BSD, CC0); "adapted" below means the rules were paraphrased
in our own words unless noted. Projects without a licence, or with copyleft or
non-commercial licences, were read for ideas only: no code or text from them is in this repo.

## Adapted (code or text)

| Source | Licence | What we took | Where it lives here |
| --- | --- | --- | --- |
| [AmitSubhash/3brown1blue](https://github.com/AmitSubhash/3brown1blue) | MIT, © 2026 Amit T Subhash | Distillation of Grant Sanderson's explanation-design principles and pedagogy checklist; visual design rules (opacity layering, semantic colour, safe area and edge buffers, annotations on objects); Manim gotchas | `skills/storytelling/references/principles.md`, `skills/manim-scenes/references/style-guide.md`, `skills/manim-scenes/references/gotchas.md` |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) `skills/creative/manim-video` | MIT, © 2025 Nous Research | Timing/"breathing room" guidance, troubleshooting list (re-verified against Manim 0.22; several items corrected) | `skills/manim-scenes/references/style-guide.md`, `skills/manim-scenes/references/gotchas.md` |
| [iart-ai/manim-skills](https://github.com/iart-ai/manim-skills) | MIT, © 2026 iart.ai | Verify-by-frames loop and the contact-sheet idea (`contact-sheet.sh`) | `scripts/render.py` (`extract_frames`), `skills/manim-scenes/references/render-loop.md` |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) `skills/creative/manim-video` (`animation-design-thinking.md`, `production-quality.md`) | MIT, © 2025 Nous Research | Paraphrased pacing rules: mark a visual beat on the key word of each sentence, "see, then hear" (the visual lands on or just before its word), a tempo curve across the video, a held beat before the aha, varied entrances between scenes | `skills/manim-scenes/references/style-guide.md` ("Alive, not busy"), `skills/storytelling/SKILL.md` ("Energy and pacing") |
| [subinium/3b1b-style-animation-skill](https://github.com/subinium/3b1b-style-animation-skill) `rules/audio-sync.md` | MIT, © subinium | The no-still-frame rule (nothing stays completely still for more than ~3 s under narration), paraphrased | `skills/manim-scenes/references/style-guide.md`, `skills/waitwhat/references/scene-builder.md` |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) (`motion-doctrine`, `hyperframes-audio`, `narration.md`, `beat-direction.md`) | Apache-2.0, © HeyGen | Paraphrased: motion must mean something (no idle wobble), a short "dramatic comma" before a climax, keep effects on their own bus so they never pump the music's ducking | `skills/manim-scenes/references/style-guide.md`, `skills/storytelling/SKILL.md`, `scripts/stitch.py` (effects bus) |
| [HirogaKatageri/hirokata](https://github.com/HirogaKatageri/hirokata) `plugins/storytelling` (`abt`, `pixar-pitch`) | MIT, © HirogaKatageri | "And, but, therefore": find the *but*; a chain of "and"s is information, not a story (the ABT framework is Randy Olson's; the story spine is Kenn Adams') | `skills/storytelling/SKILL.md`, `skills/storytelling/references/arcs.md` |
| [ghaida/intent](https://github.com/ghaida/intent) `skills/storytelling` | CC0-1.0 | Don't manufacture conflict in a company story: tension must come from the record; use a turn (introduce, develop, twist, reconcile) when there is no conflict | `skills/storytelling/SKILL.md`, `skills/storytelling/references/arcs.md` |
| [elevenlabs/skills](https://github.com/elevenlabs/skills) (`sound-effects`, `text-to-speech`) | MIT, © ElevenLabs | Sound-effect prompting (specific source, style and mood; high prompt influence for short UI sounds) used to write the library prompts; v4 tag phrasing as short voice directions | `scripts/sfx_library.py`, `skills/voice/SKILL.md` |
| [ManimCommunity/manim-voiceover](https://github.com/ManimCommunity/manim-voiceover) | MIT, © 2022 the Manim Community Developers | `<bookmark mark="…"/>` narration markup and the approach of timing animations to bookmark times measured against the renderer clock | `skills/manim-scenes/lib/waitwhat_style.py` (`WaitwhatScene` timing), `scripts/tts.py` (markup parsing) |

## Used as dependencies (not copied)

| Project | Licence | Use |
| --- | --- | --- |
| [ElevenLabs Sound Effects API](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert) | web service, output licensed for commercial use on paid plans | Generated the sound-effect library in `assets/sfx/` **once** (see "Music and sound" below); not called per video |
| [ElevenLabs](https://elevenlabs.io) models via [OpenRouter](https://openrouter.ai) | web service | Narration: `scripts/tts.py` calls OpenRouter's `POST /api/v1/audio/speech` (ElevenLabs text-to-speech models) and `POST /api/v1/audio/transcriptions` (ElevenLabs Scribe, word timestamps for forced alignment), and reads per-call cost from `GET /api/v1/generation`. The direct ElevenLabs REST API (`/v1/text-to-speech/{voice_id}/with-timestamps`) is an optional fallback. No ElevenLabs code is included. |
| [Manim Community Edition](https://github.com/ManimCommunity/manim) | MIT | Animation engine (installed by `scripts/setup.sh`) |
| [TinyTeX](https://github.com/rstudio/tinytex-releases) / TeX Live | GPL-2 (installer) and the various TeX Live package licences | LaTeX for `MathTex`, downloaded into the user's home by `setup.sh`; not redistributed |
| [cm-unicode](https://ctan.org/pkg/cm-unicode) (CMU Serif) | SIL Open Font License | Text face, installed through TinyTeX and registered at render time; not redistributed |
| FFmpeg | LGPL/GPL | Encoding, mixing (`sidechaincompress`, `loudnorm`), frame extraction; external tool |
| [Jina Reader](https://jina.ai/reader) | web service | `https://r.jina.ai/<url>` for reading pages and documents (`scripts/fetch.py`) |

## Ideas only (no code or text copied)

| Source | Licence | What we learned |
| --- | --- | --- |
| [3b1b/videos](https://github.com/3b1b/videos) | CC BY-NC-SA 4.0 | The house look: pure black background, CMU Serif text, a small palette used semantically (we counted colour, font-size and `run_time` usage across the 2025–2026 scenes), objects built once and transformed many times |
| Grant Sanderson's talks and writing: "Designing Math" (Config 2026), JMM 2023 JPBM lecture, [Summer of Math Exposition rules](https://some.3b1b.co/rules) | n/a | Principles summarised in `skills/storytelling` (via the MIT adaptation above, plus our own reading) |
| [showlab/Code2Video](https://github.com/showlab/Code2Video) | MIT | Visual-anchor layout and a layout-feedback loop; inspired our automatic layout lint (`WaitwhatScene._check_layout`), which is our own code |
| [rohitg00/manim-video-generator](https://github.com/rohitg00/manim-video-generator) | MIT | Hook → setup → rising action → aha → resolution framing, informing `skills/storytelling/references/arcs.md` |
| [paulnegz/manim-mcp](https://github.com/paulnegz/manim-mcp) | MIT | Separate concept-analysis and scene-planning stages; audio pacing. (We deliberately invert its order: narration first, animation timed to it.) |
| [adithya-s-k/manim_skill](https://github.com/adithya-s-k/manim_skill) `manim-composer` | MIT | "History as narrative" (the problem as it was first met, then the discovery), and asking up front how much background to assume; informed the founding-story arc and audience levels |
| [Yusuke710/manim-skill](https://github.com/Yusuke710/manim-skill) | MIT | Treating each narration line's measured duration as a hard time budget (we already time scenes to the audio) |
| [yonatangross/orchestkit](https://github.com/yonatangross/orchestkit) (music-sfx-selection, audio-mixing-patterns; at commit 20d1f4f) | MIT | Starting points for effect levels under narration and the anticipation/hit/settle timing of effects; our numbers were set by measurement |
| [kapishdima/soundcn](https://github.com/kapishdima/soundcn) | MIT (code), sounds mostly CC0 | The palette of short UI sounds an explainer needs (pop, click, coin, keys); we generated our own instead of shipping any of its files |
| [remotion-dev/skills](https://github.com/remotion-dev/skills) | no licence | Sizing each scene to its measured voiceover; effects as normalised short WAVs. Ideas only |
| [arrrnmp/motion-design](https://github.com/arrrnmp/motion-design) `references/direction.md` | AGPL-3.0 | Pick the visual medium a topic is "made of" (blueprint, chalkboard, notebook) and match the sound to the medium (chalk on a chalkboard). Ideas only: no text or code copied |
| [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) (contrast minimum 1.4.3, non-text contrast 1.4.11, low or no background audio 1.4.7) | W3C document licence | Contrast thresholds checked for every theme palette (`waitwhat_themes.py`); background audio well under speech |
| [nabin2004/AOS](https://github.com/nabin2004/AOS) | no licence file | Constrained yes/no visual-critic questions; informed the checklist in `render-loop.md` |
| [Leoyishou/personal-ai-company](https://github.com/Leoyishou/personal-ai-company) `3b1b-video` skill | no licence | Narrative modes (mystery → resolution, build-up → payoff, two views → unity, specific → general); informed `arcs.md` |
| Research on learning from video: Guo, Kim & Rubin (2014) *How video production affects student engagement*; Mayer's multimedia learning principles; Loewenstein (1994) information-gap theory of curiosity | n/a | Summarised in `skills/storytelling/references/principles.md` |

## Music and sound

- **Music**: generated procedurally by `scripts/music.py` (additive synthesis, filtered noise, a
  synthetic reverb), written for this project and MIT-licensed like the rest of the repo.
  `assets/music/*.m4a` are 60-second renders of its four moods. No third-party recordings.
- **Sound effects** (`assets/sfx/*.wav`, 56 takes of 20 sounds, listed in
  `assets/sfx/library.json` with the prompt that made each one): generated once, on
  2026-10-12, with the ElevenLabs Sound Effects API (`eleven_text_to_sound_v2`) by
  `scripts/sfx_library.py`, on the project owner's paid ElevenLabs plan (Starter tier), then
  trimmed and loudness-matched by the same script. ElevenLabs' terms give paid users a
  commercial licence to content generated during a paid subscription, usable indefinitely
  ("All paid plans include a commercial license, provided you're not using Beta Services";
  [help centre](https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform),
  [terms](https://elevenlabs.io/terms), checked 2026-10-12), subject to their Prohibited Use
  Policy. We redistribute these files as part of this repository on that basis; if you reuse
  them outside waitwhat, check those terms yourself. No sample libraries were used.
- The older procedural whoosh and scribble (`music.py sfx`) remain as a fallback when the
  library is missing.

## MIT licence text (applies to each MIT source above, with its own copyright line)

```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
