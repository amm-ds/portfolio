"""Smoke-test the Compose API, Postgres worker, page progress, chat, downloads.

Run after ``docker compose -f infra/docker-compose.yml up --build -d`` from the
app root. Uses only the committed deterministic fixture and development identity.
"""

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx

BASE_URL = os.environ.get("DOCUMENT_INTELLIGENCE_SMOKE_BASE_URL", "http://127.0.0.1:8001")
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    headers = {"X-Dev-Tenant": f"compose-smoke-{uuid4().hex[:12]}", "X-Dev-Actor": "analyst"}
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        for _ in range(30):
            try:
                if client.get("/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Compose API did not become healthy")
        assert client.get("/ready").status_code == 200
        payload = (ROOT / "fixtures" / "analysis-multipage.pdf").read_bytes()
        files = {"file": ("analysis-multipage.pdf", payload, "application/pdf")}
        response = client.post("/documents", files=files)
        response.raise_for_status()
        document = response.json()["document"]
        document_id = document["id"]

        duplicate = client.post("/documents", files=files)
        duplicate.raise_for_status()
        assert duplicate.json()["duplicate"] is True

        for _ in range(60):
            response = client.get(f"/documents/{document_id}")
            response.raise_for_status()
            current = response.json()
            if current["status"] in {"completed", "failed"}:
                break
            time.sleep(1)
        assert current["status"] == "completed", current

        response = client.get(f"/documents/{document_id}/analysis")
        response.raise_for_status()
        analysis = response.json()
        progress = analysis["progress"]
        assert progress == {"page_count": 2, "processed_pages": 2, "failed_pages": 0}, progress
        pages = analysis["analysis"]["pages"]
        assert [page["page"] for page in pages] == [1, 2]
        assert all(page["status"] == "completed" for page in pages)
        # Four page modes data: summary/key points, entities, topics, issues.
        for page in pages:
            assert page["summary"]["summary"]
            assert page["summary"]["key_points"]
            assert page["summary"]["key_points"][0]["evidence"][0]["resolved"] is True
            assert page["issues"] == []
        assert pages[0]["entities"], "page 1 entities missing"
        assert pages[1]["topics"], "page 2 topics missing"

        answer = client.post(
            f"/documents/{document_id}/pages/2/chat",
            json={
                "messages": [{"role": "user", "content": "What did the research program improve?"}]
            },
        )
        answer.raise_for_status()
        assert answer.json()["citations"][0]["resolved"] is True
        assert answer.json()["citations"][0]["page"] == 2

        full_json = client.get(f"/documents/{document_id}/analysis/export?format=json")
        full_json.raise_for_status()
        assert full_json.json()["analysis"]["schema_version"] == "page-analysis-v1"
        full_md = client.get(f"/documents/{document_id}/analysis/export?format=md")
        full_md.raise_for_status()
        assert "## Page 2" in full_md.text
        page_json = client.get(f"/documents/{document_id}/pages/1/export?format=json")
        page_json.raise_for_status()
        assert page_json.json()["page"]["page"] == 1
        page_md = client.get(f"/documents/{document_id}/pages/1/export?format=md")
        page_md.raise_for_status()
        assert "# Page 1 analysis" in page_md.text

        other = client.get(
            f"/documents/{document_id}",
            headers={"X-Dev-Tenant": "other", "X-Dev-Actor": "analyst"},
        )
        assert other.status_code == 404

    print(
        json.dumps(
            {
                "status": "completed",
                "duplicate": True,
                "progress": progress,
                "page_modes_data": True,
                "chat": True,
                "downloads": {
                    "full_json": True,
                    "full_md": True,
                    "page_json": True,
                    "page_md": True,
                },
                "cross_tenant": 404,
            }
        )
    )


if __name__ == "__main__":
    main()
