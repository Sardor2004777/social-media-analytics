from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"
    label = "analytics"
    verbose_name = "Analytics"

    def ready(self) -> None:
        # Wire Alert post_save → notify_alert.delay
        from . import signals  # noqa: F401
