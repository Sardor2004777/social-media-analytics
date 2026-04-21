from django.urls import path

from . import views

app_name = "social"

urlpatterns = [
    path("",                        views.accounts_list,       name="accounts"),
    path("connect/<str:platform>/", views.account_connect,     name="connect"),
    path("<int:pk>/disconnect/",    views.account_disconnect,  name="disconnect"),
    path("<int:pk>/share/",         views.toggle_share_link,   name="toggle_share"),
    path("share/<str:token>/",      views.public_share,        name="public_share"),
]
