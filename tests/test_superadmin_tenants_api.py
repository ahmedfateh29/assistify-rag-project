"""Tests for superadmin tenant detail assembly."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Login_system.login_server import build_tenant_details
from Login_system.memberships import ensure_membership_schema


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE tenants (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            active INTEGER DEFAULT 1,
            plan TEXT DEFAULT 'standard',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            allow_multiple_admins INTEGER DEFAULT 0
        )
        """
    )
    c.execute(
        "INSERT INTO tenants (id, name, slug, active) VALUES (1, 'Tenant A', 'tenant-a', 1)"
    )
    c.execute(
        "INSERT INTO tenants (id, name, slug, active) VALUES (2, 'Tenant B', 'tenant-b', 1)"
    )
    c.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            active INTEGER DEFAULT 1,
            email TEXT,
            full_name TEXT,
            tenant_id INTEGER
        )
        """
    )
    c.execute(
        "INSERT INTO users (username, password_hash, role, tenant_id, email, full_name) "
        "VALUES ('admin_a', 'x', 'admin', 1, 'admin@a.test', 'Admin A')"
    )
    c.execute(
        "INSERT INTO users (username, password_hash, role, tenant_id, email, full_name) "
        "VALUES ('emp_a', 'x', 'employee', 1, 'emp@a.test', 'Employee A')"
    )
    c.execute(
        "INSERT INTO users (username, password_hash, role, tenant_id, email, full_name) "
        "VALUES ('cust_b', 'x', 'customer', 2, 'cust@b.test', 'Customer B')"
    )
    c.execute(
        "INSERT INTO users (username, password_hash, role, tenant_id, email, full_name) "
        "VALUES ('cust_pending', 'x', 'customer', 2, 'pend@b.test', 'Pending Cust')"
    )
    ensure_membership_schema(c)
    c.execute(
        """
        INSERT INTO tenant_memberships (username, tenant_id, status, reviewed_at)
        VALUES ('cust_b', 2, 'approved', '2026-01-15 10:00:00')
        """
    )
    c.execute(
        """
        INSERT INTO tenant_memberships (username, tenant_id, status)
        VALUES ('cust_pending', 2, 'pending')
        """
    )
    conn.commit()
    return conn


def test_build_tenant_details_admins_and_employees():
    conn = _memory_db()
    details = build_tenant_details(conn, [1, 2])

    assert len(details[1]["admins"]) == 1
    assert details[1]["admins"][0]["username"] == "admin_a"
    assert details[1]["admins"][0]["email"] == "admin@a.test"
    assert len(details[1]["employees"]) == 1
    assert details[1]["employees"][0]["username"] == "emp_a"
    assert details[1]["role_counts"]["admin"] == 1
    assert details[1]["role_counts"]["employee"] == 1
    conn.close()


def test_build_tenant_details_membership_stats():
    conn = _memory_db()
    details = build_tenant_details(conn, [2])

    assert details[2]["membership_stats"]["pending"] == 1
    assert details[2]["membership_stats"]["approved"] == 1
    assert details[2]["membership_stats"]["rejected"] == 0
    conn.close()


def test_build_tenant_details_approved_customers_only():
    conn = _memory_db()
    details = build_tenant_details(conn, [2])

    customers = details[2]["membership_customers"]
    assert len(customers) == 1
    assert customers[0]["username"] == "cust_b"
    assert customers[0]["approved_at"] == "2026-01-15 10:00:00"
    usernames = {c["username"] for c in customers}
    assert "cust_pending" not in usernames
    conn.close()


def test_build_tenant_details_empty_ids():
    conn = _memory_db()
    assert build_tenant_details(conn, []) == {}
    conn.close()
