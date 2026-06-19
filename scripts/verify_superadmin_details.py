#!/usr/bin/env python3
"""Verify superadmin tenant details API returns enriched fields."""
import sys
import time

import requests

BASE = "http://127.0.0.1:7001"
MAX_RETRIES = 5


def api_get(session, url):
    for attempt in range(MAX_RETRIES):
        r = session.get(url)
        if r.status_code != 500:
            return r
        body = r.json()
        if body.get("error") != "database is locked":
            return r
        time.sleep(1.5 * (attempt + 1))
    return r


def main() -> int:
    s = requests.Session()
    r = s.post(
        f"{BASE}/login",
        data={"username": "superadmin", "password": "superadmin123"},
        allow_redirects=False,
    )
    if r.status_code not in (302, 303):
        print("FAIL: superadmin login", r.status_code)
        return 1

    r = api_get(s, f"{BASE}/api/tenants")
    if not r.ok:
        print("FAIL: /api/tenants", r.status_code, r.text[:200])
        return 1

    tenants = r.json()
    required_keys = {
        "role_counts", "admins", "employees",
        "membership_customers", "membership_stats",
    }
    for t in tenants:
        missing = required_keys - set(t.keys())
        if missing:
            print(f"FAIL: tenant {t.get('slug')} missing keys {missing}")
            return 1

    default = next((t for t in tenants if t["slug"] == "default"), None)
    acme = next((t for t in tenants if t["slug"] == "acme-corp"), None)

    if not default:
        print("WARN: default tenant not found")
    else:
        admin_names = {a["username"] for a in default["admins"]}
        print("Default admins:", sorted(admin_names))
        if not admin_names:
            print("FAIL: Default tenant has no admins listed")
            return 1

    if acme:
        acme_admins = [a["username"] for a in acme["admins"]]
        print("Acme admins:", acme_admins)
        if "acme_admin" not in acme_admins:
            print("WARN: acme_admin not in Acme admins (may not exist yet)")

    r = s.get(f"{BASE}/superadmin")
    html = r.text
    checks = [
        ('id="summary"' in html, "summary bar"),
        ("details-grid" in html, "details grid CSS"),
        ("renderTenantCard" in html, "tenant card renderer"),
        ("Platform Super Admin" in html, "page title"),
    ]
    for ok, label in checks:
        if not ok:
            print(f"FAIL: superadmin page missing {label}")
            return 1

    # Template renders client-side; static checks on shell only
    print(f"Tenants loaded: {len(tenants)}")
    print("All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
