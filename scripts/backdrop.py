#!/usr/bin/env python3
"""Optional: an AI-painted backdrop for a video's theme, through OpenRouter (one image per video).

  backdrop.py "a quiet harbour at dawn, painterly, no text" [-o workspace/backdrop.png] [--model M]

Writes the image and prints a JSON line with its path and cost. Then point the theme at it:
  "theme": {"name": "ocean", "backdrop": "backdrop.png"}      (path relative to workspace/)
The style lib cover-fits it, blurs it and lays the theme's background over it (backdrop_dim,
default 0.72 = 72 % theme), so the picture is a mood behind the content, never competing with it.

Use it rarely: only when an illustrated world really serves the story (a place, an era) and the
procedural themes don't fit. Never ask for text, logos, real people or brands in the image.
Needs OPENROUTER_API_KEY. Stdlib only.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts import SSL_CTX  # noqa: E402  (verified TLS on any Python)

API = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.environ.get("WAITWHAT_BACKDROP_MODEL", "bytedance-seed/seedream-5-0-flash")
STYLE = ("Wide 16:9 background illustration, soft and low in detail, calm colours, large simple shapes, "
         "lots of empty space in the middle, no text, no letters, no logos, no people's faces.")


def post(key: str, path: str, body: dict) -> tuple[dict, str | None]:
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/luiginotmario/waitwhat", "X-Title": "waitwhat"})
    with urllib.request.urlopen(req, timeout=180, context=SSL_CTX) as r:
        return json.loads(r.read()), r.headers.get("x-generation-id")


def cost_of(key: str, gen_id: str | None) -> float | None:
    if not gen_id:
        return None
    for _ in range(6):
        try:
            req = urllib.request.Request(f"{API}/generation?id={gen_id}", headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
                return float(json.loads(r.read())["data"].get("total_cost") or 0)
        except Exception:
            time.sleep(1.5)
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt")
    ap.add_argument("-o", "--out", default="workspace/backdrop.png")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        sys.exit("backdrop: OPENROUTER_API_KEY is not set")
    body = {"model": a.model, "modalities": ["image"],
            "messages": [{"role": "user", "content": f"{a.prompt}. {STYLE}"}],
            "image_config": {"aspect_ratio": "16:9"}}
    try:
        res, gen = post(key, "/chat/completions", body)
    except urllib.error.HTTPError as e:
        sys.exit(f"backdrop: HTTP {e.code}: {e.read().decode(errors='ignore')[:400]}")
    msg = (res.get("choices") or [{}])[0].get("message") or {}
    imgs = msg.get("images") or []
    url = (imgs[0].get("image_url") or {}).get("url", "") if imgs else ""
    if not url.startswith("data:image"):
        sys.exit(f"backdrop: no image in the response ({json.dumps(res)[:300]})")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(url.split(",", 1)[1]))
    cost = (res.get("usage") or {}).get("cost")
    if cost is None:
        cost = cost_of(key, gen or res.get("id"))
    print(json.dumps({"ok": True, "path": str(out), "model": a.model, "cost_usd": cost}))


if __name__ == "__main__":
    main()
