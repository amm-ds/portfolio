"""Zero-cost replay harness (R7): recorded model responses + request rails.

Deterministic evaluation without network: a :class:`RecordedModel` wraps an
inner pydantic-ai model. In record mode it calls the inner model and persists
each response keyed by a hash of the message list; in replay mode it returns
the recording, raising if none exists — so a CI run with
``ALLOW_MODEL_REQUESTS=false`` can never silently hit a real provider.

The :class:`RequestGuard` counts model responses and tool calls per question
and enforces the R7 rails (``max_model_requests``, ``max_tool_calls``), so
bounded-evaluation invariants are tested, not assumed.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from pydantic_ai import messages as _messages
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import FunctionModel


def _response_to_json(response: ModelResponse) -> str:
    """Serialize a ModelResponse by parts: type tag + dataclass fields."""
    payload = [_part_to_dict(part) for part in response.parts]
    return json.dumps(payload, ensure_ascii=False)


def _part_to_dict(part: Any) -> dict[str, Any]:
    if not dataclasses.is_dataclass(part):
        raise TypeError(f"cannot serialize response part type {type(part).__name__}")
    return {"__type__": type(part).__name__, "dump": dataclasses.asdict(cast(Any, part))}


def _response_from_json(text: str) -> ModelResponse:
    payload = json.loads(text)
    parts = [getattr(_messages, item["__type__"])(**item["dump"]) for item in payload]
    return ModelResponse(parts=parts)


def messages_key(messages: list[ModelMessage]) -> str:
    """Stable content key for a conversation: role + part payloads."""
    digest = hashlib.sha256()
    for message in messages:
        parts = getattr(message, "parts", [])
        for part in parts:
            kind = type(part).__name__
            content = getattr(part, "content", None)
            if callable(content):  # some parts expose content as a method
                content = content()
            digest.update(kind.encode())
            digest.update(repr(content).encode())
    return digest.hexdigest()[:24]


class RequestGuard:
    """Hard rails on model requests and tool calls per question."""

    def __init__(self, max_model_requests: int = 4, max_tool_calls: int = 6) -> None:
        self.max_model_requests = max_model_requests
        self.max_tool_calls = max_tool_calls
        self.model_requests = 0
        self.tool_calls = 0

    def count_model_request(self) -> None:
        self.model_requests += 1
        if self.model_requests > self.max_model_requests:
            raise RuntimeError(
                f"R7 rail: {self.model_requests} model requests > "
                f"{self.max_model_requests} allowed per question"
            )

    def count_tool_call(self) -> None:
        self.tool_calls += 1
        if self.tool_calls > self.max_tool_calls:
            raise RuntimeError(
                f"R7 rail: {self.tool_calls} tool calls > {self.max_tool_calls} "
                f"allowed per question"
            )


class RecordedModel:
    """Record/replay pydantic-ai model backed by a fixtures directory.

    ``record=True`` requires a working inner model (development machine);
    ``record=False`` is the CI/offline mode: a missing fixture raises, and
    with ``ALLOW_MODEL_REQUESTS=false`` pydantic-ai additionally refuses any
    real call — the run is provably network-free.
    """

    def __init__(
        self,
        inner: Any,
        fixtures_dir: Path,
        record: bool = False,
        guard: RequestGuard | None = None,
    ) -> None:
        self._inner = inner
        self._dir = fixtures_dir
        self._record = record
        self._guard = guard or RequestGuard()
        self._dir.mkdir(parents=True, exist_ok=True)

    def __call__(self, messages: list[ModelMessage], info: Any) -> ModelResponse:
        key = messages_key(messages)
        fixture = self._dir / f"{key}.json"
        if fixture.exists():
            self._count_calls(messages)
            return _response_from_json(fixture.read_text(encoding="utf-8"))
        if not self._record:
            raise FileNotFoundError(
                f"no replay fixture for key {key} under {self._dir}; "
                f"record it with record=True first"
            )
        if not callable(self._inner):  # pragma: no cover - inner is always callable
            raise TypeError("inner model is not callable")
        response = cast(ModelResponse, self._inner(messages, info))
        self._count_calls(messages)
        fixture.write_text(_response_to_json(response), encoding="utf-8")
        return response

    def _count_calls(self, messages: list[ModelMessage]) -> None:
        """Charge the guard: one model request per invocation + tool calls seen."""
        self._guard.count_model_request()
        for message in messages:
            for part in getattr(message, "parts", []):
                if type(part).__name__ == "ToolCallPart":
                    self._guard.count_tool_call()

    def function_model(self) -> FunctionModel:
        """The pydantic-ai FunctionModel view of this recorder."""
        return FunctionModel(self)
