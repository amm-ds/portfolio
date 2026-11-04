"""Request/response schemas mirroring experiment 12's feature contract exactly.

The contract (data/models/feature_contract.json) selects 15 numeric features;
`atemp` was pruned (r = 0.987 with `temp`), and raw `hour` feeds the embedding
index rather than the numeric trunk. Bounds are 12's DQ-gate ranges, so a
payload that passes here provably lies inside the training distribution's
envelope.
"""

from typing import Literal

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field

#: Served numeric features, in contract order (mirrors mlp_meta.numeric_cols).
NUMERIC_FIELDS = [
    "temp",
    "hum",
    "windspeed",
    "weathersit",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
    "month_sin",
    "month_cos",
    "holiday",
    "workingday",
    "cnt_lag_1h",
    "cnt_lag_24h",
    "cnt_lag_168h",
]


class FeatureRow(PortfolioBaseModel):
    """One row of model inputs — the serving surface of the feature contract."""

    hour: int = Field(ge=0, le=23, description="Raw hour of day; feeds the embedding index.")
    temp: float = Field(ge=0.0, le=1.0)
    hum: float = Field(ge=0.0, le=1.0)
    windspeed: float = Field(ge=0.0, le=1.0)
    weathersit: int = Field(ge=1, le=4)
    hour_sin: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    hour_cos: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    weekday_sin: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    weekday_cos: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    month_sin: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    month_cos: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    holiday: int = Field(ge=0, le=1)
    workingday: int = Field(ge=0, le=1)
    cnt_lag_1h: float = Field(ge=0.0, le=1e7, allow_inf_nan=False)
    cnt_lag_24h: float = Field(ge=0.0, le=1e7, allow_inf_nan=False)
    cnt_lag_168h: float = Field(ge=0.0, le=1e7, allow_inf_nan=False)


class PredictRequest(PortfolioBaseModel):
    """POST /predict body — a single feature row."""

    row: FeatureRow


class BatchPredictRequest(PortfolioBaseModel):
    """POST /predict/batch body — rows scored in one pass."""

    rows: list[FeatureRow] = Field(min_length=1, max_length=1024)


class PredictResponse(PortfolioBaseModel):
    """Shared response shape: prediction(s) plus the serving envelope."""

    prediction: float | None = None
    predictions: list[float] | None = None
    backend: Literal["native", "onnx"]
    request_id: str
