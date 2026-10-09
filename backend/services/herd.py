"""Traffic-light health rules (green / yellow / red) for each animal.

The rules are simple on purpose, so you can explain them to judges:
  * Fever: 40.0 C or higher is red, 39.5 C to 39.9 C is yellow.
  * Severity: "severe" is red, "mild" or "moderate" is yellow.
  * Symptoms other than "normal" are yellow.
  * Milk: a drop of 25% or more (last 3 days vs the 7 days before) is red,
    10% to 25% is yellow. Only lactating animals are checked.
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models as m

FEVER_RED_C = 40.0
FEVER_YELLOW_C = 39.5
RECENT_CHECK_DAYS = 7
MILK_RED_DROP_PCT = 25.0
MILK_YELLOW_DROP_PCT = 10.0

_RANK = {"green": 0, "yellow": 1, "red": 2}


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes. Treat them as UTC so comparisons work."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _worst(a: str, b: str) -> str:
    return b if _RANK[b] > _RANK[a] else a


def evaluate_health(animal: m.Animal, now: datetime) -> tuple[str, list[str]]:
    """Return (color, explanations) based on the most recent health check."""
    color = "green"
    reasons: list[str] = []

    recent = [
        r for r in animal.health_records
        if now - _aware(r.recorded_at) <= timedelta(days=RECENT_CHECK_DAYS)
    ]
    if not recent:
        return color, [f"No health check in the last {RECENT_CHECK_DAYS} days"]

    latest = max(recent, key=lambda r: _aware(r.recorded_at))

    if latest.temperature_c is not None:
        if latest.temperature_c >= FEVER_RED_C:
            color = _worst(color, "red")
            reasons.append(f"Temperature {latest.temperature_c} C is high (fever)")
        elif latest.temperature_c >= FEVER_YELLOW_C:
            color = _worst(color, "yellow")
            reasons.append(f"Temperature {latest.temperature_c} C is slightly raised")

    if latest.severity == "severe":
        color = _worst(color, "red")
        reasons.append("Latest health check severity: severe")
    elif latest.severity in ("mild", "moderate"):
        color = _worst(color, "yellow")
        reasons.append(f"Latest health check severity: {latest.severity}")

    symptoms = (latest.symptoms or "").strip()
    if symptoms and symptoms.lower() != "normal":
        color = _worst(color, "yellow")
        reasons.append(f"Symptoms reported: {symptoms}")

    if not reasons:
        reasons.append("Latest health check is normal")
    return color, reasons


def evaluate_milk(animal: m.Animal, today: date) -> tuple[str, list[str]]:
    """Compare the last 3 days of milk with the 7 days before that."""
    if not animal.lactating:
        return "green", []

    recent = [r.liters for r in animal.milk_records if 0 <= (today - r.recorded_on).days <= 2]
    previous = [r.liters for r in animal.milk_records if 3 <= (today - r.recorded_on).days <= 9]
    if not recent or not previous:
        return "green", []

    avg_recent = sum(recent) / len(recent)
    avg_previous = sum(previous) / len(previous)
    if avg_previous <= 0:
        return "green", []

    drop = (avg_previous - avg_recent) / avg_previous * 100
    if drop >= MILK_RED_DROP_PCT:
        return "red", [f"Milk down {drop:.0f}% in the last 3 days compared with the week before"]
    if drop >= MILK_YELLOW_DROP_PCT:
        return "yellow", [f"Milk down {drop:.0f}% in the last 3 days compared with the week before"]
    return "green", ["Milk yield is steady"]


def health_indicator(animal: m.Animal, now: datetime | None = None, today: date | None = None) -> dict:
    """Combine health and milk checks into one color plus explanations."""
    now = now or datetime.now(timezone.utc)
    today = today or date.today()

    health_color, health_reasons = evaluate_health(animal, now)
    milk_color, milk_reasons = evaluate_milk(animal, today)

    return {
        "color": _worst(health_color, milk_color),
        "explanations": health_reasons + milk_reasons,
    }


def animal_to_dict(animal: m.Animal) -> dict:
    return {
        "id": animal.id,
        "tag_id": animal.tag_id,
        "name": animal.name,
        "breed": animal.breed,
        "sex": animal.sex,
        "age_months": animal.age_months,
        "lactating": animal.lactating,
        "is_monitored": animal.is_monitored,
        "data_source": animal.data_source,
        "health_indicator": health_indicator(animal),
    }


def get_herd(db: Session) -> list[dict]:
    animals = db.query(m.Animal).order_by(m.Animal.tag_id).all()
    return [animal_to_dict(a) for a in animals]


def find_animal(db: Session, cow_id: str) -> m.Animal | None:
    """Accept either the numeric database id (12) or the tag (IND-012, any case)."""
    if cow_id.isdigit():
        return db.query(m.Animal).filter(m.Animal.id == int(cow_id)).first()
    return db.query(m.Animal).filter(func.upper(m.Animal.tag_id) == cow_id.upper()).first()


def get_cow_detail(db: Session, animal: m.Animal) -> dict:
    health = sorted(animal.health_records, key=lambda r: _aware(r.recorded_at), reverse=True)
    milk = sorted(animal.milk_records, key=lambda r: r.recorded_on, reverse=True)
    return {
        "animal": animal_to_dict(animal),
        "health_history": health,
        "milk_history": milk,
    }
