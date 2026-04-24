from django.urls import path

from . import views

app_name = "social"

urlpatterns = [
    path("",                                views.accounts_list,              name="accounts"),
    path("connect/youtube/start/",          views.youtube_connect_start,      name="youtube_connect_start"),
    path("connect/youtube/callback/",       views.youtube_connect_callback,   name="youtube_connect_callback"),
    path("connect/instagram/start/",        views.instagram_connect_start,    name="instagram_connect_start"),
    path("connect/instagram/callback/",     views.instagram_connect_callback, name="instagram_connect_callback"),
    path("connect/<str:platform>/",         views.account_connect,            name="connect"),
    path("<int:pk>/disconnect/",            views.account_disconnect,         name="disconnect"),
    path("<int:pk>/refresh/",               views.account_refresh,            name="refresh"),
    path("<int:pk>/share/",                 views.toggle_share_link,          name="toggle_share"),
    path("share/<str:token>/",              views.public_share,               name="public_share"),
]
