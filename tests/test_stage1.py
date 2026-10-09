"""Stage 1 checks: tables are created, seed data is inserted, and re-seeding adds nothing."""
from backend import models as m
from backend.database import SessionLocal, init_db
from backend.seed_data import seed_database


def _counts(db):
    return {
        "animals": db.query(m.Animal).count(),
        "feed": db.query(m.FeedItem).count(),
        "memory": db.query(m.FarmMemory).count(),
        "health": db.query(m.HealthRecord).count(),
        "milk": db.query(m.MilkRecord).count(),
    }


def test_seed_creates_required_sample_data():
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
        counts = _counts(db)
        assert counts["animals"] >= 10
        assert counts["feed"] >= 10
        assert counts["memory"] == 3
        assert counts["health"] > 0
        assert counts["milk"] > 0
    finally:
        db.close()


def test_seed_is_idempotent():
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
        before = _counts(db)
        result = seed_database(db)  # simulate a server restart
        after = _counts(db)
        assert result == {"animals_added": 0, "feed_items_added": 0, "incidents_added": 0}
        assert before == after
    finally:
        db.close()


def test_animals_are_labelled_synthetic():
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
        sources = {a.data_source for a in db.query(m.Animal).all()}
        assert sources == {"SYNTHETIC_DEMO"}
    finally:
        db.close()
