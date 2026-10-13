"""The video's aspect: landscape 16:9 (1920x1080, the default) or vertical 9:16 (1080x1920).

One render per video, laid out for its aspect from the start (never cropped). Resolved, first hit wins:
  1. WAITWHAT_ASPECT (env; for local experiments and tests)
  2. workspace/plan.json "aspect"      (the orchestrator copies request.aspect here)
  3. <job>/request.json "aspect"       (what the person picked in the web app)
  4. "16:9"
Accepts "16:9" / "9:16" and the words landscape / horizontal / vertical / portrait / tall.
Stdlib only: render.py, stitch.py and job.py import it (the style lib has its own copy of the rule).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

LANDSCAPE, VERTICAL = "16:9", "9:16"
_WORDS = {"16:9": LANDSCAPE, "landscape": LANDSCAPE, "horizontal": LANDSCAPE, "wide": LANDSCAPE,
          "9:16": VERTICAL, "vertical": VERTICAL, "portrait": VERTICAL, "tall": VERTICAL}
#: (width, height) of the final video
SIZE = {LANDSCAPE: (1920, 1080), VERTICAL: (1080, 1920)}
#: (width, height) of a fast preview (Manim -ql is 854x480)
PREVIEW = {LANDSCAPE: (854, 480), VERTICAL: (480, 854)}


def normalize(value) -> str | None:
    if not isinstance(value, str):
        return None
    return _WORDS.get(value.strip().lower())


def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def aspect_of(ws: Path) -> str:
    """The aspect of the video whose workspace is `ws` (see the module docstring)."""
    ws = Path(ws)
    for v in (os.environ.get("WAITWHAT_ASPECT"), _read(ws / "plan.json").get("aspect"),
              _read(ws.parent / "request.json").get("aspect")):
        a = normalize(v)
        if a:
            return a
    return LANDSCAPE


def is_vertical(ws: Path) -> bool:
    return aspect_of(ws) == VERTICAL
