#!/usr/bin/env python3
"""Fetch a URL (web page, PDF, docs) as clean Markdown via Jina Reader and save it as a source.

  fetch.py https://example.com            → workspace/research/example-com.md (prints the path)
  fetch.py https://example.com/pricing -o workspace/research/pricing.md
  fetch.py --search "acme payroll api pricing"   (Jina search; needs JINA_API_KEY)

Uses https://r.jina.ai/<url>; JINA_API_KEY (optional) raises rate limits. Each saved file starts
with a header recording the source URL and fetch time, so every fact can be traced back.
Stdlib only.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _ssl_context():
    """Verified TLS even on Pythons without a CA bundle (e.g. python.org builds on macOS)."""
    import ssl
    ctx = ssl.create_default_context()
    for cafile in (os.environ.get("SSL_CERT_FILE"), "/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if cafile and os.path.exists(cafile):
            try:
                ctx.load_verify_locations(cafile)
            except Exception:
                pass
    try:
        import certifi  # type: ignore
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


SSL_CTX = _ssl_context()


def get(url: str, headers: dict) -> str:
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90, context=SSL_CTX) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise SystemExit(f"fetch: {e.code} for {url}: {e.read().decode(errors='replace')[:300]}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise SystemExit(f"fetch: {e.reason} for {url}")
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--search")
    ap.add_argument("--ws", default="workspace")
    a = ap.parse_args()
    headers = {"Accept": "text/plain", "X-Return-Format": "markdown", "User-Agent": "waitwhat/1.0"}
    key = os.environ.get("JINA_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    if a.search:
        if not key:
            sys.exit("fetch: --search needs JINA_API_KEY; use your web search tool instead")
        text = get("https://s.jina.ai/" + urllib.parse.quote(a.search), headers)
        source = f"search: {a.search}"
        slug = "search-" + re.sub(r"[^a-z0-9]+", "-", a.search.lower()).strip("-")[:50]
    elif a.url:
        url = a.url if re.match(r"https?://", a.url) else "https://" + a.url
        text = get("https://r.jina.ai/" + url, headers)
        source = url
        slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"https?://(www\.)?", "", url.lower())).strip("-")[:60]
    else:
        ap.error("give a url or --search")
    out = Path(a.out) if a.out else Path(a.ws) / "research" / f"{slug}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"<!-- source: {source} | fetched: {time.strftime('%Y-%m-%d %H:%M')} -->\n\n{text}")
    print(f"{out}  ({len(text):,} chars)")


if __name__ == "__main__":
    main()
