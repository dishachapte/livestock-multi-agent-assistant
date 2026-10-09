"""FastAPI application. Start it with:  uvicorn backend.main:app --reload"""
import json
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.agents.manager import merge_actions, run_manager
from backend import models as m
from backend.config import settings
from backend.database import get_db
from backend.schemas import (
    ActionDecisionResponse,
    ActionListResponse,
    AppointmentsResponse,
    AskRequest,
    AskResponse,
    BriefingResponse,
    CowDetail,
    HealthResponse,
    HerdResponse,
    InventoryResponse,
    Lang,
    MemoryResponse,
    OrdersResponse,
    AssessmentResponse,
    BenchmarkResponse,
    CowReport,
    DiagnosisResponse,
    RejectRequest,
)
from backend.seed_data import run_seed
from backend.services import actions as action_service
from backend.services import briefing as briefing_service
from backend.services import herd as herd_service
from backend.services import records
from backend.services.actions import ActionError
from backend.services import vet_report, vision
from backend.services.streaming import stream_ask
from backend.services import public_data
from backend.services import disease


@asynccontextmanager
async def lifespan(app: FastAPI):
    result = run_seed()  # create tables and demo data; safe to repeat
    print(f"[startup] demo data: {result}")
    yield


app = FastAPI(
    title="Livestock Multi-Agent Farm Assistant",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    print(f"[error] {request.method} {request.url.path}: {exc!r}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Unexpected server error. Check the terminal for details."},
    )


def _run_action_step(fn, *args):
    """Turn ActionError into an HTTP error with a clear message."""
    try:
        return fn(*args)
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


# ---- Stage 2 endpoints ----------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "ai_mode": "gemini" if settings.gemini_enabled else "demo",
        "gemini_key_configured": settings.gemini_enabled,
        "database": db_status,
        "server_time": datetime.now(timezone.utc),
    }


@app.get("/api/herd", response_model=HerdResponse)
def herd(db: Session = Depends(get_db)):
    animals = herd_service.get_herd(db)
    counts = {"green": 0, "yellow": 0, "red": 0}
    for animal in animals:
        counts[animal["health_indicator"]["color"]] += 1
    return {"count": len(animals), **counts, "animals": animals}


@app.get("/api/cow/{cow_id}", response_model=CowDetail)
def cow(cow_id: str, db: Session = Depends(get_db)):
    animal = herd_service.find_animal(db, cow_id)
    if animal is None:
        raise HTTPException(
            status_code=404,
            detail=f"No animal found with id or tag '{cow_id}'. Try IND-001 or 1.",
        )
    return herd_service.get_cow_detail(db, animal)


@app.get("/api/briefing", response_model=BriefingResponse)
def briefing(lang: Lang = Query("en"), db: Session = Depends(get_db)):
    return briefing_service.build_briefing(db, lang)


# ---- Stage 3 endpoint -----------------------------------------------------

@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    return run_manager(db, payload.question, payload.language)


# ---- Stage 4 endpoints ----------------------------------------------------

@app.get("/api/inventory", response_model=InventoryResponse)
def inventory(db: Session = Depends(get_db)):
    return records.list_inventory(db)


@app.get("/api/memory", response_model=MemoryResponse)
def memory(db: Session = Depends(get_db)):
    return records.list_memory(db)


@app.get("/api/actions", response_model=ActionListResponse)
def actions(
    status: Literal["proposed", "approved", "rejected", "completed", "failed"] | None = Query(None),
    db: Session = Depends(get_db),
):
    result = records.list_actions(db, status)
    return {
        "count": result["count"],
        "actions": [action_service.serialize_action(row) for row in result["actions"]],
    }


@app.post("/api/actions/{action_id}/approve", response_model=ActionDecisionResponse)
def approve(action_id: int, db: Session = Depends(get_db)):
    row = _run_action_step(action_service.approve_action, db, action_id)
    serialized = action_service.serialize_action(row)
    message = (serialized["result"] or {}).get("message", "Action completed.")
    return {"message": message, "action": serialized}


