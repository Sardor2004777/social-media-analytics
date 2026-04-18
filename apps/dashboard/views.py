"""Dashboard views — placeholder home page until Phase 6."""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """Public landing page. Later becomes the dashboard for logged-in users."""
    return render(request, "dashboard/home.html")
