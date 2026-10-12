#!/usr/bin/env bash
# Run a command inside the waitwhat toolchain: plugin venv + TinyTeX on PATH.
#   scripts/run.sh manim -qh scene_03.py Scene03
#   scripts/run.sh python scripts/tts.py ...
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "waitwhat: toolchain missing, running scripts/setup.sh first" >&2
  "$ROOT/scripts/setup.sh" >&2
fi
PATH="$ROOT/.venv/bin:$PATH"
[ -f "$ROOT/.venv/texbin" ] && PATH="$(cat "$ROOT/.venv/texbin"):$PATH"
export PATH VIRTUAL_ENV="$ROOT/.venv"
# Lets scene files `from waitwhat_style import *` without copying it around.
export PYTHONPATH="$ROOT/skills/manim-scenes/lib${PYTHONPATH:+:$PYTHONPATH}"
export WAITWHAT_ROOT="$ROOT"
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore::SyntaxWarning}"
exec "$@"
