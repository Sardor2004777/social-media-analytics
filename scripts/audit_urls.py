"""Smoke-audit script for the local dev server.

Purpose
-------
Fast pre-flight check before a demo / diploma defence. Hits every public URL
as both an anonymous visitor and the seeded demo user, then additionally:

    • Flags responses that contain known Django error markers.
    • Re-probes every internal ``<a href=...>`` link on the landing page.
    • Drives the signup form with a fresh random email (so we catch bugs in
      allauth + email backend + post-login redirect together).
    • POSTs the i18n language switch form.

Prerequisites
-------------
    python manage.py runserver 127.0.0.1:8000
    python manage.py create_demo_user        (demo@social-analytics.app)

Usage:
    python scripts/audit_urls.py

Exit code is non-zero if any probe flagged an issue.
"""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from dataclasses import dataclass, field
from typing import Optional

BASE = "http://127.0.0.1:8000"

ERROR_MARKERS = (
    "TemplateSyntaxError",
    "NoReverseMatch",
    "TemplateDoesNotExist",
    "Traceback (most recent call last)",
    "ValueError at /",
    "TypeError at /",
    "KeyError at /",
    "OperationalError",
    "IntegrityError",
    "DoesNotExist at /",
    "Server Error (500)",
    "invalid literal for",
    "Page not found (404)",
)

# URLs we want to test for both anonymous + authenticated users
TARGETS = [
    ("landing",           "/",                         True,  True),
    ("home /en/",         "/en/",                      True,  True),
    ("signup",            "/accounts/signup/",         True,  True),
    ("login",             "/accounts/login/",          True,  True),
    ("password-reset",    "/accounts/password/reset/", True,  True),
    ("password-reset-done", "/accounts/password/reset/done/", True, True),
    ("logout",            "/accounts/logout/",         True,  True),
    ("email-verification-sent", "/accounts/confirm-email/", True, True),
    ("dashboard",         "/dashboard/",               False, True),
    ("reports-xlsx",      "/reports/export.xlsx",      False, True),
    ("api-docs",          "/api/v1/docs/",             True,  True),
    ("api-schema",        "/api/v1/schema/",           True,  True),
    ("api-redoc",         "/api/v1/redoc/",            True,  True),
    ("admin-login",       "/admin/",                   True,  True),
    ("nonexistent-404",   "/foobar/",                  True,  True),
    ("static-css",        "/static/css/output.css",    True,  True),
    ("static-js",         "/static/js/app.js",         True,  True),
]


@dataclass
class Probe:
    name: str
    method: str
    url: str
    as_user: str
    status: int | None = None
    final_url: str = ""
    size: int = 0
    errors: list[str] = field(default_factory=list)


def login(opener) -> bool:
    """Log into /accounts/login/ as demo user via the opener cookiejar."""
    try:
        r = opener.open(f"{BASE}/accounts/login/", timeout=10)
        html = r.read().decode("utf-8", "ignore")
        m = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)', html)
        if not m:
            return False
        data = urllib.parse.urlencode({
            "csrfmiddlewaretoken": m.group(1),
            "login": "demo@social-analytics.app",
            "password": "Demo12345!",
        }).encode()
        req = urllib.request.Request(
            f"{BASE}/accounts/login/",
            data=data,
            headers={"Referer": f"{BASE}/accounts/login/",
                     "Content-Type": "application/x-www-form-urlencoded"},
        )
        r = opener.open(req, timeout=10)
        return "login" not in r.geturl()
    except Exception as exc:
        print(f"[login error] {exc}")
        return False


def fetch(opener, url: str) -> tuple[int | None, str, bytes]:
    try:
        r = opener.open(url, timeout=15)
        body = r.read()
        return r.status, r.geturl(), body
    except urllib.error.HTTPError as e:
        return e.code, url, e.read() if hasattr(e, "read") else b""
    except Exception as exc:
        return None, url, str(exc).encode()


def detect_errors(body: bytes, url: str, expected_404: bool = False) -> list[str]:
    text = body.decode("utf-8", "ignore")
    found = []
    for m in ERROR_MARKERS:
        if m == "Page not found (404)" and expected_404:
            continue
        if m in text:
            found.append(m)
    return found


def extract_links(body: bytes, base_url: str) -> list[str]:
    text = body.decode("utf-8", "ignore")
    out: set[str] = set()
    # Match only attribute href="..." (not Alpine :href="..." which is dynamic JS)
    for href in re.findall(r'(?<![:\w])href=["\']([^"\']+)', text):
        href = href.strip()
        if not href or href.startswith(("mailto:", "javascript:", "tel:", "#")):
            continue
        if href.startswith("//"):
            continue
        if href.startswith("http"):
            if not href.startswith(BASE):
                continue  # skip external
            out.add(href)
        else:
            out.add(urllib.parse.urljoin(base_url, href))
    return sorted(out)


