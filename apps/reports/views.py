"""Report views — index + XLSX and PDF export endpoints."""
from __future__ import annotations

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.analytics.models import SentimentResult
from apps.collectors.models import Comment
from apps.social.models import ConnectedAccount, Post

from .services.excel import build_workbook
from .services.pdf import build_pdf


@login_required
def reports_index(request: HttpRequest) -> HttpResponse:
    """Landing page for exports: stats summary + cards linking to XLSX / PDF."""
    user = request.user
    ctx = {
        "active_nav": "reports",
        "accounts_count":   ConnectedAccount.objects.filter(user=user).count(),
        "posts_count":      Post.objects.filter(account__user=user).count(),
        "comments_count":   Comment.objects.filter(post__account__user=user).count(),
        "sentiments_count": SentimentResult.objects.filter(comment__post__account__user=user).count(),
    }
    return render(request, "dashboard/reports.html", ctx)


@login_required
def export_xlsx(request: HttpRequest) -> HttpResponse:
    data = build_workbook(request.user)
    fname = f"social-analytics-{request.user.id}-{datetime.now():%Y%m%d-%H%M}.xlsx"
    resp = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{fname}"'
    return resp


@login_required
def export_pdf(request: HttpRequest) -> HttpResponse:
    data = build_pdf(request.user)
    fname = f"social-analytics-{request.user.id}-{datetime.now():%Y%m%d-%H%M}.pdf"
    resp = HttpResponse(data, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{fname}"'
    return resp
