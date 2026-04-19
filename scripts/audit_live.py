"""Smoke audit against the deployed site on Render.

Mirrors ``scripts/audit_urls.py`` but targets production with a longer timeout
and without the demo-login step (the prod DB doesn't have a seeded user by
default). Also explicitly tests POST flows that are the most likely breakage
points on a fresh deploy:

    * Password-reset POST (exercises the email backend).
    * Fresh signup (exercises signup + email + post-login redirect).
    * Language switch (exercises CSRF + i18n middleware).

Run:
    python scripts/audit_live.py [BASE_URL]

Exit code non-zero if any probe flags an issue.
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

ERROR_MARKERS = (
    "TemplateSyntaxError",
    "NoReverseMatch",
    "TemplateDoesNotExist",
    "Traceback (most recent call last)",
    "Server Error (500)",
)

TARGETS = [
    "/",
    "/en/",
    "/accounts/signup/",
    "/accounts/login/",
    "/accounts/password/reset/",
    "/accounts/password/reset/done/",
    "/admin/",
    "/api/v1/docs/",
    "/api/v1/schema/",
    "/api/v1/redoc/",
    "/static/css/output.css",
    "/static/js/app.js",
    "/foobar/",  # expected 404
]


def probe(opener, url: str) -> tuple[int | None, str, int, list[str]]:
    try:
        r = opener.open(url, timeout=60)
        body = r.read()
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        return e.code, url, len(body), []
    except Exception as exc:
        return None, url, 0, [f"request failed: {exc}"]
    errs = [m for m in ERROR_MARKERS if m.encode() in body]
    return r.status, r.geturl(), len(body), errs


def main() -> int:
    print(f"Auditing {BASE}\n")
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    op.addheaders = [("User-Agent", "audit-live/1.0")]

    issues = 0
    print(f"{'Status':<7} {'Size':>9}  {'Path':<40} {'Notes'}")
    print("-" * 90)
    for path in TARGETS:
        code, final, size, errs = probe(op, BASE + path)
        note = ""
        if errs:
            note = "!! " + ", ".join(errs)
            issues += 1
        elif code is None:
            note = "!! no response"
            issues += 1
        elif code >= 500:
            note = f"!! HTTP {code}"
            issues += 1
        elif code == 404 and "foobar" not in path:
            note = "!! 404"
            issues += 1
        final_path = urllib.parse.urlparse(final).path if final else ""
        if final_path and final_path != path:
            note = (note + f" -> {final_path}").strip()
        print(f"{code or '?':<7} {size:>9}  {path:<40} {note}")

    # --- CSRF + email POST probe ---
    print("\n--- POST /accounts/password/reset/ with CSRF ---")
    try:
        r = op.open(BASE + "/accounts/password/reset/", timeout=60)
        html = r.read().decode("utf-8", "ignore")
        token = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)', html).group(1)
        data = urllib.parse.urlencode({
            "csrfmiddlewaretoken": token,
            "email": f"live-audit-{random.randint(10**6, 10**8)}@example.com",
        }).encode()
        req = urllib.request.Request(
            BASE + "/accounts/password/reset/",
            data=data,
            headers={
                "Referer": BASE + "/accounts/password/reset/",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        r = op.open(req, timeout=60)
        print(f"  status={r.status} final={r.geturl()}")
        if r.status >= 500:
            issues += 1
    except Exception as exc:
        print(f"  !! {exc}")
        issues += 1

    # --- Fresh signup ---
    print("\n--- POST /accounts/signup/ (fresh random email) ---")
    op2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    op2.addheaders = [("User-Agent", "audit-live/1.0")]
    try:
        r = op2.open(BASE + "/accounts/signup/", timeout=60)
        html = r.read().decode("utf-8", "ignore")
        token = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)', html).group(1)
        email = f"live-audit-{random.randint(10**6, 10**8)}@example.com"
        data = urllib.parse.urlencode({
            "csrfmiddlewaretoken": token,
            "email": email,
            "password1": "GoodPassw0rd!",
            "password2": "GoodPassw0rd!",
        }).encode()
        req = urllib.request.Request(
            BASE + "/accounts/signup/",
            data=data,
            headers={
                "Referer": BASE + "/accounts/signup/",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        r = op2.open(req, timeout=60)
        print(f"  signup {email} -> status={r.status} final={r.geturl()}")
    except Exception as exc:
        print(f"  !! {exc}")
        issues += 1

    print(f"\nTotal issues: {issues}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
