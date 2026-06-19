#!/usr/bin/env python3
"""Quick verification for superadmin error handling fixes."""
import sys
import time

import requests

BASE = "http://127.0.0.1:7001"
MAX_RETRIES = 5


def api_post(session, url, **kwargs):
    for attempt in range(MAX_RETRIES):
        r = session.post(url, **kwargs)
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
    print("login status", r.status_code)
    csrf = s.cookies.get("csrf_token")
    if not csrf:
        print("FAIL: no csrf_token cookie after login")
        return 1
    print("csrf cookie present:", bool(csrf))

    headers = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}

    r = api_post(
        s,
        f"{BASE}/api/tenants/create",
        headers=headers,
        json={"name": "Acme Corp", "slug": "acme-corp"},
    )
    body = r.json()
    print("duplicate slug:", r.status_code, body)
    if r.status_code != 400 or body.get("detail") != "slug already exists":
        print("FAIL: expected 400 with detail 'slug already exists'")
        return 1

    tenants = s.get(f"{BASE}/api/tenants").json()
    acme = next((t for t in tenants if t["slug"] == "acme-corp"), None)
    if not acme:
        print("FAIL: acme-corp tenant not found")
        return 1

    r = api_post(
        s,
        f"{BASE}/api/tenants/{acme['id']}/managers",
        headers=headers,
        json={"username": "acme_admin", "password": "ValidPass1"},
    )
    body = r.json()
    print("duplicate admin:", r.status_code, body)
    if r.status_code != 400 or body.get("detail") != "Username already exists":
        print("FAIL: expected 400 with detail 'Username already exists'")
        return 1

    r = s.get(f"{BASE}/static/security.js")
    if "parseApiError" not in r.text or "parseApiError," not in r.text:
        print("FAIL: parseApiError not exported in security.js")
        return 1
    print("security.js: parseApiError OK")

    r = s.get(f"{BASE}/superadmin")
    html = r.text
    checks = [
        ("/static/security.js" in html, "security.js included"),
        ("View KB" not in html, "View KB link removed"),
        ("Security.parseApiError" in html, "parseApiError used in template"),
    ]
    for ok, label in checks:
        print(f"superadmin {label}:", "OK" if ok else "FAIL")
        if not ok:
            return 1

    print("All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
