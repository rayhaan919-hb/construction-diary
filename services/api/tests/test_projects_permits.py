from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Project, User
from tests.conftest import assert_problem_json, auth_headers


def test_project_crud_and_authorization(
    client: TestClient,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    # Supervisor cannot create project
    forbidden_create = client.post(
        "/v1/projects",
        headers=supervisor_headers,
        json={"name": "Blocked", "site_address": "123 St"},
    )
    assert_problem_json(forbidden_create, 403, "FORBIDDEN")

    # Invalid IANA timezone -> 422
    bad_tz = client.post(
        "/v1/projects",
        headers=owner_headers,
        json={"name": "Bad TZ", "site_address": "123 St", "timezone": "Mars/Olympus"},
    )
    assert_problem_json(bad_tz, 422, "VALIDATION")

    # Owner creates project
    create_resp = client.post(
        "/v1/projects",
        headers=owner_headers,
        json={
            "name": "Marina Residences",
            "site_address": "Plot 7, Clifton",
            "timezone": "Asia/Karachi",
            "allow_photo_gps": True,
        },
    )
    assert create_resp.status_code == 201
    project = create_resp.json()
    pid = project["id"]
    assert project["allow_photo_gps"] is True

    # Non-member supervisor cannot see it -> 404 NOT_FOUND
    non_member_get = client.get(f"/v1/projects/{pid}", headers=supervisor_headers)
    assert_problem_json(non_member_get, 404, "NOT_FOUND")

    # Owner updates project (including clearing owner_phone with null)
    patch_resp = client.patch(
        f"/v1/projects/{pid}",
        headers=owner_headers,
        json={"name": "Marina Residences v2", "owner_phone": None},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Marina Residences v2"
    assert patch_resp.json()["owner_phone"] is None

    # Portfolio permit_health transitions: NONE -> OK -> WARN -> EXPIRED
    portfolio = client.get("/v1/projects", headers=owner_headers).json()
    assert len(portfolio) == 1
    assert portfolio[0]["permit_health"] == "NONE"
    assert portfolio[0]["next_expiring_permit"] is None

    # Owner soft-deletes project
    del_resp = client.delete(f"/v1/projects/{pid}", headers=owner_headers)
    assert del_resp.status_code == 204
    after_del = client.get(f"/v1/projects/{pid}", headers=owner_headers)
    assert_problem_json(after_del, 404, "NOT_FOUND")


def test_member_invite_temp_password_and_removal(
    client: TestClient,
    sample_project: Project,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
) -> None:
    pid = str(sample_project.id)

    # Supervisor cannot invite or remove or patch/delete project
    sup_patch_proj = client.patch(
        f"/v1/projects/{pid}",
        headers=supervisor_headers,
        json={"name": "Sup Rename"},
    )
    assert_problem_json(sup_patch_proj, 403, "FORBIDDEN")

    sup_del_proj = client.delete(f"/v1/projects/{pid}", headers=supervisor_headers)
    assert_problem_json(sup_del_proj, 403, "FORBIDDEN")

    sup_invite = client.post(
        f"/v1/projects/{pid}/members",
        headers=supervisor_headers,
        json={"email": "newsup@example.com", "full_name": "New Sup"},
    )
    assert_problem_json(sup_invite, 403, "FORBIDDEN")

    # Owner invites brand-new supervisor -> gets one-time temporary_password
    inv1 = client.post(
        f"/v1/projects/{pid}/members",
        headers=owner_headers,
        json={"email": "newsup@example.com", "full_name": "New Sup"},
    )
    assert inv1.status_code == 201
    data1 = inv1.json()
    temp_pw = data1["temporary_password"]
    assert isinstance(temp_pw, str) and len(temp_pw) >= 8
    new_uid = data1["member"]["user_id"]

    # Duplicate active invite -> 409 CONFLICT
    dup_inv = client.post(
        f"/v1/projects/{pid}/members",
        headers=owner_headers,
        json={"email": "newsup@example.com", "full_name": "New Sup"},
    )
    assert_problem_json(dup_inv, 409, "CONFLICT")

    # Invited supervisor logs in with temp password & must_change_password=true
    new_sup_login = client.post(
        "/v1/auth/login",
        json={"email": "newsup@example.com", "password": temp_pw},
    )
    assert new_sup_login.status_code == 200
    assert new_sup_login.json()["user"]["must_change_password"] is True

    # Invite existing supervisor to second project -> temporary_password is null
    p2_resp = client.post(
        "/v1/projects",
        headers=owner_headers,
        json={"name": "Second Site", "site_address": "DHA Phase 8"},
    )
    p2_id = p2_resp.json()["id"]
    inv2 = client.post(
        f"/v1/projects/{p2_id}/members",
        headers=owner_headers,
        json={"email": "newsup@example.com", "full_name": "New Sup"},
    )
    assert inv2.status_code == 201
    assert inv2.json()["temporary_password"] is None

    # Owner removes new supervisor from project 1
    rem_resp = client.delete(
        f"/v1/projects/{pid}/members/{new_uid}",
        headers=owner_headers,
    )
    assert rem_resp.status_code == 204

    new_sup_headers = auth_headers(client, "newsup@example.com", temp_pw)
    must_change = client.get(f"/v1/projects/{pid}", headers=new_sup_headers)
    assert_problem_json(must_change, 403, "PASSWORD_CHANGE_REQUIRED")

    ch_resp = client.post(
        "/v1/me/password",
        headers=new_sup_headers,
        json={"current_password": temp_pw, "new_password": "NewSupPassword1!"},
    )
    assert ch_resp.status_code == 204
    verified_headers = auth_headers(client, "newsup@example.com", "NewSupPassword1!")
    denied = client.get(f"/v1/projects/{pid}", headers=verified_headers)
    assert_problem_json(denied, 404, "NOT_FOUND")


def test_permits_derived_status_and_timezone_and_permissions(
    client: TestClient,
    db_session: Session,
    owner_user: User,
    owner_headers: dict[str, str],
    supervisor_headers: dict[str, str],
    sample_project: Project,
) -> None:
    pid = str(sample_project.id)
    local_today = datetime.now(ZoneInfo(sample_project.timezone)).date()

    # Create permits across all 3 derived statuses
    p_active = client.post(
        f"/v1/projects/{pid}/permits",
        headers=owner_headers,
        json={
            "permit_name": "Active Permit",
            "authority": "SBCA",
            "expiry_date": (local_today + timedelta(days=30)).isoformat(),
        },
    )
    assert p_active.status_code == 201
    assert p_active.json()["status"] == "ACTIVE"
    assert p_active.json()["days_to_expiry"] == 30
    owner_permit_id = p_active.json()["id"]

    p_soon = client.post(
        f"/v1/projects/{pid}/permits",
        headers=supervisor_headers,
        json={
            "permit_name": "Expiring Soon Permit",
            "authority": "KMC",
            "expiry_date": (local_today + timedelta(days=14)).isoformat(),
        },
    )
    assert p_soon.status_code == 201
    assert p_soon.json()["status"] == "EXPIRING_SOON"
    sup_permit_id = p_soon.json()["id"]

    p_expired = client.post(
        f"/v1/projects/{pid}/permits",
        headers=owner_headers,
        json={
            "permit_name": "Expired Permit",
            "authority": "EPA",
            "expiry_date": (local_today - timedelta(days=1)).isoformat(),
        },
    )
    assert p_expired.status_code == 201
    assert p_expired.json()["status"] == "EXPIRED"
    assert p_expired.json()["days_to_expiry"] == -1

    # Ordered by expiry_date ascending
    listed = client.get(f"/v1/projects/{pid}/permits", headers=owner_headers).json()
    assert [p["permit_name"] for p in listed] == [
        "Expired Permit",
        "Expiring Soon Permit",
        "Active Permit",
    ]

    # Supervisor CANNOT patch/delete owner's permit -> 403 FORBIDDEN
    sup_patch_owner = client.patch(
        f"/v1/permits/{owner_permit_id}",
        headers=supervisor_headers,
        json={"permit_name": "Hacked"},
    )
    assert_problem_json(sup_patch_owner, 403, "FORBIDDEN")

    # Supervisor CAN patch their own permit
    sup_patch_own = client.patch(
        f"/v1/permits/{sup_permit_id}",
        headers=supervisor_headers,
        json={"permit_name": "Updated By Supervisor"},
    )
    assert sup_patch_own.status_code == 200
    assert sup_patch_own.json()["permit_name"] == "Updated By Supervisor"

    # Owner CAN patch/delete supervisor's permit
    owner_del_sup = client.delete(
        f"/v1/permits/{sup_permit_id}",
        headers=owner_headers,
    )
    assert owner_del_sup.status_code == 204

    # Timezone boundary verification:
    # Pacific/Kiritimati (UTC+14) and Pacific/Midway (UTC-11) are 25h apart,
    # so their local calendar dates are ALWAYS different at any UTC instant.
    p_midway = client.post(
        "/v1/projects",
        headers=owner_headers,
        json={
            "name": "Midway Site",
            "site_address": "Midway",
            "timezone": "Pacific/Midway",
        },
    ).json()
    p_kiritimati = client.post(
        "/v1/projects",
        headers=owner_headers,
        json={
            "name": "Kiritimati Site",
            "site_address": "Kiritimati",
            "timezone": "Pacific/Kiritimati",
        },
    ).json()

    midway_today = datetime.now(ZoneInfo("Pacific/Midway")).date()
    kiritimati_today = datetime.now(ZoneInfo("Pacific/Kiritimati")).date()
    assert kiritimati_today > midway_today

    perm_midway = client.post(
        f"/v1/projects/{p_midway['id']}/permits",
        headers=owner_headers,
        json={
            "permit_name": "TZ Test",
            "authority": "Auth",
            "expiry_date": midway_today.isoformat(),
        },
    ).json()
    perm_kiritimati = client.post(
        f"/v1/projects/{p_kiritimati['id']}/permits",
        headers=owner_headers,
        json={
            "permit_name": "TZ Test",
            "authority": "Auth",
            "expiry_date": midway_today.isoformat(),
        },
    ).json()

    assert perm_midway["days_to_expiry"] == 0
    assert perm_midway["status"] == "EXPIRING_SOON"
    assert perm_kiritimati["days_to_expiry"] < 0
    assert perm_kiritimati["status"] == "EXPIRED"
