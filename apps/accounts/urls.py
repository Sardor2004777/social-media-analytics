from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("",           views.settings_page,   name="settings"),
    path("export/",    views.export_my_data,  name="export_data"),
    path("delete/",    views.delete_account,  name="delete_account"),
    path("2fa/",       views.two_factor_setup, name="two_factor"),
    path("activity/",  views.activity_log_view, name="activity"),
]
