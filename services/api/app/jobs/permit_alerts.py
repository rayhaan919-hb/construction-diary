from __future__ import annotations

import contextlib
import logging
import smtplib
from collections import defaultdict
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Literal, Protocol
from uuid import UUID

import httpx
from sqlalchemy import select, text
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

_ADVISORY_LOCK_KEY = 72424201


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
        logger.info(
            "Permit alert dispatched threshold=%s permit_id=%s project_id=%s user_id=%s days=%s",
            payload.threshold,
            payload.permit_id,
            payload.project_id,
            payload.recipient_user_id,
            payload.days_to_expiry,
        )
        return True


class EmailNotifier:
    channel: AlertChannel = "EMAIL"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._smtp: smtplib.SMTP | None = None
        self._pooled: bool = False

    def begin_batch(self) -> None:
        self._pooled = True

    def _connect(self) -> smtplib.SMTP:
        smtp = smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT, timeout=15)
        smtp.ehlo()
        if smtp.has_extn("starttls"):
            smtp.starttls()
            smtp.ehlo()
        if self.settings.SMTP_USER and self.settings.SMTP_PASSWORD:
            smtp.login(self.settings.SMTP_USER, self.settings.SMTP_PASSWORD)
        return smtp

    def _get_smtp(self) -> smtplib.SMTP:
        if self._smtp is None:
            self._smtp = self._connect()
        return self._smtp

    def close(self) -> None:
        self._pooled = False
        if self._smtp is not None:
            with contextlib.suppress(Exception):
                self._smtp.quit()
            self._smtp = None

    def send(self, db: Session, payload: PermitAlertPayload) -> bool:
        del db
        if not self.settings.SMTP_HOST:
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
        if self._pooled:
            self._get_smtp().send_message(msg)
        else:
            with self._connect() as smtp:
                smtp.send_message(msg)
        return True


class FcmNotifier:
    channel: AlertChannel = "FCM"

    def __init__(
        self,
        settings: Settings,
        *,
        tokens_by_user: dict[UUID, list[str]] | None = None,
    ) -> None:
        self.settings = settings
        self._tokens_by_user = tokens_by_user
        self._cached_access_token: str | None = None
        self._client: httpx.Client | None = None
        self._pooled: bool = False

    def begin_batch(self) -> None:
        self._pooled = True

    def _get_access_token(self) -> str:
        if self._cached_access_token:
            return self._cached_access_token
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
        self._cached_access_token = str(creds.token)
        return self._cached_access_token

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=15.0)
        return self._client

    def close(self) -> None:
        self._pooled = False
        if self._client is not None:
            self._client.close()
            self._client = None

    def _send_with_client(
        self,
        client: httpx.Client,
        tokens: list[str],
        endpoint: str,
        headers: dict[str, str],
        payload: PermitAlertPayload,
    ) -> bool:
        sent_any = False
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
                    "FCM send failed for user=%s status=%s",
                    payload.recipient_user_id,
                    resp.status_code,
                )
        return sent_any

    def send(self, db: Session, payload: PermitAlertPayload) -> bool:
        if not self.settings.FCM_PROJECT_ID:
            return False

        if self._tokens_by_user is not None:
            tokens = self._tokens_by_user.get(payload.recipient_user_id, [])
        else:
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
        if self._pooled:
            return self._send_with_client(
                self._get_client(), tokens, endpoint, headers, payload
            )
        with httpx.Client(timeout=15.0) as client:
            return self._send_with_client(client, tokens, endpoint, headers, payload)


def build_notifiers(
    settings: Settings,
    *,
    tokens_by_user: dict[UUID, list[str]] | None = None,
) -> list[Notifier]:
    notifiers: list[Notifier] = []
    for channel_name in settings.notifier_channels:
        if channel_name == "console":
            notifiers.append(ConsoleNotifier())
        elif channel_name == "email":
            notifiers.append(EmailNotifier(settings))
        elif channel_name == "fcm":
            notifiers.append(FcmNotifier(settings, tokens_by_user=tokens_by_user))
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
    """Evaluate permits_with_status thresholds and dispatch deduplicated alerts safely."""
    cfg = settings or get_settings()

    acquired = db.scalar(select(text(f"pg_try_advisory_xact_lock({_ADVISORY_LOCK_KEY})")))
    if not acquired:
        logger.info("Permit alerts run skipped because another worker holds advisory lock")
        return 0

    permit_rows = db.execute(
        select(PermitWithStatus, Project.name)
        .join(Project, Project.id == PermitWithStatus.project_id)
        .where(
            PermitWithStatus.deleted_at.is_(None),
            Project.deleted_at.is_(None),
        )
        .order_by(PermitWithStatus.expiry_date.asc())
    ).all()

    matched_rows = [
        (permit, project_name, threshold)
        for permit, project_name in permit_rows
        if (threshold := match_threshold(permit.days_to_expiry)) is not None
    ]
    if not matched_rows:
        db.commit()
        return 0

    project_ids = list({permit.project_id for permit, _, _ in matched_rows})
    member_rows = db.execute(
        select(ProjectMember.project_id, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(
            ProjectMember.project_id.in_(project_ids),
            ProjectMember.deleted_at.is_(None),
            User.status == "ACTIVE",
        )
    ).all()
    recipients_by_project: dict[UUID, list[User]] = defaultdict(list)
    user_ids: set[UUID] = set()
    for pid, user in member_rows:
        recipients_by_project[pid].append(user)
        user_ids.add(user.id)

    tokens_by_user: dict[UUID, list[str]] = defaultdict(list)
    if user_ids:
        for uid, fcm_token in db.execute(
            select(DeviceToken.user_id, DeviceToken.fcm_token).where(
                DeviceToken.user_id.in_(user_ids)
            )
        ).all():
            tokens_by_user[uid].append(fcm_token)

    active_notifiers = (
        notifiers
        if notifiers is not None
        else build_notifiers(cfg, tokens_by_user=tokens_by_user)
    )

    sent_count = 0
    for notifier in active_notifiers:
        begin_fn = getattr(notifier, "begin_batch", None)
        if callable(begin_fn):
            begin_fn()
    try:
        for permit, project_name, threshold in matched_rows:
            for user in recipients_by_project.get(permit.project_id, []):
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
                                    permit_expiry_date=permit.expiry_date,
                                )
                                .on_conflict_do_nothing(
                                    index_elements=[
                                        PermitAlert.permit_id,
                                        PermitAlert.threshold,
                                        PermitAlert.channel,
                                        PermitAlert.recipient_user_id,
                                        PermitAlert.permit_expiry_date,
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
    finally:
        for notifier in active_notifiers:
            close_fn = getattr(notifier, "close", None)
            if callable(close_fn):
                close_fn()

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
