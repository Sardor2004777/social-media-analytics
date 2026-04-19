from django.contrib import admin

from .models import ConnectedAccount, Post


@admin.register(ConnectedAccount)
class ConnectedAccountAdmin(admin.ModelAdmin):
    list_display  = ("handle", "platform", "user", "follower_count", "is_demo", "created_at")
    list_filter   = ("platform", "is_demo")
    search_fields = ("handle", "display_name", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display  = ("__str__", "post_type", "likes", "comments_count", "views", "published_at")
    list_filter   = ("post_type", "account__platform")
    search_fields = ("caption", "account__handle")
    date_hierarchy = "published_at"
    readonly_fields = ("created_at", "updated_at", "engagement_rate")
