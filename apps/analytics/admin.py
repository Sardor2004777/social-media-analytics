from django.contrib import admin

from .models import Alert, NotificationPref, SentimentResult


@admin.register(SentimentResult)
class SentimentResultAdmin(admin.ModelAdmin):
    list_display    = ("short_comment", "label", "score_percent", "model_name", "comment_language", "created_at")
    list_filter     = ("label", "model_name", "created_at", "comment__language")
    search_fields   = ("comment__body",)
    raw_id_fields   = ("comment",)
    readonly_fields = ("created_at", "updated_at")
    list_per_page   = 100
    date_hierarchy  = "created_at"
    ordering        = ("-created_at",)

    @admin.display(description="Comment", ordering="comment__body")
    def short_comment(self, obj) -> str:
        return (obj.comment.body or "")[:70]

    @admin.display(description="Score", ordering="score")
    def score_percent(self, obj) -> str:
        return f"{obj.score * 100:.1f}%"

    @admin.display(description="Lang", ordering="comment__language")
    def comment_language(self, obj) -> str:
        return obj.comment.language.upper()


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display    = ("detected_for", "account", "metric", "direction", "severity", "z_score_fmt", "is_read", "is_resolved")
    list_filter     = ("severity", "metric", "direction", "is_read", "is_resolved", "detected_for")
    search_fields   = ("account__handle", "message")
    raw_id_fields   = ("account",)
    readonly_fields = ("created_at", "updated_at")
    list_per_page   = 100
    date_hierarchy  = "detected_for"
    actions         = ("mark_read", "mark_resolved")

    @admin.display(description="z", ordering="z_score")
    def z_score_fmt(self, obj) -> str:
        return f"{obj.z_score:+.2f}"

    @admin.action(description="Mark selected as read")
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description="Mark selected as resolved")
    def mark_resolved(self, request, queryset):
        queryset.update(is_resolved=True, is_read=True)


@admin.register(NotificationPref)
class NotificationPrefAdmin(admin.ModelAdmin):
    list_display    = ("user", "channel", "is_active", "min_severity", "telegram_chat_id")
    list_filter     = ("channel", "is_active", "min_severity")
    search_fields   = ("user__email", "telegram_chat_id")
    raw_id_fields   = ("user",)
    readonly_fields = ("created_at", "updated_at")
