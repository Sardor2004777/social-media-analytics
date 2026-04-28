from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("",          views.analytics_overview, name="overview"),
    path("sentiment/", views.sentiment_page,    name="sentiment"),
    path("compare/",  views.analytics_compare,  name="compare"),
    path("top/",      views.analytics_top_posts, name="top_posts"),
    path("chat/",     views.analytics_chat,     name="chat"),
    path("digest/",   views.ai_digest,          name="digest"),
    path("predict/",  views.engagement_predict, name="predict"),
    path("correlation/", views.correlation_page, name="correlation"),
    path("clusters/",    views.topic_clusters_page, name="clusters"),
]
