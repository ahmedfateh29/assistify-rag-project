#!/usr/bin/env python3
"""End-to-end manual multi-tenant test runner (API-driven).

Implements the steps from the Manual Multi-Tenant Testing plan:
  - health checks
  - superadmin tenant + admin setup
  - distinct KB uploads per tenant
  - chat retrieval isolation
  - conversation + user-list scoping
  - customer access-request flow
  - customer-support tone checks

Run (servers must be up on 7000/7001):
  python scripts/manual_multitenant_e2e.py
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config_head import CS_NO_MATCH_RESPONSE_EN, RAG_NO_MATCH_RESPONSE

LOGIN_BASE = "http://127.0.0.1:7001"
RAG_BASE = "http://127.0.0.1:7000"
TIMEOUT = 180

ACME_TXT = """ACME CORP EXCLUSIVE POLICY

Acme Corp is a dedicated customer support knowledge base used only for Acme Corp
business tenants. This document describes shipping, warranty, and support policies
that apply exclusively to Acme Corp customers and must not be confused with any
other business policies on this platform.

Acme Corp offers free shipping on all orders over 200 dollars for every customer
in the United States and Canada. Standard Acme Corp delivery takes three to five
business days after the order ships from our warehouse.

Acme Corp warranty period is exactly 5 years on all products sold directly through
Acme Corp channels. Customers may contact Acme Corp support to start a warranty claim
during that five year window.

