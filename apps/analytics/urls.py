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
    path("post-generator/", views.ai_post_generator, name="post_generator"),
    path("best-time/", views.best_time_page, name="best_time"),
    path("hashtags/",  views.hashtags_page,  name="hashtags"),
    path("hashtags/suggest/", views.ai_hashtag_suggest, name="hashtag_suggest"),
    path("views/",            views.saved_views_api,    name="saved_views"),
    path("digest/",   views.ai_digest,          name="digest"),
    path("predict/",  views.engagement_predict, name="predict"),
    path("correlation/", views.correlation_page, name="correlation"),
    path("clusters/",    views.topic_clusters_page, name="clusters"),
    path("translate/",   views.ai_translate,        name="translate"),
    path("alerts/",      views.alerts_inbox,        name="alerts"),
    path("alerts/<int:pk>/dismiss/", views.alerts_dismiss, name="alerts_dismiss"),
    path("alerts/unread/json/", views.alerts_unread_count, name="alerts_unread_json"),
]
