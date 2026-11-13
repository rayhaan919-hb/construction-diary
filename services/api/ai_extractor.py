"""Top-level re-export of AI extraction module (see mocks.md)."""

from app.services.ai_extractor import (
    EXTRACTION_PROMPT,
    ExtractionError,
    ExtractionResult,
    extract_from_audio,
    mock_extraction_result,
)

__all__ = [
    "EXTRACTION_PROMPT",
    "ExtractionError",
    "ExtractionResult",
    "extract_from_audio",
    "mock_extraction_result",
]
