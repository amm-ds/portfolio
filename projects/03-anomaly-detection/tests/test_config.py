"""Config model validation tests."""

from pathlib import Path

import pytest
from anomaly_detection.config import PROJECT_ROOT, AnomalyConfig
from pydantic import ValidationError


def test_defaults_match_spec() -> None:
    config = AnomalyConfig()
    assert config.n == 20_000
    assert config.anomaly_rate == pytest.approx(0.02)
    assert config.contamination == pytest.approx(0.02)
    assert config.models == ["isolation_forest", "lof", "ocsvm"]
    assert config.windows == [10, 60]


@pytest.mark.parametrize(
    "field,value",
    [
        ("anomaly_rate", 0.0),
        ("anomaly_rate", 0.5),
        ("contamination", 0.0),
        ("train_frac", 1.0),
        ("train_frac", 0.0),
        ("max_null_rate", -0.1),
        ("n", 0),
        ("windows", [0, 10]),
        ("windows", [-5]),
        ("models", ["not_a_model"]),
    ],
)
def test_invalid_values_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        AnomalyConfig.model_validate({field: value})


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        AnomalyConfig(bogus=1)  # type: ignore[call-arg]


def test_resolve_paths() -> None:
    config = AnomalyConfig(data_dir="data", reports_dir="reports")
    assert config.raw_path == PROJECT_ROOT / "data" / "raw.parquet"
    assert config.dq_report_path == PROJECT_ROOT / "reports" / "dq_report.html"
    absolute = Path("/tmp/elsewhere")
    assert AnomalyConfig(data_dir=str(absolute)).data_path == absolute
