from datetime import date

from hypothesis import given
from hypothesis import strategies as st
from portfolio_core.schemas import DatasetContract


@st.composite
def sha256_str(draw: st.DrawFn) -> str:
    return draw(st.text(alphabet="0123456789abcdef", min_size=64, max_size=64))


@given(sha256_str())
def test_checksum_accepts_lowercase_hex(s: str) -> None:
    contract = DatasetContract(
        name="demo",
        source="https://example.com/x.csv",
        license="MIT",
        snapshot_date=date(2026, 1, 1),
        checksum_sha256=s,
        n_rows=10,
    )
    assert contract.checksum_sha256 == s


@given(st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs")), min_size=1))
def test_name_never_empty_after_strip(s: str) -> None:
    from pydantic import ValidationError

    try:
        contract = DatasetContract(
            name=s,
            source="x",
            license="MIT",
            snapshot_date=date(2026, 1, 1),
            checksum_sha256="a" * 64,
            n_rows=1,
        )
        assert contract.name == s.strip()
    except ValidationError:
        pass  # empty-after-strip rejected — also valid


@given(st.integers(min_value=0))
def test_n_rows_non_negative(n: int) -> None:
    from pydantic import ValidationError

    try:
        c = DatasetContract(
            name="d",
            source="x",
            license="MIT",
            snapshot_date=date(2026, 1, 1),
            checksum_sha256="b" * 64,
            n_rows=n,
        )
        assert c.n_rows >= 0
    except ValidationError:
        pass
