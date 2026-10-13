# Job I/O contract and workspace layout

The worker (Claude Agent SDK), the Mac app and local Claude Code all drive waitwhat the same way:
they create a job dir and run the agent with that dir as cwd.

```
<job>/
  request.json              {prompt, attachments:[{path,name,mime}], plan?, answers?, research?, level?, refine?:{text, at_seconds, frame_path}}
  inputs/                   downloaded attachments (+ the refine frame png)
  workspace/                previous version's workspace when refining; otherwise empty
  .waitwhat/progress.json   written ONLY via `ww progress …`; the worker polls it
  out/video.mp4             REQUIRED  1920x1080, h264 + aac
  out/thumbnail.jpg         REQUIRED
  out/manifest.json         REQUIRED  {title, scenes:[{index,title,narration,start,duration}]}
```

- Paths inside `request.json` are relative to the job dir.
- `request.plan` (optional) is the coverage plan made before the job by
  `references/planning.md`: `{title, est_minutes, outline:[{title, summary}], audience?,
  question?, asked?:[string], note?, deferred?:[string]}`. `request.answers` (optional) holds the
  person's answers to clarifying questions: `[{id, q, a}]` (`a` null when skipped). The outline is
  the checklist the video must cover; see the `waitwhat` skill.
- `request.level` (optional): the depth the person picked, `eli10 | auto | expert | jargon`;
  anything but `auto` overrides the audience inferred from the wording (planning.md §2).
- `request.research` (optional): pages the web planner already fetched for this request (the URLs
  in the prompt), saved before the run as `workspace/research/<slug>.md` with the usual source
  header: `[{url, path, chars}]` (`path` relative to the job dir). Use them; don't fetch them again
  (`ww fetch` skips pages that are already saved).
- After success the worker tars `workspace/` (it becomes the starting point of the next refine)
  and uploads `out/*`. Keep `workspace/` self-contained and reasonably small: no Manim media
  caches (render.py deletes them), no copies of `out/`.
- `progress.json` shape: `{stage, message, scenes:[{index,title,status}], outline?:[{index,title,status}]}`
  with stage in understanding → research → script → voice → animating → stitching → done and
  scene status in pending | rendering | done | failed. Scene `index` is 1-based and matches the
  manifest. `outline` (written by `ww progress plan` when plan.json has one) is progress against
  the coverage plan: an item is done when every scene that `covers` it is done.
- `.waitwhat/usage.json` (extra, optional) accumulates billable narration usage across `ww tts`
  runs, for the worker's cost accounting: `{"openrouter_audio_cost_usd": 0.0124,
  "tts_characters": 296, "stt_seconds": 16.7, "tts_model": "elevenlabs/eleven-multilingual-v2",
  "voice": "brian", "elevenlabs_characters": 296}`. `openrouter_audio_cost_usd` is the measured
  OpenRouter cost (speech + transcription) in USD; `tts_characters` counts every character sent
  for synthesis, through any provider; `elevenlabs_characters` is a legacy alias of it.
- `manifest.json` is written by `ww stitch` from plan.json. `narration` is the plain spoken
  text (markup stripped); `start`/`duration` are seconds in the final video (after the intro).

A run is finished only when `ww check` passes and progress is `done`. If you cannot produce a
video at all, write `ww progress stage done "<what went wrong, in plain words>"` and say so; never
leave a half-written `out/`.

## workspace/ layout (ours; the worker treats it as opaque)

```
workspace/
  plan.json            the single source of truth (below)
  research/            fetched sources (*.md with source headers) + notes.md
  scenes/<id>.py       one WaitwhatScene per file; file stem = scene id
  scenes/shared.py     objects/constructors reused across scenes (continuity)
  audio/<id>.wav|json  narration + word timings + bookmark times (ww tts)
  renders/<id>.mp4|json  final 1080p30 scene renders + content hash (ww render)
  renders/<id>.cues.json sound-effect cues the scene logged ({t, name, gain, dur?, auto?}), mixed by ww stitch
  previews/<id>.mp4|json  fast 480p15 previews (ww render --preview); never stitched
  frames/<id>_*.jpg    review frames + <id>_sheet.jpg (2x2: first, ~40 %, ~75 %, last frame)
  frames/_review_*.jpg ww review: a row per scene (first | middle | last); frames/_final.jpg: ww stitch
  logs/                render logs, layout lint, probes, sfx.json (effects placed/dropped by stitch)
  timeline.json        final segment times (ww stitch), used by refine
  thumbnail.png        optional custom thumbnail (a rendered still)
  versions.md          one line per version: what changed and why (refines append)
