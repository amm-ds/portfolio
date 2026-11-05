"""POST /chat: SSE event streams, persistence, continuation, and approvals."""

import json
import queue as thread_queue
import threading
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from agent_chat.config import Settings
from agent_chat.testing import FakeStep
from tests import fakes


def _final(text: str, uncertainty: str = "low") -> FakeStep:
    return FakeStep(
        tool_call=("final_result", {"text": text, "citations": [], "uncertainty": uncertainty})
    )


def _stream_chat(
    client: TestClient,
    sink: "thread_queue.Queue[dict[str, Any]]",
    message: str,
    conversation_id: str | None = None,
) -> threading.Thread:
    """POST /chat in a background thread, putting parsed SSE events in ``sink``."""

    def _run() -> None:
        body: dict[str, Any] = {"message": message}
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        with client.stream("POST", "/chat", json=body) as response:
            assert response.status_code == 200, response.text
            assert response.headers["content-type"].startswith("text/event-stream")
            for line in response.iter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    sink.put(json.loads(line.removeprefix("data: ")))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def _next_event(
    sink: "thread_queue.Queue[dict[str, Any]]", event_type: str, timeout: float = 10.0
) -> dict[str, Any]:
    """Wait for an event of ``event_type`` (skipping others), else fail."""
    deadline = threading.Event()
    timer = threading.Timer(timeout, deadline.set)
    timer.start()
    seen: list[str] = []
    try:
        while not deadline.is_set():
            try:
                event = sink.get(timeout=0.1)
            except thread_queue.Empty:
                continue
            if event["type"] == event_type:
                return event
            seen.append(event["type"])
        raise AssertionError(f"no {event_type!r} event within {timeout}s; saw {seen}")
    finally:
        timer.cancel()


class TestChatStream:
    def test_full_event_sequence(self, client: TestClient) -> None:
        fakes.queue.append(FakeStep(tool_call=("calculator", {"expr": "2 + 2"})))
        fakes.queue.append(_final("2 + 2 = 4."))

        sink: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue()
        thread = _stream_chat(client, sink, "What is 2+2?")

        start = _next_event(sink, "tool_call_start")
        assert start["name"] == "calculator"
        assert start["args"] == {"expr": "2 + 2"}

        end = _next_event(sink, "tool_call_end")
        assert end["call_id"] == start["call_id"]
        assert end["name"] == "calculator"
        assert "4" in end["result"]

        done = _next_event(sink, "done")
        assert done["answer"]["text"] == "2 + 2 = 4."
        assert done["answer"]["uncertainty"] == "low"
        assert done["usage"]["input_tokens"] > 0
        assert done["conversation_id"]
        thread.join(timeout=10)
        assert not thread.is_alive()

        # the conversation was persisted under the id the stream reported
        got = client.get(f"/conversations/{done['conversation_id']}")
        assert got.status_code == 200

    def test_text_deltas_stream(self, client: TestClient) -> None:
        """A plain-text run still ends in a structured done event."""
        fakes.queue.append(_final("plain answer"))
        sink: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue()
        thread = _stream_chat(client, sink, "hi")
        done = _next_event(sink, "done")
        assert done["answer"]["text"] == "plain answer"
        thread.join(timeout=10)

    def test_conversation_continuation(self, client: TestClient) -> None:
        fakes.queue.append(_final("first answer"))
        sink: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue()
        t1 = _stream_chat(client, sink, "first question")
        done1 = _next_event(sink, "done")
        t1.join(timeout=10)

        # second turn in the same conversation, guarded on history threading
        fakes.queue.append(
            FakeStep(
                tool_call=(
                    "final_result",
                    {"text": "second answer", "citations": [], "uncertainty": "low"},
                ),
                expect="first question",
            )
        )
        t2 = _stream_chat(client, sink, "second question", conversation_id=done1["conversation_id"])
        done2 = _next_event(sink, "done")
        t2.join(timeout=10)
        assert done2["conversation_id"] == done1["conversation_id"]

        history = client.get(f"/conversations/{done1['conversation_id']}")
        assert history.status_code == 200
        assert len(history.json()["conversation"]["messages"]) >= 4

    def test_unknown_conversation_is_404(self, client: TestClient) -> None:
        response = client.post("/chat", json={"message": "hi", "conversation_id": "missing"})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "http_404"

    def test_model_failure_becomes_error_event(self, client: TestClient) -> None:
        """An empty script makes the fake model raise; the stream reports it."""
        sink: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue()
        thread = _stream_chat(client, sink, "boom")
        error = _next_event(sink, "error")
        assert error["code"] == "assertion_error"
        assert "exhausted" in error["message"]
        thread.join(timeout=10)

    def test_validation_error_envelope(self, client: TestClient) -> None:
        response = client.post("/chat", json={})
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "validation_error"
        assert body["error"]["request_id"]


