"""Stage 8 checks: symptom screening, severity, milk anomaly, and Health Agent integration."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def assess(client, payload):
    response = client.post("/api/assess", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def condition_names(body):
    return [c["name"] for c in body["possible_conditions"]]


def test_mastitis_example_is_high_priority(client):
    body = assess(client, {"cow_id": "IND-004", "temperature_c": 40.2, "milk_before_l": 18,
                           "milk_now_l": 10, "appetite": "reduced", "udder": "swollen",
                           "milk_appearance": "abnormal"})
    assert "Mastitis" in condition_names(body)
    assert body["priority"] == "high"
    assert body["milk_production_anomaly"] is True
    assert body["milk_drop_percent"] == 44.4
    assert any(a["action_type"] == "book_vet" and a["status"] == "proposed"
               for a in body["proposed_actions"])


def test_foot_and_mouth_is_urgent_and_notifiable(client):
    body = assess(client, {"cow_id": "IND-006", "temperature_c": 40.5, "mouth_blisters": True})
    assert "Foot-and-Mouth Disease (FMD)" in condition_names(body)
    assert body["priority"] == "urgent"
    assert any("notifiable" in r for r in body["urgent_reasons"])


def test_milk_fever_after_calving_is_urgent(client):
    body = assess(client, {"cow_id": "IND-009", "temperature_c": 38.6,
                           "days_since_calving": 1, "unable_to_stand": True})
    assert "Milk Fever" in condition_names(body)
    assert body["priority"] == "urgent"


def test_no_symptoms_is_low_priority(client):
    body = assess(client, {"cow_id": "IND-012", "temperature_c": 38.5})
    assert body["possible_conditions"] == []
    assert body["priority"] == "low"


def test_no_confidence_scores_are_shown(client):
    body = assess(client, {"cow_id": "IND-004", "temperature_c": 40.2, "udder": "swollen"})
    assert "confidence" not in str(body).lower()
    assert "disclaimer" in body and "not a confirmed diagnosis" in body["disclaimer"]


def test_symptom_report_reaches_farm_manager(client):
    assess(client, {"cow_id": "IND-004", "temperature_c": 40.2, "milk_before_l": 18,
                    "milk_now_l": 10, "appetite": "reduced", "udder": "swollen",
                    "milk_appearance": "abnormal"})
    body = client.post("/api/ask", json={"question": "How is Kaveri doing?"}).json()
    health = next(f for f in body["agent_findings"] if f["agent"] == "Health Agent")
    assert any("symptom report" in f for f in health["findings"])


def test_unknown_cow_returns_404(client):
    assert client.post("/api/assess", json={"cow_id": "NOPE-999"}).status_code == 404


def test_out_of_range_temperature_is_rejected(client):
    assert client.post("/api/assess", json={"cow_id": "IND-004", "temperature_c": 99}).status_code == 422
