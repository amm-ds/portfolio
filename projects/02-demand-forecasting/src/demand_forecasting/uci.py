"""UCI Online Retail II real-data track (wave 7).

Downloads the ~45 MB XLSX snapshot via the platform's checksum-pinned fetch,
streams the *Year 2009-2010* sheet with a dependency-free parser (stdlib
zipfile + iterparse — no openpyxl/pandas-excel in the venv), and aggregates
transactions to a daily store-product panel matching the synthetic schema:

- ``store``  = top ``uci_n_stores`` countries by unit volume,
- ``product`` = top ``uci_n_products`` stock codes by unit volume,
- ``units``  = daily sum of positive-quantity sales lines (returns and
  cancellations excluded; documented — returns are a separate business
  process, and net-of-returns demand double-counts reverse logistics),
- missing day-series combinations reindexed to the full calendar and filled
  with 0 (true zero demand — this is *intermittent* demand, unlike the
  synthetic panel, and the models must live with it).

The synthetic track stays the default so CI remains fully offline.
"""

import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET

import polars as pl
from portfolio_core.io import fetch, sha256_of
from portfolio_core.logging import get_logger

from demand_forecasting.config import DemandSettings, ForecastConfig

logger = get_logger(__name__)

UCI_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
UCI_SHEET = "Year 2009-2010"
ZIP_XLSX = "online retail ii.xlsx"
_COL_RE = re.compile(r"([A-Z]+)")
_EPOCH = date(1899, 12, 30)  # Excel serial day zero
_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}relationshi"
_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

# expected columns of the sheet, mapped by header name
_WANT = ["InvoiceDate", "StockCode", "Quantity", "Price", "Country"]


def fetch_uci(settings: DemandSettings, config: ForecastConfig) -> Path:
    """Download + unzip the pinned snapshot; returns the xlsx path.

    The pin is verified *before* fetching so cached snapshots are reused
    fully offline; a changed upstream file fails loudly.
    """
    raw_dir = settings.data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "online_retail_ii.zip"
    if (
        config.uci_checksum_sha256
        and zip_path.exists()
        and sha256_of(zip_path) != config.uci_checksum_sha256.lower()
    ):
        raise ValueError(
            f"UCI snapshot checksum changed: {sha256_of(zip_path)}. "
            "Update params.yaml deliberately."
        )
    zip_path = fetch(UCI_URL, zip_path, expected_sha256=config.uci_checksum_sha256)
    xlsx_path = raw_dir / ZIP_XLSX
    if not xlsx_path.exists():
        logger.info("unzipping %s", zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".xlsx")]
            if not names:
                raise ValueError(f"no xlsx inside {zip_path}")
            xlsx_path.write_bytes(zf.read(names[0]))
    checksum = sha256_of(zip_path)
    logger.info("uci snapshot sha256=%s", checksum)
    return xlsx_path


def _column_index(cell_ref: str) -> int:
    """'AB12' -> zero-based column index 27."""
    match = _COL_RE.match(cell_ref)
    if match is None:
        return 0
    letters = match.group(1)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _sheet_target(zf: zipfile.ZipFile, sheet_name: str) -> str:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    for sheet in wb.iter(_MAIN_NS + "sheet"):
        if sheet.get("name") == sheet_name:
            rid = sheet.get(_REL_ID)
            target = relmap[rid] if rid is not None else None
            if target is None:
                break
            return target.lstrip("/") if target.startswith("xl/") else f"xl/{target}"
    available = [s.get("name") for s in wb.iter(_MAIN_NS + "sheet")]
    raise ValueError(f"sheet {sheet_name!r} not found; available: {available}")


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        fh = zf.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    out: list[str] = []
    with fh:
        for _, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag == _MAIN_NS + "si":
                out.append("".join(t.text or "" for t in elem.iter(_MAIN_NS + "t")))
                elem.clear()
    return out


def _parse_date(value: Any) -> date | None:
    if isinstance(value, float):
        return _EPOCH + timedelta(days=int(value))
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def iter_sheet_rows(xlsx_path: Path, sheet_name: str) -> Any:
    """Yield rows (lists of cell values, shared strings resolved) of a sheet."""
    with zipfile.ZipFile(xlsx_path) as zf:
        shared = _shared_strings(zf)
        target = _sheet_target(zf, sheet_name)
        with zf.open(target) as fh:
            for _, elem in ET.iterparse(fh, events=("end",)):
                if elem.tag != _MAIN_NS + "row":
                    continue
                cells: dict[int, Any] = {}
                for c in elem.iter(_MAIN_NS + "c"):
                    ref = c.get("r", "A1")
                    v = c.find(_MAIN_NS + "v")
                    if v is None or v.text is None:
                        continue
                    kind = c.get("t")
                    if kind == "s":
                        cells[_column_index(ref)] = shared[int(v.text)]
                    elif kind in ("str", "inlineStr"):
                        cells[_column_index(ref)] = v.text
                    else:
                        try:
                            cells[_column_index(ref)] = float(v.text)
                        except ValueError:
                            cells[_column_index(ref)] = v.text
                if cells:
                    width = max(cells) + 1
                    yield [cells.get(i, "") for i in range(width)]
                elem.clear()


