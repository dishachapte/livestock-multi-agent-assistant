"""Stage 7 checks: importing the INRAE file, duplicate protection, and the benchmark endpoint."""
import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.database import SessionLocal, init_db
from backend.main import app
from backend.services import public_data


def make_row(values: dict) -> list[str]:
    row = [""] * 97
    for index, value in values.items():
        row[index] = value
    return row


@pytest.fixture(scope="module")
def sample_file(tmp_path_factory) -> Path:
    header = [f"col{i}" for i in range(97)]
    rows = [
        make_row({0: "ORG", 1: "HOL", 2: "TEST0001", 3: "11-11-96", 5: "20-11-99", 7: "1",
                  23: "20-11-99", 26: "1", 27: "3", 39: ".", 42: "4.5", 49: "6800", 50: "7975"}),
        make_row({0: "ORG", 1: "HOL", 2: "TEST0001", 3: "11-11-96", 5: "31-03-01", 7: "2",
                  23: "31-03-01", 26: "0", 27: "1", 39: "280", 42: "5.0", 49: "7200", 50: "8100"}),
        make_row({0: "ORG", 1: "MONT", 2: "TEST0002", 3: "02-02-98", 5: "10-05-02", 7: "1",
                  23: "10-05-02", 26: "2", 27: "0", 39: "275", 42: "3.9", 49: "5000", 50: "5600"}),
    ]
    path = tmp_path_factory.mktemp("data") / "inrae_sample.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_import_creates_cows_and_lactations(sample_file):
    init_db()
    db = SessionLocal()
    try:
        result = public_data.import_file(db, sample_file)
        assert result["cows_added"] == 2
        assert result["lactations_added"] == 3
    finally:
        db.close()


def test_second_import_adds_nothing(sample_file):
    db = SessionLocal()
    try:
        result = public_data.import_file(db, sample_file)
        assert result == {"cows_added": 0, "lactations_added": 0, "rows_skipped": 3}
    finally:
        db.close()


def test_missing_value_becomes_none(client):
    body = client.get("/api/benchmark/TEST0001").json()
    first = next(l for l in body["lactations"] if l["lactation_number"] == 1)
    assert first["milk_305_kg"] == 6800.0
    assert first["calving_date"] == "1999-11-20"


def test_benchmark_compares_with_dataset(client):
    body = client.get("/api/benchmark/TEST0001").json()
    assert body["lactation_count"] == 2
    assert body["cow_avg_305_kg"] == 7000.0
    assert body["dataset_avg_305_kg"] is not None
    assert body["percent_vs_dataset"] is not None
    assert "not live farm data" in body["note"].lower()


def test_benchmark_unknown_cow_returns_404(client):
    assert client.get("/api/benchmark/NOPE-999").status_code == 404


def test_wrong_file_is_rejected(tmp_path):
    bad = tmp_path / "wrong.csv"
    bad.write_text("name,age\nBessie,4\nDaisy,5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="columns"):
        public_data.read_rows(bad)
