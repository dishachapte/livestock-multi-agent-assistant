# Livestock Multi-Agent Farm Assistant (Backend)

A beginner-friendly FastAPI backend for a livestock farm assistant.
Stage 1 gives you the project setup, database models, and synthetic demo data.

## Folder layout

farm-assistant/
  .env.example          <- copy to .env and add your Gemini key (optional)
  pytest.ini
  README.md
  backend/
    __init__.py
    config.py           <- reads settings from .env
    database.py         <- SQLite engine and sessions
    models.py           <- database tables
    seed_data.py        <- synthetic demo data (safe to run many times)
    requirements.txt
    agents/             <- specialist agents (added in Stage 3)
    services/           <- memory, actions, vision, PDF (added in later stages)
  tests/
    conftest.py
    test_stage1.py

## Setup in PowerShell (Windows)

Run these commands from the folder that contains farm-assistant:

cd farm-assistant
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
copy .env.example .env
python -m backend.seed_data
pytest tests -v

If activation is blocked, run this once and try again:
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

## Expected output

The first seed run prints:
{'animals_added': 12, 'feed_items_added': 10, 'incidents_added': 3}

Running the seed again prints all zeros, which proves restarts do not duplicate data:
{'animals_added': 0, 'feed_items_added': 0, 'incidents_added': 0}

pytest should show 3 passed.

## Notes

* All sample data is labelled SYNTHETIC_DEMO. It is not real farm data.
* Money values are in INR (Indian Rupees), which is an assumption for the demo.
* The database file farm.db is created automatically inside farm-assistant/.
