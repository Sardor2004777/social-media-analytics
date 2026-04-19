"""Report views."""
from __future__ import annotations

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse

from .services.excel import build_workbook


@login_required
def export_xlsx(request: HttpRequest) -> HttpResponse:
    """Stream a multi-sheet Excel workbook of the user's data."""
    workbook_bytes = build_workbook(request.user)
    filename = f"social-analytics-{request.user.id}-{datetime.now():%Y%m%d-%H%M}.xlsx"
    response = HttpResponse(
        workbook_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