def transactions_to_panel(
    transactions: pl.DataFrame, n_stores: int, n_products: int
) -> pl.DataFrame:
    """Aggregate raw transactions to the bounded daily store-product panel.

    ``transactions`` columns: date, stock_code, quantity, unit_price, country.
    Sales lines only (quantity > 0); top countries/stock codes by volume;
    reindexed to a complete daily calendar with zero fill (intermittent demand).
    """
    tx = transactions.filter(
        (pl.col("quantity") > 0)
        & pl.col("stock_code").is_not_null()
        & (pl.col("stock_code").cast(pl.String).str.strip_chars() != "")
    )
    top_stores = (
        tx.group_by("country")
        .agg(pl.col("quantity").sum().alias("vol"))
        .sort("vol", descending=True)
        .head(n_stores)["country"]
        .to_list()
    )
    top_products = (
        tx.group_by("stock_code")
        .agg(pl.col("quantity").sum().alias("vol"))
        .sort("vol", descending=True)
        .head(n_products)["stock_code"]
        .to_list()
    )
    tx = tx.filter(pl.col("country").is_in(top_stores) & pl.col("stock_code").is_in(top_products))
    daily = tx.group_by(["date", "country", "stock_code"]).agg(
        pl.col("quantity").sum().alias("units"),
        pl.col("unit_price").mean().alias("price"),
    )
    lo = cast(date, daily["date"].min())
    hi = cast(date, daily["date"].max())
    n_days = (hi - lo).days + 1
    grid = pl.DataFrame({"date": pl.date_range(lo, hi, eager=True)}).with_columns(
        pl.lit(0, dtype=pl.Int8).alias("key")
    )
    series = (
        daily.select(["country", "stock_code"])
        .unique()
        .with_columns(pl.lit(0, dtype=pl.Int8).alias("key"))
    )
    full = (
        grid.join(series, on="key", how="inner")
        .join(
            daily.with_columns(
                pl.col("stock_code").cast(pl.String), pl.col("country").cast(pl.String)
            ),
            on=["date", "country", "stock_code"],
            how="left",
        )
        .with_columns(
            pl.col("units").fill_null(0).cast(pl.Int64),
            pl.col("price").fill_null(strategy="forward").fill_null(0.0),
        )
        .drop("key")
        .rename({"country": "store", "stock_code": "product"})
        .sort(["date", "store", "product"])
    )
    logger.info(
        "uci panel: %d rows, %d series, %d days (%s..%s), %d tx used",
        full.height,
        full["store"].n_unique() * full["product"].n_unique(),
        n_days,
        lo,
        hi,
        tx.height,
    )
    return full.select(["date", "store", "product", "units", "price"])


def build_uci_panel(settings: DemandSettings, config: ForecastConfig) -> pl.DataFrame:
    """Fetch (once), stream-parse the sheet and build the daily panel."""
    xlsx_path = fetch_uci(settings, config)
    rows = iter(iter_sheet_rows(xlsx_path, UCI_SHEET))
    header = next(rows)
    col = {name: header.index(name) for name in _WANT}

    dates: list[date] = []
    codes: list[str] = []
    qty: list[float] = []
    price: list[float] = []
    country: list[str] = []
    n_bad = 0
    for row in rows:
        try:
            d = _parse_date(row[col["InvoiceDate"]])
            q = float(row[col["Quantity"]])
            p = float(row[col["Price"]])
            c = str(row[col["Country"]]).strip()
            raw_code = row[col["StockCode"]]
            s = (
                str(int(raw_code))
                if isinstance(raw_code, float) and raw_code.is_integer()
                else str(raw_code).strip()
            )
        except (IndexError, TypeError, ValueError):
            n_bad += 1
            continue
        if d is None or not c or not s:
            n_bad += 1
            continue
        dates.append(d)
        codes.append(s)
        qty.append(q)
        price.append(p)
        country.append(c)
    logger.info("parsed %d transactions (%d skipped)", len(dates), n_bad)
    transactions = pl.DataFrame(
        {
            "date": dates,
            "stock_code": codes,
            "quantity": qty,
            "unit_price": price,
            "country": country,
        }
    )
    return transactions_to_panel(transactions, config.uci_n_stores, config.uci_n_products)