def run():
    jar_anon = CookieJar()
    op_anon = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar_anon))

    jar_auth = CookieJar()
    op_auth = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar_auth))

    ok = login(op_auth)
    print(f"auth login ok: {ok}")

    probes: list[Probe] = []
    for name, path, probe_anon, probe_auth in TARGETS:
        url = BASE + path
        if probe_anon:
            status, final, body = fetch(op_anon, url)
            errs = detect_errors(body, url, expected_404="foobar" in url)
            probes.append(Probe(name, "GET", url, "anon",
                                status=status, final_url=final,
                                size=len(body), errors=errs))
        if probe_auth:
            status, final, body = fetch(op_auth, url)
            errs = detect_errors(body, url, expected_404="foobar" in url)
            probes.append(Probe(name, "GET", url, "auth",
                                status=status, final_url=final,
                                size=len(body), errors=errs))

    # ---------- Print report ----------
    print(f"\n{'Status':<7} {'User':<4} {'Size':>8}  {'Path':<36} {'Notes'}")
    print("-" * 100)
    issues = 0
    for p in probes:
        note = ""
        if p.errors:
            note = "!! " + ", ".join(p.errors)
            issues += 1
        elif p.status is None:
            note = "!! no response"
            issues += 1
        elif p.status >= 500:
            note = f"!! HTTP {p.status}"
            issues += 1
        elif p.status == 404 and "foobar" not in p.url and "confirm-email" not in p.url:
            note = "!! 404"
            issues += 1

        path = urllib.parse.urlparse(p.url).path
        final_path = urllib.parse.urlparse(p.final_url).path
        if final_path and final_path != path:
            note = (note + f" -> {final_path}").strip()
        print(f"{p.status or '?':<7} {p.as_user:<4} {p.size:>8}  {path:<36} {note}")

    # ---------- Link validation (sample of landing links) ----------
    print("\n--- Internal link validation (landing as anon) ---")
    status, final, body = fetch(op_anon, BASE + "/")
    links = extract_links(body, BASE + "/")
    bad_links: list[tuple[str, int | None]] = []
    seen = set()
    for link in links[:40]:
        if link in seen:
            continue
        seen.add(link)
        st, _, _ = fetch(op_anon, link)
        if st is None or st >= 400:
            bad_links.append((link, st))
    for link, st in bad_links:
        print(f"  BROKEN {st} {link}")
        issues += 1
    if not bad_links:
        print(f"  {len(seen)} links probed, all OK.")

    # ---------- Form submission: fresh signup ----------
    print("\n--- Signup form submission (fresh user) ---")
    op_fresh = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    try:
        r = op_fresh.open(f"{BASE}/accounts/signup/", timeout=10)
        html = r.read().decode("utf-8", "ignore")
        token = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)', html).group(1)
        import random
        email = f"audit-{random.randint(10**6, 10**8)}@example.com"
        data = urllib.parse.urlencode({
            "csrfmiddlewaretoken": token,
            "email": email,
            "password1": "GoodPassw0rd!",
            "password2": "GoodPassw0rd!",
        }).encode()
        req = urllib.request.Request(
            f"{BASE}/accounts/signup/",
            data=data,
            headers={"Referer": f"{BASE}/accounts/signup/", "Content-Type": "application/x-www-form-urlencoded"},
        )
        r = op_fresh.open(req, timeout=10)
        body = r.read().decode("utf-8", "ignore")
        if "error" in body.lower() and "alert-error" in body:
            print(f"  !! signup returned errors for {email}")
            issues += 1
        else:
            print(f"  signup OK for {email} -> {r.geturl()}")
    except Exception as exc:
        print(f"  !! signup flow failed: {exc}")
        issues += 1

    # ---------- Language switch ----------
    print("\n--- i18n: POST /i18n/setlang/ ---")
    try:
        r = op_anon.open(BASE + "/", timeout=10)
        html = r.read().decode("utf-8", "ignore")
        token_match = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)', html)
        if token_match:
            data = urllib.parse.urlencode({
                "csrfmiddlewaretoken": token_match.group(1),
                "language": "en",
                "next": "/",
            }).encode()
            req = urllib.request.Request(BASE + "/i18n/setlang/", data=data,
                                        headers={"Referer": BASE + "/"})
            r = op_anon.open(req, timeout=10)
            print(f"  setlang=en -> {r.status} {r.geturl()}")
        else:
            print("  !! no CSRF token found on landing for language form")
            issues += 1
    except Exception as exc:
        print(f"  !! setlang failed: {exc}")
        issues += 1

    print(f"\nTotal issues flagged: {issues}")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    run()
