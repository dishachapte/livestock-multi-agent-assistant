"""Synthetic demo data. Running it again never creates duplicates.

Run from the farm-assistant folder:
    python -m backend.seed_data
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend import models as m
from backend.database import SessionLocal, init_db

# ---- Animals (all SYNTHETIC_DEMO) -----------------------------------------
ANIMALS = [
    {"tag_id": "IND-001", "name": "Lakshmi", "breed": "Holstein Friesian", "sex": "female", "age_months": 52, "lactating": True},
    {"tag_id": "IND-002", "name": "Gowri", "breed": "Jersey", "sex": "female", "age_months": 40, "lactating": True},
    {"tag_id": "IND-003", "name": "Nandini", "breed": "Holstein Friesian", "sex": "female", "age_months": 60, "lactating": True},
    {"tag_id": "IND-004", "name": "Kaveri", "breed": "Sahiwal cross", "sex": "female", "age_months": 45, "lactating": True},
    {"tag_id": "IND-005", "name": "Sita", "breed": "Jersey", "sex": "female", "age_months": 30, "lactating": False},
    {"tag_id": "IND-006", "name": "Ganga", "breed": "Holstein Friesian", "sex": "female", "age_months": 24, "lactating": False},
    {"tag_id": "IND-007", "name": "Parvati", "breed": "Sahiwal cross", "sex": "female", "age_months": 66, "lactating": True},
    {"tag_id": "IND-008", "name": "Yamuna", "breed": "Red Sindhi", "sex": "female", "age_months": 36, "lactating": True},
    {"tag_id": "IND-009", "name": "Tulsi", "breed": "Jersey", "sex": "female", "age_months": 18, "lactating": False},
    {"tag_id": "IND-010", "name": "Radha", "breed": "Holstein Friesian", "sex": "female", "age_months": 50, "lactating": True},
    {"tag_id": "IND-011", "name": "Bhima", "breed": "Hallikar", "sex": "male", "age_months": 48, "lactating": False},
    {"tag_id": "IND-012", "name": "Chandra", "breed": "Red Sindhi", "sex": "female", "age_months": 28, "lactating": False},
]

# Average daily milk (litres) for lactating animals
MILK_BASE = {
    "IND-001": 18.5, "IND-002": 12.0, "IND-003": 21.0, "IND-004": 14.0,
    "IND-007": 16.5, "IND-008": 9.5, "IND-010": 17.0,
}

# (days_ago, temperature_c, symptoms, severity, notes)
HEALTH_EVENTS = {
    "IND-004": [
        (6, 39.0, "normal", "none", "Routine check"),
        (3, 39.9, "reduced appetite, slight udder swelling", "mild", "Synthetic demo event"),
    ],
    "IND-010": [
        (2, 40.1, "fever, reduced milk, warm udder on one side", "moderate", "Synthetic demo event"),
    ],
    "IND-007": [
        (20, 38.6, "normal", "none", "Routine check"),
    ],
}

# (days_ago, event_type, notes)
BREEDING_EVENTS = {
    "IND-005": [(45, "heat_observed", "Standing heat seen in the afternoon")],
    "IND-006": [(70, "heat_observed", "Restless, not confirmed")],
    "IND-003": [(90, "insemination", "Artificial insemination performed")],
}

# ---- Feed inventory (costs in INR, a demo assumption) ----------------------
FEED_ITEMS = [
    {"name": "Green Napier grass", "category": "fodder", "quantity_kg": 800, "reorder_level_kg": 300, "unit_cost_inr": 4.0, "supplier": "Local farm co-op", "quality_grade": "A"},
    {"name": "Maize silage", "category": "silage", "quantity_kg": 1200, "reorder_level_kg": 500, "unit_cost_inr": 6.5, "supplier": "Local farm co-op", "quality_grade": "A"},
    {"name": "Dry hay", "category": "roughage", "quantity_kg": 400, "reorder_level_kg": 300, "unit_cost_inr": 12.0, "supplier": "Hay Traders", "quality_grade": "B"},
    {"name": "Dairy concentrate pellets", "category": "concentrate", "quantity_kg": 250, "reorder_level_kg": 300, "unit_cost_inr": 28.0, "supplier": "FeedMart Pvt Ltd", "quality_grade": "A"},
    {"name": "Mineral mixture", "category": "supplement", "quantity_kg": 60, "reorder_level_kg": 50, "unit_cost_inr": 90.0, "supplier": "FeedMart Pvt Ltd", "quality_grade": "A"},
    {"name": "Mustard oil cake", "category": "protein", "quantity_kg": 120, "reorder_level_kg": 100, "unit_cost_inr": 35.0, "supplier": "Oilseed Depot", "quality_grade": "A"},
    {"name": "Wheat bran", "category": "concentrate", "quantity_kg": 180, "reorder_level_kg": 150, "unit_cost_inr": 22.0, "supplier": "Mill Direct", "quality_grade": "B"},
    {"name": "Groundnut cake", "category": "protein", "quantity_kg": 90, "reorder_level_kg": 120, "unit_cost_inr": 45.0, "supplier": "Oilseed Depot", "quality_grade": "A"},
    {"name": "Salt lick blocks", "category": "supplement", "quantity_kg": 40, "reorder_level_kg": 20, "unit_cost_inr": 18.0, "supplier": "FeedMart Pvt Ltd", "quality_grade": "A"},
    {"name": "Calcium supplement", "category": "supplement", "quantity_kg": 25, "reorder_level_kg": 15, "unit_cost_inr": 150.0, "supplier": "VetCare Supplies", "quality_grade": "A"},
]

# ---- Past farm incidents (farm memory) -------------------------------------
INCIDENTS = [
    {
        "title": "Milk drop after feed supplier change",
        "category": "nutrition",
        "summary": "Milk yield fell across several cows about a week after the farm switched to a cheaper concentrate brand.",
        "keywords": "milk,drop,feed,supplier,concentrate,yield",
        "outcome": "Yield recovered within about 10 days after returning to the previous feed.",
    },
    {
        "title": "Udder infection after heavy rain",
        "category": "health",
        "summary": "A cow developed fever and a swollen, warm udder during a wet week with muddy shelter floors.",
        "keywords": "udder,fever,infection,wet,mud,milk",
        "outcome": "Vet visit confirmed infection (synthetic record). Cow recovered in about 10 days. Shelter drainage was improved.",
    },
    {
        "title": "Missed heat detection delayed breeding",
        "category": "breeding",
        "summary": "Heat signs were not recorded for a cow, so insemination was delayed by one full cycle.",
        "keywords": "heat,breeding,insemination,cycle,missed",
        "outcome": "Heat checks moved to twice daily, morning and evening.",
    },
]


def _days_ago_dt(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _seed_animal_history(db: Session, animal: m.Animal) -> None:
    """Add milk, health and breeding history for a newly created animal."""
    today = date.today()
    tag = animal.tag_id

    if tag in MILK_BASE:
        base = MILK_BASE[tag]
        for days_ago in range(13, -1, -1):
            liters = base + ((days_ago * 3) % 5 - 2) * 0.3  # small daily variation
            if tag == "IND-004" and days_ago <= 3:
                liters *= 0.7  # demo: milk drop
            if tag == "IND-010" and days_ago <= 1:
                liters *= 0.8  # demo: fever-related drop
            db.add(m.MilkRecord(
                animal=animal,
                recorded_on=today - timedelta(days=days_ago),
                liters=round(liters, 1),
            ))

    for days_ago, temp, symptoms, severity, notes in HEALTH_EVENTS.get(tag, []):
        db.add(m.HealthRecord(
            animal=animal,
            recorded_at=_days_ago_dt(days_ago),
            temperature_c=temp,
            symptoms=symptoms,
            severity=severity,
            notes=notes,
        ))

    for days_ago, event_type, notes in BREEDING_EVENTS.get(tag, []):
        db.add(m.BreedingRecord(
            animal=animal,
            event_type=event_type,
            event_date=today - timedelta(days=days_ago),
            notes=notes,
        ))


def seed_database(db: Session) -> dict:
    """Insert demo data that is not already present. Returns how many rows were added."""
    animals_added = 0
    for data in ANIMALS:
        if db.query(m.Animal).filter_by(tag_id=data["tag_id"]).first():
            continue  # already seeded, skip so restarts do not duplicate
        animal = m.Animal(**data, data_source="SYNTHETIC_DEMO")
        db.add(animal)
        db.flush()  # gives the animal an id before adding its history
        _seed_animal_history(db, animal)
        animals_added += 1

    feed_added = 0
    for data in FEED_ITEMS:
        if db.query(m.FeedItem).filter_by(name=data["name"]).first():
            continue
        db.add(m.FeedItem(**data))
        feed_added += 1

    incidents_added = 0
    for data in INCIDENTS:
        if db.query(m.FarmMemory).filter_by(title=data["title"]).first():
            continue
        db.add(m.FarmMemory(**data))
        incidents_added += 1

    db.commit()
    return {
        "animals_added": animals_added,
        "feed_items_added": feed_added,
        "incidents_added": incidents_added,
    }


def run_seed() -> dict:
    """Create tables if needed, then seed. Used by the server and by the command line."""
    init_db()
    db = SessionLocal()
    try:
        return seed_database(db)
    finally:
        db.close()


if __name__ == "__main__":
    print(run_seed())
