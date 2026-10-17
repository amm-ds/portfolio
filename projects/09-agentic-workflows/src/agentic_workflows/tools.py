"""Research-ops toolsets: a deterministic synthetic domain for tool-using agents.

The domain is a fictional remote field-research station ("Atlas Valley").
Five typed tools give the agents everything they need — four over a small
canned handbook, plus ``search_documents`` for dense retrieval over project
01's Wikipedia corpus (read-only); a second, math-focused toolset shows
``PrefixedToolset`` composition — two toolsets combined in one agent with
zero name collisions.

Everything here is pure and offline: the handbook corpus is in-code, search
scores are keyword overlap, the document corpus is a pre-built local FAISS
index, and the calculator is a locked-down AST evaluator. Ground truths in
the eval suite are therefore exact, not model-judged.
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from typing import Literal

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import CombinedToolset, FunctionToolset, PrefixedToolset

from agentic_workflows.documents import search_documents

# ---------------------------------------------------------------------------
# Canned domain corpus ("Atlas Valley Field Station — ops handbook")
# ---------------------------------------------------------------------------


class HandbookDoc(PortfolioBaseModel):
    """One document of the deterministic search corpus."""

    doc_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    body: str = Field(min_length=1)


HANDBOOK: tuple[HandbookDoc, ...] = (
    HandbookDoc(
        doc_id="gen-fuel",
        title="Generator fuel consumption",
        keywords=["generator", "diesel", "fuel", "consumption", "burns", "tank"],
        body=(
            "The prime diesel generator burns 1.8 L/h under full load and is "
            "scheduled to run 6 h/day. Its onboard fuel tank holds 240 L."
        ),
    ),
    HandbookDoc(
        doc_id="fuel-reserve",
        title="Fuel reserve policy",
        keywords=["fuel", "reserve", "policy", "resupply", "runtime"],
        body=(
            "Station policy requires a minimum fuel reserve of 72 h of generator "
            "runtime at full load; resupply is ordered as soon as stocks drop "
            "below that figure."
        ),
    ),
    HandbookDoc(
        doc_id="solar-spec",
        title="Solar array output",
        keywords=["solar", "panel", "array", "yield", "kwh", "inverter"],
        body=(
            "Each 320 Wp panel delivers an average yield of 3.2 kWh/day in the "
            "valley. The array has 12 panels; the inverter runs at 96% efficiency."
        ),
    ),
    HandbookDoc(
        doc_id="drone",
        title="Survey drone operations",
        keywords=["drone", "payload", "flight", "range", "wind", "survey"],
        body=(
            "The survey drone carries a maximum payload of 2.5 kg, flies for up "
            "to 42 min per charge and has a rated range of 8 km. Pre-flight "
            "checks require wind below 12 m/s."
        ),
    ),
    HandbookDoc(
        doc_id="satellite-window",
        title="Satellite comms windows",
        keywords=["satellite", "uplink", "window", "transfer", "mb", "bandwidth"],
        body=(
            "Satellite uplink windows open daily at 06:10-06:40 and 18:20-18:50 "
            "UTC. Each window can transfer at most 250 MB."
        ),
    ),
    HandbookDoc(
        doc_id="data-budget",
        title="Science data budget",
        keywords=["data", "science", "mb", "compression", "uplink", "budget"],
        body=(
            "Instruments produce 1,800 MB of science data per day. Data is "
            "compressed 4:1 before satellite uplink."
        ),
    ),
    HandbookDoc(
        doc_id="water",
        title="Water storage and budget",
        keywords=["water", "tank", "storage", "liters", "consumption", "crew"],
        body=(
            "The main water tank holds 5,000 L and the secondary bladder holds "
            "1,200 L. The consumption budget is 85 L per person per day for a "
            "crew of 6."
        ),
    ),
    HandbookDoc(
        doc_id="cache",
        title="Supply caches",
        keywords=["cache", "ration", "packs", "supplies", "km", "alpha", "bravo"],
        body=(
            "Cache Alpha sits at km 4.2 north and holds 40 ration packs; cache "
            "Bravo sits at km 7.8 north and holds 25 ration packs. Each ration "
            "pack weighs 0.6 kg."
        ),
    ),
    HandbookDoc(
        doc_id="battery",
        title="Battery bank",
        keywords=["battery", "bank", "kwh", "load", "overnight", "hvac"],
        body=(
            "The LiFePO4 battery bank provides 24 kWh of usable capacity. "
            "Overnight base load is 1.6 kW for 8 h; the HVAC surge adds 0.9 kW "
            "for about 3 h."
        ),
    ),
    HandbookDoc(
        doc_id="radio",
        title="Radio protocol",
        keywords=["radio", "channel", "check-in", "frequency", "call", "sign"],
        body=(
            "Hourly check-ins use channel 3 at 146.46 MHz. Channel 1 is "
            "reserved for emergencies. The base call sign is 'Atlas Base'."
        ),
    ),
    HandbookDoc(
        doc_id="weather-cal",
        title="Weather station calibration",
        keywords=["weather", "calibration", "calibrate", "days", "drift"],
        body=(
            "The weather station must be calibrated every 45 days. The accepted "
            "temperature drift tolerance is +/-0.4 °C between calibrations."
        ),
    ),
    HandbookDoc(
        doc_id="cold-storage",
        title="Sample cold storage",
        keywords=["freezer", "sample", "storage", "setpoint", "alarm", "boxes"],
        body=(
            "The sample freezer setpoint is -20 °C with an alarm band of +/-3 "
            "°C. It stores up to 180 sample boxes."
        ),
    ),
)

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "per",
        "is",
        "are",
        "what",
        "how",
        "many",
        "much",
        "does",
        "do",
        "and",
        "for",
        "at",
        "on",
        "it",
        "its",
        "that",
        "this",
        "with",
        "holds",
    }
)


def _tokens(text: str) -> list[str]:
    return [t.strip(".,?;:!()°+/-") for t in text.lower().split()]


# ---------------------------------------------------------------------------
# Agent dependencies
# ---------------------------------------------------------------------------


@dataclass
class Notebook:
    """Per-run working memory for the ``note_store`` tool."""

    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Research-ops tools (toolset 1)
# ---------------------------------------------------------------------------


_BIN_OPS: dict[type[ast.operator], object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY_OPS: dict[type[ast.unaryop], object] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculator(expr: str) -> float:
    """Evaluate a basic arithmetic expression (+ - * / ** % and parentheses).

    Only numeric literals and arithmetic operators are allowed; anything else
    (names, calls, attribute access) is rejected.

    Args:
        expr: Arithmetic expression, e.g. "(2400 + 380) / 7".

    Returns:
        The numeric result.
    """
    tree = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 64:
                raise ValueError("exponent too large")
            return float(_BIN_OPS[type(node.op)](left, right))  # type: ignore[operator]
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return float(_UNARY_OPS[type(node.op)](_eval(node.operand)))  # type: ignore[operator]
        raise ValueError(f"unsupported expression element: {ast.dump(node)}")

    result = _eval(tree)
    return round(result, 6)


# Conversion factors expressed relative to a canonical unit.
_CONVERSIONS: dict[str, dict[str, float]] = {
    "length": {"km": 1000.0, "m": 1.0, "mi": 1609.344, "ft": 0.3048},
    "mass": {"kg": 1.0, "lb": 0.45359237, "g": 0.001},
    "volume": {"l": 1.0, "gal": 3.785411784, "ml": 0.001},
}
_UNIT_ALIASES = {
    "kilometer": "km",
    "kilometers": "km",
    "mile": "mi",
    "miles": "mi",
    "meter": "m",
    "meters": "m",
    "foot": "ft",
    "feet": "ft",
    "kilogram": "kg",
    "kilograms": "kg",
    "pound": "lb",
    "pounds": "lb",
    "gram": "g",
    "grams": "g",
    "liter": "l",
    "liters": "l",
    "gallon": "gal",
    "gallons": "gal",
}


def _resolve_unit(unit: str) -> tuple[str, float]:
    """Return (dimension, factor to canonical unit) for a unit name."""
    u = _UNIT_ALIASES.get(unit.lower(), unit.lower())
    if u == "c" or u == "f":
        return ("temperature", 1.0)
    for dimension, table in _CONVERSIONS.items():
        if u in table:
            return (dimension, table[u])
    raise ValueError(f"unknown unit: {unit!r}")


def unit_convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a value between supported units.

    Supports length (km, m, mi, ft), mass (kg, lb, g), volume (l, gal, ml)
    and temperature (c, f).

    Args:
        value: Numeric value to convert.
        from_unit: Source unit (e.g. "km", "lb", "c").
        to_unit: Target unit (e.g. "mi", "kg", "f").

    Returns:
        The converted value, rounded to 4 decimals.
    """
    src_dim, src_factor = _resolve_unit(from_unit)
    dst_dim, dst_factor = _resolve_unit(to_unit)
    if src_dim != dst_dim:
        raise ValueError(f"cannot convert {from_unit!r} ({src_dim}) to {to_unit!r} ({dst_dim})")
    if src_dim == "temperature":
        if from_unit.lower() == "c" and to_unit.lower() == "f":
            return round(value * 9 / 5 + 32, 4)
        if from_unit.lower() == "f" and to_unit.lower() == "c":
            return round((value - 32) * 5 / 9, 4)
        return round(value, 4)
    return round(value * src_factor / dst_factor, 4)


