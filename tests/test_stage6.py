"""Stage 6 checks: every endpoint responds, the full demo flow works, and live events stream."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200

GET_ENDPOINTS = [
    "/api/health",
    "/api/herd",
    "/api/cow/IND-001",
    "/api/briefing?lang=en",
    "/api/briefing?lang=hi",
    "/api/briefing?lang=kn",
    "/api/memory",
    "/api/inventory",
    "/api/actions",
    "/api/orders",
    "/api/appointments",
    "/api/vet-report/IND-010",
]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_every_get_endpoint_responds(client, path):
    assert client.get(path).status_code == 200, path


def test_diagnose_endpoint_responds(client):
    response = client.post(
        "/api/diagnose",
        files={"photo": ("cow.png", PNG, "image/png")},
        data={"animal_id": "IND-010"},
    )
    assert response.status_code == 200


def test_end_to_end_fever_to_appointment(client):
    """The full demo story: question -> proposal -> farmer approves -> record -> memory -> report."""
    ask = client.post("/api/ask", json={"question": "Radha has a fever, what should we do?"}).json()
    vet = next(
        a for a in ask["proposed_actions"]
        if a["action_type"] == "book_vet" and a["parameters"]["target"] == "animal:IND-010"
    )
    assert vet["status"] == "proposed"

    approved = client.post(f"/api/actions/{vet['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["action"]["status"] == "completed"

    appointments = client.get("/api/appointments").json()["appointments"]
    assert any(a["action_id"] == vet["id"] for a in appointments)

    memory_titles = [i["title"] for i in client.get("/api/memory").json()["incidents"]]
    assert f"Action #{vet['id']}: book_vet for Radha (IND-010)" in memory_titles

    report = client.get("/api/vet-report/IND-010")
    assert report.content.startswith(b"%PDF")


def test_live_stream_emits_each_stage(client):
    with client.stream("GET", "/api/ask/stream",
                       params={"question": "Radha has a fever, what should we do?"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        text = "".join(response.iter_text())

    assert "event: started" in text
    assert "event: agent_done" in text
    assert "event: proposals_ready" in text
    assert "event: final" in text
