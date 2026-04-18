from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard_app, name="app"),
]
