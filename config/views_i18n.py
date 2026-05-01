"""Robust language-switching view.

Wraps Django's stock ``set_language`` to fix a quirk: Django's
``translate_url`` resolves the ``next`` URL under the *currently active*
language. When that URL already carries a foreign-language prefix
(``/en/dashboard/`` while UZ is the active middleware lang), resolution
fails and the redirect silently keeps the old prefix — so switching from
EN to RU bounces back to /en/.

The fix is to strip any ``/uz/``, ``/ru/``, ``/en/`` prefix from ``next``
before delegating to Django. The cookie is then set, and the redirect
goes to a no-prefix path which Django's translate_url handles correctly.
"""
from __future__ import annotations

import re

from django.http import HttpRequest, HttpResponse
from django.views.i18n import set_language as django_set_language

LANG_PREFIX_RE = re.compile(r"^/(uz|ru|en)(/|$)")


def set_language(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        # POST data is immutable; copy and strip the prefix from next.
        post = request.POST.copy()
        next_url = post.get("next") or ""
        stripped = LANG_PREFIX_RE.sub("/", next_url)
        if stripped != next_url:
            post["next"] = stripped
            request.POST = post
    return django_set_language(request)
