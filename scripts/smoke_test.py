"""Calls every endpoint on a RUNNING server and prints PASS, FAIL or SKIP for each.

Start the server first in one PowerShell window:
    uvicorn backend.main:app --reload

Then in a second window (with the venv active):
    python scripts\\smoke_test.py
    python scripts\\smoke_test.py http://127.0.0.1:8000

SKIP means the check depends on data you have not imported yet. It is not a failure.
"""
import sys

import httpx

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200
results: list[tuple[str, str]] = []  # (name, PASS / FAIL / SKIP)


def record(name: str, status: str, detail: str) -> None:
    results.append((name, status))
    print(f"{status:<5} {name:<40} {detail}")


def verify(name: str, condition: bool, detail: str) -> None:
    """Checks the content of a response, not just its status code."""
    record(name, "PASS" if condition else "FAIL", detail)


def check(name: str, method: str, path: str, expected: int = 200,
          skip_status: int | None = None, skip_hint: str = "", **kwargs):
    try:
        response = httpx.request(method, BASE + path, timeout=60, **kwargs)
    except Exception as exc:
        record(name, "FAIL", f"error: {exc}")
        return None

    if skip_status is not None and response.status_code == skip_status:
        record(name, "SKIP", skip_hint)
        return None

    ok = response.status_code == expected
    record(name, "PASS" if ok else "FAIL", f"HTTP {response.status_code}")
    return response if ok else None


print(f"Testing {BASE}\n")

# ---- Core dashboard and records --------------------------------------------
check("GET  /api/health", "GET", "/api/health")
check("GET  /api/herd", "GET", "/api/herd")
check("GET  /api/cow/IND-001", "GET", "/api/cow/IND-001")
check("GET  /api/memory", "GET", "/api/memory")
check("GET  /api/inventory", "GET", "/api/inventory")
check("GET  /api/actions", "GET", "/api/actions")
check("GET  /api/orders", "GET", "/api/orders")
check("GET  /api/appointments", "GET", "/api/appointments")

# ---- Briefing in English and Hindi -----------------------------------------
check("GET  /api/briefing (en)", "GET", "/api/briefing?lang=en")
hindi = check("GET  /api/briefing (hi)", "GET", "/api/briefing?lang=hi")
if hindi:
    body = hindi.json()
    verify("  briefing hi: translation result",
           body["language"] == "hi" and body["translation_mode"] in ("gemini", "demo"),
           f"translation_mode={body['translation_mode']}")

# ---- Photo diagnosis and PDF report ----------------------------------------
check("POST /api/diagnose", "POST", "/api/diagnose",
      files={"photo": ("cow.png", PNG, "image/png")}, data={"animal_id": "IND-010"})
check("GET  /api/vet-report/IND-010", "GET", "/api/vet-report/IND-010")

# ---- Symptom screening (Health Agent) --------------------------------------
assessed = check("POST /api/assess (mastitis)", "POST", "/api/assess", json={
    "cow_id": "IND-004", "temperature_c": 40.2, "milk_before_l": 18, "milk_now_l": 10,
    "appetite": "reduced", "udder": "swollen", "milk_appearance": "abnormal",
})
if assessed:
    body = assessed.json()
    names = [c["name"] for c in body["possible_conditions"]]
    verify("  assess: Mastitis, high priority",
           "Mastitis" in names and body["priority"] == "high",
           f"priority={body['priority']}, conditions={names}")
    verify("  assess: milk drop calculated",
           body["milk_drop_percent"] == 44.4,
           f"milk_drop_percent={body['milk_drop_percent']}")

# ---- Real research benchmark (needs the INRAE file imported) ---------------
bench = check("GET  /api/benchmark/FR1997603", "GET", "/api/benchmark/FR1997603",
              skip_status=404,
              skip_hint="not imported yet: python -m backend.services.public_data data\\test1.csv")
if bench:
    body = bench.json()
    verify("  benchmark: has lactation data",
           body["lactation_count"] >= 1 and body["cow_avg_305_kg"] is not None,
           f"lactations={body['lactation_count']}, avg_305={body['cow_avg_305_kg']} kg")

# ---- Asking the Manager and approving an action ----------------------------
ask = check("POST /api/ask", "POST", "/api/ask",
            json={"question": "Radha has a fever, what should we do?", "language": "en"})
if ask:
    body = ask.json()
    verify("  ask: AI mode reported honestly",
           body["ai_mode_used"] in ("gemini", "demo"),
           f"ai_mode_used={body['ai_mode_used']}")
    vet = [a for a in body["proposed_actions"]
           if a["action_type"] == "book_vet" and a["status"] == "proposed"]
    if vet:
        check("POST /api/actions/{id}/approve", "POST",
              f"/api/actions/{vet[0]['id']}/approve")
    else:
        record("POST /api/actions/{id}/approve", "SKIP", "no pending vet visit to approve")

# ---- Live agent updates over SSE -------------------------------------------
try:
    with httpx.stream("GET", BASE + "/api/ask/stream",
                      params={"question": "Radha has a fever"}, timeout=60) as response:
        text = "".join(response.iter_text())
    ok = response.status_code == 200 and "event: final" in text and "event: agent_done" in text
    record("GET  /api/ask/stream", "PASS" if ok else "FAIL",
           "live events received" if ok else "missing events")
except Exception as exc:
    record("GET  /api/ask/stream", "FAIL", f"error: {exc}")

# ---- Summary ---------------------------------------------------------------
passed = sum(1 for _, s in results if s == "PASS")
failed = sum(1 for _, s in results if s == "FAIL")
skipped = sum(1 for _, s in results if s == "SKIP")
print(f"\n{passed} passed, {skipped} skipped, {failed} failed.")
sys.exit(1 if failed else 0)