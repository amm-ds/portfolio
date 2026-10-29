#!/usr/bin/env python3
"""Generate apps/showcase-web/public/sitemap.xml.

Static routes plus one /projects/<id> entry per projects/*/portfolio.yaml.
Also rewrites the static canonical/Open Graph/Twitter and robots URLs. Set
SITE_URL (or VITE_SITE_URL) for a non-default deployment. Exits non-zero if any
portfolio.yaml is unreadable or lacks an id, so CI can gate on it.
"""

import datetime
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "apps" / "showcase-web"

DEFAULT_SITE_URL = "https://amm-ds.github.io/portfolio"

STATIC_ROUTES = [
    "/",
    "/experiments",
    "/services",
    "/contact",
    "/demos/churn-sandbox",
    "/demos/forecast-workbench",
]


def project_ids() -> list[str]:
    ids = []
    for yaml_path in sorted((ROOT / "projects").glob("*/portfolio.yaml")):
        if not yaml_path.is_file() or yaml_path.stat().st_size == 0:
            sys.exit(f"gen_sitemap: {yaml_path} is missing or empty")
        text = yaml_path.read_text(encoding="utf-8")
        match = re.search(r"^id:\s*([^\s#]+)\s*$", text, re.MULTILINE)
        if not match:
            sys.exit(f"gen_sitemap: {yaml_path} has no id field")
        ids.append(match.group(1))
    if not ids:
        sys.exit("gen_sitemap: no projects/*/portfolio.yaml found")
    return ids


def write_static_metadata(base: str) -> None:
    index_path = WEB_DIR / "index.html"
    index = index_path.read_text(encoding="utf-8")
    replacements = [
        (r'(<link rel="canonical" href=")[^"]+(")', f"{base}/", 1),
        (r'(<meta property="og:url" content=")[^"]+(")', f"{base}/", 1),
        (
            r'((?:property="og:image"|name="twitter:image")\s+content=")[^"]+(")',
            f"{base}/social-card.png",
            2,
        ),
        (
            r'(<meta name="build-sha" content=")[^"]+(")',
            os.environ.get("VITE_BUILD_SHA", "dev"),
            1,
        ),
    ]
    for pattern, value, expected in replacements:
        index, count = re.subn(pattern, rf"\g<1>{value}\g<2>", index)
        if count != expected:
            message = f"expected {expected} metadata matches for {pattern}, got {count}"
            sys.exit(f"gen_sitemap: {message}")
    index_path.write_text(index, encoding="utf-8")

    robots_path = WEB_DIR / "public" / "robots.txt"
    robots = robots_path.read_text(encoding="utf-8")
    robots, count = re.subn(r"(?m)^Sitemap:.*$", f"Sitemap: {base}/sitemap.xml", robots)
    if count != 1:
        sys.exit("gen_sitemap: expected one Sitemap line in robots.txt")
    robots_path.write_text(robots, encoding="utf-8")


def main() -> None:
    base = (
        os.environ.get("SITE_URL") or os.environ.get("VITE_SITE_URL") or DEFAULT_SITE_URL
    ).rstrip("/")
    today = datetime.date.today().isoformat()

    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for route in STATIC_ROUTES + [f"/projects/{pid}" for pid in project_ids()]:
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = f"{base}{route}"
        ET.SubElement(url, "lastmod").text = today

    write_static_metadata(base)
    out = WEB_DIR / "public" / "sitemap.xml"
    ET.ElementTree(urlset).write(out, encoding="utf-8", xml_declaration=True)
    print(f"wrote {out} ({len(urlset)} urls) and static metadata for {base}")


if __name__ == "__main__":
    main()
