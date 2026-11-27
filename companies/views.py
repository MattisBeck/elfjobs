from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from jobs.models import JobPosting

from .forms import CompanySignupForm, PostingForm, ShiftFormSet
from .models import CompanyMember


def company_required(view):
    """Nur für Firmenkonten. Ohne Login zum Firmen-Login, Studi-Konten bekommen 403.

    Setzt request.company auf die Firma des Kontos.
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        member = CompanyMember.objects.select_related("company").filter(user=request.user).first()
        if member is None:
            raise PermissionDenied("Nur für Firmenkonten.")
        request.company = member.company
        return view(request, *args, **kwargs)
    return login_required(wrapper, login_url="company_login")


class CompanyLoginForm(AuthenticationForm):
    username = forms.CharField(label="Mail")

    def clean_username(self):
        return self.cleaned_data["username"].lower()


company_login = LoginView.as_view(
    template_name="companies/login.html", authentication_form=CompanyLoginForm, next_page="company_home"
)


def company_signup(request):
    if request.method == "POST":
        form = CompanySignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("company_home")
    else:
        form = CompanySignupForm()
    return render(request, "companies/signup.html", {"form": form})


@company_required
def company_home(request):
    """Firmenbereich: alle Stellen der eigenen Firma."""
    postings = request.company.postings.prefetch_related("shifts").order_by("-created_at", "-id")
    return render(request, "companies/home.html", {"company": request.company, "postings": postings})


@company_required
def posting_edit(request, pk=None):
    """Stelle anlegen (ohne pk) oder bearbeiten. Fremde Stellen gibt es hier nicht (404)."""
    if pk is None:
        posting = JobPosting(company=request.company)
    else:
        posting = get_object_or_404(JobPosting, pk=pk, company=request.company)

    data = request.POST if request.method == "POST" else None
    form = PostingForm(data, instance=posting)
    shifts = ShiftFormSet(data, instance=posting)
    if data is not None and form.is_valid() and shifts.is_valid():
        kept = [f for f in shifts.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        if form.cleaned_data["schedule"] == JobPosting.Schedule.FIXED and not kept:
            form.add_error("schedule", "Bei festen Zeiten bitte mindestens eine Schicht eintragen.")
        else:
            with transaction.atomic():
                posting = form.save()
                shifts.instance = posting
                shifts.save()
            messages.success(request, f"„{posting.title}“ gespeichert.")
            return redirect("company_home")

    return render(request, "companies/posting_form.html", {
        "company": request.company, "form": form, "shifts": shifts, "posting": posting,
    })
