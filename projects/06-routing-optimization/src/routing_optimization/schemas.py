"""Pydantic problem and solution models for the VRPTW (ADR-0002).

All cross-module boundaries use these models. ``RoutePlan.validate_against``
is the hard gate every solver output must pass: every customer served exactly
once and per-route capacity respected.
"""

from collections import Counter

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, field_validator, model_validator

_EPS = 1e-9


class Customer(PortfolioBaseModel):
    """One VRPTW customer; customer 0 is the depot with zero demand."""

    id: int = Field(ge=0)
    x: float
    y: float
    demand: float = Field(ge=0)
    ready_time: float = Field(
        ge=0, description="Earliest service start; the vehicle waits if early."
    )
    due_time: float = Field(ge=0, description="Latest service start.")
    service_time: float = Field(ge=0)

    @field_validator("x", "y", "demand", "ready_time", "due_time", "service_time", mode="before")
    @classmethod
    def _coerce_float(cls, v: object) -> object:
        return float(v) if isinstance(v, int) else v

    @model_validator(mode="after")
    def _time_window_consistent(self) -> "Customer":
        if self.due_time < self.ready_time - _EPS:
            raise ValueError(
                f"customer {self.id}: due_time {self.due_time} < ready_time {self.ready_time}"
            )
        return self


class Problem(PortfolioBaseModel):
    """A parsed VRPTW instance: customers (depot first) plus fleet parameters."""

    name: str = Field(min_length=1)
    customers: list[Customer] = Field(min_length=1)
    vehicle_capacity: float = Field(gt=0)
    max_vehicles: int = Field(
        default=25, ge=1, description="Fleet size stated by the instance file."
    )

    @model_validator(mode="after")
    def _ids_are_zero_based_and_unique(self) -> "Problem":
        ids = [c.id for c in self.customers]
        if ids[0] != 0:
            raise ValueError("customers[0] must be the depot with id 0")
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate customer ids")
        if sorted(ids) != list(range(len(ids))):
            raise ValueError("customer ids must be the consecutive range 0..n-1")
        return self

    @property
    def depot(self) -> Customer:
        """The depot (first customer, id 0)."""
        return self.customers[0]

    @property
    def customer_ids(self) -> list[int]:
        """All ids including the depot, in file order."""
        return [c.id for c in self.customers]

    @property
    def n_customers(self) -> int:
        """Number of customers excluding the depot."""
        return len(self.customers) - 1


class RoutePlan(PortfolioBaseModel):
    """A candidate solution: customer ids per route (depot legs implied)."""

    instance: str = Field(min_length=1)
    solver: str = Field(min_length=1)
    routes: list[list[int]] = Field(min_length=1)
    total_distance: float = Field(ge=0)
    n_vehicles: int = Field(ge=1)

    def validate_against(self, problem: Problem) -> None:
        """Raise ``ValueError`` unless the plan is structurally valid.

        Checks: no empty routes, every customer served exactly once, no unknown
        ids, and per-route demand within vehicle capacity.
        """
        errors: list[str] = []
        if self.n_vehicles != len(self.routes):
            errors.append(f"n_vehicles={self.n_vehicles} != len(routes)={len(self.routes)}")

        known = set(problem.customer_ids)
        served = [cid for route in self.routes for cid in route]
        counts = Counter(served)

        duplicates = sorted(cid for cid, n in counts.items() if n > 1)
        if duplicates:
            errors.append(f"customers served more than once: {duplicates}")
        missing = sorted(known - set(served) - {0})
        if missing:
            errors.append(f"customers never served: {missing}")
        unknown = sorted(set(served) - known)
        if unknown:
            errors.append(f"unknown customer ids: {unknown}")
        if any(cid == 0 for cid in served):
            errors.append("depot (id 0) must not appear inside routes")

        for k, route in enumerate(self.routes):
            if not route:
                errors.append(f"empty route at index {k}")
                continue
            known_route = [cid for cid in route if cid in known]
            load = sum(problem.customers[cid].demand for cid in known_route)
            if load > problem.vehicle_capacity + _EPS:
                errors.append(
                    f"route {k} load {load:g} exceeds capacity {problem.vehicle_capacity:g}"
                )

        if errors:
            raise ValueError(f"invalid route plan for {self.instance}: {'; '.join(errors)}")
