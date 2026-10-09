"""Translates farmer-facing text with Gemini. Falls back to English with a clear reason."""
import json

from backend.config import settings
from backend.services import llm

LANG_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}


def translate_texts(texts: list[str], lang: str) -> tuple[list[str], str, str | None]:
    """Return (texts, translation_mode, fallback_reason).

    translation_mode is "not_needed" for English, "gemini" when translation worked,
    and "demo" when it fell back to English.
    """
    if lang == "en" or not texts:
        return texts, "not_needed", None

    if not settings.gemini_enabled:
        return texts, "demo", "GEMINI_API_KEY is not set, so the text is shown in English"

    prompt = f"""Translate each item in the JSON list below into {LANG_NAMES[lang]}.

Rules:
- Keep numbers, units (kg, C, INR, %), tag IDs such as IND-001 and animal names unchanged.
- Keep the same order and return exactly the same number of items.
- Use simple, farmer-friendly language.

Return ONLY a JSON object in this form: {{"translations": ["...", "..."]}}

ITEMS:
{json.dumps(texts, ensure_ascii=False)}
"""
    try:
        data = llm.generate_json(prompt)
        translated = data.get("translations")
        valid = (
            isinstance(translated, list)
            and len(translated) == len(texts)
            and all(isinstance(t, str) and t.strip() for t in translated)
        )
        if not valid:
            raise llm.LLMError("Translation returned an unexpected shape")
        return [t.strip() for t in translated], "gemini", None
    except llm.LLMError as exc:
        return texts, "demo", f"Translation failed, so the text is shown in English: {str(exc)[:200]}"
