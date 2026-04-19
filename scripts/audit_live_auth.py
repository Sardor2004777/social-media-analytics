"""End-to-end authenticated audit against the deployed site.

Flow:
  1. Sign up a fresh random user on the live site.
  2. Follow the redirect to /dashboard/.
  3. Hit every authenticated page and verify we really get a rendered page
     (not just a redirect back to /accounts/login/).
  4. POST /social/connect/instagram/ to exercise the add-account flow.
  5. Download /reports/export.xlsx and /reports/export.pdf, verify magic bytes.
  6. Log out and make sure /dashboard/ bounces back to login.

Exit code signals PASS (0) or FAIL (1).

Run:
    python scripts/audit_live_auth.py [BASE_URL]
"""
from __future__ import annotations

import random
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://social-media-analytics-9rre.onrender.com"


def opener() -> urllib.request.OpenerDirector:
    o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    o.addheaders = [("User-Agent", "audit-live-auth/1.0")]
    return o


def csrf(body: bytes) -> str | None:
    m = re.search(rb'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)', body)
    return m.group(1).decode() if m else None


def pp(label: str, ok: bool, detail: str = "") -> None:
    status = "OK " if ok else "XX "
    print(f"  {status} {label:<44} {detail}")


def check(condition: bool, msg: str) -> bool:
    if not condition:
        print(f"  !! {msg}")
    return condition


def main() -> int:
    print(f"Authenticated audit: {BASE}\n")
    o = opener()
    issues = 0

    # --- 1. Sign up ---
    print("1. Fresh signup")
    try:
        r = o.open(BASE + "/accounts/signup/", timeout=60)
        token = csrf(r.read())
        assert token, "no CSRF on signup"
        email = f"live-auth-{random.randint(10**6, 10**8)}@example.com"
        data = urllib.parse.urlencode({
            "csrfmiddlewaretoken": token,
            "email": email,
            "password1": "GoodPassw0rd!",
            "password2": "GoodPassw0rd!",
        }).encode()
        r = o.open(urllib.request.Request(
            BASE + "/accounts/signup/", data=data,
            headers={"Referer": BASE + "/accounts/signup/", "Content-Type": "application/x-www-form-urlencoded"},
        ), timeout=60)
        pp(f"signup {email}", "/dashboard/" in r.geturl(), f"-> {r.geturl()}")
        if "/dashboard/" not in r.geturl():
            issues += 1
    except Exception as exc:
        print(f"  !! {exc}"); issues += 1; return 1

    # --- 2. Crawl every authenticated page ---
    print("\n2. Authenticated page crawl")
    targets = [
        ("/dashboard/",            ["Dashboard", "activityChart"]),
        ("/social/",               ["Akkauntlarim", "Ulangan akkauntlar"]),
        ("/social/connect/instagram/", ["Instagram", "Handle"]),
        ("/social/connect/telegram/",  ["Telegram", "Handle"]),
        ("/social/connect/youtube/",   ["YouTube", "Handle"]),
        ("/social/connect/x/",         ["X", "Handle"]),
        ("/analytics/",            ["Analytics", "30 kunlik"]),
        ("/analytics/sentiment/",  ["Sentiment", "taqsimot"]),
        ("/reports/",              ["Hisobotlar", "PDF"]),
        ("/settings/",             ["Profil", "Shaxsiy"]),
    ]
    for path, must_contain in targets:
        try:
            r = o.open(BASE + path, timeout=60)
            body = r.read().decode("utf-8", "ignore")
            ok = r.status == 200 and all(k in body for k in must_contain) and "login" not in r.geturl()
            pp(path, ok, "" if ok else f"status={r.status} final={r.geturl()} missing={[k for k in must_contain if k not in body]}")
            if not ok: issues += 1
        except Exception as exc:
            pp(path, False, str(exc)); issues += 1

    # --- 3. Connect a demo Instagram account ---
    print("\n3. Connect a demo Instagram account")
    try:
        r = o.open(BASE + "/social/connect/instagram/", timeout=60)
        token = csrf(r.read())
        handle = f"live_audit_{random.randint(100, 9999)}"
        data = urllib.parse.urlencode({
            "csrfmiddlewaretoken": token,
            "handle": handle,
            "posts": "30",
        }).encode()
        r = o.open(urllib.request.Request(
            BASE + "/social/connect/instagram/", data=data,
            headers={"Referer": BASE + "/social/connect/instagram/", "Content-Type": "application/x-www-form-urlencoded"},
        ), timeout=120)
        pp("POST connect Instagram", "/social/" in r.geturl(), f"-> {r.geturl()}")

        # Confirm handle appears
        r = o.open(BASE + "/social/", timeout=60)
        body = r.read().decode("utf-8", "ignore")
        pp(f"@{handle} appears in /social/", handle in body)
        if handle not in body: issues += 1
    except Exception as exc:
        pp("connect flow", False, str(exc)); issues += 1

    # --- 4. Downloads ---
    print("\n4. Exports")
    try:
        r = o.open(BASE + "/reports/export.xlsx", timeout=120)
        data = r.read()
        ok = r.status == 200 and data[:4] == b"PK\x03\x04"
        pp("/reports/export.xlsx", ok, f"bytes={len(data)}")
        if not ok: issues += 1
    except Exception as exc:
        pp("xlsx", False, str(exc)); issues += 1

    try:
        r = o.open(BASE + "/reports/export.pdf", timeout=120)
        data = r.read()
        ok = r.status == 200 and data[:5] == b"%PDF-"
        pp("/reports/export.pdf", ok, f"bytes={len(data)}")
        if not ok: issues += 1
    except Exception as exc:
        pp("pdf", False, str(exc)); issues += 1

    # --- 5. Dashboard has real data after connect ---
    print("\n5. Dashboard now has real content")
    try:
        r = o.open(BASE + "/dashboard/", timeout=60)
        body = r.read().decode("utf-8", "ignore")
        has_kpi_nonzero = bool(re.search(r'>([1-9]\d*|\d+,\d+)<', body))
        pp("dashboard shows non-zero KPIs", has_kpi_nonzero)
        if not has_kpi_nonzero: issues += 1
    except Exception as exc:
        pp("dashboard", False, str(exc)); issues += 1

    # --- 6. Logout ---
    print("\n6. Logout + re-auth gate")
    try:
        # allauth logout is a POST
        r = o.open(BASE + "/accounts/logout/", timeout=60)
        body = r.read()
        token = csrf(body)
        if token:
            data = urllib.parse.urlencode({"csrfmiddlewaretoken": token}).encode()
            r = o.open(urllib.request.Request(
                BASE + "/accounts/logout/", data=data,
                headers={"Referer": BASE + "/accounts/logout/", "Content-Type": "application/x-www-form-urlencoded"},
            ), timeout=60)
        r = o.open(BASE + "/dashboard/", timeout=60)
        ok = "/accounts/login/" in r.geturl()
        pp("/dashboard/ redirects anon user to login", ok, f"-> {r.geturl()}")
        if not ok: issues += 1
    except Exception as exc:
        pp("logout", False, str(exc)); issues += 1

    print(f"\nTotal issues: {issues}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