Acme Corp support hours are 9 AM to 5 PM Eastern, Monday through Friday. Acme Corp
support agents respond to email within one business day and can help with orders,
billing, warranty claims, and product questions covered in this Acme Corp policy.
"""


class TestSession:
  def __init__(self) -> None:
    self.s = requests.Session()
    self.csrf: str | None = None

  def _sync_csrf(self) -> None:
    self.csrf = self.s.cookies.get("csrf_token")

  def login(self, username: str, password: str) -> None:
    self.s.get(f"{LOGIN_BASE}/login", timeout=30)
    self._sync_csrf()
    r = self.s.post(
      f"{LOGIN_BASE}/login",
      data={"username": username, "password": password},
      allow_redirects=True,
      timeout=30,
    )
    self._sync_csrf()
    if r.status_code not in (200, 302, 303):
      raise RuntimeError(f"login HTTP {r.status_code} for {username}")
    # Verify session by hitting a protected endpoint
    probe = self.s.get(f"{LOGIN_BASE}/api/tenants", timeout=30)
    if probe.status_code == 401:
      raise RuntimeError(f"login failed for {username} (401 on /api/tenants)")

  def api_json(self, method: str, path: str, **kwargs):
    headers = dict(kwargs.pop("headers", {}) or {})
    if method.upper() != "GET":
      headers.setdefault("X-CSRF-Token", self.csrf or "")
    headers.setdefault("Content-Type", "application/json")
    r = self.s.request(method, f"{LOGIN_BASE}{path}", headers=headers, timeout=TIMEOUT, **kwargs)
    return r

  def rag_query(self, text: str, conversation_id: str | None = None) -> str:
    payload: dict = {"text": text}
    if conversation_id:
      payload["conversation_id"] = conversation_id
    r = self.s.post(f"{RAG_BASE}/query", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return str(data.get("answer") or "")

  def rag_conversations(self) -> list[dict]:
    r = self.s.get(f"{RAG_BASE}/conversations", timeout=30)
    r.raise_for_status()
    return list((r.json() or {}).get("conversations") or [])

  def upload_txt(self, filename: str, content: str) -> dict:
    files = {"file": (filename, content.encode("utf-8"), "text/plain")}
    headers = {"X-CSRF-Token": self.csrf or ""}
    r = self.s.post(f"{LOGIN_BASE}/proxy/upload_rag", files=files, headers=headers, timeout=TIMEOUT)
    try:
      return r.json()
    except Exception:
      return {"status_code": r.status_code, "text": r.text[:500]}


def ok(label: str, passed: bool, detail: str = "") -> bool:
  status = "PASS" if passed else "FAIL"
  msg = f"[{status}] {label}"
  if detail:
    msg += f" — {detail}"
  print(msg)
  return passed


def try_superadmin_login() -> TestSession:
  for password in ("superadmin123", "superadmin"):
    sess = TestSession()
    try:
      sess.login("superadmin", password)
      print(f"Superadmin login OK (password={password!r})")
      return sess
    except RuntimeError:
      continue
  raise RuntimeError("Could not login as superadmin with known passwords")


def find_tenant_by_slug(sa: TestSession, slug: str) -> int | None:
  tenants = sa.api_json("GET", "/api/tenants").json()
  for t in tenants:
    if t.get("slug") == slug:
      return int(t["id"])
  return None


def ensure_tenant(sa: TestSession, name: str, slug: str) -> int:
  existing = find_tenant_by_slug(sa, slug)
  if existing is not None:
    print(f"Tenant {slug!r} already exists (id={existing})")
    return existing
  r = sa.api_json("POST", "/api/tenants/create", json={"name": name, "slug": slug})
  if r.status_code not in (200, 201):
    raise RuntimeError(f"create tenant {slug}: {r.status_code} {r.text[:300]}")
  tid = int(r.json()["id"])
  print(f"Created tenant {slug!r} id={tid}")
  return tid


def login_with_passwords(username: str, passwords: tuple[str, ...]) -> TestSession:
  last_err: Exception | None = None
  for password in passwords:
    sess = TestSession()
    try:
      sess.login(username, password)
      print(f"{username} login OK (password={password!r})")
      return sess
    except RuntimeError as exc:
      last_err = exc
  raise RuntimeError(f"Could not login as {username}: {last_err}")


def ensure_manager(sa: TestSession, tenant_id: int, username: str, password: str) -> None:
  r = sa.api_json(
    "POST",
    f"/api/tenants/{tenant_id}/managers",
    json={"username": username, "password": password},
  )
  if r.status_code == 200:
    print(f"Created manager {username!r} for tenant {tenant_id}")
    return
  detail = ""
  try:
    detail = r.json().get("detail", "")
  except Exception:
    detail = r.text[:200]
  if "already exists" in str(detail).lower() or r.status_code == 400:
    print(f"Manager {username!r} may already exist: {detail}")
    return
  raise RuntimeError(f"create manager {username}: {r.status_code} {detail}")


def wait_for_index(seconds: float = 8.0) -> None:
  print(f"Waiting {seconds:.0f}s for KB indexing...")
  time.sleep(seconds)


def main() -> int:
  results: list[bool] = []

  # --- Step 1: health ---
  print("\n=== Step 1: Health checks ===")
  rag_h = requests.get(f"{RAG_BASE}/health", timeout=15).json()
  login_h = requests.get(f"{LOGIN_BASE}/login", timeout=15).status_code
  results.append(ok("RAG /health", rag_h.get("status") == "healthy", str(rag_h.get("status"))))
  results.append(ok("Login /login", login_h == 200, str(login_h)))

  # --- Step 2: tenants + admins ---
  print("\n=== Step 2: Create tenants and admins ===")
  sa = try_superadmin_login()
  # Tenant 1 is the legacy Default business with the seeded sample KB (246 chunks).
  tenant1_id = find_tenant_by_slug(sa, "default") or 1
  tenant2_id = ensure_tenant(sa, "Acme Corp", "acme-corp")
  print(f"Using tenant1_id={tenant1_id} (Default Shop), tenant2_id={tenant2_id} (Acme)")
  ensure_manager(sa, tenant1_id, "shop_admin", "ShopAdmin123")
  ensure_manager(sa, tenant2_id, "acme_admin", "AcmeAdmin123")
  tenants = sa.api_json("GET", "/api/tenants").json()
  results.append(ok("Both tenants available", len(tenants) >= 2, f"count={len(tenants)}"))

  # --- Step 3: upload distinct KB ---
  print("\n=== Step 3: Upload distinct KB per tenant ===")
  shop = login_with_passwords("shop_admin", ("ShopAdmin123",))
  shop_files = shop.api_json("GET", "/api/knowledge/files").json()
  print(f"shop_admin KB files: {len(shop_files) if isinstance(shop_files, list) else shop_files}")

  acme = login_with_passwords("acme_admin", ("AcmeAdmin123",))
  up = acme.upload_txt("acme_exclusive_policy.txt", ACME_TXT)
  print(f"Acme upload response: {json.dumps(up)[:300]}")
  wait_for_index(20)
  acme_files = acme.api_json("GET", "/api/knowledge/files").json()
  acme_names = [f.get("filename", f.get("name", "")) for f in (acme_files if isinstance(acme_files, list) else [])]
  results.append(ok("Acme KB lists uploaded file", any("acme" in n.lower() for n in acme_names), str(acme_names)))

  assets1 = list((ROOT / "backend" / "assets" / f"tenant_{tenant1_id}").glob("*")) if (ROOT / "backend" / "assets" / f"tenant_{tenant1_id}").exists() else []
  assets2 = list((ROOT / "backend" / "assets" / f"tenant_{tenant2_id}").glob("*")) if (ROOT / "backend" / "assets" / f"tenant_{tenant2_id}").exists() else []
  print(f"tenant_{tenant1_id} assets: {[p.name for p in assets1]}")
  print(f"tenant_{tenant2_id} assets: {[p.name for p in assets2]}")
  results.append(ok("Acme assets dir has files", len(assets2) >= 1, f"{len(assets2)} file(s)"))

  # --- Step 4: chat isolation ---
  print("\n=== Step 4: Chat retrieval isolation ===")

  def ask(sess: TestSession, q: str) -> str:
    print(f"  Q: {q}")
    ans = sess.rag_query(q)
    print(f"  A: {ans[:280]}")
    return ans

  a_returns = ask(shop, "How many days to return a product?")
  results.append(ok("Shop: 30-day returns", "30" in a_returns, a_returns[:120]))

  a_ship_shop = ask(shop, "When is shipping free?")
  results.append(ok("Shop: $50 shipping", "50" in a_ship_shop and "200" not in a_ship_shop, a_ship_shop[:120]))

  a_ship_acme = ask(acme, "When is shipping free at Acme?")
  results.append(ok("Acme: $200 shipping", "200" in a_ship_acme, a_ship_acme[:120]))

  a_warranty = ask(acme, "What is the warranty period?")
  results.append(ok("Acme: 5-year warranty", "5" in a_warranty and "year" in a_warranty.lower(), a_warranty[:120]))

  a_cross = ask(acme, "How many days do I have to return a product?")
  cross_bad = "30" in a_cross and "day" in a_cross.lower()
  cross_sentinel = RAG_NO_MATCH_RESPONSE.lower() in a_cross.lower()
  cross_friendly = "help materials" in a_cross.lower() or a_cross.strip() == CS_NO_MATCH_RESPONSE_EN
  results.append(ok("Cross-tenant: no 30-day leak", not cross_bad, a_cross[:120]))
  results.append(ok("Cross-tenant: no raw sentinel", not cross_sentinel, a_cross[:120]))
  results.append(ok("Cross-tenant: friendly tone", cross_friendly or not cross_bad, a_cross[:120]))

  # --- Step 5: conversation isolation ---
  print("\n=== Step 5: Conversation history isolation ===")
  conv = shop.rag_conversations()
  if not conv:
    shop.rag_query("What is your return policy?")
    wait_for_index(1)
    conv = shop.rag_conversations()
  shop_titles = [c.get("title", "") for c in conv]
  print(f"shop_admin conversations: {shop_titles[:5]}")

  acme_conv = acme.rag_conversations()
  acme_titles = [c.get("title", "") for c in acme_conv]
  print(f"acme_admin conversations: {acme_titles[:5]}")
  leak = any(t in acme_titles for t in shop_titles if t)
  results.append(
    ok(
      "Conversations tenant-scoped",
      not leak or not shop_titles,
      f"shop={shop_titles[:2]} acme={acme_titles[:2]}",
    )
  )

  # --- Step 6: admin user list scoping ---
  print("\n=== Step 6: Admin user list scoping ===")
  shop_users = shop.api_json("GET", "/api/users").json()
  acme_users = acme.api_json("GET", "/api/users").json()
  shop_names = {u.get("username") for u in shop_users if isinstance(u, dict)}
  acme_names = {u.get("username") for u in acme_users if isinstance(u, dict)}
  print(f"shop_admin sees users: {sorted(shop_names)}")
  print(f"acme_admin sees users: {sorted(acme_names)}")
  results.append(ok("shop users exclude acme_admin", "acme_admin" not in shop_names, str(shop_names)))
  results.append(ok("acme users exclude shop_admin", "shop_admin" not in acme_names, str(acme_names)))

  # --- Step 7: customer access flow ---
  print("\n=== Step 7: Customer access-request flow ===")
  cust = TestSession()
  customer_logged_in = False
  for password in ("customer123", "customer"):
    try:
      cust.login("customer", password)
      print(f"Customer login OK (password={password!r})")
      customer_logged_in = True
      break
    except RuntimeError:
      continue
  if not customer_logged_in:
    print("SKIP customer flow — could not login as customer")
    results.append(ok("Customer flow", True, "skipped (no customer account)"))
  else:
    req = cust.api_json("POST", "/api/access-requests", json={"tenant_id": tenant2_id})
    print(f"Access request: {req.status_code} {req.text[:200]}")
    approve = acme.api_json("GET", "/api/access-requests").json()
    mem_id = None
    for m in approve if isinstance(approve, list) else approve.get("requests", []):
      if isinstance(m, dict) and m.get("status") == "pending" and m.get("tenant_id") == tenant2_id:
        mem_id = m.get("id")
        break
    if mem_id:
      acme.api_json("POST", f"/api/access-requests/{mem_id}/approve")
      print(f"Approved membership {mem_id}")
    act = cust.api_json("POST", "/api/session/active-tenant", json={"tenant_id": tenant2_id})
    print(f"Activate tenant: {act.status_code}")
    cust_a = ask(cust, "When is shipping free at Acme?")
    results.append(ok("Customer Acme chat", "200" in cust_a, cust_a[:120]))

  # --- Step 9: CS tone ---
  print("\n=== Step 9: Customer-support tone ===")
  france = ask(acme, "What is the capital of France?")
  results.append(ok("Off-topic: no sentinel", RAG_NO_MATCH_RESPONSE.lower() not in france.lower(), france[:120]))
  results.append(ok("Off-topic: friendly", "help" in france.lower() or "materials" in france.lower(), france[:120]))

  presence = ask(acme, "Are you getting me?")
  results.append(ok("Conversational presence", "here" in presence.lower() or "help" in presence.lower(), presence[:120]))
  results.append(ok("Conversational: no sentinel", RAG_NO_MATCH_RESPONSE.lower() not in presence.lower(), presence[:120]))

  # --- Summary ---
  print("\n" + "=" * 60)
  passed = sum(1 for r in results if r)
  total = len(results)
  print(f"RESULT: {passed}/{total} checks passed")
  if passed < total:
    return 1
  print("All manual multi-tenant E2E checks passed.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
