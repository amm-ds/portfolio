"""Backend loader: native torch state_dict or ONNX Runtime session.

Both backends implement the same contract: apply the train-fitted input
standardization, run the persisted graph, invert the y standardization. A
backend is a plain class (not a protocol zoo) because there are exactly two,
paired by the benchmark; ``BackendName`` is the single switch.

Torch is imported lazily (native backend only): the ONNX-only serving image
ships without torch — 6.5 GB down to a few hundred MB — and the parity gate
guarantees both backends agree where both exist.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from portfolio_core.logging import get_logger

from model_serving.service.schemas import NUMERIC_FIELDS, FeatureRow

if TYPE_CHECKING:
    from model_serving.mlp import RentalMLP

log = get_logger(__name__)

BackendName = Literal["native", "onnx"]


class ModelLoader:
    """Loads the persisted champion for one backend and warms it at startup.

    ``ready`` flips only after warm-up rows have flowed through the backend,
    so /ready is an honest readiness probe (the harness and the Docker
    healthcheck both gate on it).
    """

    def __init__(self, models_dir: Path, backend: BackendName) -> None:
        self.models_dir = models_dir
        self.backend = backend
        self.ready = False
        meta = json.loads((models_dir / "mlp_meta.json").read_text())
        arch = json.loads((models_dir / "mlp_arch.json").read_text())
        self.numeric_cols: list[str] = list(meta["numeric_cols"])
        if self.numeric_cols != NUMERIC_FIELDS:
            raise ValueError(
                f"service schema and artifact disagree on features: {self.numeric_cols}"
            )
        self.x_mean = np.asarray(meta["x_mean"], dtype=np.float64)
        self.x_std = np.asarray(meta["x_std"], dtype=np.float64)
        self.y_mean = float(meta["y_mean"])
        self.y_std = float(meta["y_std"])
        self._hour_cardinality = int(arch["hour_cardinality"])
        self._model: RentalMLP | None = None
        self._session: Any = None

        if backend == "native":
            import torch  # lazy: the ONNX-only image ships without torch

            from model_serving import mlp as mlp_module

            model = mlp_module.RentalMLP(
                n_numeric=int(arch["n_numeric"]),
                embed_dim=int(arch["embed_dim"]),
                hidden_dims=[int(h) for h in arch["hidden_dims"]],
                dropout=float(arch["dropout"]),
            )
            state = torch.load(models_dir / "mlp.pt", weights_only=True)
            model.load_state_dict(state)
            model.eval()
            self._model = model
        else:
            import onnxruntime as ort  # type: ignore[import-untyped]  # no stubs shipped

            self._session = ort.InferenceSession(
                str(models_dir / "model.onnx"), providers=["CPUExecutionProvider"]
            )
        log.info("loader: backend=%s numeric=%d ready=False", backend, len(self.numeric_cols))

    def _predict_scaled(self, hour: np.ndarray, x_num: np.ndarray) -> np.ndarray:
        """Raw network output (standardized-y space) for prepared arrays."""
        if self._session is not None:
            (out,) = self._session.run(
                None, {"hour": hour.astype(np.int64), "x_num": x_num.astype(np.float32)}
            )
            return np.asarray(out, dtype=float)
        if self._model is None:
            raise RuntimeError(f"backend {self.backend} holds no native model")
        import torch  # lazy: native path only, like the loader above

        torch.set_num_threads(1)  # multi-thread predict deadlocks on the shared libomp
        with torch.no_grad():
            t_hour = torch.tensor(hour, dtype=torch.long)
            t_num = torch.tensor(x_num, dtype=torch.float32)
            native_out: np.ndarray = self._model(t_hour, t_num).numpy()
            return native_out

    def predict_rows(self, rows: list[FeatureRow]) -> np.ndarray:
        """Contract-order scoring of pydantic-validated rows (rentals scale)."""
        hour = np.asarray([r.hour for r in rows], dtype=np.int64)
        raw = np.asarray(
            [[getattr(r, c) for c in self.numeric_cols] for r in rows], dtype=np.float64
        )
        x_num = ((raw - self.x_mean) / self.x_std).astype(np.float32)
        scaled = self._predict_scaled(hour, x_num)
        return scaled * self.y_std + self.y_mean

    def warmup(self, n: int = 16) -> None:
        """Run warm-up rows through the backend; failure here is a startup error."""
        hour = np.arange(n, dtype=np.int64) % self._hour_cardinality
        zeros = np.zeros((n, len(self.numeric_cols)), dtype=np.float32)
        scaled = self._predict_scaled(hour, ((zeros.astype(np.float64) - self.x_mean) / self.x_std))
        if not np.all(np.isfinite(scaled)):
            raise RuntimeError(f"{self.backend} warm-up produced non-finite output")
        self.ready = True
        log.info("loader: backend=%s warmed on %d rows, ready", self.backend, n)
