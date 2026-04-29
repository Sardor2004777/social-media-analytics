"""Shared abstract models used across apps."""
from django.conf import settings
from django.db import models


class TimestampedModel(models.Model):
    """Abstract base providing created_at / updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ActivityLog(models.Model):
    """User-facing audit trail.

    Records "what the user did" — login, account connect, sync, AI request,
    export, 2FA changes — so they can review their own history under
    /accounts/activity/. Intentionally per-user (no admin/system events
    here) and with a small bounded ``kind`` vocabulary so the UI can map
    icons + colours without free-text matching.
    """
    KINDS = [
        ("login",        "Login"),
        ("logout",       "Logout"),
        ("connect",      "Account connected"),
        ("disconnect",   "Account disconnected"),
        ("sync",         "Sync"),
        ("ai",           "AI request"),
        ("export",       "Export"),
        ("2fa",          "2FA change"),
        ("share",        "Share toggle"),
        ("settings",     "Settings change"),
        ("other",        "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_log",
    )
    kind    = models.CharField(max_length=24, choices=KINDS, db_index=True, default="other")
    message = models.CharField(max_length=400)
    meta    = models.JSONField(default=dict, blank=True)
    ip      = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"[{self.kind}] {self.user_id}: {self.message[:60]}"


class SavedView(models.Model):
    """A bookmarked filter combination for a list page (e.g. Top Posts).

    The ``page`` field is a free-form key (``"top_posts"``, ``"sentiment"``)
    so the UI can scope which saved views to show on each page. ``query``
    is the URL querystring (without the leading ``?``) — opaque to the
    backend, the page just appends it to its own URL when restoring.
    """
    user  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_views",
    )
    page  = models.CharField(max_length=40, db_index=True)
    name  = models.CharField(max_length=80)
    query = models.CharField(max_length=600, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("user", "page", "name")]

    def __str__(self) -> str:
        return f"{self.page}/{self.name}"


def log_activity(user, kind: str, message: str, *, request=None, **meta):
    """Convenience: create an ActivityLog entry, swallowing any DB error.

    Caller use: ``log_activity(request.user, "ai", "AI Chat asked")``.
    Returns the created row, or None on failure (we never want logging to
    break the feature being logged).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None
    ip = None
    if request is not None:
        ip = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
        ip = ip or request.META.get("REMOTE_ADDR")
    try:
        return ActivityLog.objects.create(
            user=user, kind=kind, message=message[:400], meta=meta or {}, ip=ip,
        )
    except Exception:
        return None
