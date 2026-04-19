from django.contrib import admin

from .models import SentimentResult


@admin.register(SentimentResult)
class SentimentResultAdmin(admin.ModelAdmin):
    list_display  = ("comment", "label", "score", "model_name", "created_at")
    list_filter   = ("label", "model_name")
    search_fields = ("comment__body",)
    raw_id_fields = ("comment",)
    readonly_fields = ("created_at", "updated_at")
