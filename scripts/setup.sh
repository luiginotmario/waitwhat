#!/usr/bin/env bash
# waitwhat toolchain setup. Idempotent: safe to run again at any time.
#
#   - Python 3.12 venv at <plugin>/.venv via uv, with Manim Community Edition
#   - TinyTeX (no sudo) in the user's home, from the official GitHub releases,
#     plus the LaTeX packages Manim needs for MathTex/Tex
#   - checks ffmpeg/ffprobe
#
# Env overrides:
#   WAITWHAT_TEX_DIR   where to put TinyTeX   (default: ~/Library/TinyTeX on macOS, ~/.TinyTeX on Linux)
#   WAITWHAT_SKIP_TEX=1  skip LaTeX entirely (Text-only scenes still work)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
say_step() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }

OS="$(uname -s)"; ARCH="$(uname -m)"

# ---------------------------------------------------------------- uv
if ! command -v uv >/dev/null 2>&1; then
  say_step "installing uv (user-local)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# ---------------------------------------------------------------- system libs Manim links against
if [ "$OS" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
  for pkg in pkg-config cairo; do
    brew list --versions "$pkg" >/dev/null 2>&1 || { say_step "brew install $pkg"; brew install "$pkg"; }
  done
elif [ "$OS" = "Linux" ] && ! pkg-config --exists cairo 2>/dev/null; then
  warn "cairo headers not found; pycairo needs them. On Debian/Ubuntu:"
  warn "  sudo apt-get install -y build-essential pkg-config libcairo2-dev libpango1.0-dev ffmpeg"
fi

# ---------------------------------------------------------------- python venv
if [ ! -x "$VENV/bin/python" ]; then
  say_step "creating venv (Python 3.12) at $VENV"
  uv venv --python 3.12 "$VENV"
fi
say_step "installing Python packages"
uv pip install --python "$VENV/bin/python" -q -r "$ROOT/scripts/requirements.txt"

# ---------------------------------------------------------------- ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  if [ "$OS" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    say_step "brew install ffmpeg"; brew install ffmpeg
  else
    warn "ffmpeg/ffprobe not found. Install them (e.g. apt-get install ffmpeg) and re-run."
  fi
fi

# ---------------------------------------------------------------- TinyTeX
if [ "${WAITWHAT_SKIP_TEX:-0}" != "1" ]; then
  if [ "$OS" = "Darwin" ]; then TEXDIR="${WAITWHAT_TEX_DIR:-$HOME/Library/TinyTeX}"; else TEXDIR="${WAITWHAT_TEX_DIR:-$HOME/.TinyTeX}"; fi

  find_tlbin() { ls -d "$TEXDIR"/bin/* 2>/dev/null | head -1; }

  if ! command -v latex >/dev/null 2>&1 && [ -z "$(find_tlbin)" ]; then
    case "$OS-$ARCH" in
      Darwin-*)            ASSET_RE='^TinyTeX-1-darwin-v.*\.tar\.xz$' ;;
      Linux-x86_64)        ASSET_RE='^TinyTeX-1-linux-x86_64-v.*\.tar\.xz$' ;;
      Linux-aarch64|Linux-arm64) ASSET_RE='^TinyTeX-1-linux-arm64-v.*\.tar\.xz$' ;;
      *) warn "no TinyTeX build for $OS-$ARCH; install a LaTeX distribution yourself"; ASSET_RE='' ;;
    esac
    if [ -n "$ASSET_RE" ]; then
      say_step "finding latest TinyTeX release"
      API="https://api.github.com/repos/rstudio/tinytex-releases/releases/latest"
      URL="$(curl -fsSL "$API" | "$VENV/bin/python" -c "
import json,re,sys
rel=json.load(sys.stdin)
for a in rel['assets']:
    if re.match(r'''$ASSET_RE''', a['name']): print(a['browser_download_url']); break
")"
      [ -n "$URL" ] || { warn "could not resolve TinyTeX asset"; exit 1; }
      TMP="$(mktemp -d)"
      say_step "downloading $URL"
      curl -fL --progress-bar "$URL" -o "$TMP/tinytex.tar.xz"
      mkdir -p "$(dirname "$TEXDIR")"
      tar -xJf "$TMP/tinytex.tar.xz" -C "$TMP"
      # archive contains a single top-level dir (TinyTeX or .TinyTeX)
      SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)"
      rm -rf "$TEXDIR"; mv "$SRC" "$TEXDIR"; rm -rf "$TMP"
    fi
  fi

  TLBIN="$(find_tlbin)"
  if [ -n "$TLBIN" ]; then
    export PATH="$TLBIN:$PATH"
    # TinyTeX archives ship with a relocatable tree; tell tlmgr where it lives.
    tlmgr option sys_bin "$TLBIN" >/dev/null 2>&1 || true
    tlmgr postaction install script xetex >/dev/null 2>&1 || true
    NEED=(standalone preview doublestroke relsize fundus-calligra wasysym physics dvisvgm
          rsfs wasy cm-super everysel setspace ragged2e microtype babel-english jknapltx
          mathastext xkeyval xcolor amsfonts tipa cm-unicode)
    MISSING=()
    for p in "${NEED[@]}"; do
      tlmgr info --only-installed --data name "$p" 2>/dev/null | grep -qx "$p" || MISSING+=("$p")
    done
    if [ "${#MISSING[@]}" -gt 0 ]; then
      say_step "tlmgr install ${MISSING[*]}"
      tlmgr install "${MISSING[@]}" || {
        warn "tlmgr install failed once; updating tlmgr and retrying"
        tlmgr update --self && tlmgr install "${MISSING[@]}"
      }
    fi
    # Remember where TeX lives so scripts/run.sh can put it on PATH without a login shell.
    printf '%s\n' "$TLBIN" > "$ROOT/.venv/texbin"
  elif command -v latex >/dev/null 2>&1; then
    dirname "$(command -v latex)" > "$ROOT/.venv/texbin"
  fi
fi

# ---------------------------------------------------------------- smoke test
say_step "smoke test"
"$ROOT/scripts/run.sh" python - <<'PY'
import shutil, manim, sys
print("manim", manim.__version__, "| python", sys.version.split()[0])
for t in ("ffmpeg", "ffprobe", "latex", "dvisvgm"):
    print(f"  {t:8s}", shutil.which(t) or "MISSING")
PY
say_step "done. Use scripts/run.sh <cmd> to run anything inside the toolchain."
