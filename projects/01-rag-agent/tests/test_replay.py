"""Zero-cost replay harness tests: record → replay offline, with hard rails."""

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from rag_agent.replay import RecordedModel, RequestGuard, messages_key


def _user(text: str) -> list[ModelMessage]:
    return [ModelRequest(parts=[UserPromptPart(content=text)])]


def _scripted(text: str):
    def respond(messages: list, info) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=text)])

    return respond


def test_messages_key_is_stable_and_sensitive() -> None:
    a = messages_key(_user("hello"))
    assert a == messages_key(_user("hello"))
    assert a != messages_key(_user("goodbye"))


def test_record_then_replay_round_trip(tmp_path: Path) -> None:
    recorder = RecordedModel(_scripted("recorded answer"), tmp_path, record=True)
    first = recorder(_user("hello"), info=None)
    assert any(getattr(p, "content", None) == "recorded answer" for p in first.parts)
    assert len(list(tmp_path.glob("*.json"))) == 1

    # Offline replay from a FRESH recorder over the same fixtures: no inner model.
    replay = RecordedModel(_scripted("SHOULD NOT BE CALLED"), tmp_path, record=False)
    second = replay(_user("hello"), info=None)
    assert any(getattr(p, "content", None) == "recorded answer" for p in second.parts)


def test_replay_missing_fixture_raises(tmp_path: Path) -> None:
    recorder = RecordedModel(_scripted("x"), tmp_path, record=False)
    with pytest.raises(FileNotFoundError, match="no replay fixture"):
        recorder(_user("never recorded"), info=None)


def test_guard_caps_model_requests() -> None:
    guard = RequestGuard(max_model_requests=2)
    guard.count_model_request()
    guard.count_model_request()
    with pytest.raises(RuntimeError, match="R7 rail"):
        guard.count_model_request()


def test_guard_caps_tool_calls() -> None:
    guard = RequestGuard(max_tool_calls=1)
    guard.count_tool_call()
    with pytest.raises(RuntimeError, match="R7 rail"):
        guard.count_tool_call()


def test_recorded_model_charges_guard_per_invocation(tmp_path: Path) -> None:
    guard = RequestGuard(max_model_requests=1)
    recorder = RecordedModel(_scripted("a"), tmp_path, record=True, guard=guard)
    recorder(_user("one"), info=None)
    with pytest.raises(RuntimeError, match="R7 rail"):
        recorder(_user("two"), info=None)  # second request over the rail