def search_handbook(query: str, top_k: int = 3) -> list[str]:
    """Search the Atlas Valley ops handbook (deterministic keyword corpus).

    Ranking is keyword-overlap on the document title, keywords and body — the
    same query always returns the same order, so downstream ground truths are
    stable.

    Args:
        query: Natural-language question or topic.
        top_k: Maximum number of document snippets to return (1-5).

    Returns:
        Formatted snippets "doc_id — title: body", best match first.
    """
    k = max(1, min(top_k, 5))
    terms = [t for t in _tokens(query) if t not in _STOPWORDS and t]
    if not terms:
        terms = [t for t in _tokens(query) if t]
    scored: list[tuple[int, HandbookDoc]] = []
    for doc in HANDBOOK:
        haystack = f"{doc.title} {' '.join(doc.keywords)} {doc.body}".lower()
        score = sum(1 for t in terms if t in haystack)
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda pair: (-pair[0], pair[1].doc_id))
    return [f"{doc.doc_id} — {doc.title}: {doc.body}" for _, doc in scored[:k]]


def note_store(
    ctx: RunContext[Notebook], action: Literal["append", "list"], note: str = ""
) -> list[str]:
    """Append to or list the run's ops notebook (working memory across steps).

    Args:
        action: "append" to add a note, "list" to return all notes so far.
        note: The note to append (ignored for "list").

    Returns:
        The notebook contents after the action.
    """
    if action == "append":
        if not note.strip():
            raise ValueError("note must be non-empty when action='append'")
        ctx.deps.notes.append(note.strip())
    return list(ctx.deps.notes)


