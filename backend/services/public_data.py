"""Imports the INRAE dairy-cow lactation file (real research-herd history).

These cows are kept in their own tables, not the live herd. Their dates are
years old, so they must never trigger live alerts.

Run from the farm-assistant folder (PowerShell):
    python -m backend.services.public_data data\\test1.csv
"""
import csv
import sys
from datetime import date, datetime
from pathlib import Path
from statistics import mean

from sqlalchemy.orm import Session

from backend import models as m
from backend.database import SessionLocal, init_db

SOURCE = "PUBLIC_INRAE"
SOURCE_NOTE = ("Historical records from a French INRAE research dairy herd (1996-2010). "
               "Not live farm data.")
MIN_COLUMNS = 51  # the file has 97 columns; fewer means it is the wrong file
MISSING = {"", ".", "na", "nan", "-"}
BREED_NAMES = {"HOL": "Holstein", "MON": "Montbeliarde", "MONT": "Montbeliarde"}

# Column positions (0-based). Positions are used because the file repeats some column names.
COL = {
    "breed": 1,
    "animal_id": 2,
    "birth": 3,
    "lactation_start": 5,
    "lactation_number": 7,
    "calving": 23,          # calving date of this lactation
    "mastitis": 26,         # "Nb Mam"
    "lameness": 27,         # "Nb boiterie"
    "gestation_days": 39,
    "avg_daily_milk": 42,   # "Average daily MY (kg/day)"
    "milk_305": 49,         # "Cumulative MY until 305 days (kg)"
    "milk_total": 50,       # "Cumulative MY total lactation (kg)"
}


def _cell(row: list[str], index: int) -> str:
    return row[index] if index < len(row) else ""


def _clean(value: str) -> str | None:
    text = (value or "").strip()
    return None if text.lower() in MISSING else text


def _float(value: str) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int(value: str) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _date(value: str) -> date | None:
    text = _clean(value)
    if text is None:
        return None
    for fmt in ("%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def read_rows(path: Path) -> list[list[str]]:
    """Return the data rows (header removed). Raises ValueError if the file looks wrong."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    rows = list(csv.reader(text.splitlines(), delimiter=","))
    if len(rows) < 2:
        raise ValueError("The file has no data rows.")
    if len(rows[0]) < MIN_COLUMNS:
        raise ValueError(
            f"This file has {len(rows[0])} columns, but the INRAE lactation file has 97. "
            "Check that you downloaded the right file."
        )
    return rows[1:]


def import_file(db: Session, path: Path) -> dict:
    rows = read_rows(path)
    cows = {c.source_id: c for c in db.query(m.PublicCow).all()}
    existing = {(l.cow_id, l.lactation_number) for l in db.query(m.PublicLactation).all()}

    cows_added = lactations_added = skipped = 0
    for row in rows:
        animal_id = _clean(_cell(row, COL["animal_id"]))
        lactation_number = _int(_cell(row, COL["lactation_number"]))
        if animal_id is None or lactation_number is None:
            skipped += 1
            continue

        cow = cows.get(animal_id)
        if cow is None:
            raw_breed = _clean(_cell(row, COL["breed"])) or "Unknown"
            cow = m.PublicCow(
                source_id=animal_id,
                source=SOURCE,
                breed=BREED_NAMES.get(raw_breed.upper(), raw_breed),
                birth_date=_date(_cell(row, COL["birth"])),
            )
            db.add(cow)
            db.flush()
            cows[animal_id] = cow
            cows_added += 1

        key = (cow.id, lactation_number)
        if key in existing:
            skipped += 1
            continue

        db.add(m.PublicLactation(
            cow_id=cow.id,
            lactation_number=lactation_number,
            lactation_start=_date(_cell(row, COL["lactation_start"])),
            calving_date=_date(_cell(row, COL["calving"])),
            milk_305_kg=_float(_cell(row, COL["milk_305"])),
            milk_total_kg=_float(_cell(row, COL["milk_total"])),
            avg_daily_milk_kg=_float(_cell(row, COL["avg_daily_milk"])),
            mastitis_count=_int(_cell(row, COL["mastitis"])),
            lameness_count=_int(_cell(row, COL["lameness"])),
            gestation_days=_float(_cell(row, COL["gestation_days"])),
        ))
        existing.add(key)
        lactations_added += 1

    db.commit()
    return {"cows_added": cows_added, "lactations_added": lactations_added, "rows_skipped": skipped}


def benchmark(db: Session, source_id: str) -> dict | None:
    """Compare one cow's 305-day milk with the average across the whole dataset."""
    cow = db.query(m.PublicCow).filter(m.PublicCow.source_id == source_id).first()
    if cow is None:
        return None

    lactations = sorted(cow.lactations, key=lambda l: l.lactation_number)
    cow_values = [l.milk_305_kg for l in lactations if l.milk_305_kg is not None]
    all_values = [v for (v,) in db.query(m.PublicLactation.milk_305_kg)
                  .filter(m.PublicLactation.milk_305_kg.isnot(None)).all()]

    cow_avg = round(mean(cow_values), 1) if cow_values else None
    dataset_avg = round(mean(all_values), 1) if all_values else None
    percent = (round((cow_avg - dataset_avg) / dataset_avg * 100, 1)
               if cow_avg is not None and dataset_avg else None)

    return {
        "source": SOURCE,
        "cow_id": cow.source_id,
        "breed": cow.breed,
        "lactation_count": len(lactations),
        "cow_avg_305_kg": cow_avg,
        "dataset_avg_305_kg": dataset_avg,
        "percent_vs_dataset": percent,
        "lactations": [
            {
                "lactation_number": l.lactation_number,
                "calving_date": l.calving_date,
                "milk_305_kg": l.milk_305_kg,
                "milk_total_kg": l.milk_total_kg,
                "avg_daily_milk_kg": l.avg_daily_milk_kg,
                "mastitis_count": l.mastitis_count,
                "lameness_count": l.lameness_count,
            }
            for l in lactations
        ],
        "note": SOURCE_NOTE,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m backend.services.public_data data\\test1.csv")
    init_db()
    db = SessionLocal()
    try:
        print(import_file(db, Path(sys.argv[1])))
    finally:
        db.close()
