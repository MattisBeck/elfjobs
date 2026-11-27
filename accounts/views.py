from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from jobs.models import JobPosting, Tag
from jobs.travel import warm_home_commutes
from jobs.views import FILTER_CHIPS

from .cv import accept_cv_skills, cv_suggestions, sample_cv_path
from .forms import CvSampleForm, NameForm, OnboardingSkillsForm, ProfileForm, SignupForm, set_profile_skills
from .geocode import geocode
from .models import ProfileSkill, StudentProfile


def signup(request):
    """Registrieren. Das Konto bleibt inaktiv, bis der Link aus der Mail geklickt wurde (#31)."""
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_confirmation_mail(request, user)
            request.session["pending_email"] = user.email
            return redirect("confirm_pending")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


def send_confirmation_mail(request, user):
    """Mail mit Bestätigungslink. Token von Django: gilt 3 Tage und nur einmal,
    weil er nach dem Login (last_login ändert sich) nicht mehr passt."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = request.build_absolute_uri(reverse("confirm_email", args=[uid, token]))
    send_mail(
        "Bestätige deine Uni-Mail für elfjobs",
        f"Hallo {user.first_name},\n\n"
        f"bitte bestätige deine Uni-Mail, dann ist dein Konto bei elfjobs aktiv:\n\n{link}\n\n"
        "Der Link gilt 3 Tage. Wenn du dich nicht registriert hast, ignoriere diese Mail einfach.\n",
        None,  # DEFAULT_FROM_EMAIL
        [user.email],
    )


def confirm_pending(request):
    """Seite „Bitte bestätige deine Mail“ mit „Mail erneut senden“.

    Sagt nie, ob es ein Konto zu einer Adresse gibt; gesendet wird nur an unbestätigte Konten.
    """
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        user = User.objects.filter(username=email, is_active=False).first()
        if user:
            send_confirmation_mail(request, user)
        request.session["pending_email"] = email
        messages.info(request, "Wenn es zu dieser Adresse ein unbestätigtes Konto gibt, ist eine neue Mail unterwegs.")
        return redirect("confirm_pending")
    return render(request, "accounts/confirm_pending.html", {"email": request.session.get("pending_email", "")})


def confirm_email(request, uidb64, token):
    """Link aus der Mail: Konto aktivieren und gleich einloggen."""
    try:
        user = User.objects.get(pk=urlsafe_base64_decode(uidb64).decode())
    except (ValueError, TypeError, OverflowError, User.DoesNotExist):
        user = None
    if user is None or user.is_active or not default_token_generator.check_token(user, token):
        return render(request, "accounts/confirm_invalid.html", status=400)
    user.is_active = True
    user.save(update_fields=["is_active"])
    login(request, user)
    messages.success(request, "Danke, deine Uni-Mail ist bestätigt. Willkommen bei elfjobs!")
    # Neue Konten gehen durchs Onboarding (#35). Die Kopfzeile zeigt den Weg zurück, bis es fertig ist.
    request.session["onboarding"] = True
    return redirect("onboarding_skills")


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
            if "home_town" in profile_form.changed_data:
                update_home(request, student)
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
        "my_fairs": request.user.fairs.filter(date__gte=timezone.localdate()).order_by("date"),
        # Eigene Bewerbungen (#14), neueste zuerst.
        "my_applications": student.applications.select_related("posting__company").order_by("-applied_at"),
    })


def update_home(request, student):
    """Wohnort geändert: Koordinaten suchen (#53) und ÖPNV-Zeiten zu den nächsten Stellen holen."""
    point = geocode(student.home_town) if student.home_town else None
    student.home_latitude, student.home_longitude = point if point else (None, None)
    student.save(update_fields=["home_latitude", "home_longitude"])
    if point:
        warm_home_commutes(student, list(JobPosting.objects.exclude(latitude=None)))
    elif student.home_town:
        messages.warning(
            request,
            f"„{student.home_town}“ haben wir auf der Karte nicht gefunden. "
            "Bis dahin rechnen wir mit der geschätzten Fahrzeit der Firmen.",
        )


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


# Onboarding nach der Registrierung (#35): drei Schritte, jeder überspringbar.


@login_required
def onboarding_skills(request):
    """Schritt 1: Skills. Was aus den belegten Modulen kommt, steht schon fest."""
    student, _ = StudentProfile.objects.get_or_create(user=request.user)
    course_skills = Tag.objects.filter(courses__in=student.courses.all()).distinct().order_by("name")
    if request.method == "POST":
        if "ueberspringen" in request.POST:
            return redirect("onboarding_timetable")
        form = OnboardingSkillsForm(request.POST, course_skills=course_skills)
        if form.is_valid():
            set_profile_skills(student, form.cleaned_data["skills"])
            return redirect("onboarding_timetable")
    else:
        form = OnboardingSkillsForm(course_skills=course_skills, initial={
            "skills": Tag.objects.filter(
                profile_skills__profile=student, profile_skills__source=ProfileSkill.Source.PROFILE
            )
        })
    return render(request, "accounts/onboarding_skills.html", {"form": form, "course_skills": course_skills})


@login_required
def onboarding_timetable(request):
    """Schritt 2: Stundenplan. Eingetragen wird auf der Stundenplan-Seite."""
    return render(request, "accounts/onboarding_timetable.html")


@login_required
def onboarding_kinds(request):
    """Schritt 3: Art des Jobs. Danach die Stellenliste mit diesen Filtern."""
    if request.method == "POST":
        request.session.pop("onboarding", None)
        chosen = [] if "ueberspringen" in request.POST else request.POST.getlist("filter")
        query = urlencode([("filter", key) for key in FILTER_CHIPS if key in chosen])
        return redirect(reverse("job_list") + (f"?{query}" if query else ""))
    return render(request, "accounts/onboarding_kinds.html", {"chips": FILTER_CHIPS})
