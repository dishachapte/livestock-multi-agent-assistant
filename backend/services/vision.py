"""Photo diagnosis: visual assessment with Gemini vision, or a safe demo answer.

This never gives a confirmed diagnosis and never recommends medicines.
"""
from backend.config import settings
from backend.services import llm

DISCLAIMER = (
    "This is an AI-assisted visual check, not a confirmed veterinary diagnosis. "
    "Please consult a veterinarian before acting on it."
)
URGENCY_LEVELS = {"routine", "see_vet_soon", "urgent", "unknown"}
LIKELIHOODS = {"low", "medium", "high"}
DEMO_NEXT_STEPS = [
    "Check the animal's temperature, eating and milk yield today.",
    "If you see swelling, discharge, limping, bleeding, or the animal is off its feed, call a veterinarian.",
]


class ImageError(ValueError):
    """The upload is not a usable photo. The route turns this into HTTP 400."""


def detect_image_type(data: bytes) -> str | None:
    """Check the real file signature (magic bytes), not just the file name."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_image(data: bytes, max_mb: int) -> str:
    if not data:
        raise ImageError("The uploaded file is empty")
    if len(data) > max_mb * 1024 * 1024:
        raise ImageError(f"The photo is larger than {max_mb} MB")
    mime = detect_image_type(data)
    if mime is None:
        raise ImageError("Only JPEG, PNG or WebP images are accepted")
    return mime


def _prompt(animal_context: str) -> str:
    return f"""You are assisting a livestock farmer with a photo of an animal.

Rules:
- Describe only what is visible. Say so if the photo is unclear.
- Do NOT give a definitive diagnosis. You may list possibilities with a likelihood of low, medium or high.
- Do NOT recommend medicines, doses or treatments. Recommend next steps such as calling a veterinarian,
  isolating the animal, checking temperature, and watching eating and milk yield.
- urgency must be one of: routine, see_vet_soon, urgent, unknown.
- Use "urgent" for signs such as heavy bleeding, severe swelling, trouble breathing, or inability to stand.

Return ONLY a JSON object in this form:
{{"observations": ["..."], "possible_conditions": [{{"name": "...", "likelihood": "low"}}],
  "urgency": "routine", "next_steps": ["..."]}}

Animal context: {animal_context}
"""


def _clean(data: dict) -> dict:
    observations = [str(x)[:300] for x in data.get("observations", []) if str(x).strip()][:6]

    conditions = []
    for item in (data.get("possible_conditions") or [])[:5]:
        if isinstance(item, dict) and str(item.get("name", "")).strip():
            likelihood = str(item.get("likelihood", "low")).lower()
            conditions.append({
                "name": str(item["name"])[:120],
                "likelihood": likelihood if likelihood in LIKELIHOODS else "low",
            })

    urgency = data.get("urgency") if data.get("urgency") in URGENCY_LEVELS else "unknown"
    steps = [str(x)[:300] for x in data.get("next_steps", []) if str(x).strip()][:6]
    if not steps:
        steps = DEMO_NEXT_STEPS

    return {"observations": observations, "possible_conditions": conditions,
            "urgency": urgency, "next_steps": steps}


def diagnose(data: bytes, max_mb: int, animal_context: str | None) -> dict:
    mime = validate_image(data, max_mb)
    file_info = {"type": mime, "size_kb": round(len(data) / 1024, 1)}
    context_text = animal_context or "No animal selected"

    if settings.gemini_enabled:
        try:
            result = llm.generate_json_with_image(_prompt(context_text), data, mime)
            return {"ai_mode_used": "gemini", "fallback_reason": None, "file": file_info,
                    "disclaimer": DISCLAIMER, **_clean(result)}
        except llm.LLMError as exc:
            reason = str(exc)[:300]
    else:
        reason = "GEMINI_API_KEY is not set, so demo mode answered"

    # Demo answer: honest about what it cannot see, invents no conditions
    return {
        "ai_mode_used": "demo",
        "fallback_reason": reason,
        "file": file_info,
        "observations": [
            f"Photo received ({file_info['size_kb']} KB, {mime}). "
            "Visual analysis needs Gemini vision, which is not active in demo mode."
        ],
        "possible_conditions": [],
        "urgency": "unknown",
        "next_steps": DEMO_NEXT_STEPS,
        "disclaimer": DISCLAIMER,
    }
