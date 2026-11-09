#!/usr/bin/env python3
"""Pin floating CDN references in committed report/figure HTML (audit L-5).

Committed artifacts under ``projects/*/reports*/`` load third-party scripts two
ways:

- mermaid via ``https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.js``
  — a floating major, and worse a path that 404s in every published 11.x (the
  ESM build moved to ``.mjs``; the classic ``dist/mermaid.min.js`` now assigns
  ``globalThis.mermaid``), so the diagrams never rendered. The floating
  ES-module import block is rewritten to the classic build of the newest
  verified 11.x with an exact version plus ``integrity="sha512-…"`` and
  ``crossorigin="anonymous"`` computed from the served bytes. SRI cannot
  attach to an ES-module ``import`` statement, and the ESM entry lazy-loads
  unsigned chunk files, so the single-file classic build is what makes the
  integrity check meaningful. The report/figure CSP already allows
  cdn.jsdelivr.net in script-src; this script does not touch the CSP.
- plotly via ``https://cdn.plot.ly/…`` direct links (already exact-version).
  SRI on cdn.plot.ly direct links needs their cooperation, so they are
  reported and skipped. A plotly reference served from cdn.jsdelivr.net
  would be pinned + integrity-protected like any other floating jsDelivr
  ``<script src>``; none exist today. Self-hosting is the follow-up.

Idempotent: already-pinned files are left untouched, so re-running only
reports. Only git-committed HTML is scanned; regenerable/ignored files the
pipelines overwrite locally are not touched.

Run: uv run python scripts/pin_report_cdn.py
"""

import base64
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

JSDELIVR = "https://cdn.jsdelivr.net/npm"
# The classic build: one file, sets window.mermaid, SRI covers the whole
# payload. The old esm.min.js path 404s in all 11.x and its .mjs replacement
# lazy-loads unsigned chunks, so it cannot be integrity-protected.
MERMAID_SPEC = "mermaid@11"
MERMAID_PATH = "dist/mermaid.min.js"
MERMAID_GLOBAL_MARKER = b'globalThis["mermaid"]'

_REPORT_DIR_RE = re.compile(r"^reports([_.]|$)")
_MERMAID_FLOAT_RE = re.compile(
    r'<script type="module">\s*'
    r'import mermaid from "https://cdn\.jsdelivr\.net/npm/mermaid@11/dist/mermaid\.esm\.min\.js";\s*'
    r"(mermaid\.initialize\(.*?\);)\s*</script>",
    re.DOTALL,
)
_SCRIPT_SRC_RE = re.compile(
    r'<script src="https://cdn\.jsdelivr\.net/npm/(?P<pkg>[^/@]+)@(?P<float>[^/"]+)/(?P<path>[^"]+)"'
    r"(?P<attrs>[^>]*)>",
)
_PLOTLY_DIRECT_RE = re.compile(r"https://cdn\.plot\.ly/\S+?\.js")


def _http_get(url: str) -> bytes:
    request = urllib.request.Request(  # noqa: S310 (scheme+host fixed above)
        url, headers={"User-Agent": "portfolio-cdn-pin/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (fixed host)
            return response.read()
    except urllib.error.URLError as exc:
        raise SystemExit(f"error: failed to fetch {url}: {exc}") from exc


class Pinner:
    """Resolves a floating jsDelivr spec once and caches pins per URL."""

    def __init__(self) -> None:
        self._pins: dict[tuple[str, str], tuple[str, str]] = {}

    def pin(self, package: str, float_spec: str, path: str) -> tuple[str, str]:
        key = (f"{package}@{float_spec}", path)
        if key not in self._pins:
            meta = json.loads(_http_get(f"{JSDELIVR}/{key[0]}/package.json"))
            version = str(meta["version"])
            url = f"{JSDELIVR}/{package}@{version}/{path}"
            body = _http_get(url)
            integrity = "sha512-" + base64.b64encode(hashlib.sha512(body).digest()).decode()
            self._pins[key] = (url, integrity)
        return self._pins[key]


def _committed_report_html() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "projects"],  # noqa: S607 (git is on PATH in every gate env)
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout
    paths = []
    for raw in listed.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode()
        parts = Path(rel).parts
        if not rel.endswith(".html"):
            continue
        if not any(_REPORT_DIR_RE.match(part) for part in parts):
            continue
        paths.append(REPO / rel)
    return paths


def _pin_mermaid_block(body: str, url: str, integrity: str) -> tuple[str, int]:
    def repl(match: re.Match[str]) -> str:
        return (
            f'<script src="{url}"\n'
            f'        integrity="{integrity}" crossorigin="anonymous"></script>\n'
            f"<script>\n{match.group(1)}\n</script>"
        )

    return _MERMAID_FLOAT_RE.subn(repl, body)


def _pin_floating_script_srcs(body: str, pinner: Pinner) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        attrs = match.group("attrs")
        if 'integrity="' in attrs:
            return match.group(0)  # already pinned — idempotent re-run
        url, integrity = pinner.pin(match.group("pkg"), match.group("float"), match.group("path"))
        count += 1
        return (
            f'<script src="{url}"{attrs.rstrip()} integrity="{integrity}" crossorigin="anonymous">'
        )

    return _SCRIPT_SRC_RE.sub(repl, body), count


def main() -> int:
    pinner = Pinner()
    mermaid_url, mermaid_integrity = pinner.pin(
        "mermaid", MERMAID_SPEC.split("@", 1)[1], MERMAID_PATH
    )
    if MERMAID_GLOBAL_MARKER not in _http_get(mermaid_url):
        raise SystemExit(
            f"error: {mermaid_url} no longer sets globalThis.mermaid — "
            "re-check the mermaid 11.x dist layout before pinning it"
        )
    print(f"mermaid pin: {mermaid_url}")

    changed: list[str] = []
    plotly_files = 0
    already_pinned = 0
    for path in _committed_report_html():
        body = path.read_text()
        plotly_hits = len(_PLOTLY_DIRECT_RE.findall(body))
        if plotly_hits:
            plotly_files += 1
        new_body, mermaid_n = _pin_mermaid_block(body, mermaid_url, mermaid_integrity)
        new_body, src_n = _pin_floating_script_srcs(new_body, pinner)
        if mermaid_n == 0 and src_n == 0:
            if "cdn.jsdelivr.net" in body and "integrity=" in body:
                already_pinned += 1
            continue
        path.write_text(new_body)
        changed.append(str(path.relative_to(REPO)))
        print(f"pinned {path.relative_to(REPO)} (mermaid block: {mermaid_n}, script src: {src_n})")

    print(f"\nchanged: {len(changed)} file(s); already pinned: {already_pinned}")
    print(
        f"plotly: {plotly_files} committed report/figure file(s) reference cdn.plot.ly "
        "directly — skipped (SRI on cdn.plot.ly direct links needs their "
        "cooperation; references are already exact-version)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
