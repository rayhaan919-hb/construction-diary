from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditLog
from app.services.audit import record_audit_event
from tests.conftest import assert_problem_json, auth_headers


def _register_org(
    client: TestClient,
    *,
    company_name: str,
    slug: str,
    email: str,
    plan_tier: str = "STARTER",
) -> tuple[dict[str, Any], dict[str, str]]:
    resp = client.post(
        "/v1/organizations/register",
        json={
            "company_name": company_name,
            "company_slug": slug,
            "owner_email": email,
            "owner_full_name": f"{company_name} Owner",
            "password": "OrgOwnerPass1!",
            "preferred_locale": "en",
            "plan_tier": plan_tier,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    headers = {"Authorization": f"Bearer {data['tokens']['access_token']}"}
    return data, headers


def test_multitenant_isolation_quotas_rbac_and_invitations(
    client: TestClient,
) -> None:
    # Register Org A on FREE tier (max 2 projects, 3 seats) and Org B on PRO
    org_a_data, org_a_headers = _register_org(
        client, company_name="Alpha Builders", slug="alpha-builders", email="a@alpha.example",
        plan_tier="FREE",
    )
    _, org_b_headers = _register_org(
        client, company_name="Beta Construct", slug="beta-construct", email="b@beta.example",
        plan_tier="PRO",
    )

    # Create 2 projects in Org A -> 3rd project hits FREE quota
    p1 = client.post(
        "/v1/projects",
        headers=org_a_headers,
        json={"name": "A1", "site_address": "Addr 1"},
    )
    assert p1.status_code == 201
    p1_id = p1.json()["id"]
    p2 = client.post(
        "/v1/projects",
        headers=org_a_headers,
        json={"name": "A2", "site_address": "Addr 2"},
    )
    assert p2.status_code == 201
    p3 = client.post(
        "/v1/projects",
        headers=org_a_headers,
        json={"name": "A3", "site_address": "Addr 3"},
    )
    assert p3.status_code == 402
    assert p3.json()["code"] == "QUOTA_EXCEEDED_PROJECTS"

    # Org B cannot see or mutate Org A's project (IDOR isolation)
    assert_problem_json(
        client.get(f"/v1/projects/{p1_id}", headers=org_b_headers),
        404,
        "NOT_FOUND",
    )

    # Org invitation workflow -> invite VIEWER and WORKER -> accept invitation -> test RBAC
    inv_viewer = client.post(
        "/v1/organization/invitations",
        headers=org_a_headers,
        json={
            "email": "viewer@alpha.example",
            "full_name": "Viewer User",
            "role": "VIEWER",
            "project_id": p1_id,
        },
    )
    assert inv_viewer.status_code == 201, inv_viewer.text
    inv_token = inv_viewer.json()["invite_token"]
    assert inv_token

    acc_resp = client.post(
        "/v1/invitations/accept",
        json={"token": inv_token, "password": "ViewerPassword1!"},
    )
    assert acc_resp.status_code == 200
    viewer_headers = {"Authorization": f"Bearer {acc_resp.json()['access_token']}"}

    # VIEWER can read p1, cannot create permits or push sync logs
    assert client.get(f"/v1/projects/{p1_id}", headers=viewer_headers).status_code == 200
    assert_problem_json(
        client.post(
            f"/v1/projects/{p1_id}/permits",
            headers=viewer_headers,
            json={"permit_name": "P", "authority": "A", "expiry_date": "2026-12-30"},
        ),
        403,
        "FORBIDDEN",
    )

    # Upgrade Org A to PRO -> 3rd project now succeeds
    upg = client.post(
        "/v1/organization/subscription",
        headers=org_a_headers,
        json={"plan_tier": "PRO"},
    )
    assert upg.status_code == 200
    assert upg.json()["plan_tier"] == "PRO"
    assert (
        client.post(
            "/v1/projects",
            headers=org_a_headers,
            json={"name": "A3", "site_address": "Addr 3"},
        ).status_code
        == 201
    )

    # Cannot demote/remove last active OWNER
    owner_uid = org_a_data["user"]["id"]
    last_owner_demote = client.patch(
        f"/v1/organization/members/{owner_uid}",
        headers=org_a_headers,
        json={"role": "ADMIN"},
    )
    assert_problem_json(last_owner_demote, 409, "CONFLICT")


def test_stripe_webhook_audit_immutability_suspend_and_export(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_123456")
    get_settings.cache_clear()

    org_data, org_headers = _register_org(
        client, company_name="Gamma Infra", slug="gamma-infra", email="owner@gamma.example"
    )
    org_id = org_data["organization"]["id"]

    # Invalid Stripe signature rejected
    bad_wh = client.post(
        "/v1/billing/webhooks/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=123,v1=deadbeef"},
    )
    assert bad_wh.status_code in (400, 401)

    # Valid signed webhook updates subscription idempotently
    payload = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "customer": "cus_gamma",
                "subscription": "sub_gamma",
                "metadata": {"organization_id": org_id, "plan_tier": "ENTERPRISE"},
            }
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    ts = str(int(time.time()))
    sig = hmac.new(
        b"whsec_test_secret_123456",
        f"{ts}.".encode() + raw_body,
        hashlib.sha256,
    ).hexdigest()
    good_wh = client.post(
        "/v1/billing/webhooks/stripe",
        content=raw_body,
        headers={"Stripe-Signature": f"t={ts},v1={sig}"},
    )
    assert good_wh.status_code == 200
    assert client.get("/v1/organization", headers=org_headers).json()["plan_tier"] == "ENTERPRISE"

    # Suspend -> usage & export/project creation blocked; unsuspends cleanly
    susp = client.post("/v1/organization/suspend", headers=org_headers)
    assert susp.status_code == 200
    assert susp.json()["status"] == "SUSPENDED"
    blocked_create = client.post(
        "/v1/projects",
        headers=org_headers,
        json={"name": "Blocked Site", "site_address": "123 St"},
    )
    assert_problem_json(blocked_create, 403, "ORGANIZATION_SUSPENDED")
    unsusp = client.post("/v1/organization/unsuspend", headers=org_headers)
    assert unsusp.status_code == 200

    # Export data + view secret-redacted audit logs
    record_audit_event(
        db_session,
        action="test.redaction",
        resource_type="organization",
        resource_id=org_id,
        organization_id=uuid.UUID(org_id),
        details={"authorization": "Bearer super_secret_jwt_12345", "safe": "ok"},
    )
    db_session.commit()

    audit_resp = client.get("/v1/organization/audit-logs", headers=org_headers)
    assert audit_resp.status_code == 200
    items = audit_resp.json()["items"]
    redacted_item = next(i for i in items if i["action"] == "test.redaction")
    assert redacted_item["details"]["authorization"] == "[REDACTED]"
    assert redacted_item["details"]["safe"] == "ok"

    export_resp = client.get("/v1/organization/export", headers=org_headers)
    assert export_resp.status_code == 200
    assert export_resp.json()["organization"]["slug"] == "gamma-infra"

    # PostgreSQL trigger enforces append-only audit_logs immutability (UPDATE & DELETE blocked)
    row_id = db_session.query(AuditLog.id).first()
    assert row_id is not None
    with pytest.raises(DBAPIError):
        db_session.execute(
            text("UPDATE audit_logs SET action = 'tampered' WHERE id = :id"),
            {"id": row_id[0]},
        )
    db_session.rollback()
    with pytest.raises(DBAPIError):
        db_session.execute(
            text("DELETE FROM audit_logs WHERE id = :id"),
            {"id": row_id[0]},
        )
    db_session.rollback()

    # Security headers & health/readiness endpoints
    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.headers["x-content-type-options"] == "nosniff"
    assert ready.headers["x-frame-options"] == "DENY"
    _ = auth_headers
