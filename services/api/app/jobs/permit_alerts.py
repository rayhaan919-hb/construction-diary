from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Literal, Protocol
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import (
    DeviceToken,
    PermitAlert,
    PermitWithStatus,
    Project,
    ProjectMember,
    User,
)
from app.db.session import create_session_factory

logger = logging.getLogger(__name__)

AlertThreshold = Literal["D30", "D14", "D7", "D1", "EXPIRED"]
AlertChannel = Literal["CONSOLE", "EMAIL", "FCM"]


@dataclass(frozen=True)
class PermitAlertPayload:
    permit_id: UUID
    project_id: UUID
    project_name: str
    permit_name: str
    authority: str
    expiry_date: str
    days_to_expiry: int
    threshold: AlertThreshold
    recipient_user_id: UUID
    recipient_email: str
    recipient_name: str


class Notifier(Protocol):
    channel: AlertChannel

    def send(self, db: Session, payload: PermitAlertPayload) -> bool:
        """Send an alert notification. Returns True if delivered/recorded."""


class _SkipAlertRecord(Exception):
    pass


def match_threshold(days_to_expiry: int) -> AlertThreshold | None:
    if days_to_expiry < 0:
        return "EXPIRED"
    if 0 <= days_to_expiry <= 1:
        return "D1"
    if 2 <= days_to_expiry <= 7:
        return "D7"
    if 8 <= days_to_expiry <= 14:
        return "D14"
    if 15 <= days_to_expiry <= 30:
        return "D30"
    return None


class ConsoleNotifier:
    channel: AlertChannel = "CONSOLE"

    def send(self, db: Session, payload: PermitAlertPayload) -> bool:
        del db
        msg = (
            f"[PERMIT ALERT {payload.threshold}] project={payload.project_name} "
            f"permit={payload.permit_name} ({payload.authority}) "
            f"expiry={payload.expiry_date} days_to_expiry={payload.days_to_expiry} "
            f"recipient={payload.recipient_email}"
        )
        logger.warning(msg)
        print(msg)
        return True


class EmailNotifier:
    channel: AlertChannel = "EMAIL"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, db: Session, payload: PermitAlertPayload) -> bool:
        del db
        if not self.settings.SMTP_HOST:
            logger.warning("SMTP_HOST not configured; skipping email alert")
            return False

        msg = EmailMessage()
        msg["Subject"] = (
            f"[{payload.threshold}] Permit expiry alert: "
            f"{payload.permit_name} ({payload.project_name})"
        )
        msg["From"] = self.settings.SMTP_FROM
        msg["To"] = payload.recipient_email
        msg.set_content(
            f"Hello {payload.recipient_name},\n\n"
            f"Permit '{payload.permit_name}' issued by {payload.authority} for project "
            f"'{payload.project_name}' has reached alert threshold {payload.threshold}.\n"
            f"Expiry date: {payload.expiry_date} (days remaining: {payload.days_to_expiry}).\n"
        )

        with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT, timeout=15) as smtp:
            if self.settings.SMTP_USER and self.settings.SMTP_PASSWORD:
                smtp.starttls()
                smtp.login(self.settings.SMTP_USER, self.settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True


class FcmNotifier:
    channel: AlertChannel = "FCM"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _get_access_token(self) -> str:
        import google.auth
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        scopes = ["https://www.googleapis.com/auth/firebase.messaging"]
        if self.settings.GOOGLE_APPLICATION_CREDENTIALS:
            creds = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                self.settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=scopes,
            )
        else:
            creds, _ = google.auth.default(scopes=scopes)
        creds.refresh(Request())
        if not creds.token:
            raise RuntimeError("Failed to obtain OAuth2 token for FCM HTTP v1")
        return str(creds.token)

    def send(self, db: Session, payload: PermitAlertPayload) -> bool:
        if not self.settings.FCM_PROJECT_ID:
            logger.warning("FCM_PROJECT_ID not configured; skipping FCM alert")
            return False

        tokens = list(
            db.scalars(
                select(DeviceToken.fcm_token).where(
                    DeviceToken.user_id == payload.recipient_user_id
                )
            )
        )
        if not tokens:
            return False

        access_token = self._get_access_token()
        endpoint = (
            f"https://fcm.googleapis.com/v1/projects/{self.settings.FCM_PROJECT_ID}"
            "/messages:send"
        )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        sent_any = False
        with httpx.Client(timeout=15.0) as client:
            for token in tokens:
                body = {
                    "message": {
                        "token": token,
                        "notification": {
                            "title": f"Permit Alert ({payload.threshold}): {payload.permit_name}",
                            "body": (
                                f"{payload.project_name} — expires {payload.expiry_date} "
                                f"({payload.days_to_expiry}d)"
                            ),
                        },
                        "data": {
                            "permit_id": str(payload.permit_id),
                            "project_id": str(payload.project_id),
                            "threshold": payload.threshold,
                        },
                    }
                }
                resp = client.post(endpoint, headers=headers, json=body)
                if resp.is_success:
                    sent_any = True
                else:
                    logger.warning(
                        "FCM send failed for user %s: status=%s body=%s",
                        payload.recipient_user_id,
                        resp.status_code,
                        resp.text[:300],
                    )
        return sent_any


