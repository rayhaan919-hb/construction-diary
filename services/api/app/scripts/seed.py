from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import (
    Organization,
    OrganizationMember,
    Permit,
    Project,
    ProjectMember,
    SiteLog,
    User,
)
from app.db.session import create_session_factory
from app.services.auth import hash_password
from app.services.saas import apply_plan_quotas

logger = logging.getLogger(__name__)

SEED_NAMESPACE = uuid.UUID("72424200-0000-4000-8000-000000000001")
SEED_ORG_ID = uuid.uuid5(SEED_NAMESPACE, "organization.default-org")
SEED_PROJECT_ID = uuid.uuid5(SEED_NAMESPACE, "project.clifton-tower-phase-2")
SEED_PERMIT_ACTIVE_ID = uuid.uuid5(SEED_NAMESPACE, "permit.excavation-noc")
SEED_PERMIT_WARN_ID = uuid.uuid5(SEED_NAMESPACE, "permit.tower-crane")
SEED_PERMIT_EXPIRED_ID = uuid.uuid5(SEED_NAMESPACE, "permit.debris-haulage")
SEED_LOG_TODAY_ID = uuid.uuid5(SEED_NAMESPACE, "log.today-pouring")
SEED_LOG_YESTERDAY_ID = uuid.uuid5(SEED_NAMESPACE, "log.yesterday-rebar")


def _upsert_seed_org(db: Session) -> Organization:
    org = db.scalar(select(Organization).where(Organization.slug == "default-org"))
    if org is None:
        org = Organization(
            id=SEED_ORG_ID,
            name="Default Construction Org",
            slug="default-org",
            status="ACTIVE",
            subscription_status="ACTIVE",
            billing_month=datetime.now(UTC).strftime("%Y-%m"),
        )
        apply_plan_quotas(org, "PRO")
        db.add(org)
        db.flush()
    return org


def _upsert_seed_user(
    db: Session,
    *,
    organization_id: uuid.UUID,
    email: str,
    password: str,
    full_name: str,
    role: str,
) -> User:
    normalized = email.strip().lower()
    user = db.scalar(
        select(User).where(text("LOWER(email) = :email")).params(email=normalized)
    )
    if user is None:
        user = User(
            organization_id=organization_id,
            email=normalized,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            status="ACTIVE",
            preferred_locale="en",
            must_change_password=False,
        )
        db.add(user)
        db.flush()
    elif user.organization_id is None:
        user.organization_id = organization_id

    if db.get(OrganizationMember, (organization_id, user.id)) is None:
        db.add(
            OrganizationMember(
                organization_id=organization_id,
                user_id=user.id,
                role=role,
            )
        )
    return user


def _ensure_membership(
    db: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> None:
    member = db.get(ProjectMember, (project_id, user_id))
    if member is None:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=user_id,
                role=role,
            )
        )
    elif member.deleted_at is not None:
        member.deleted_at = None
        member.role = role


