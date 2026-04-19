from django.contrib import admin

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display  = ("author_handle", "language", "likes", "published_at", "post")
    list_filter   = ("language", "post__account__platform")
    search_fields = ("body", "author_handle")
    date_hierarchy = "published_at"
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("post",)
