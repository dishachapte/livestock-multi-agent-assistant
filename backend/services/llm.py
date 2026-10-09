"""Gemini wrapper. Every AI call goes through here, so fallback handling lives in one place."""
import json

from google import genai
from google.genai import types

from backend.config import settings


class LLMError(Exception):
    """Raised when Gemini is missing, fails, or returns something unusable."""


_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _parse_json_object(text: str) -> dict:
    try:
        data = json.loads((text or "").strip())
    except json.JSONDecodeError as exc:
        raise LLMError("Gemini returned text that is not valid JSON") from exc
    if not isinstance(data, dict):
        raise LLMError("Gemini JSON was not an object")
    return data


def generate_json(prompt: str) -> dict:
    """Send a text prompt and return the parsed JSON object."""
    if not settings.gemini_enabled:
        raise LLMError("GEMINI_API_KEY is not set")
    try:
        response = _get_client().models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
    except Exception as exc:
        raise LLMError(f"Gemini request failed: {exc}") from exc
    return _parse_json_object(response.text)


def generate_json_with_image(prompt: str, image_bytes: bytes, mime_type: str) -> dict:
    """Send a photo plus a prompt to Gemini vision and return the parsed JSON object."""
    if not settings.gemini_enabled:
        raise LLMError("GEMINI_API_KEY is not set")
    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = _get_client().models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
    except Exception as exc:
        raise LLMError(f"Gemini vision request failed: {exc}") from exc
    return _parse_json_object(response.text)
