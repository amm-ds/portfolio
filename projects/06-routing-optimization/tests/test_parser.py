"""Parser tests: inline 5-customer instance plus hypothesis round-trips."""

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from routing_optimization.parser import parse_solomon, parse_solomon_file
from routing_optimization.schemas import Customer


def test_parse_tiny_instance(tiny_text: str) -> None:
    problem = parse_solomon(tiny_text)
    assert problem.name == "TINY"
    assert problem.vehicle_capacity == 60.0
    assert problem.max_vehicles == 5
    assert problem.n_customers == 5
    assert problem.depot.id == 0 and problem.depot.demand == 0.0
    assert [c.id for c in problem.customers] == [0, 1, 2, 3, 4, 5]
    assert problem.customers[2].x == 50.0 and problem.customers[2].y == 52.0
    assert problem.customers[5].ready_time == 0.0
    assert problem.customers[5].due_time == 500.0
    assert problem.customers[1].service_time == 10.0


def test_parse_uses_name_override(tiny_text: str) -> None:
    problem = parse_solomon(tiny_text, name="OVERRIDE")
    assert problem.name == "OVERRIDE"


def test_parse_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_solomon("")
    with pytest.raises(ValueError, match="NUMBER/CAPACITY"):
        parse_solomon("just a name\nand nothing else")


def test_parse_solomon_file_uses_file_stem(tiny_text: str, tmp_path: Path) -> None:
    path = tmp_path / "c101.txt"
    path.write_text(tiny_text)
    problem = parse_solomon_file(path)
    assert problem.name == "c101"


_customer_fields = st.tuples(
    st.integers(min_value=1, max_value=100),  # x
    st.integers(min_value=0, max_value=100),  # y
    st.integers(min_value=0, max_value=50),  # demand
    st.integers(min_value=0, max_value=500),  # ready
    st.integers(min_value=0, max_value=500),  # window width
    st.integers(min_value=0, max_value=50),  # service
)


@given(st.lists(_customer_fields, min_size=1, max_size=20, unique_by=lambda t: t[:2]))
def test_parser_roundtrip_numeric_rows(fields: list[tuple[int, ...]]) -> None:
    """Every generated customer row must survive parsing with identical values."""
    # Re-key ids to the consecutive range 1..n (the Problem contract) and keep
    # the (x, y) pair unique so ordering is deterministic.
    ordered = sorted(fields)
    lines = [
        f"{i} {x} {y} {demand} {ready} {ready + width} {service}"
        for i, (x, y, demand, ready, width, service) in enumerate(ordered, start=1)
    ]
    body = "0 0 0 0 0 1000 0\n" + "\n".join(lines)
    problem = parse_solomon(
        f"PROP\n\nVEHICLE\nNUMBER     CAPACITY\n  25      200\n\nCUSTOMER\n{body}"
    )
    expected = [ln.split() for ln in lines]
    parsed = [
        [
            str(c.id),
            f"{c.x:g}",
            f"{c.y:g}",
            f"{c.demand:g}",
            f"{c.ready_time:g}",
            f"{c.due_time:g}",
            f"{c.service_time:g}",
        ]
        for c in problem.customers[1:]
    ]
    assert parsed == expected


@given(
    st.integers(min_value=0, max_value=10_000),
    st.integers(min_value=0, max_value=10_000),
    st.integers(min_value=0, max_value=10_000),
)
def test_customer_rejects_inverted_window(ready: int, due: int, service: int) -> None:
    if due < ready:
        with pytest.raises(ValueError):
            Customer(
                id=1, x=0.0, y=0.0, demand=1.0, ready_time=ready, due_time=due, service_time=service
            )
    else:
        Customer(
            id=1, x=0.0, y=0.0, demand=1.0, ready_time=ready, due_time=due, service_time=service
        )
