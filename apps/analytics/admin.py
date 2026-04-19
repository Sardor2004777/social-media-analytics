from django.contrib import admin

from .models import SentimentResult


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
