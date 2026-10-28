#!/usr/bin/env python3
"""Generate apps/showcase-web/public/sitemap.xml.

Static routes plus one /projects/<id> entry per projects/*/portfolio.yaml.
Exits non-zero if any portfolio.yaml is unreadable or lacks an id, so CI can
gate on it. Keep SITE_URL in sync with the VITE_SITE_URL default in
apps/showcase-web/src/config.ts.
"""

import datetime
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "apps" / "showcase-web"

SITE_URL = "https://amm-ds.github.io/portfolio"

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


def main() -> None:
    base = SITE_URL.rstrip("/")
    today = datetime.date.today().isoformat()

    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for route in STATIC_ROUTES + [f"/projects/{pid}" for pid in project_ids()]:
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = f"{base}{route}"
        ET.SubElement(url, "lastmod").text = today

    out = WEB_DIR / "public" / "sitemap.xml"
    ET.ElementTree(urlset).write(out, encoding="utf-8", xml_declaration=True)
    print(f"wrote {out} ({len(urlset)} urls)")


if __name__ == "__main__":
    main()