class TestApprovals:
    def test_approve_posts_the_message(self, client: TestClient) -> None:
        fakes.queue.append(
            FakeStep(tool_call=("send_message", {"channel": "ops", "text": "Deploy done."}))
        )
        fakes.queue.append(_final("Announcement posted to #ops."))

        sink: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue()
        thread = _stream_chat(client, sink, "announce in ops")

        request = _next_event(sink, "approval_request")
        assert request["tool"] == "send_message"
        assert "Deploy done" in request["summary"]

        # a second client (same app) answers from another thread/loop
        other = TestClient(client.app)
        answer = other.post(f"/approvals/{request['approval_id']}", json={"approved": True})
        assert answer.status_code == 200

        response_event = _next_event(sink, "approval_response")
        assert response_event["approved"] is True

        end = _next_event(sink, "tool_call_end")
        assert end["name"] == "send_message"
        assert "sent" in end["result"]

        done = _next_event(sink, "done")
        assert done["answer"]["text"] == "Announcement posted to #ops."
        thread.join(timeout=10)
        other.close()

    def test_deny_blocks_the_action(self, client: TestClient) -> None:
        fakes.queue.append(FakeStep(tool_call=("send_message", {"channel": "ops", "text": "hi"})))
        fakes.queue.append(_final("The operator declined; nothing was posted."))

        sink: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue()
        thread = _stream_chat(client, sink, "announce")

        request = _next_event(sink, "approval_request")
        other = TestClient(client.app)
        answer = other.post(f"/approvals/{request['approval_id']}", json={"approved": False})
        assert answer.status_code == 200

        response_event = _next_event(sink, "approval_response")
        assert response_event["approved"] is False
        end = _next_event(sink, "tool_call_end")
        assert "NOT sent" in end["result"]
        thread.join(timeout=10)
        other.close()

    def test_timeout_defaults_to_deny(self, tmp_path: Path) -> None:
        from agent_chat.api.app import create_app
        from agent_chat.rag.embeddings import HashingEmbedder

        settings = Settings(
            database_url=f"sqlite:///{tmp_path}/timeout.db",
            embedder="hashing",
            approval_timeout_s=0.3,
        )
        app = create_app(settings=settings, model=fakes.app_model(), embedder=HashingEmbedder())
        with TestClient(app) as client:
            fakes.queue.append(
                FakeStep(tool_call=("send_message", {"channel": "ops", "text": "hi"}))
            )
            fakes.queue.append(_final("No approval arrived; nothing was posted."))
            sink: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue()
            thread = _stream_chat(client, sink, "announce")
            request = _next_event(sink, "approval_request")
            response_event = _next_event(sink, "approval_response", timeout=5.0)
            assert response_event["approval_id"] == request["approval_id"]
            assert response_event["approved"] is False
            end = _next_event(sink, "tool_call_end")
            assert "NOT sent" in end["result"]
            thread.join(timeout=10)

    def test_unknown_approval_is_404(self, client: TestClient) -> None:
        response = client.post("/approvals/does-not-exist", json={"approved": True})
        assert response.status_code == 404
