"""Daily farm briefing: the top alerts and the priorities for today."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend import models as m
from backend.services import translate
from backend.services.herd import get_herd

_LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2}


def build_briefing(db: Session, lang: str = "en") -> dict:
    herd = get_herd(db)
    alerts: list[dict] = []
    priorities: list[str] = []

    red = [a for a in herd if a["health_indicator"]["color"] == "red"]
    yellow = [a for a in herd if a["health_indicator"]["color"] == "yellow"]

    for animal in red:
        reasons = "; ".join(animal["health_indicator"]["explanations"])
        alerts.append({
            "level": "high",
            "category": "health",
            "message": f"{animal['name']} ({animal['tag_id']}) is red: {reasons}",
        })
        priorities.append(
            f"Check {animal['name']} ({animal['tag_id']}) today: {animal['health_indicator']['explanations'][0]}"
        )

    for animal in yellow:
        reasons = "; ".join(animal["health_indicator"]["explanations"])
        alerts.append({
            "level": "medium",
            "category": "health",
            "message": f"{animal['name']} ({animal['tag_id']}) to watch: {reasons}",
        })

    low_stock = [
        item for item in db.query(m.FeedItem).order_by(m.FeedItem.name).all()
        if item.quantity_kg < item.reorder_level_kg
    ]
    for item in low_stock:
        alerts.append({
            "level": "medium",
            "category": "inventory",
            "message": (f"{item.name}: {item.quantity_kg:.0f} kg left, "
                        f"reorder level is {item.reorder_level_kg:.0f} kg"),
        })
        priorities.append(f"Reorder {item.name}")

    alerts.sort(key=lambda a: _LEVEL_ORDER[a["level"]])

    if not priorities:
        priorities.append("No urgent priorities. Continue routine monitoring.")

    summary = (
        f"{len(red)} animal(s) need attention today, {len(yellow)} to watch, "
        f"and {len(low_stock)} feed item(s) are below reorder level."
    )

    # Translate everything in one request: summary, alert messages, priorities
    texts = [summary] + [a["message"] for a in alerts] + priorities
    translated, mode, reason = translate.translate_texts(texts, lang)

    summary = translated[0]
    for i, alert in enumerate(alerts):
        alert["message"] = translated[1 + i]
    priorities = translated[1 + len(alerts):]

    if mode == "gemini":
        note = f"Translated with Gemini."
    elif mode == "demo":
        note = reason
    else:
        note = None

    return {
        "language": lang,
        "language_note": note,
        "translation_mode": mode,
        "generated_at": datetime.now(timezone.utc),
        "summary": summary,
        "alerts": alerts,
        "priorities": priorities,
    }
