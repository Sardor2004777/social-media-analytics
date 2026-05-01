from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("",          views.analytics_overview, name="overview"),
    path("sentiment/", views.sentiment_page,    name="sentiment"),
    path("compare/",  views.analytics_compare,  name="compare"),
    path("top/",      views.analytics_top_posts, name="top_posts"),
    path("chat/",     views.analytics_chat,     name="chat"),
    path("insight/",  views.ai_insight,         name="insight"),
    path("best-time/", views.best_time_page, name="best_time"),
    path("views/",            views.saved_views_api,    name="saved_views"),
    path("digest/",   views.ai_digest,          name="digest"),
    path("translate/",   views.ai_translate,        name="translate"),
    path("alerts/",      views.alerts_inbox,        name="alerts"),
    path("alerts/<int:pk>/dismiss/", views.alerts_dismiss, name="alerts_dismiss"),
    path("alerts/unread/json/", views.alerts_unread_count, name="alerts_unread_json"),
]
