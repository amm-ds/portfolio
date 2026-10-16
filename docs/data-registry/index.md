# Data registry

Every external dataset used in this portfolio has a card here: canonical source,
license/terms, snapshot date, checksum, size, access method, and which project
consumes it. Snapshots are content-pinned — `prepare` stages fail loudly on
checksum mismatch, turning silent upstream drift into explicit failures
(see the [drift-response runbook](../runbooks/drift-response.md)).

| Dataset | Card | License | Consumed by |
|---|---|---|---|
| NYC TLC Trip Records | [nyc-tlc](nyc-tlc.md) | NYC terms of use | 07 |
| NOAA GHCN-Daily | [noaa-ghcn](noaa-ghcn.md) | Public domain (US Gov) | 07 |
| UCI Online Retail II | [uci-online-retail-ii](uci-online-retail-ii.md) | Free for research | 02 (optional) |
| CVRPLIB — Solomon VRPTW | [cvrplib-solomon](cvrplib-solomon.md) | Academic benchmark | 06 |
| Telco churn (IBM sample) | [telco-churn](telco-churn.md) | IBM sample-data terms | 05 |
| AG News (HF) | [ag-news](ag-news.md) | Research purposes | 04 |
| NSL-KDD | [nsl-kdd](nsl-kdd.md) | Research benchmark (UNB CIC) | 03 |
| NAB (Numenta Anomaly Benchmark) | [nab](nab.md) | Research benchmark (cite Ahmad et al. 2017) | 03 (primary) |
| Wikipedia (HF) | [wikipedia](wikipedia.md) | CC BY-SA / GFDL (attribution required) | 01 |
| Hillstrom email marketing | [hillstrom](hillstrom.md) | MineThatData challenge data (research use, attribute) | 10 |

Access scripts live in `scripts/` next to the cards.