def research_ops_toolset() -> FunctionToolset[Notebook]:
    """The five research-ops tools as a reusable ``FunctionToolset``.

    ``search_documents`` is the cross-project arm: dense retrieval over
    project 01's Wikipedia corpus (read-only, see ``documents.py``).
    """
    return FunctionToolset(
        [calculator, unit_convert, search_handbook, search_documents, note_store]
    )


# ---------------------------------------------------------------------------
# Math helper toolset (toolset 2) — composed with a prefix, never colliding
# ---------------------------------------------------------------------------


def percent_change(old_value: float, new_value: float) -> float:
    """Percentage change from ``old_value`` to ``new_value``.

    Args:
        old_value: Baseline value (must be non-zero).
        new_value: New value to compare against the baseline.

    Returns:
        Percent change, rounded to 2 decimals (negative = decrease).
    """
    if old_value == 0:
        raise ValueError("old_value must be non-zero")
    return round((new_value - old_value) / old_value * 100, 2)


def round_to(value: float, digits: int = 2) -> float:
    """Round a number to ``digits`` decimal places.

    Args:
        value: The number to round.
        digits: Decimal places (0-6).

    Returns:
        The rounded value.
    """
    if not 0 <= digits <= 6:
        raise ValueError("digits must be between 0 and 6")
    return round(value, digits)


def math_toolset() -> FunctionToolset[Notebook]:
    """Small math helper toolset (intended for prefixed composition)."""
    return FunctionToolset([percent_change, round_to])


def composed_toolset() -> CombinedToolset[Notebook]:
    """Research-ops + math helper combined without name collisions.

    The math tools are wrapped in a ``PrefixedToolset`` so they surface as
    ``math_percent_change`` / ``math_round_to`` alongside the unprefixed
    research-ops tools — two independently authored toolsets in one agent.
    """
    return CombinedToolset([research_ops_toolset(), PrefixedToolset(math_toolset(), "math_")])
