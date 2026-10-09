"""Stage 4 checks: approve, reject, orders, appointments, memory and inventory."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def pending(client, question, action_type, target=None):
    """Ask a question and return the first proposal that is still waiting for approval."""
    body = client.post("/api/ask", json={"question": question}).json()
    matches = [
        a for a in body["proposed_actions"]
        if a["action_type"] == action_type
        and a["status"] == "proposed"
        and (target is None or a["parameters"]["target"] == target)
    ]
    assert matches, f"no pending {action_type} for question {question!r}"
    return matches[0]


def test_approve_feed_reorder_creates_order(client):
    action = pending(client, "What feed reorder do we need for stock?", "reorder_feed")
    response = client.post(f"/api/actions/{action['id']}/approve")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"]["status"] == "completed"
    assert body["action"]["result"]["order_id"]
    orders = client.get("/api/orders").json()["orders"]
    assert any(o["action_id"] == action["id"] for o in orders)


def test_approving_twice_does_not_run_again(client):
    action = pending(client, "What feed reorder do we need for stock?", "reorder_feed")
    assert client.post(f"/api/actions/{action['id']}/approve").status_code == 200
    orders_before = client.get("/api/orders").json()["count"]

    second = client.post(f"/api/actions/{action['id']}/approve")
    assert second.status_code == 409
    assert client.get("/api/orders").json()["count"] == orders_before


def test_reject_executes_nothing(client):
    action = pending(client, "Radha has a fever, what should we do?", "book_vet", "animal:IND-010")
    appointments_before = client.get("/api/appointments").json()["count"]

    response = client.post(f"/api/actions/{action['id']}/reject", json={"reason": "Vet already booked"})
    assert response.status_code == 200
    assert response.json()["action"]["status"] == "rejected"
    assert client.get("/api/appointments").json()["count"] == appointments_before

    # A rejected action can never be approved afterwards
    assert client.post(f"/api/actions/{action['id']}/approve").status_code == 409


def test_approve_vet_creates_appointment(client):
    action = pending(client, "Radha has a fever, what should we do?", "book_vet", "animal:IND-010")
    response = client.post(f"/api/actions/{action['id']}/approve")
    assert response.status_code == 200
    appointments = client.get("/api/appointments").json()["appointments"]
    assert any(a["action_id"] == action["id"] and a["status"] == "scheduled" for a in appointments)


def test_approve_flag_sets_monitoring(client):
    action = pending(client, "Radha has a fever", "flag_animal", "animal:IND-010")
    assert client.post(f"/api/actions/{action['id']}/approve").status_code == 200
    herd = client.get("/api/herd").json()["animals"]
    radha = next(a for a in herd if a["tag_id"] == "IND-010")
    assert radha["is_monitored"] is True


def test_completed_action_is_saved_to_memory(client):
    incidents = client.get("/api/memory").json()["incidents"]
    assert any(i["title"].startswith("Action #") for i in incidents)
    assert len(incidents) >= 3


def test_inventory_shows_low_stock(client):
    inventory = client.get("/api/inventory").json()
    assert inventory["low_stock_count"] >= 1
    dairy = next(i for i in inventory["items"] if i["name"] == "Dairy concentrate pellets")
    assert dairy["low_stock"] is True


def test_actions_filter_by_status(client):
    response = client.get("/api/actions?status=completed")
    assert response.status_code == 200
    assert all(a["status"] == "completed" for a in response.json()["actions"])


def test_action_not_found_returns_404(client):
    assert client.post("/api/actions/999999/approve").status_code == 404


def test_invalid_status_filter_returns_422(client):
    assert client.get("/api/actions?status=bogus").status_code == 422
