# Third-party sources and credits

waitwhat stands on other people's work. Everything we copied or adapted is listed here with its
licence; sources we only learned from are listed too. We copy or adapt only from permissively
licensed projects (MIT, Apache-2.0, BSD). Projects without a licence, or with copyleft or
non-commercial licences, were read for ideas only: no code or text from them is in this repo.

## Adapted (code or text)

| Source | Licence | What we took | Where it lives here |
| --- | --- | --- | --- |
| [AmitSubhash/3brown1blue](https://github.com/AmitSubhash/3brown1blue) | MIT, © 2026 Amit T Subhash | Distillation of Grant Sanderson's explanation-design principles and pedagogy checklist; visual design rules (opacity layering, semantic colour, safe area and edge buffers, annotations on objects); Manim gotchas | `skills/storytelling/references/principles.md`, `skills/manim-scenes/references/style-guide.md`, `skills/manim-scenes/references/gotchas.md` |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) `skills/creative/manim-video` | MIT, © 2025 Nous Research | Timing/"breathing room" guidance, troubleshooting list (re-verified against Manim 0.22; several items corrected) | `skills/manim-scenes/references/style-guide.md`, `skills/manim-scenes/references/gotchas.md` |
| [iart-ai/manim-skills](https://github.com/iart-ai/manim-skills) | MIT, © 2026 iart.ai | Verify-by-frames loop and the contact-sheet idea (`contact-sheet.sh`) | `scripts/render.py` (`extract_frames`), `skills/manim-scenes/references/render-loop.md` |
| [ManimCommunity/manim-voiceover](https://github.com/ManimCommunity/manim-voiceover) | MIT, © 2022 the Manim Community Developers | `<bookmark mark="…"/>` narration markup and the approach of timing animations to bookmark times measured against the renderer clock | `skills/manim-scenes/lib/waitwhat_style.py` (`WaitwhatScene` timing), `scripts/tts.py` (markup parsing) |

## Used as dependencies (not copied)

| Project | Licence | Use |
| --- | --- | --- |
| [elevenlabs/elevenlabs-mcp](https://github.com/elevenlabs/elevenlabs-mcp) | MIT, © 2025 Eleven Labs Inc. | MCP server run via `uvx` (`.mcp.json`) for voice search and auditions. `scripts/tts.py` calls the public ElevenLabs REST API (`/v1/text-to-speech/{voice_id}/with-timestamps`) directly because the MCP returns no word timings. |
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
| [nabin2004/AOS](https://github.com/nabin2004/AOS) | no licence file | Constrained yes/no visual-critic questions; informed the checklist in `render-loop.md` |
| [Leoyishou/personal-ai-company](https://github.com/Leoyishou/personal-ai-company) `3b1b-video` skill | no licence | Narrative modes (mystery → resolution, build-up → payoff, two views → unity, specific → general); informed `arcs.md` |
| Research on learning from video: Guo, Kim & Rubin (2014) *How video production affects student engagement*; Mayer's multimedia learning principles; Loewenstein (1994) information-gap theory of curiosity | n/a | Summarised in `skills/storytelling/references/principles.md` |

## Music and sound

All music and sound effects are generated procedurally by `scripts/music.py` (additive synthesis,
filtered noise, a synthetic reverb), written for this project and MIT-licensed like the rest of
the repo. `assets/music/*.m4a` are 60-second renders of its four moods. No third-party
recordings or samples are included. We did not ship CC0 loops because we could not verify their
licences to our satisfaction; procedural generation avoids the question entirely.

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
