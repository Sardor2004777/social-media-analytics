"""Profile / settings views."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

User = get_user_model()


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "field-input", "placeholder": "Ism"}),
            "last_name":  forms.TextInput(attrs={"class": "field-input", "placeholder": "Familiya"}),
            "email":      forms.EmailInput(attrs={"class": "field-input"}),
        }


@login_required
def settings_page(request: HttpRequest) -> HttpResponse:
    """Profile form + links to password change / data export."""
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil yangilandi.")
            return redirect("accounts:settings")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "dashboard/settings.html", {
        "active_nav": "settings",
        "form": form,
    })
