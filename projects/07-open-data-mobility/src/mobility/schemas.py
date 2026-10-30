"""Pydantic contracts for every cross-stage dataframe (ADR-0002).

Each model documents the physical columns of one parquet dataset and enforces
the sanity ranges the DQ gates rely on. Unit conventions:

- distances are kilometres (TLC ships miles; converted at validate time),
- temperatures are degrees Celsius (GHCN ships tenths; converted at join time),
- precipitation/snow are millimetres (GHCN ships tenths of mm).
"""

from datetime import date, datetime

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, model_validator


class Trip(PortfolioBaseModel):
    """Validated, unit-normalised trip record (subset of TLC yellow columns).

    Field names are the validated parquet's column names (TLC's
    ``tpep_*_datetime``/``*LocationID`` renamed at validate time).
    """

    pickup_ts: datetime
    dropoff_ts: datetime
    pulocation_id: int = Field(ge=1, le=265)
    dolocation_id: int = Field(ge=1, le=265)
    passenger_count: int = Field(ge=0, le=8)
    trip_distance_km: float = Field(ge=0.0, le=400.0, description="0-400 km sanity bound")
    fare_amount: float = Field(ge=0.0)
    duration_min: float = Field(ge=0.0, description="Trip length in minutes")

    @model_validator(mode="after")
    def _dropoff_after_pickup(self) -> "Trip":
        if self.dropoff_ts < self.pickup_ts:
            raise ValueError("dropoff before pickup")
        return self


class Zone(PortfolioBaseModel):
    """Taxi zone reference row (taxi_zone_lookup.csv)."""

    location_id: int = Field(ge=1, le=265)
    borough: str = Field(min_length=1)
    zone: str = Field(min_length=1)


class WeatherDay(PortfolioBaseModel):
    """Daily GHCN-Daily observations for Central Park, QC-failed values null.

    Measurement fields are optional: the by-station file spans 1869-present
    and early decades genuinely lack some elements. Units are converted from
    GHCN tenths (PRCP mm, TMAX/TMIN °C; SNOW is whole mm).
    """

    date: date
    prcp_mm: float | None = Field(default=None, ge=0.0)
    tmax_c: float | None = Field(default=None, ge=-60.0, le=60.0)
    tmin_c: float | None = Field(default=None, ge=-60.0, le=60.0)
    snow_mm: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _max_ge_min(self) -> "WeatherDay":
        if self.tmax_c is not None and self.tmin_c is not None and self.tmax_c < self.tmin_c:
            raise ValueError("tmax_c below tmin_c")
        return self


class ZoneHourDemand(PortfolioBaseModel):
    """Curated grain: one row per (zone, hour) with weather context."""

    zone_id: int = Field(ge=1, le=265)
    borough: str = Field(min_length=1)
    ts: datetime
    pickup_count: int = Field(ge=0)
    prcp_mm: float | None = Field(default=None, ge=0.0)
    tmax_c: float | None = Field(default=None, ge=-60.0, le=60.0)
    tmin_c: float | None = Field(default=None, ge=-60.0, le=60.0)
    snow_mm: float | None = Field(default=None, ge=0.0)


class DemandRow(PortfolioBaseModel):
    """Feature-matrix row: lags + calendar + weather, target = next-hour pickups.

    ``target`` is the pickup count of the hour *after* ``ts`` (one-step-ahead
    nowcasting horizon), per DESIGN.md §Feature engineering.
    """

    zone_id: int = Field(ge=1, le=265)
    borough: str = Field(min_length=1)
    ts: datetime
    lag_1: float = Field(ge=0.0)
    lag_2: float = Field(ge=0.0)
    lag_24: float = Field(ge=0.0)
    lag_168: float = Field(ge=0.0)
    hour: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=1, le=7)
    month: int = Field(ge=1, le=12)
    prcp_mm: float | None = Field(default=None, ge=0.0)
    tmax_c: float | None = Field(default=None, ge=-60.0, le=60.0)
    tmin_c: float | None = Field(default=None, ge=-60.0, le=60.0)
    snow_mm: float | None = Field(default=None, ge=0.0)
    target: int = Field(ge=0)


class ServiceEntry(PortfolioBaseModel):
    """One per-service bundle in the serving registry (``services.json``).

    ``dir`` is the bundle directory relative to ``reports/models/serving/``
    (``"."`` = the root yellow bundle). Every listed bundle obeys the same
    three-file contract as the root (SERVING.md), so the showcase API loader
    can serve any entry from its directory unchanged.
    """

    dir: str = Field(min_length=1)
    train_runs: list[str] = Field(min_length=1)
    n_features: int = Field(gt=0)
    built_at: str = Field(min_length=1)


class ServingRegistry(PortfolioBaseModel):
    """Typed index of the per-service bundles under ``reports/models/serving/``."""

    services: dict[str, ServiceEntry] = Field(min_length=1)


class ServiceForecast(PortfolioBaseModel):
    """Typed response of :func:`mobility.serving.predict_service`.

    Field-for-field the showcase API's forecast response plus the service
    name; the mobility-side function is the reference implementation the API
    mirrors (apps/showcase-api serves the yellow bundle at the root path).
    """

    service: str = Field(min_length=1)
    zone_id: int = Field(ge=1)
    borough: str = Field(min_length=1)
    zone: str = Field(min_length=1)
    prediction: float = Field(ge=0.0)
    p90: float = Field(ge=0.0)
