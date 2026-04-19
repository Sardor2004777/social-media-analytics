from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("",          views.analytics_overview, name="overview"),
    path("sentiment/", views.sentiment_page,    name="sentiment"),
]
