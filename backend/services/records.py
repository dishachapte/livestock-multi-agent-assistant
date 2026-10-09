"""Read-only queries for inventory, memory, orders and appointments."""
from sqlalchemy.orm import Session

from backend import models as m


def list_inventory(db: Session) -> dict:
    items = db.query(m.FeedItem).order_by(m.FeedItem.name).all()
    rows = []
    alerts = []
    for item in items:
        low = item.quantity_kg < item.reorder_level_kg
        rows.append({
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "quantity_kg": item.quantity_kg,
            "reorder_level_kg": item.reorder_level_kg,
            "unit_cost_inr": item.unit_cost_inr,
            "supplier": item.supplier,
            "quality_grade": item.quality_grade,
            "low_stock": low,
        })
        if low:
            alerts.append(f"{item.name}: {item.quantity_kg:.0f} kg left, reorder level {item.reorder_level_kg:.0f} kg")
    return {"count": len(rows), "low_stock_count": len(alerts),
            "low_stock_alerts": alerts, "items": rows}


def list_memory(db: Session) -> dict:
    incidents = db.query(m.FarmMemory).order_by(m.FarmMemory.created_at.desc(), m.FarmMemory.id.desc()).all()
    return {"count": len(incidents), "incidents": incidents}


def list_actions(db: Session, status: str | None = None) -> dict:
    query = db.query(m.ProposedAction)
    if status:
        query = query.filter(m.ProposedAction.status == status)
    actions = query.order_by(m.ProposedAction.id.desc()).all()
    return {"count": len(actions), "actions": actions}


def list_orders(db: Session) -> dict:
    orders = db.query(m.Order).order_by(m.Order.id.desc()).all()
    return {"count": len(orders), "orders": orders}


def list_appointments(db: Session) -> dict:
    appointments = db.query(m.VetAppointment).order_by(m.VetAppointment.id.desc()).all()
    return {"count": len(appointments), "appointments": appointments}
