from django.urls import path

from . import views

app_name = "social"

urlpatterns = [
    path("",                                views.accounts_list,              name="accounts"),
    path("connect/youtube/start/",          views.youtube_connect_start,      name="youtube_connect_start"),
    path("connect/youtube/callback/",       views.youtube_connect_callback,   name="youtube_connect_callback"),
    path("connect/instagram/start/",        views.instagram_connect_start,    name="instagram_connect_start"),
    path("connect/instagram/callback/",     views.instagram_connect_callback, name="instagram_connect_callback"),
    path("connect/telegram/start/",         views.telegram_connect_start,     name="telegram_connect_start"),
    path("connect/telegram/code/",          views.telegram_code_submit,       name="telegram_code"),
    path("connect/telegram/password/",      views.telegram_password_submit,   name="telegram_password"),
    path("connect/telegram/channels/",      views.telegram_channels_pick,     name="telegram_channels"),
    path("connect/vk/start/",               views.vk_connect_start,           name="vk_connect_start"),
    path("connect/vk/callback/",            views.vk_connect_callback,        name="vk_connect_callback"),
    path("connect/<str:platform>/",         views.account_connect,            name="connect"),
    path("<int:pk>/disconnect/",            views.account_disconnect,         name="disconnect"),
    path("<int:pk>/refresh/",               views.account_refresh,            name="refresh"),
    path("<int:pk>/share/",                 views.toggle_share_link,          name="toggle_share"),
    path("share/<str:token>/",              views.public_share,               name="public_share"),
]
