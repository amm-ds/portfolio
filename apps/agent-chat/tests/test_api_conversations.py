"""Conversation CRUD: list, read, delete, and the 404 paths."""

from fastapi.testclient import TestClient

from agent_chat.testing import FakeStep
from tests import fakes


def _final(text: str) -> FakeStep:
    return FakeStep(
        tool_call=("final_result", {"text": text, "citations": [], "uncertainty": "low"})
    )


class TestConversationsCrud:
    def test_list_empty(self, client: TestClient) -> None:
        response = client.get("/conversations")
        assert response.status_code == 200
        assert response.json() == {"conversations": []}

    def test_chat_then_list_and_get(self, client: TestClient) -> None:
        fakes.queue.append(_final("hello there"))
        client.post("/chat", json={"message": "say hello"}).raise_for_status()

        listing = client.get("/conversations").json()["conversations"]
        assert len(listing) == 1
        assert listing[0]["title"] == "say hello"

        full = client.get(f"/conversations/{listing[0]['conversation_id']}")
        assert full.status_code == 200
        body = full.json()
        assert body["meta"]["message_count"] >= 2
        messages = body["conversation"]["messages"]
        assert any("say hello" in str(m) for m in messages)

    def test_get_unknown_is_404(self, client: TestClient) -> None:
        response = client.get("/conversations/nope")
        assert response.status_code == 404
        assert response.json()["error"]["request_id"]

    def test_delete(self, client: TestClient) -> None:
        fakes.queue.append(_final("temporary"))
        sink = client.post("/chat", json={"message": "short-lived"})
        assert sink.status_code == 200
        # find the id via the listing (the non-streaming surface)
        listing = client.get("/conversations").json()["conversations"]
        conversation_id = listing[0]["conversation_id"]

        deleted = client.delete(f"/conversations/{conversation_id}")
        assert deleted.status_code == 200
        assert client.get("/conversations").json() == {"conversations": []}
        again = client.delete(f"/conversations/{conversation_id}")
        assert again.status_code == 404
