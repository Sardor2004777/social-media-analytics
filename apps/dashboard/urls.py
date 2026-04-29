from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "dashboard"

urlpatterns = [
    path("",          views.home,          name="home"),
    path("dashboard/", views.dashboard_app, name="app"),
    path("api/search/", views.global_search, name="search"),
    path("help/",     TemplateView.as_view(template_name="dashboard/help.html"),    name="help"),
    path("terms/",    TemplateView.as_view(template_name="dashboard/terms.html"),   name="terms"),
    path("privacy/",  TemplateView.as_view(template_name="dashboard/privacy.html"), name="privacy"),
]
