"""Project-local FastAPI service for the champion MLP.

Two interchangeable backends behind one pydantic request schema that mirrors
experiment 12's feature contract exactly: ``native`` (torch, the persisted
state_dict + architecture json) and ``onnx`` (ONNX Runtime session warmed at
startup). A loader failure is a startup failure — the service never serves
half-initialised state.
"""

from model_serving.service.app import create_app
from model_serving.service.model import BackendName, ModelLoader

__all__ = ["BackendName", "ModelLoader", "create_app"]
