# UCI Online Retail II

- **Canonical source:** https://archive.ics.uci.edu/dataset/502/online+retail+ii
- **License/terms:** Free for research use; cite Daqing Chen et al. (2012),
  "Data mining for the online retail industry".
- **Used by:** Project 02 (optional real-data track; synthetic hierarchy is the
  default so CI stays offline)
- **Size:** ~1.07M transactions, UK e-commerce, 2009–2011 (two Excel sheets).

## Snapshot policy

UCI archives are stable; the download URL and expected size are pinned in
`scripts/fetch_retail.py`. Checksum verification on fetch is mandatory.

| Field | Value |
|---|---|
| Snapshot date | 2026-10-12 |
| Format | XLSX (two sheets: 2009–2010, 2010–2011) |

## Access

```bash
uv run python docs/data-registry/scripts/fetch_retail.py --dest data/02/raw
```
