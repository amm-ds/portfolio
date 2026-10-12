"""Schema validators accept valid rows and reject out-of-range ones."""

from datetime import datetime
from typing import Any

import pytest
from mobility.schemas import DemandRow, Trip, WeatherDay, Zone, ZoneHourDemand
from pydantic import ValidationError

_TS = datetime(2024, 1, 1, 12, 0, 0)


def _trip_kwargs(**over: Any) -> Any:
    base: dict[str, Any] = {
        "pickup_ts": _TS,
        "dropoff_ts": _TS.replace(hour=13),
        "pulocation_id": 100,
        "dolocation_id": 200,
        "passenger_count": 2,
        "trip_distance_km": 10.5,
        "fare_amount": 30.0,
        "duration_min": 60.0,
    }
    base.update(over)
    return base


def test_trip_valid() -> None:
    assert Trip(**_trip_kwargs()).passenger_count == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("passenger_count", 9),
        ("passenger_count", -1),
        ("trip_distance_km", 401.0),
        ("trip_distance_km", -0.1),
        ("fare_amount", -1.0),
        ("pulocation_id", 0),
        ("pulocation_id", 266),
    ],
)
def test_trip_rejects_out_of_range(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Trip(**_trip_kwargs(**{field: value}))


def test_trip_rejects_dropoff_before_pickup() -> None:
    with pytest.raises(ValidationError):
        Trip(**_trip_kwargs(dropoff_ts=_TS.replace(hour=11)))


def test_zone_and_zone_hour_demand_contracts() -> None:
    assert Zone(location_id=1, borough="Manhattan", zone="Midtown").borough == "Manhattan"
    with pytest.raises(ValidationError):
        Zone(location_id=0, borough="Manhattan", zone="Midtown")
    row = ZoneHourDemand(
        zone_id=5,
        borough="Queens",
        ts=_TS,
        pickup_count=7,
        prcp_mm=1.0,
        tmax_c=9.0,
        tmin_c=1.0,
        snow_mm=0.0,
    )
    assert row.pickup_count == 7
    with pytest.raises(ValidationError):
        ZoneHourDemand(zone_id=5, borough="Queens", ts=_TS, pickup_count=-1)


def test_weather_day_contract() -> None:
    day = WeatherDay(date=_TS.date(), prcp_mm=5.5, tmax_c=11.0, tmin_c=3.0, snow_mm=20.0)
    assert day.tmax_c == 11.0
    with pytest.raises(ValidationError):
        WeatherDay(date=_TS.date(), prcp_mm=-1.0, tmax_c=11.0, tmin_c=3.0, snow_mm=0.0)
    with pytest.raises(ValidationError):  # tmax below tmin
        WeatherDay(date=_TS.date(), prcp_mm=0.0, tmax_c=1.0, tmin_c=3.0, snow_mm=0.0)


def test_demand_row_contract() -> None:
    row = DemandRow(
        zone_id=1,
        borough="Manhattan",
        ts=_TS,
        lag_1=1.0,
        lag_2=2.0,
        lag_24=3.0,
        lag_168=4.0,
        hour=12,
        day_of_week=1,
        month=1,
        prcp_mm=None,
        tmax_c=None,
        tmin_c=None,
        snow_mm=None,
        target=9,
    )
    assert row.target == 9
    with pytest.raises(ValidationError):
        DemandRow(
            zone_id=1,
            borough="Manhattan",
            ts=_TS,
            lag_1=1.0,
            lag_2=2.0,
            lag_24=3.0,
            lag_168=4.0,
            hour=25,
            day_of_week=1,
            month=1,
            target=9,
        )
