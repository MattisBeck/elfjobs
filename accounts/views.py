from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .cv import accept_cv_skills, cv_suggestions, sample_cv_path
from .forms import CvSampleForm, NameForm, ProfileForm, SignupForm
from .models import StudentProfile


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("profile")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile(request):
    student, _ = StudentProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        name_form = NameForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, instance=student)
        if name_form.is_valid() and profile_form.is_valid():
            name_form.save()
            profile_form.save()
            messages.success(request, "Profil gespeichert.")
            return redirect("profile")
    else:
        name_form = NameForm(instance=request.user)
        profile_form = ProfileForm(instance=student)
    new_skills, existing_skills = cv_suggestions(student)
    return render(request, "accounts/profile.html", {
        "name_form": name_form,
        "profile_form": profile_form,
        "cv_form": CvSampleForm(instance=student),
        "cv_new_skills": new_skills,
        "cv_existing_skills": existing_skills,
    })


@login_required
@require_POST
def cv_select(request):
    """Beispiel-Lebenslauf wählen („Auslesen“). Die Vorschläge zeigt danach das Profil."""
    student, _ = StudentProfile.objects.get_or_create(user=request.user)
    form = CvSampleForm(request.POST, instance=student)
    if form.is_valid():
        form.save()
    return redirect(reverse("profile") + "#lebenslauf")


@login_required
@require_POST
def cv_accept(request):
    """Angehakte Vorschläge aus dem Lebenslauf als Skills übernehmen."""
    student, _ = StudentProfile.objects.get_or_create(user=request.user)
    count = accept_cv_skills(student, request.POST.getlist("skills"))
    if count:
        messages.success(request, f"Aus deinem Lebenslauf übernommen: {count} Skills.")
    return redirect(reverse("profile") + "#lebenslauf")


@login_required
def cv_pdf(request):
    """Liefert den eigenen Lebenslauf aus. Fremde Lebensläufe sind über diese URL nicht erreichbar."""
    student, _ = StudentProfile.objects.get_or_create(user=request.user)
    path = sample_cv_path(student)
    if path is None or not path.exists():
        raise Http404("Kein Lebenslauf gewählt.")
    return FileResponse(open(path, "rb"), content_type="application/pdf", filename="lebenslauf.pdf")
