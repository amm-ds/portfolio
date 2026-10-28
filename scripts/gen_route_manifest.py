#!/usr/bin/env python3
"""Generate the showcase API's SPA route manifest (committed artifact).

The FastAPI catch-all serves index.html for known client-side routes and must
return a real JSON 404 for everything else. The set of known SPA routes is
derived here, at build/CI time, from three sources:

- ``apps/showcase-web/src/App.tsx`` — static routes (``/projects``,
  ``/demos/churn-sandbox``, ...); ``:param`` segments become ``*`` patterns
  and the ``*`` NotFound catch-all is skipped;
- ``projects/*/portfolio.yaml`` — one ``/projects/<id>`` deep link per project;
- ``projects/*/demo.yaml`` + ``projects/*/demos/*.yaml`` — one ``/demos/<id>``
  deep link per demo manifest.

Output: ``apps/showcase-api/src/showcase_api/route_manifest.json`` (packaged
with the wheel, so the Docker image ships it without re-running this script).

Usage::

    uv run python scripts/gen_route_manifest.py

Run it whenever App.tsx routes, project ids, or demo ids change (CI should
fail the build when the committed file drifts — regenerate and commit).
"""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_TSX = REPO_ROOT / "apps" / "showcase-web" / "src" / "App.tsx"
PROJECTS_ROOT = REPO_ROOT / "projects"
OUT_FILE = REPO_ROOT / "apps" / "showcase-api" / "src" / "showcase_api" / "route_manifest.json"

_PID_RE = re.compile(r"^\d{2}-[a-z0-9-]+$")


def _yaml_ids(files: list[Path]) -> list[str]:
    """Best-effort ``id:`` extraction; prefers PyYAML, falls back to a regex."""
    ids: list[str] = []
    try:
        import yaml  # type: ignore[import-untyped]

        for f in files:
            data = yaml.safe_load(f.read_text())
            if isinstance(data, dict) and isinstance(data.get("id"), str):
                ids.append(data["id"])
        return ids
    except ImportError:
        pass
    for f in files:
        m = re.search(r"^id:\s*([A-Za-z0-9_-]+)\s*$", f.read_text(), re.MULTILINE)
        if m:
            ids.append(m.group(1))
    return ids


def spa_routes() -> list[str]:
    """All known SPA paths (exact or single-``*``-segment patterns), sorted."""
    routes: set[str] = set()

    text = APP_TSX.read_text()
    for m in re.finditer(r'<Route\s+path="([^"]+)"', text):
        p = m.group(1).strip()
        if not p or p == "*":
            continue  # the NotFound catch-all is not a known route
        # /projects/:id -> /projects/* (:param matches exactly one segment)
        routes.add(re.sub(r":\w+", "*", p))

    if PROJECTS_ROOT.is_dir():
        portfolio = sorted(PROJECTS_ROOT.glob("*/portfolio.yaml"))
        for pid in _yaml_ids(portfolio):
            if _PID_RE.match(pid):
                routes.add(f"/projects/{pid}")
        demos = sorted(PROJECTS_ROOT.glob("*/demo.yaml")) + sorted(
            PROJECTS_ROOT.glob("*/demos/*.yaml")
        )
        for demo_id in _yaml_ids(demos):
            routes.add(f"/demos/{demo_id}")

    return sorted(routes)


def main() -> int:
    routes = spa_routes()
    if not routes:
        print("error: no SPA routes discovered — check paths", file=sys.stderr)
        return 1
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": [
            "apps/showcase-web/src/App.tsx",
            "projects/*/portfolio.yaml",
            "projects/*/demo.yaml",
            "projects/*/demos/*.yaml",
        ],
        "spa_routes": routes,
    }
    OUT_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT_FILE.relative_to(REPO_ROOT)} ({len(routes)} routes)")
    for r in routes:
        print(f"  {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
