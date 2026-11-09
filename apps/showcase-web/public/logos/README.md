# Local brand logos

Self-hosted SVG logos referenced by `FrameworkTile` (`src/components/Frameworks.tsx`)
via each entry's `logo` field. Everything is local because the production CSP
(`img-src 'self' data:`) blocks the third-party icon CDNs — the Simple Icons
copies below are CC0-licensed, so nothing hotlinks brand art. AWS and Azure
were removed from Simple Icons (no CC0 source), and RAGAS / pydantic-ai never
had entries, so those keep their documented local reconstructions.

The Simple Icons files are downloaded as the white (`fff`) variants —
`https://cdn.simpleicons.org/<slug>/fff` — recolored like the house dark-tile
copies for legibility on the site's dark tiles.

Every tile keeps its accessible fallback: if the image fails to load, the tile
degrades to its mono initial-letter block (`letters`), and the `<img>` carries
explicit `width`/`height` plus a `"{name} logo"` alt text.

| File | Brand | Source | License / usage note |
| --- | --- | --- | --- |
| `pydantic.svg` | pydantic | `https://cdn.simpleicons.org/pydantic/fff` (Simple Icons slug `pydantic`) | CC0 (Simple Icons); pydantic is a trademark of Pydantic Services Inc., reproduced for identification only. |
| `ollama.svg` | Ollama | `https://cdn.simpleicons.org/ollama/fff` (Simple Icons slug `ollama`) | CC0 (Simple Icons); Ollama is a trademark of Ollama, Inc. |
| `scikitlearn.svg` | scikit-learn | `https://cdn.simpleicons.org/scikitlearn/fff` (Simple Icons slug `scikitlearn`) | CC0 (Simple Icons). |
| `pytorch.svg` | PyTorch | `https://cdn.simpleicons.org/pytorch/fff` (Simple Icons slug `pytorch`) | CC0 (Simple Icons); PyTorch is a trademark of The Linux Foundation. |
| `polars.svg` | Polars | `https://cdn.simpleicons.org/polars/fff` (Simple Icons slug `polars`) | CC0 (Simple Icons). |
| `plotly.svg` | Plotly | `https://cdn.simpleicons.org/plotly/fff` (Simple Icons slug `plotly`) | CC0 (Simple Icons). |
| `dvc.svg` | DVC | `https://cdn.simpleicons.org/dvc/fff` (Simple Icons slug `dvc`) | CC0 (Simple Icons). |
| `uv.svg` | uv | `https://cdn.simpleicons.org/uv/fff` (Simple Icons slug `uv`) | CC0 (Simple Icons). |
| `fastapi.svg` | FastAPI | `https://cdn.simpleicons.org/fastapi/fff` (Simple Icons slug `fastapi`) | CC0 (Simple Icons). |
| `react.svg` | React | `https://cdn.simpleicons.org/react/fff` (Simple Icons slug `react`) | CC0 (Simple Icons); React is a trademark of Meta Platforms, Inc. |
| `typescript.svg` | TypeScript | `https://cdn.simpleicons.org/typescript/fff` (Simple Icons slug `typescript`) | CC0 (Simple Icons); TypeScript is a trademark of Microsoft Corporation. |
| `optuna.svg` | Optuna | `https://cdn.simpleicons.org/optuna/fff` (Simple Icons slug `optuna`) | CC0 (Simple Icons). |
| `huggingface.svg` | Hugging Face | `https://cdn.simpleicons.org/huggingface/fff` (Simple Icons slug `huggingface`) | CC0 (Simple Icons); Hugging Face is a trademark of Hugging Face, Inc. |
| `googlecloud.svg` | Google Cloud | `https://cdn.simpleicons.org/googlecloud/fff` (Simple Icons slug `googlecloud`) | CC0 (Simple Icons); Google Cloud is a trademark of Google LLC. |
| `docker.svg` | Docker | `https://cdn.simpleicons.org/docker/fff` (Simple Icons slug `docker`) | CC0 (Simple Icons); Docker is a trademark of Docker, Inc. |
| `ragas.svg` | RAGAS | Hand-traced recreation of the official mark (`#ffcb4c`), rebuilt from the 50×50 PNG at `https://docs.ragas.io/_static/imgs/ragas-logo.png` (no SVG source is published) | Unofficial reconstruction for identification only; RAGAS is a trademark of Exploding Gradients. |
| `pydantic-ai.svg` | pydantic-ai | Pydantic hexagon brand mark, `https://raw.githubusercontent.com/pydantic/pydantic/main/docs/logo-white.svg` | Pydantic's project code is MIT; the mark itself is a brand asset of Pydantic Services Inc., reproduced for identification only. The pydantic-ai wordmark (`viewBox 0 0 605 120`) is text-led and illegible at tile size, so the shared pydantic hexagon mark is used. |
| `aws.svg` | AWS | `https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg` | Wikimedia Commons "non-free logo", reproduced here for identification under the same rationale. AWS and the smile logo are trademarks of Amazon.com, Inc. or its affiliates. Wordmark fill recolored `#252F3E → #fff` for legibility on the site's dark tiles (AWS guidelines provide white/monochrome variants). |
| `azure.svg` | Microsoft Azure | `https://upload.wikimedia.org/wikipedia/commons/f/fa/Microsoft_Azure.svg` | Wikimedia Commons "non-free logo", reproduced here for identification under the same rationale. Microsoft Azure is a trademark of Microsoft Corporation. Unmodified apart from the added `<title>`. |
| `duckdb.svg` | DuckDB | Hand-drawn simplification of the DuckDB mark (duck silhouette over stacked data bars), white on the dark tiles; official art at `https://duckdb.org/images/duckdb-logo.svg` is not CC0 | Unofficial reconstruction for identification only; DuckDB is a trademark of the DuckDB Foundation. |

If a mark's owner asks for removal, delete the file and drop the entry's `logo`
field in `Frameworks.tsx` — the tile then renders the letter fallback again.
