"""Stage 2 checks: the four core endpoints return the expected data."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client():
    # "with" runs the startup code (seeding) just like uvicorn does.
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["ai_mode"] in ("gemini", "demo")


def test_herd_lists_all_animals_with_indicators(client):
    response = client.get("/api/herd")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 10
    assert body["count"] == body["green"] + body["yellow"] + body["red"]
    for animal in body["animals"]:
        assert animal["health_indicator"]["color"] in ("green", "yellow", "red")
        assert len(animal["health_indicator"]["explanations"]) >= 1


def test_fever_cow_is_red(client):
    body = client.get("/api/herd").json()
    radha = next(a for a in body["animals"] if a["tag_id"] == "IND-010")
    assert radha["health_indicator"]["color"] == "red"


def test_milk_drop_is_flagged(client):
    body = client.get("/api/herd").json()
    kaveri = next(a for a in body["animals"] if a["tag_id"] == "IND-004")
    assert kaveri["health_indicator"]["color"] in ("yellow", "red")
    assert any("Milk down" in e for e in kaveri["health_indicator"]["explanations"])


def test_cow_lookup_by_tag_and_by_id(client):
    by_tag = client.get("/api/cow/IND-001")
    assert by_tag.status_code == 200
    assert by_tag.json()["animal"]["tag_id"] == "IND-001"
    assert len(by_tag.json()["milk_history"]) == 14

    first_id = client.get("/api/herd").json()["animals"][0]["id"]
    by_id = client.get(f"/api/cow/{first_id}")
    assert by_id.status_code == 200


def test_cow_not_found_returns_404(client):
    response = client.get("/api/cow/NOPE-999")
    assert response.status_code == 404
    assert "No animal found" in response.json()["detail"]


def test_briefing_english(client):
    response = client.get("/api/briefing?lang=en")
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "en"
    assert len(body["alerts"]) >= 1
    assert len(body["priorities"]) >= 1


def test_briefing_alerts_sorted_high_first(client):
    alerts = client.get("/api/briefing").json()["alerts"]
    order = {"high": 0, "medium": 1, "low": 2}
    levels = [order[a["level"]] for a in alerts]
    assert levels == sorted(levels)


def test_briefing_rejects_unsupported_language(client):
    response = client.get("/api/briefing?lang=fr")
    assert response.status_code == 422