```

## plan.json

(The `//` comments below are explanations; the real file is plain JSON.)

```json
{
  "title": "Why the Pythagorean theorem is true",
  "mode": "topic",                       // topic | attachments | company | refine (mixes allowed)
  "question": "Why should the squares on the two short sides add up to the square on the long side?",
  "audience": "newcomer: curious adult, no algebra needed beyond squaring",  // level first: newcomer | intermediate | expert
  "aha": "The same four triangles leave behind either a² + b² or c², so they must be equal.",
  "duration_target": 150,                // seconds: request.plan.est_minutes × 60
  "asked": ["why a² + b² = c²"],          // what the person explicitly asked for (from request.plan)
  "outline": [                           // the coverage checklist (from request.plan; refine, never silently drop)
    {"title": "The claim", "summary": "The squares on the short sides always add up to the big one."},
    {"title": "Four triangles, two ways", "summary": "Rearranging the same triangles proves it."}
  ],
  "deferred": [],                        // free preview only: what was left for later
  "dropped": [],                         // outline items you could not cover: [{"title", "why"}]
  "voice": {"backend": "auto", "voice_id": "…", "voice_name": "…", "model_id": "elevenlabs/eleven-multilingual-v2",
            "stability": 0.45, "similarity_boost": 0.8, "style": 0.15, "speed": 1.12,
            "say_voice": "Daniel", "say_rate": 182},
  "pronunciations": {"Euler": "Oiler"},
  "theme": "classic",                    // the video's world (style guide): classic | studio | chalkboard | blueprint | space | ocean | city | whiteboard | graph_paper | paper | hills; or {"name", "ambient": false}
  "palette": {"a": "BLUE", "b": "TEAL", "c": "YELLOW_SOFT", "triangle": "GREY"},  // colour NAMES, so they follow the theme
  "sound": {"music": "calm", "music_db": -17, "sfx": true, "sfx_auto": true, "sfx_db": 0, "intro": true, "outro": true},
  "thumbnail": {"scene": "rearrange", "t": 9.5},
  "scenes": [
    {
      "id": "hook",                      // stable slug; never renumber ids, only reorder
      "title": "A 2,500-year-old claim",
      "goal": "Make the viewer want to know why a² + b² = c² could possibly be true.",
      "narration": "Take any right triangle … <bookmark mark=\"squares\"/> build a square on each side …",
      "visual": "Right triangle fades up; three squares grow off its sides in their concept colours …",
      "build": "shared.make_triangle(), centred; ends on triangle + 3 squares (next scene continues). Beats: squares, compare. pop on each square; chime@compare.",  // the builder's notes
      "covers": [1],                     // 1-based outline items this scene serves (every item needs at least one scene)
      "transition": "cut",               // how THIS scene is entered: continuous (starts on the previous scene's last frame, no whoosh) | cut
      "energy": "high",                  // delivery + tempo: high | medium | low | reveal | close (optional, default medium)
      "theme": "space",                  // optional: only when the story moves to another place
      "lead_in": 0.35                    // optional seconds before narration starts
    }
  ],
  "sources": [{"title": "…", "url": "…", "used_for": "…"}]
}
```

Rules of thumb: ids are short kebab-case and stable across refines (insert "hook-2", don't
renumber). Keep `palette` complete for every concept that appears in more than one scene.
