"""Stage 3 checks: the Manager Agent, specialist routing, proposals and memory search."""
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def ask(client, question, language="en"):
    response = client.post("/api/ask", json={"question": question, "language": language})
    assert response.status_code == 200, response.text
    return response.json()


def test_ask_response_shape_and_fallback_honesty(client):
    body = ask(client, "Why is milk low for Kaveri?")
    for key in ["final_recommendation", "agent_findings", "memory_matches",
                "proposed_actions", "agents_consulted", "ai_mode_used", "fallback_reason"]:
        assert key in body
    assert "Health Agent" in body["agents_consulted"]
    assert "Nutrition Agent" in body["agents_consulted"]
    assert "Breeding Agent" not in body["agents_consulted"]
    assert body["ai_mode_used"] in ("gemini", "demo")
    if not settings.gemini_enabled:
        assert body["ai_mode_used"] == "demo"
        assert body["fallback_reason"]


def test_fever_proposes_vet_visit_without_executing(client):
    body = ask(client, "Radha has a fever, what should we do?")
    vet = [a for a in body["proposed_actions"]
           if a["action_type"] == "book_vet" and a["parameters"]["target"] == "animal:IND-010"]
    assert vet, "expected a vet visit proposal for Radha"
    assert vet[0]["status"] == "proposed"
    assert vet[0]["result"] is None


def test_same_proposal_is_not_duplicated(client):
    first = ask(client, "Radha has a fever")
    second = ask(client, "Radha has a fever")
    ids_first = sorted(a["id"] for a in first["proposed_actions"]
                       if a["parameters"]["target"] == "animal:IND-010")
    ids_second = sorted(a["id"] for a in second["proposed_actions"]
                        if a["parameters"]["target"] == "animal:IND-010")
    assert ids_first == ids_second


def test_farm_memory_match_for_milk_drop(client):
    body = ask(client, "milk dropped after changing feed")
    titles = [m["title"] for m in body["memory_matches"]]
    assert "Milk drop after feed supplier change" in titles


def test_breeding_question_routes_breeding_agent(client):
    body = ask(client, "Is any cow due for a heat check or breeding?")
    assert "Breeding Agent" in body["agents_consulted"]
    targets = {a["parameters"]["target"] for a in body["proposed_actions"]}
    assert targets & {"animal:IND-005", "animal:IND-006", "animal:IND-003"}


def test_finance_costs_feed_reorder(client):
    body = ask(client, "What will the feed reorder cost?")
    assert "Finance Agent" in body["agents_consulted"]
    reorders = [a for a in body["proposed_actions"] if a["action_type"] == "reorder_feed"]
    assert reorders, "expected at least one feed reorder proposal"
    assert all("estimated_cost_inr" in a["parameters"] for a in reorders)


def test_validation_rejects_short_question_and_bad_language(client):
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 422
    assert client.post("/api/ask", json={"question": "Is the herd ok?", "language": "fr"}).status_code == 422
