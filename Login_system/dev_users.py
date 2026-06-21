"""Single source of truth for default development user accounts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True)
class DevUser:
    username: str
    password: str
    role: str
    tenant_id: int | None = 1


# Dev passwords equal usernames. Run `python Login_system/init_users_db.py` to (re)seed.
DEV_USER_ACCOUNTS: Sequence[DevUser] = (
    DevUser("superadmin", "superadmin", "superadmin", None),
    DevUser("master_admin", "master_admin", "master_admin", 1),
    DevUser("admin", "admin", "admin", 1),
    DevUser("employee", "employee", "employee", 1),
    DevUser("customer", "customer", "customer", 1),
)


def dev_user_summary() -> str:
    return ", ".join(f"{u.username}/{u.password}" for u in DEV_USER_ACCOUNTS)


def seed_dev_users(cursor, pwd_context, tenant_id: int = 1) -> None:
    """Upsert default dev accounts with bcrypt hashes."""
    now = datetime.utcnow().isoformat()
    upsert_sql = """
        INSERT INTO users (username, password_hash, role, active, tenant_id, created_at)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            password_hash = excluded.password_hash,
            role = excluded.role,
            active = excluded.active,
            tenant_id = excluded.tenant_id,
            created_at = excluded.created_at
    """
    for user in DEV_USER_ACCOUNTS:
        tid = user.tenant_id if user.tenant_id is not None else None
        cursor.execute(
            upsert_sql,
            (user.username, pwd_context.hash(user.password), user.role, tid, now),
        )
