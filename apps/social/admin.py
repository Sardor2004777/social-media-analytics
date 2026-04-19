from django.contrib import admin

from .models import ConnectedAccount, Post


@admin.register(ConnectedAccount)
class ConnectedAccountAdmin(admin.ModelAdmin):
    list_display  = ("handle", "platform", "user_email", "follower_count", "following_count", "is_demo", "created_at")
    list_filter   = ("platform", "is_demo", "created_at")
    search_fields = ("handle", "display_name", "user__email")
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    actions = ("mark_as_demo", "unmark_demo")

    @admin.display(description="User", ordering="user__email")
    def user_email(self, obj) -> str:
        return obj.user.email

    @admin.action(description="Mark selected as demo")
    def mark_as_demo(self, request, queryset) -> None:
        queryset.update(is_demo=True)

    @admin.action(description="Unmark as demo")
    def unmark_demo(self, request, queryset) -> None:
        queryset.update(is_demo=False)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display  = ("short_caption", "platform_badge", "post_type", "likes", "comments_count", "views", "engagement_percent", "published_at")
    list_filter   = ("post_type", "account__platform", "published_at")
    search_fields = ("caption", "account__handle")
    date_hierarchy = "published_at"
    readonly_fields = ("created_at", "updated_at", "engagement_rate")
    raw_id_fields = ("account",)
    list_per_page = 50
    ordering = ("-published_at",)

    @admin.display(description="Caption", ordering="caption")
    def short_caption(self, obj) -> str:
        return (obj.caption or "—")[:60]

    @admin.display(description="Platform", ordering="account__platform")
    def platform_badge(self, obj) -> str:
        return obj.account.get_platform_display()

    @admin.display(description="Eng. %", ordering="engagement_rate")
    def engagement_percent(self, obj) -> str:
        return f"{obj.engagement_rate * 100:.2f}%"
