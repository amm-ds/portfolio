# Local brand logos

Self-hosted SVG logos referenced by `FrameworkTile` (`src/components/Frameworks.tsx`)
via each entry's `logo` field. They exist so the site never hotlinks brand art that
no CC0-licensed CDN (Simple Icons) serves — AWS and Azure were removed from
Simple Icons, and RAGAS / pydantic-ai never had entries.

Every tile keeps its accessible fallback: if the image fails to load, the tile
degrades to its mono initial-letter block (`letters`), and the `<img>` carries
explicit `width`/`height` plus a `"{name} logo"` alt text.

| File | Brand | Source | License / usage note |
| --- | --- | --- | --- |
| `ragas.svg` | RAGAS | Hand-traced recreation of the official mark (`#ffcb4c`), rebuilt from the 50×50 PNG at `https://docs.ragas.io/_static/imgs/ragas-logo.png` (no SVG source is published) | Unofficial reconstruction for identification only; RAGAS is a trademark of Exploding Gradients. |
| `pydantic-ai.svg` | pydantic-ai | Pydantic hexagon brand mark, `https://raw.githubusercontent.com/pydantic/pydantic/main/docs/logo-white.svg` | Pydantic's project code is MIT; the mark itself is a brand asset of Pydantic Services Inc., reproduced for identification only. The pydantic-ai wordmark (`viewBox 0 0 605 120`) is text-led and illegible at tile size, so the shared pydantic hexagon mark is used. |
| `aws.svg` | AWS | `https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg` | Wikimedia Commons "non-free logo", reproduced here for identification under the same rationale. AWS and the smile logo are trademarks of Amazon.com, Inc. or its affiliates. Wordmark fill recolored `#252F3E → #fff` for legibility on the site's dark tiles (AWS guidelines provide white/monochrome variants). |
| `azure.svg` | Microsoft Azure | `https://upload.wikimedia.org/wikipedia/commons/f/fa/Microsoft_Azure.svg` | Wikimedia Commons "non-free logo", reproduced here for identification under the same rationale. Microsoft Azure is a trademark of Microsoft Corporation. Unmodified apart from the added `<title>`. |

If a mark's owner asks for removal, delete the file and drop the entry's `logo`
field in `Frameworks.tsx` — the tile then renders the letter fallback again.
