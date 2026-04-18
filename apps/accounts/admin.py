from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class UserAdminCustom(UserAdmin):
    list_display = ("email", "username", "is_staff", "is_active", "date_joined")
    ordering = ("-date_joined",)
    search_fields = ("email", "username")