def build_notifiers(settings: Settings) -> list[Notifier]:
    notifiers: list[Notifier] = []
    for channel_name in settings.notifier_channels:
        if channel_name == "console":
            notifiers.append(ConsoleNotifier())
        elif channel_name == "email":
            notifiers.append(EmailNotifier(settings))
        elif channel_name == "fcm":
            notifiers.append(FcmNotifier(settings))
        else:
            logger.warning("Unknown NOTIFIER channel ignored: %s", channel_name)
    if not notifiers:
        notifiers.append(ConsoleNotifier())
    return notifiers


def run_permit_alerts(
    db: Session,
    notifiers: list[Notifier] | None = None,
    settings: Settings | None = None,
) -> int:
    """Evaluate permits_with_status thresholds and dispatch deduplicated alerts."""
    cfg = settings or get_settings()
    active_notifiers = notifiers if notifiers is not None else build_notifiers(cfg)

    permit_rows = db.execute(
        select(PermitWithStatus, Project.name)
        .join(Project, Project.id == PermitWithStatus.project_id)
        .where(
            PermitWithStatus.deleted_at.is_(None),
            Project.deleted_at.is_(None),
        )
        .order_by(PermitWithStatus.expiry_date.asc())
    ).all()

    sent_count = 0
    for permit, project_name in permit_rows:
        threshold = match_threshold(permit.days_to_expiry)
        if threshold is None:
            continue

        recipients = list(
            db.scalars(
                select(User)
                .join(ProjectMember, ProjectMember.user_id == User.id)
                .where(
                    ProjectMember.project_id == permit.project_id,
                    ProjectMember.deleted_at.is_(None),
                )
            )
        )
        for user in recipients:
            payload = PermitAlertPayload(
                permit_id=permit.id,
                project_id=permit.project_id,
                project_name=project_name,
                permit_name=permit.permit_name,
                authority=permit.authority,
                expiry_date=permit.expiry_date.isoformat(),
                days_to_expiry=permit.days_to_expiry,
                threshold=threshold,
                recipient_user_id=user.id,
                recipient_email=user.email,
                recipient_name=user.full_name,
            )
            for notifier in active_notifiers:
                try:
                    with db.begin_nested():
                        inserted_id = db.scalar(
                            pg_insert(PermitAlert)
                            .values(
                                permit_id=permit.id,
                                threshold=threshold,
                                channel=notifier.channel,
                                recipient_user_id=user.id,
                            )
                            .on_conflict_do_nothing(
                                index_elements=[
                                    PermitAlert.permit_id,
                                    PermitAlert.threshold,
                                    PermitAlert.channel,
                                    PermitAlert.recipient_user_id,
                                ]
                            )
                            .returning(PermitAlert.id)
                        )
                        if inserted_id is None:
                            continue
                        delivered = notifier.send(db, payload)
                        if not delivered:
                            raise _SkipAlertRecord()
                        sent_count += 1
                except _SkipAlertRecord:
                    continue
                except Exception:
                    logger.exception(
                        "Failed sending %s alert for permit=%s user=%s",
                        notifier.channel,
                        permit.id,
                        user.id,
                    )
                    continue

    db.commit()
    return sent_count


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    session_factory = create_session_factory()
    with session_factory() as db:
        count = run_permit_alerts(db=db, settings=settings)
        logger.info("Permit alerts run finished: %s alert(s) dispatched", count)


if __name__ == "__main__":
    main()
