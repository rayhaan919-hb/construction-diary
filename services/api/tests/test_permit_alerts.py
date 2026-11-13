from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import DeviceToken, Permit, PermitAlert, Project, User
from app.jobs.permit_alerts import (
    ConsoleNotifier,
    EmailNotifier,
    FcmNotifier,
    PermitAlertPayload,
    run_permit_alerts,
)


def test_permit_alerts_thresholds_and_deduplication(
    db_session: Session,
    sample_project: Project,
    owner_user: User,
) -> None:
    local_today = datetime.now(ZoneInfo(sample_project.timezone)).date()

    # One permit in each threshold + one outside (>30d) + one soft-deleted
    specs = [
        ("P_D30", local_today + timedelta(days=20), None),
        ("P_D14", local_today + timedelta(days=10), None),
        ("P_D7", local_today + timedelta(days=5), None),
        ("P_D1", local_today + timedelta(days=0), None),
        ("P_EXPIRED", local_today - timedelta(days=3), None),
        ("P_FAR", local_today + timedelta(days=45), None),
        ("P_DELETED", local_today + timedelta(days=3), datetime.now(UTC)),
    ]
    permits: dict[str, Permit] = {}
    for name, exp, deleted_at in specs:
        permit = Permit(
            project_id=sample_project.id,
            permit_name=name,
            authority="SBCA",
            expiry_date=exp,
            created_by=owner_user.id,
            deleted_at=deleted_at,
        )
        db_session.add(permit)
        db_session.flush()
        permits[name] = permit
    db_session.commit()

    # sample_project has 2 active members (owner + supervisor) and 5 matching permits -> 10 alerts
    sent_first = run_permit_alerts(db_session, notifiers=[ConsoleNotifier()])
    assert sent_first == 10

    alerts = list(db_session.scalars(select(PermitAlert)))
    assert len(alerts) == 10

    thresholds_by_permit = {
        a.permit_id: a.threshold for a in alerts
    }
    assert thresholds_by_permit[permits["P_D30"].id] == "D30"
    assert thresholds_by_permit[permits["P_D14"].id] == "D14"
    assert thresholds_by_permit[permits["P_D7"].id] == "D7"
    assert thresholds_by_permit[permits["P_D1"].id] == "D1"
    assert thresholds_by_permit[permits["P_EXPIRED"].id] == "EXPIRED"
    assert permits["P_FAR"].id not in thresholds_by_permit
    assert permits["P_DELETED"].id not in thresholds_by_permit

    # Second run on same day -> 0 new alerts sent due to ON CONFLICT DO NOTHING deduplication
    sent_second = run_permit_alerts(db_session, notifiers=[ConsoleNotifier()])
    assert sent_second == 0
    assert len(list(db_session.scalars(select(PermitAlert)))) == 10


def test_email_and_fcm_notifiers_mocked(
    db_session: Session,
    sample_project: Project,
    owner_user: User,
) -> None:
    payload = PermitAlertPayload(
        permit_id=sample_project.id,
        project_id=sample_project.id,
        project_name=sample_project.name,
        permit_name="Crane Permit",
        authority="SBCA",
        expiry_date="2026-11-20",
        days_to_expiry=6,
        threshold="D7",
        recipient_user_id=owner_user.id,
        recipient_email=owner_user.email,
        recipient_name=owner_user.full_name,
    )

    smtp_cfg = Settings(SMTP_HOST="smtp.example.com", SMTP_PORT=587, SMTP_FROM="a@example.com")
    smtp_mock = MagicMock()
    with patch("smtplib.SMTP", return_value=smtp_mock):
        assert EmailNotifier(smtp_cfg).send(db_session, payload) is True
        smtp_mock.__enter__.return_value.send_message.assert_called_once()

    fcm_cfg = Settings(FCM_PROJECT_ID="demo-proj")
    fcm_notifier = FcmNotifier(fcm_cfg)
    # Without device token -> False
    assert fcm_notifier.send(db_session, payload) is False

    # With device token -> sends FCM HTTP v1 request
    db_session.add(DeviceToken(user_id=owner_user.id, fcm_token="tok-1"))
    db_session.commit()
    mock_resp = MagicMock(is_success=True)
    mock_http = MagicMock()
    mock_http.__enter__.return_value.post.return_value = mock_resp
    with (
        patch.object(fcm_notifier, "_get_access_token", return_value="oauth-tok"),
        patch("httpx.Client", return_value=mock_http),
    ):
        assert fcm_notifier.send(db_session, payload) is True
        mock_http.__enter__.return_value.post.assert_called_once()
