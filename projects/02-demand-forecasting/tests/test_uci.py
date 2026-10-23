"""UCI track: stdlib xlsx parsing and transaction aggregation (offline fixtures)."""

import zipfile
from pathlib import Path

import polars as pl
import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.uci import _parse_date, iter_sheet_rows, transactions_to_panel
from pydantic import ValidationError


def _tiny_xlsx(path: Path) -> Path:
    """Minimal one-sheet xlsx with a shared-strings table (no dependencies)."""
    sheet = """<?xml version="1.0"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1"><v>1.5</v></c></row>
<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>7</v></c><c r="C2"><v>2.5</v></c></row>
</sheetData></worksheet>"""
    workbook = """<?xml version="1.0"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>"""
    rels = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="x" Target="worksheets/sheet1.xml"/>
</Relationships>"""
    shared = """<?xml version="1.0"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<si><t>hello</t></si><si><t>world</t></si><si><t>again</t></si></sst>"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
        zf.writestr("xl/sharedStrings.xml", shared)
    return path


def test_iter_sheet_rows_resolves_shared_strings(tmp_path: Path) -> None:
    rows = list(iter_sheet_rows(_tiny_xlsx(tmp_path / "t.xlsx"), "Sheet1"))
    assert rows[0][:2] == ["hello", "world"]
    assert rows[1][0] == "again"
    assert rows[1][1] == 7.0  # numeric cell


def test_parse_date_serial_and_strings() -> None:
    assert _parse_date(40148.0).isoformat() == "2009-12-01"  # Excel serial
    assert _parse_date("2010-01-05 13:42:00").isoformat() == "2010-01-05"
    assert _parse_date("07/02/2010 08:00").isoformat() == "2010-02-07"
    assert _parse_date("not a date") is None


def _transactions() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "date": ["2010-01-01", "2010-01-01", "2010-01-02", "2010-01-03", "2010-01-03"],
            "stock_code": ["A", "A", "A", "A", "B"],
            "quantity": [5.0, 3.0, -9.0, 4.0, 2.0],  # negative = return line
            "unit_price": [1.0, 1.0, 1.0, 1.0, 2.0],
            "country": ["UK", "UK", "UK", "UK", "FR"],
        },
        schema_overrides={"date": pl.Date},
    )


def test_transactions_to_panel_bounds_and_zero_fills() -> None:
    panel = transactions_to_panel(_transactions(), n_stores=1, n_products=1)
    # top store = UK (12 gross units), top product = A; returns excluded
    assert panel["store"].unique().to_list() == ["UK"]
    assert panel["product"].unique().to_list() == ["A"]
    assert panel.height == 3  # full 3-day calendar reindex
    assert panel["units"].to_list() == [8, 0, 4]  # returns excluded, gaps zero-filled
    assert panel.schema["units"] == pl.Int64


def test_data_source_validation() -> None:
    with pytest.raises(ValidationError):
        ForecastConfig(data_source="other")  # type: ignore[arg-type]
    assert ForecastConfig(data_source="uci").data_source == "uci"


def test_fetch_uci_rejects_changed_checksum(settings: DemandSettings) -> None:
    """A changed upstream snapshot must fail loudly against the pinned sha256."""
    from demand_forecasting.uci import ZIP_XLSX, fetch_uci

    raw = settings.data_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "online_retail_ii.zip").write_bytes(b"fake snapshot")
    (raw / ZIP_XLSX).write_bytes(b"fake xlsx")
    config = ForecastConfig(data_source="uci", uci_checksum_sha256="0" * 64)
    with pytest.raises(ValueError, match="checksum changed"):
        fetch_uci(settings, config)


def test_fetch_uci_cache_hit(settings: DemandSettings) -> None:
    """A cached snapshot matching the pin is used without re-downloading."""
    from demand_forecasting.uci import ZIP_XLSX, fetch_uci
    from portfolio_core.io import sha256_of

    raw = settings.data_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "online_retail_ii.zip").write_bytes(b"cached snapshot")
    (raw / ZIP_XLSX).write_bytes(b"cached xlsx")
    config = ForecastConfig(
        data_source="uci", uci_checksum_sha256=sha256_of(raw / "online_retail_ii.zip")
    )
    assert fetch_uci(settings, config).exists()


def test_dataset_metadata_documents_the_generating_process(
    settings: DemandSettings,
) -> None:
    """dataset_metadata.json states the filtering/aggregation/caveat, and the
    doc agrees with what transactions_to_panel actually does (P4 hardening)."""
    from demand_forecasting.uci import dataset_metadata, write_dataset_metadata

    config = ForecastConfig(data_source="uci")
    panel = transactions_to_panel(_transactions(), n_stores=1, n_products=1)
    meta = dataset_metadata(panel, config)

    # source + pin
    assert meta["source"]["url"].startswith("https://archive.ics.uci.edu")
    assert meta["source"]["sha256"] == config.uci_checksum_sha256
    assert meta["source"]["sheet"] == "Year 2009-2010"
    # the material doc/code agreement: sales lines only, cancellations removed
    assert "Quantity > 0" in meta["cancellation_filtering"]
    assert panel["units"].to_list() == [8, 0, 4]  # returns line (-9) excluded
    # geography + products bounded by config
    assert "Top 8 countries" in meta["geography"]
    assert "Top 200 stock codes" in meta["products"]
    # observed panel stats are computed from the frame itself
    assert meta["observed_panel"]["n_rows"] == panel.height
    assert meta["observed_panel"]["date_start"] == "2010-01-01"
    assert meta["observed_panel"]["date_end"] == "2010-01-03"
    # the explicit zero-demand caveat and the one-sentence target definition
    assert "no trading calendar" in meta["zero_sales_caveat"]
    target = meta["target_definition"]
    assert target.startswith("The forecast target is the next 14 days of daily units")
    assert "cancellations removed" in target

    out = write_dataset_metadata(settings, config, panel)
    assert out.exists()
    import json

    persisted = json.loads(out.read_text())
    assert persisted["source"]["sha256"] == config.uci_checksum_sha256
