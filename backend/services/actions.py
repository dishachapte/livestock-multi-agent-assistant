"""Action proposals, approval, rejection and execution.

Lifecycle of one action:
  proposed --approve--> approved --run ok--> completed   (record saved, memory saved)
  proposed --reject---> rejected                          (nothing runs)
  approved --run fails-> failed                           (nothing saved; farmer can retry)

A completed or rejected action can never run again.
"""
import json
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from backend import models as m
from backend.services.memory import tokenize


class ActionError(Exception):
    """Raised for user-facing problems (not found, already done). Main turns it into an HTTP error."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_description(action_type: str, label: str, reasons: list[str], params: dict) -> str:
    reason_text = "; ".join(reasons)
    if action_type == "flag_animal":
        return f"Flag {label} for monitoring. Reasons: {reason_text}"
    if action_type == "book_vet":
        return f"Book a veterinary visit for {label} on {params['requested_for']}. Reasons: {reason_text}"
    if action_type == "reorder_feed":
        return f"Reorder {params['quantity_kg']:.0f} kg of {label}. Reasons: {reason_text}"
    return f"{action_type} for {label}"


def create_proposals(db: Session, actions: list[dict]) -> list[m.ProposedAction]:
    """Save proposals. If an identical proposal is still waiting, reuse it instead of duplicating."""
    rows: list[m.ProposedAction] = []
    for action in actions:
        target = action["parameters"]["target"]
        pending = (
            db.query(m.ProposedAction)
            .filter(m.ProposedAction.action_type == action["action_type"],
                    m.ProposedAction.status == "proposed")
            .all()
        )
        match = next((p for p in pending if json.loads(p.parameters_json).get("target") == target), None)
        if match:
            rows.append(match)
            continue

        row = m.ProposedAction(
            action_type=action["action_type"],
            description=action["description"],
            priority=action["priority"],
            parameters_json=json.dumps(action["parameters"]),
            status="proposed",
        )
        db.add(row)
        db.flush()
        _log(db, row.id, "proposed", row.description)
        rows.append(row)

    db.commit()
    return rows


def serialize_action(row: m.ProposedAction) -> dict:
    return {
        "id": row.id,
        "action_type": row.action_type,
        "description": row.description,
        "priority": row.priority,
        "parameters": json.loads(row.parameters_json or "{}"),
        "status": row.status,
        "result": json.loads(row.result_json) if row.result_json else None,
        "created_at": row.created_at,
    }


def _log(db: Session, action_id: int, event: str, detail: str | None = None) -> None:
    db.add(m.ActionLog(action_id=action_id, event=event, detail=detail))


def _get_action(db: Session, action_id: int) -> m.ProposedAction:
    row = db.get(m.ProposedAction, action_id)
    if row is None:
        raise ActionError(404, f"No action with id {action_id}")
    return row


# ---- Execution: the only place where approved actions change the database ----

def _execute(db: Session, row: m.ProposedAction) -> dict:
    params = json.loads(row.parameters_json)

    if row.action_type == "reorder_feed":
        item = db.get(m.FeedItem, params["feed_item_id"])
        if item is None:
            raise ValueError("The feed item no longer exists")
        order = m.Order(
            feed_item_id=item.id,
            quantity_kg=params["quantity_kg"],
            status="placed",
            action_id=row.id,
        )
        db.add(order)
        db.flush()
        return {
            "order_id": order.id,
            "feed": item.name,
            "quantity_kg": order.quantity_kg,
            "message": (f"Order #{order.id} placed for {order.quantity_kg:.0f} kg of {item.name}. "
                        "Stock will rise when delivery is recorded."),
        }

    if row.action_type == "book_vet":
        animal = db.get(m.Animal, params["animal_id"])
        if animal is None:
            raise ValueError("The animal no longer exists")
        appointment = m.VetAppointment(
            animal_id=animal.id,
            reason="; ".join(params.get("reasons", [])) or "Veterinary check",
            requested_for=date.fromisoformat(params["requested_for"]),
            status="scheduled",
            action_id=row.id,
        )
        db.add(appointment)
        db.flush()
        return {
            "appointment_id": appointment.id,
            "animal": animal.tag_id,
            "requested_for": appointment.requested_for.isoformat(),
            "message": (f"Vet visit requested for {animal.name} ({animal.tag_id}) on "
                        f"{appointment.requested_for.isoformat()}."),
        }

    if row.action_type == "flag_animal":
        animal = db.get(m.Animal, params["animal_id"])
        if animal is None:
            raise ValueError("The animal no longer exists")
        animal.is_monitored = True
        return {
            "animal": animal.tag_id,
            "is_monitored": True,
            "message": f"{animal.name} ({animal.tag_id}) is now on daily monitoring.",
        }

    raise ValueError(f"Unknown action type: {row.action_type}")


def _save_outcome_memory(db: Session, row: m.ProposedAction, params: dict, result: dict) -> None:
    """Store the finished action in farm memory so future questions can find it."""
    label = params.get("label", "farm item")
    keywords = (
        tokenize(row.action_type.replace("_", " "))
        | tokenize(label)
        | tokenize(" ".join(params.get("reasons", [])))
    )
    db.add(m.FarmMemory(
        title=f"Action #{row.id}: {row.action_type} for {label}",
        category="action_outcome",
        summary=row.description,
        keywords=",".join(sorted(keywords))[:300],
        outcome=result.get("message", "Completed"),
    ))


def approve_action(db: Session, action_id: int) -> m.ProposedAction:
    row = _get_action(db, action_id)

    if row.status == "completed":
        raise ActionError(409, f"Action {action_id} was already completed. It was not run again.")
    if row.status == "rejected":
        raise ActionError(409, f"Action {action_id} was rejected and cannot be approved.")
    if row.status == "approved":
        raise ActionError(409, f"Action {action_id} is already being approved.")

    row.status = "approved"
    row.decided_at = _now()
    _log(db, row.id, "approved")
    db.commit()  # the farmer's decision is saved first

    try:
        params = json.loads(row.parameters_json)
        result = _execute(db, row)
        row.status = "completed"
        row.result_json = json.dumps(result)
        row.executed_at = _now()
        _log(db, row.id, "executed", result.get("message"))
        _save_outcome_memory(db, row, params, result)
        db.commit()  # only now is the action called successful
    except Exception as exc:
        db.rollback()  # undo any half-finished database changes
        row = db.get(m.ProposedAction, action_id)
        row.status = "failed"
        row.result_json = json.dumps({"error": str(exc)})
        _log(db, row.id, "failed", str(exc))
        db.commit()
        raise ActionError(500, f"The action failed and nothing was saved: {exc}")

    return row


def reject_action(db: Session, action_id: int, reason: str | None = None) -> m.ProposedAction:
    row = _get_action(db, action_id)

    if row.status == "rejected":
        return row  # rejecting twice is harmless
    if row.status in ("approved", "completed"):
        raise ActionError(409, f"Action {action_id} is already {row.status} and cannot be rejected.")

    row.status = "rejected"
    row.decided_at = _now()
    _log(db, row.id, "rejected", reason or "Rejected by farmer")
    db.commit()
    return row
