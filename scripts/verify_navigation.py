"""Verify unified navigation shell is present on authenticated pages."""
import re
import sys

import requests

BASE = "http://127.0.0.1:7001"
USERS = [
    ("superadmin", "superadmin", "superadmin", ["/superadmin", "/profile", "/notifications"]),
    ("admin", "admin", "admin", ["/admin", "/admin/users", "/profile", "/notifications"]),
    ("employee", "employee", "employee", ["/employee", "/employee/customers", "/profile", "/notifications"]),
    ("customer", "customer", "customer", ["/main", "/my-tickets", "/profile", "/notifications"]),
]


def login(username: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.get(f"{BASE}/login")
    csrf = ""
    m = re.search(r'name="csrf-token" content="([^"]*)"', r.text)
    if m:
        csrf = m.group(1)
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    s.post(
        f"{BASE}/login",
        data={"username": username, "password": password},
        headers=headers,
        allow_redirects=True,
    )
    return s


def main() -> int:
    errors = []
    for username, password, role, paths in USERS:
        s = login(username, password)
        probe = s.get(f"{BASE}/api/my-profile")
        if probe.status_code != 200:
            errors.append(f"{username}: api login failed ({probe.status_code})")
            continue
        if probe.json().get("role") != role:
            errors.append(f"{username}: expected role {role}, got {probe.json().get('role')}")

        for path in paths:
            r = s.get(f"{BASE}{path}")
            if r.status_code != 200:
                errors.append(f"{username}{path}: status {r.status_code}")
                continue
            if "menu-btn" in r.text:
                errors.append(f"{username}{path}: legacy menu-btn still present")
            if f'assistify-role" content="{role}"' not in r.text:
                errors.append(f"{username}{path}: missing assistify-role meta for {role}")
            if "/static/navigation.css" not in r.text:
                errors.append(f"{username}{path}: missing navigation.css")
            if "/static/navigation.js" not in r.text:
                errors.append(f"{username}{path}: missing navigation.js")

        if role == "superadmin":
            r = s.get(f"{BASE}/profile")
            m = re.search(r'href="([^"]+)"[^>]*class="back-link"', r.text) or re.search(
                r'class="back-link"[^>]*href="([^"]+)"', r.text
            )
            back = m.group(1) if m else None
            if back != "/superadmin":
                errors.append(f"superadmin/profile: expected back /superadmin, got {back!r}")

    if errors:
        print("FAILURES:")
        for e in errors:
            print(" -", e)
        return 1

    print("All navigation shell checks passed for 4 roles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
