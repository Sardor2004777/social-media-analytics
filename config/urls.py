"""Root URL configuration.

- i18n_patterns wraps user-facing URLs so they get language prefixes like /uz/, /ru/, /en/.
- /admin/, /api/, /accounts/ (allauth), and /set-language/ stay at the root.
"""
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .views_i18n import set_language as robust_set_language

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    # Robust set_language wrapper — strips foreign /xx/ prefix from `next`
    # before delegating to Django, so switching from /en/ to /ru/ doesn't
    # bounce back to /en/. Must be defined BEFORE the include below to win
    # the URL match.
    path("i18n/setlang/", robust_set_language, name="set_language"),
    path("i18n/", include("django.conf.urls.i18n")),
    # REST API (no language prefix — content-negotiable via Accept-Language header)
    path("api/v1/", include("apps.api.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/v1/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

# Language-prefixed user-facing routes
urlpatterns += i18n_patterns(
    path("", include("apps.dashboard.urls")),
    path("social/", include("apps.social.urls")),
    path("analytics/", include("apps.analytics.urls")),
    path("reports/", include("apps.reports.urls")),
    path("settings/", include("apps.accounts.urls")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    try:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
