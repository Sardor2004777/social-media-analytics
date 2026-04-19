from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("export.xlsx", views.export_xlsx, name="export_xlsx"),
]
