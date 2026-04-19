from django.contrib import admin

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display    = ("short_body", "author_handle", "language", "likes", "platform", "sentiment_label", "published_at")
    list_filter     = ("language", "post__account__platform", "published_at")
    search_fields   = ("body", "author_handle")
    date_hierarchy  = "published_at"
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields   = ("post",)
    list_per_page   = 100
    ordering        = ("-published_at",)

    @admin.display(description="Comment", ordering="body")
    def short_body(self, obj) -> str:
        return (obj.body or "")[:80]

    @admin.display(description="Platform", ordering="post__account__platform")
    def platform(self, obj) -> str:
        return obj.post.account.get_platform_display()

    @admin.display(description="Sentiment")
    def sentiment_label(self, obj) -> str:
        s = getattr(obj, "sentiment", None)
        return f"{s.label} ({s.score:.2f})" if s else "—"
