from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("",             views.reports_index, name="index"),
    path("export.xlsx",  views.export_xlsx,   name="export_xlsx"),
    path("export.pdf",   views.export_pdf,    name="export_pdf"),
]
