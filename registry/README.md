# DVC dataset registry

Machine-readable, version-pinned references to every external dataset the portfolio
consumes — the DVC half of the data registry (the human-readable cards live in
`docs/data-registry/`).

Each `.dvc` file here was created with `dvc import-url --no-exec`: it records the
source URL and its version metadata (etag/modified) **without** downloading data.
Projects still fetch through their own `prepare` stages (checksum-pinned, local
artifacts tracked by DVC pipeline outs); these manifests make the external sources
themselves versioned and refreshable.

| Manifest | Dataset | Card |
|---|---|---|
| `nyc-tlc-yellow-2024-01.dvc` | NYC TLC yellow taxi (representative month; pattern in card) | [nyc-tlc](../docs/data-registry/nyc-tlc.md) |
| `noaa-ghcn-usw00094728.dvc` | NOAA GHCN-Daily, Central Park | [noaa-ghcn](../docs/data-registry/noaa-ghcn.md) |
| `uci-online-retail-ii.dvc` | UCI Online Retail II | [uci-online-retail-ii](../docs/data-registry/uci-online-retail-ii.md) |
| `cvrplib-solomon-100.dvc` | CVRPLIB Solomon VRPTW (SINTEF mirror) | [cvrplib-solomon](../docs/data-registry/cvrplib-solomon.md) |
| `ag-news-train.dvc` | AG News (HF auto-converted parquet) | [ag-news](../docs/data-registry/ag-news.md) |
| `wikipedia-20231101-en-0000.dvc` | Wikipedia 20231101.en (HF, shard 0) | [wikipedia](../docs/data-registry/wikipedia.md) |
| `hillstrom.csv.dvc` | Hillstrom email marketing (MineThatData, author's site) | [hillstrom](../docs/data-registry/hillstrom.md) |
| `telco-churn.dvc` | Telco churn, IBM sample (IBM mirror) | [telco-churn](../docs/data-registry/telco-churn.md) |

## Usage

```bash
dvc update registry/            # refresh version metadata for all imports
dvc update registry/<name>.dvc  # refresh one
```

Upstream changed? The card's checksum gate in the project prepare stage fails loudly
first; the manifest refresh records the new version deliberately.
