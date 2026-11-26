"""Backend loader: native LightGBM pickle or ONNX Runtime session.

Both backends implement the same contract: score the contract-ordered feature
matrix and return rentals. A backend is a plain class (not a protocol zoo)
because there are exactly two, paired by the benchmark; ``BackendName`` is the
single switch.

LightGBM is imported lazily (native backend only): the ONNX-only serving
image ships without it — and without torch, which the v2 served model does
not need at all — and the parity gate guarantees both backends agree where
both exist.
"""

import json
import pickle
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from portfolio_core.logging import get_logger

from model_serving.service.schemas import NUMERIC_FIELDS, FeatureRow

if TYPE_CHECKING:
    from lightgbm import LGBMRegressor

log = get_logger(__name__)

BackendName = Literal["native", "onnx"]

NATIVE_FILENAME = "lightgbm.pkl"
META_FILENAME = "lgbm_meta.json"
ONNX_FILENAME = "model.onnx"


class ModelLoader:
    """Loads the persisted served model for one backend and warms it at startup.

    ``ready`` flips only after warm-up rows have flowed through the backend,
    so /ready is an honest readiness probe (the harness and the Docker
    healthcheck both gate on it).
    """

    def __init__(self, models_dir: Path, backend: BackendName) -> None:
        self.models_dir = models_dir
        self.backend = backend
        self.ready = False
        meta = json.loads((models_dir / META_FILENAME).read_text())
        self.numeric_cols: list[str] = list(meta["numeric_cols"])
        if self.numeric_cols != NUMERIC_FIELDS:
            raise ValueError(
                f"service schema and artifact disagree on features: {self.numeric_cols}"
            )
        self._model: LGBMRegressor | None = None
        self._session: Any = None

        if backend == "native":
            # lazy: the ONNX-only image ships without lightgbm (or torch)
            with (models_dir / NATIVE_FILENAME).open("rb") as fh:
                self._model = pickle.load(fh)  # noqa: S301 - artifact persisted by the train stage
        else:
            import onnxruntime as ort  # type: ignore[import-untyped]  # no stubs shipped

            self._session = ort.InferenceSession(
                str(models_dir / ONNX_FILENAME), providers=["CPUExecutionProvider"]
            )
        log.info("loader: backend=%s numeric=%d ready=False", backend, len(self.numeric_cols))

    def _predict(self, x: np.ndarray) -> np.ndarray:
        """Raw prediction (rentals) for a contract-ordered feature matrix."""
        if self._session is not None:
            (out,) = self._session.run(None, {"input": x.astype(np.float32)})
            return np.asarray(out, dtype=float).ravel()
        if self._model is None:
            raise RuntimeError(f"backend {self.backend} holds no native model")
        return np.asarray(self._model.predict(x), dtype=float)

    def predict_rows(self, rows: list[FeatureRow]) -> np.ndarray:
        """Contract-order scoring of pydantic-validated rows (rentals scale)."""
        x = np.asarray([[getattr(r, c) for c in self.numeric_cols] for r in rows], dtype=np.float64)
        return self._predict(x)

    def warmup(self, n: int = 16) -> None:
        """Run warm-up rows through the backend; failure here is a startup error."""
        zeros = np.zeros((n, len(self.numeric_cols)), dtype=np.float64)
        out = self._predict(zeros)
        if not np.all(np.isfinite(out)):
            raise RuntimeError(f"{self.backend} warm-up produced non-finite output")
        self.ready = True
        log.info("loader: backend=%s warmed on %d rows, ready", self.backend, n)
