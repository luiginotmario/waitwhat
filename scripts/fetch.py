#!/usr/bin/env python3
"""Fetch a URL (web page, PDF, docs) as clean Markdown via Jina Reader and save it as a source.

  fetch.py https://example.com            → workspace/research/example-com.md (prints the path)
  fetch.py https://example.com/pricing -o workspace/research/pricing.md
  fetch.py --search "acme payroll api pricing"   (Jina search; needs JINA_API_KEY)
  fetch.py URL URL ... --search "q1" --search "q2"   # everything at once, fetched in parallel

Give every URL and search of a research round in ONE call: they are fetched concurrently (one
line of output each; a failed one doesn't stop the others). Pages already in workspace/research/
(e.g. prefetched by the web planner, see request.json `research`) are skipped unless --force.
Uses https://r.jina.ai/<url>; JINA_API_KEY (optional) raises rate limits. Each saved file starts
with a header recording the source URL and fetch time, so every fact can be traced back.
Stdlib only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
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


def slug_for_url(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"https?://(www\.)?", "", url.lower())).strip("-")[:60]


def fetch_one(kind: str, what: str, out: Path | None, ws: Path, headers: dict, force: bool) -> str:
    if kind == "search":
        source = f"search: {what}"
        slug = "search-" + re.sub(r"[^a-z0-9]+", "-", what.lower()).strip("-")[:50]
        url = "https://s.jina.ai/" + urllib.parse.quote(what)
    else:
        source = what if re.match(r"https?://", what) else "https://" + what
        slug = slug_for_url(source)
        url = "https://r.jina.ai/" + source
    out = out or ws / "research" / f"{slug}.md"
    if out.exists() and not force and out.stat().st_size > 200:
        return f"{out}  (already fetched, {out.stat().st_size:,} bytes)"
    text = get(url, headers)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"<!-- source: {source} | fetched: {time.strftime('%Y-%m-%d %H:%M')} -->\n\n{text}")
    return f"{out}  ({len(text):,} chars)"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="*")
    ap.add_argument("-o", "--out", help="output file (a single URL or search only)")
    ap.add_argument("--search", action="append", default=[])
    ap.add_argument("--ws", default="workspace")
    ap.add_argument("--force", action="store_true", help="re-fetch pages that are already saved")
    a = ap.parse_args()
    headers = {"Accept": "text/plain", "X-Return-Format": "markdown", "X-Retain-Images": "none",
               "User-Agent": "waitwhat/1.0"}
    key = os.environ.get("JINA_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if a.search and not key:
        sys.exit("fetch: --search needs JINA_API_KEY")
    jobs = [("url", u) for u in a.url] + [("search", q) for q in a.search]
    if not jobs:
        ap.error("give a url or --search")
    if a.out and len(jobs) > 1:
        ap.error("-o works with a single URL or search")
    out = Path(a.out) if a.out else None

    def one(job: tuple[str, str]) -> tuple[bool, str]:
        try:
            return True, fetch_one(job[0], job[1], out, Path(a.ws), headers, a.force)
        except BaseException as e:  # get() raises SystemExit on HTTP errors; report and carry on
            return False, f"fetch: FAILED {job[1]}: {e}"

    with cf.ThreadPoolExecutor(max_workers=min(8, len(jobs))) as pool:
        results = list(pool.map(one, jobs))
    for ok, line in results:
        print(line, file=sys.stdout if ok else sys.stderr)
    if not any(ok for ok, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
