from __future__ import annotations

from typing import Literal

Role = Literal[
    "OWNER",
    "ADMIN",
    "PROJECT_MANAGER",
    "SUPERVISOR",
    "WORKER",
    "VIEWER",
]

ALL_ROLES: tuple[Role, ...] = (
    "OWNER",
    "ADMIN",
    "PROJECT_MANAGER",
    "SUPERVISOR",
    "WORKER",
    "VIEWER",
)

ROLE_RANK: dict[str, int] = {
    "OWNER": 60,
    "ADMIN": 50,
    "PROJECT_MANAGER": 40,
    "SUPERVISOR": 30,
    "WORKER": 20,
    "VIEWER": 10,
}

# Organization-level administrative roles
ORG_OWNER_ROLES: frozenset[str] = frozenset({"OWNER"})
ORG_ADMIN_ROLES: frozenset[str] = frozenset({"OWNER", "ADMIN"})
ORG_AUDIT_VIEW_ROLES: frozenset[str] = frozenset({"OWNER", "ADMIN"})

# Project-level capabilities
PROJECT_CREATOR_ROLES: frozenset[str] = frozenset({"OWNER", "ADMIN", "PROJECT_MANAGER"})
PROJECT_DELETE_ROLES: frozenset[str] = frozenset({"OWNER", "ADMIN"})
PROJECT_SETTINGS_ROLES: frozenset[str] = frozenset({"OWNER", "ADMIN", "PROJECT_MANAGER"})
PROJECT_MEMBER_MANAGE_ROLES: frozenset[str] = frozenset(
    {"OWNER", "ADMIN", "PROJECT_MANAGER"}
)
PROJECT_ELEVATED_RECORD_ROLES: frozenset[str] = frozenset(
    {"OWNER", "ADMIN", "PROJECT_MANAGER"}
)
PERMIT_WRITE_ROLES: frozenset[str] = frozenset(
    {"OWNER", "ADMIN", "PROJECT_MANAGER", "SUPERVISOR"}
)
LOG_WRITE_ROLES: frozenset[str] = frozenset(
    {"OWNER", "ADMIN", "PROJECT_MANAGER", "SUPERVISOR", "WORKER"}
)
EXTRACTION_TRIGGER_ROLES: frozenset[str] = frozenset(
    {"OWNER", "ADMIN", "PROJECT_MANAGER", "SUPERVISOR"}
)


def can_assign_project_role(actor_role: str, target_role: str) -> bool:
    """Owners/Admins may assign any role up to their own rank; PMs up to SUPERVISOR."""
    if actor_role not in ROLE_RANK or target_role not in ROLE_RANK:
        return False
    if actor_role == "OWNER":
        return True
    if actor_role == "ADMIN":
        return target_role != "OWNER"
    if actor_role == "PROJECT_MANAGER":
        return target_role in {"SUPERVISOR", "WORKER", "VIEWER"}
    return False