def seed_database(db: Session, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    if cfg.is_deployed_env or not cfg.ENABLE_DEV_SEED:
        raise RuntimeError(
            "Database seeding is disabled outside development/test with ENABLE_DEV_SEED=true."
        )
    if not cfg.SEED_OWNER_PASSWORD.strip() or not cfg.SEED_SUPERVISOR_PASSWORD.strip():
        raise RuntimeError(
            "SEED_OWNER_PASSWORD and SEED_SUPERVISOR_PASSWORD must be explicitly configured "
            "before running seed_database."
        )

    org = _upsert_seed_org(db)
    owner = _upsert_seed_user(
        db=db,
        organization_id=org.id,
        email=cfg.SEED_OWNER_EMAIL,
        password=cfg.SEED_OWNER_PASSWORD,
        full_name="Tariq Mehmood",
        role="OWNER",
    )
    if org.created_by is None:
        org.created_by = owner.id

    supervisor = _upsert_seed_user(
        db=db,
        organization_id=org.id,
        email=cfg.SEED_SUPERVISOR_EMAIL,
        password=cfg.SEED_SUPERVISOR_PASSWORD,
        full_name="Bilal Ahmed",
        role="SUPERVISOR",
    )

    project = db.get(Project, SEED_PROJECT_ID)
    if project is None:
        project = Project(
            id=SEED_PROJECT_ID,
            organization_id=org.id,
            name="Clifton Tower Phase 2",
            site_address="Plot 14-C, Block 4, Clifton, Karachi",
            owner_phone="+923001234567",
            timezone="Asia/Karachi",
            allow_photo_gps=False,
            created_by=owner.id,
        )
        db.add(project)
        db.flush()
    elif project.organization_id is None:
        project.organization_id = org.id

    _ensure_membership(db, project.id, owner.id, "OWNER")
    _ensure_membership(db, project.id, supervisor.id, "SUPERVISOR")

    local_today = datetime.now(ZoneInfo(project.timezone)).date()
    now_utc = datetime.now(UTC)

    permit_specs = [
        (
            SEED_PERMIT_ACTIVE_ID,
            "Excavation & Shoring NOC",
            "Sindh Building Control Authority (SBCA)",
            "SBCA-2026-4410",
            local_today - timedelta(days=45),
            local_today + timedelta(days=45),
        ),
        (
            SEED_PERMIT_WARN_ID,
            "Tower Crane Operation Certificate",
            "Karachi Port & Safety Directorate",
            "KPSD-CR-882",
            local_today - timedelta(days=120),
            local_today + timedelta(days=6),
        ),
        (
            SEED_PERMIT_EXPIRED_ID,
            "Municipal Debris Haulage Permit",
            "KMC Solid Waste Department",
            "KMC-DH-119",
            local_today - timedelta(days=90),
            local_today - timedelta(days=2),
        ),
    ]
    for permit_id, name, authority, number, issue_d, expiry_d in permit_specs:
        if db.get(Permit, permit_id) is None:
            db.add(
                Permit(
                    id=permit_id,
                    project_id=project.id,
                    permit_name=name,
                    authority=authority,
                    permit_number=number,
                    issue_date=issue_d,
                    expiry_date=expiry_d,
                    created_by=owner.id,
                    client_updated_at=now_utc,
                )
            )

    yesterday = local_today - timedelta(days=1)
    log_specs = [
        (
            SEED_LOG_TODAY_ID,
            local_today,
            now_utc - timedelta(hours=2),
            "Block B concrete pour completed before midday heat.",
            "Aaj Block B ki foundation pouring mukammal hui, 14 mazdoor kaam par thay.",
            "ur",
            {
                "tasks_completed": ["Foundation pouring Block B"],
                "labor_count": 14,
                "material_deliveries": ["50 bags cement", "Ready-mix concrete 18 m3"],
                "blockers": ["Waiting on tower crane safety inspection"],
            },
        ),
        (
            SEED_LOG_YESTERDAY_ID,
            yesterday,
            now_utc - timedelta(days=1, hours=4),
            "Rebar tying and formwork alignment on Basement Level 1.",
            "Completed rebar tying for Block B columns with 11 workers on site.",
            "en",
            {
                "tasks_completed": ["Rebar tying Block B columns", "Formwork alignment"],
                "labor_count": 11,
                "material_deliveries": ["4 tons Grade-60 steel rebar"],
                "blockers": [],
            },
        ),
    ]
    for log_id, log_date, recorded_at, notes, transcript, lang, summary in log_specs:
        if db.get(SiteLog, log_id) is None:
            db.add(
                SiteLog(
                    id=log_id,
                    project_id=project.id,
                    author_id=supervisor.id,
                    log_date=log_date,
                    recorded_at=recorded_at,
                    notes=notes,
                    audio_uri=None,
                    audio_duration_ms=None,
                    audio_upload_status="NONE",
                    extraction_status="DONE",
                    extraction_attempts=1,
                    extraction_model="mock-gemini",
                    extracted_at=recorded_at + timedelta(seconds=15),
                    transcript=transcript,
                    detected_language=lang,
                    structured_summary=summary,
                    edited_by_human=False,
                    client_updated_at=recorded_at,
                )
            )

    db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    session_factory = create_session_factory()
    with session_factory() as db:
        seed_database(db, settings)
    logger.info("Seed completed successfully")


if __name__ == "__main__":
    main()
