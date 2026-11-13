from __future__ import annotations

from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.schemas.logs import DetectedLanguage, StructuredSummary
from app.services.storage import MediaStorageService

EXTRACTION_PROMPT = (
    "You are an expert construction site assistant. Listen to this construction site voice log "
    "(which may be spoken in Urdu, English, Arabic, or mixed languages). "
    "1. Produce an accurate transcript in the original spoken language. "
    "2. Identify detected_language as one of: 'ur', 'en', 'ar', 'mixed', 'unknown'. "
    "3. Produce an English-normalised structured_summary with: "
    "tasks_completed (list of strings), labor_count (integer headcount or null if unmentioned), "
    "material_deliveries (list of strings), and blockers (list of strings)."
)


class ExtractionResult(BaseModel):
    transcript: str
    detected_language: DetectedLanguage
    structured_summary: StructuredSummary


class ExtractionError(Exception):
    """Raised when audio extraction fails."""


def mock_extraction_result() -> ExtractionResult:
    """Deterministic offline extraction fixture matching mocks.md."""
    return ExtractionResult(
        transcript=(
            "Aaj Block B ki foundation pouring mukammal hui, 14 mazdoor kaam par thay, "
            "cement aur steel delivery aayi hai, crane safety inspection pending hai."
        ),
        detected_language="ur",
        structured_summary=StructuredSummary(
            tasks_completed=["Foundation pouring Block B"],
            labor_count=14,
            material_deliveries=["50 bags cement", "Rebar steel bundle"],
            blockers=["Waiting on tower crane safety inspection"],
        ),
    )


def extract_from_audio(
    audio_uri: str,
    storage: MediaStorageService | None = None,
    settings: Settings | None = None,
) -> ExtractionResult:
    cfg = settings or get_settings()
    if cfg.USE_MOCK_GEMINI:
        return mock_extraction_result()

    from google import genai
    from google.genai import types

    media_storage = storage or MediaStorageService(cfg)

    if cfg.GOOGLE_GENAI_USE_VERTEXAI:
        client = genai.Client(
            vertexai=True,
            project=cfg.GOOGLE_CLOUD_PROJECT or None,
            location=cfg.GOOGLE_CLOUD_LOCATION,
        )
        if audio_uri.startswith("gs://"):
            audio_part = types.Part.from_uri(file_uri=audio_uri, mime_type="audio/mp4")
        else:
            audio_bytes = media_storage.read_bytes(audio_uri)
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp4")
    else:
        if not cfg.GEMINI_API_KEY or cfg.GEMINI_API_KEY == "your_key_here":
            raise ExtractionError("GEMINI_API_KEY is not configured")
        client = genai.Client(api_key=cfg.GEMINI_API_KEY)
        audio_bytes = media_storage.read_bytes(audio_uri)
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp4")

    response = client.models.generate_content(
        model=cfg.GEMINI_MODEL,
        contents=[EXTRACTION_PROMPT, audio_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractionResult,
            temperature=0.0,
            http_options=types.HttpOptions(
                timeout=cfg.EXTRACTION_TIMEOUT_SECONDS * 1000
            ),
        ),
    )

    if response.parsed is not None and isinstance(response.parsed, ExtractionResult):
        return response.parsed

    if not response.text:
        raise ExtractionError("Gemini returned an empty response")

    return ExtractionResult.model_validate_json(response.text)
