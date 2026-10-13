# waitwhat

Type a question, attach a paper, or paste a company URL, and get back a narrated, animated
explainer video in the classic math-animation style: geometry that moves, colours that mean
something, a voice whose energy follows the story, a quiet music bed and small sounds tied to
what happens on screen, one mp4. Each video picks a world to live in: classic black for math,
or a chalkboard, blueprint, notebook paper, night sky, deep ocean, city or whiteboard when the
topic calls for it. Depth follows the way you ask: use the jargon and it goes deep and fast;
ask plainly and it starts simple and builds up.

Watching and something doesn't click? Pause, circle it, type **"wait, what?"**. waitwhat works
out what you meant and rebuilds that part of the video as a new version.

This repo is a [Claude Code](https://code.claude.com) plugin: a set of skills (story, research,
voice, animation, sound, refine) plus the scripts they drive. The agent decides what to make;
the scripts render it.

## Install

```bash
git clone https://github.com/luiginotmario/waitwhat ~/waitwhat
~/waitwhat/scripts/setup.sh        # idempotent: Python 3.12 venv (uv) + Manim + TinyTeX in your home, no sudo
```

Then either load it for one session, `claude --plugin-dir ~/waitwhat`, or install it:

```
/plugin marketplace add ~/waitwhat
/plugin install waitwhat@waitwhat
```

Needs macOS or Linux, `ffmpeg`, and `uv` (setup installs uv if missing; on macOS it also
`brew install`s cairo and pkg-config). Environment variables:

| Variable | What for |
| --- | --- |
| `OPENROUTER_API_KEY` | the one key you need: natural narration (ElevenLabs voices via OpenRouter) with word timings. Without it, macOS `say` is used |
| `ELEVENLABS_API_KEY` | optional: direct ElevenLabs, used only when `OPENROUTER_API_KEY` is not set (or for cloned voices) |
| `WAITWHAT_TTS_PROVIDER` | optional: force a narrator, `openrouter`, `elevenlabs` or `say` (or an order like `elevenlabs,say`) |
| `JINA_API_KEY` | higher rate limits when reading web pages and documents |

## Use

In Claude Code, just ask:

> make me a waitwhat video on why the sky is blue

It creates `./waitwhat-videos/why-is-the-sky-blue/`, writes the script, records the voice,
animates each scene, stitches everything and opens `out/video.mp4`. Attach files or paste a URL
in the same message to explain those instead. To refine: "wait, what? at 0:42 — why is the
middle a square?".

## Job contract (for apps and workers driving the plugin)

Create a job dir and run the agent with it as the working directory:

```
<job>/
  request.json              {prompt, attachments:[{path,name,mime}], refine?:{text, at_seconds, frame_path}}
  inputs/                   attachments (+ the refine frame png)
  workspace/                previous version's workspace when refining; otherwise empty
  .waitwhat/progress.json   {stage, message, scenes:[{index,title,status}]}  ← poll this
  out/video.mp4             1920x1080, h264 + aac
  out/thumbnail.jpg
  out/manifest.json         {title, scenes:[{index,title,narration,start,duration}]}
```

`stage` goes understanding → research → script → voice → animating → stitching → done; scene
`status` is pending | rendering | done | failed. Keep `workspace/` after a run: it is the starting
point of the next refine. `scripts/ww check <job>` validates the outputs. Full details:
[`skills/waitwhat/references/job-contract.md`](skills/waitwhat/references/job-contract.md).

## Tools

`scripts/ww <command>`: `setup`, `new`, `progress`, `tts`, `render`, `stitch`, `fetch`, `music`,
`sfx`, `refine`, `check`, `manim`. Each script has `--help`.

Sound effects come from a small curated library in `assets/sfx/` (generated once; see
THIRD_PARTY.md), so a video costs nothing extra for them. Themes live in
`skills/manim-scenes/lib/waitwhat_themes.py`; `python waitwhat_themes.py <dir>` checks every
palette's contrast and writes a preview of each background.

## Licence

MIT, © Luigi Rivolta. Borrowed ideas and code are credited in [THIRD_PARTY.md](THIRD_PARTY.md).
