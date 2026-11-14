from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import ai_extractor
from app.core.config import Settings
from app.schemas.logs import StructuredSummary
from app.services.ai_extractor import ExtractionResult, extract_from_audio
from app.services.storage import MediaStorageService


def test_mock_gemini_extractor_deterministic_and_fast() -> None:
    cfg = Settings(USE_MOCK_GEMINI=True)
    started = time.perf_counter()
    result = extract_from_audio("local://projects/p1/audio/log1.m4a", settings=cfg)
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert result.structured_summary.tasks_completed == ["Foundation pouring Block B"]
    assert result.structured_summary.labor_count == 14
    assert len(result.structured_summary.material_deliveries) > 0
    assert len(result.structured_summary.blockers) > 0
    assert result.transcript
    assert result.detected_language in ("ur", "en", "ar", "mixed", "unknown")

    # Verify top-level re-export in services/api/ai_extractor.py matches
    reexported = ai_extractor.extract_from_audio(
        "local://projects/p1/audio/log1.m4a", settings=cfg
    )
    assert reexported == result


def test_gemini_ai_studio_and_vertex_modes(tmp_path: Path) -> None:
    expected = ExtractionResult(
        transcript="Test transcript",
        detected_language="en",
        structured_summary=StructuredSummary(
            tasks_completed=["Steel fixing"],
            labor_count=9,
            material_deliveries=["Steel bars"],
            blockers=[],
        ),
    )

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = SimpleNamespace(
        parsed=expected,
        text=expected.model_dump_json(),
    )

    # AI Studio mode (inline bytes)
    storage_cfg = Settings(
        USE_MOCK_GEMINI=False,
        GEMINI_API_KEY="test-api-key",
        GOOGLE_GENAI_USE_VERTEXAI=False,
        STORAGE_BACKEND="local",
        LOCAL_STORAGE_DIR=str(tmp_path),
    )
    storage = MediaStorageService(storage_cfg)
    storage.write_local_bytes("projects/p1/audio/l1.m4a", b"m4a-audio-bytes")

    with patch("google.genai.Client", return_value=fake_client) as client_cls:
        res = extract_from_audio(
            "local://projects/p1/audio/l1.m4a", storage=storage, settings=storage_cfg
        )
        assert res == expected
        client_cls.assert_called_once()
        assert client_cls.call_args.kwargs["api_key"] == "test-api-key"
        assert client_cls.call_args.kwargs["http_options"].timeout == 60000

    # Vertex AI mode (gs:// URI)
    vertex_cfg = Settings(
        USE_MOCK_GEMINI=False,
        GOOGLE_GENAI_USE_VERTEXAI=True,
        GOOGLE_CLOUD_PROJECT="test-gcp-project",
        GOOGLE_CLOUD_LOCATION="us-central1",
    )
    with patch("google.genai.Client", return_value=fake_client) as client_cls:
        res_v = extract_from_audio(
            "gs://my-bucket/projects/p1/audio/l1.m4a", settings=vertex_cfg
        )
        assert res_v == expected
        client_cls.assert_called_once()
        assert client_cls.call_args.kwargs["vertexai"] is True
        assert client_cls.call_args.kwargs["project"] == "test-gcp-project"
        assert client_cls.call_args.kwargs["location"] == "us-central1"
        assert client_cls.call_args.kwargs["http_options"].timeout == 60000


def test_gcs_storage_signed_urls_and_exists() -> None:
    gcs_cfg = Settings(
        STORAGE_BACKEND="gcs",
        GCS_BUCKET="site-diary-test-bucket",
        SIGNED_URL_TTL_SECONDS=900,
    )
    service = MediaStorageService(gcs_cfg)

    fake_blob = MagicMock()
    fake_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-v4"
    fake_blob.exists.return_value = True
    fake_bucket = MagicMock()
    fake_bucket.blob.return_value = fake_blob
    fake_gcs_client = MagicMock()
    fake_gcs_client.bucket.return_value = fake_bucket

    pid = uuid4()
    oid = uuid4()
    tid = uuid4()
    fake_sa_creds = SimpleNamespace(sign_bytes=lambda data: b"sig")
    with (
        patch("google.cloud.storage.Client", return_value=fake_gcs_client),
        patch("google.auth.default", return_value=(fake_sa_creds, "test-proj")),
    ):
        ticket = service.create_upload_ticket(
            project_id=pid,
            kind="AUDIO",
            object_id=oid,
            content_type="audio/mp4",
            ticket_id=tid,
            expected_byte_size=2048,
        )
        assert ticket.upload_url == "https://storage.googleapis.com/signed-v4"
        assert (
            ticket.storage_uri
            == f"gs://site-diary-test-bucket/projects/{pid}/audio/{oid}/{tid}.m4a"
        )
        assert ticket.headers == {
            "Content-Type": "audio/mp4",
            "x-goog-if-generation-match": "0",
            "x-goog-content-length-range": "1,2048",
        }

        read_url = service.sign_get_url(ticket.storage_uri, ttl_seconds=3600)
        assert read_url == "https://storage.googleapis.com/signed-v4"
        assert service.exists(ticket.storage_uri) is True