@app.post("/api/actions/{action_id}/reject", response_model=ActionDecisionResponse)
def reject(action_id: int, payload: RejectRequest | None = None, db: Session = Depends(get_db)):
    reason = payload.reason if payload else None
    row = _run_action_step(action_service.reject_action, db, action_id, reason)
    return {
        "message": "Action rejected. Nothing was executed.",
        "action": action_service.serialize_action(row),
    }


@app.get("/api/orders", response_model=OrdersResponse)
def orders(db: Session = Depends(get_db)):
    return records.list_orders(db)


@app.get("/api/appointments", response_model=AppointmentsResponse)
def appointments(db: Session = Depends(get_db)):
    return records.list_appointments(db)


# ---- Stage 5 endpoints ----------------------------------------------------

@app.post("/api/diagnose", response_model=DiagnosisResponse)
def diagnose(
    photo: UploadFile = File(...),
    animal_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    # Read at most one byte over the limit, so huge uploads are never fully loaded
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = photo.file.read(limit + 1)

    animal = None
    context = None
    if animal_id and animal_id.strip():
        animal = herd_service.find_animal(db, animal_id.strip())
        if animal is None:
            raise HTTPException(status_code=404, detail=f"No animal found with id or tag '{animal_id}'.")
        detail = herd_service.animal_to_dict(animal)
        context = (f"{detail['name']} ({detail['tag_id']}), breed {detail['breed']}, "
                   f"lactating: {detail['lactating']}. Recent health flags: "
                   + "; ".join(detail["health_indicator"]["explanations"]))

    try:
        result = vision.diagnose(data, settings.MAX_UPLOAD_MB, context)
    except vision.ImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result["animal_tag"] = animal.tag_id if animal else None
    return result


@app.get("/api/vet-report/{cow_id}")
def vet_report_pdf(cow_id: str, db: Session = Depends(get_db)):
    animal = herd_service.find_animal(db, cow_id)
    if animal is None:
        raise HTTPException(status_code=404, detail=f"No animal found with id or tag '{cow_id}'.")
    pdf_bytes = vet_report.build_vet_report(db, animal)
    filename = f"vet-report-{animal.tag_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---- Stage 6: live agent updates -----------------------------------------

@app.get("/api/ask/stream")
def ask_stream(
    question: str = Query(..., min_length=3, max_length=500),
    language: Lang = Query("en"),
):
    """Streams each agent's result as it finishes (Server-Sent Events)."""
    return StreamingResponse(
        stream_ask(question.strip(), language),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


# ---- Public research benchmark (INRAE real herd history) ------------------

@app.get("/api/benchmark/{cow_id}", response_model=BenchmarkResponse)
def benchmark(cow_id: str, db: Session = Depends(get_db)):
    """Compares a research-herd cow's 305-day milk with the dataset average."""
    result = public_data.benchmark(db, cow_id.strip().upper())
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No public-dataset cow '{cow_id}'. Import the file first, then try e.g. FR1997603.",
        )
    return result


# ---- Symptom screening: Health Agent input ---------------------------------

@app.post("/api/assess", response_model=AssessmentResponse)
def assess_cow(report: CowReport, db: Session = Depends(get_db)):
    """Screens a farmer's symptom report and sends proposals to the approval queue."""
    animal = herd_service.find_animal(db, report.cow_id)
    if animal is None:
        raise HTTPException(status_code=404, detail=f"No animal found with id or tag '{report.cow_id}'.")

    payload = report.model_dump()
    result = disease.assess(payload, animal.id, animal.tag_id, animal.name, date.today())

    row = m.SymptomReport(
        animal_id=animal.id,
        input_json=json.dumps(payload, default=str),
        result_json=json.dumps(result),
    )
    db.add(row)
    db.commit()

    rows = action_service.create_proposals(db, merge_actions(result["actions"])) if result["actions"] else []
    proposed = [action_service.serialize_action(r) for r in rows]

    return {"report_id": row.id, **result, "proposed_actions": proposed}
