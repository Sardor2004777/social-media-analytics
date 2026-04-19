from django.urls import path

from . import views

app_name = "social"

urlpatterns = [
    path("",                        views.accounts_list,       name="accounts"),
    path("connect/<str:platform>/", views.account_connect,     name="connect"),
    path("<int:pk>/disconnect/",    views.account_disconnect,  name="disconnect"),
]
