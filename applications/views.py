from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from accounts.models import StudentProfile
from companies.models import CompanyMember
from jobs.models import JobPosting
from jobs.travel import apply_home_commutes
from timetable.fit import shift_collides
from timetable.models import PlannedShift
from timetable.planning import planned_hours, shift_label

from .forms import ApplyShiftForm
from .models import Application
from .shifts import suggest_shifts


def flexible_posting_for_student(request, pk):
    """Stelle für die Schicht-Knöpfe beim Bewerben: nur flexible Stellen, keine Firmenkonten."""
    posting = get_object_or_404(JobPosting, pk=pk, schedule=JobPosting.Schedule.FLEXIBLE)
    if CompanyMember.objects.filter(user=request.user).exists():
        raise PermissionDenied("Firmenkonten können sich nicht bewerben.")
    return posting


@login_required
def apply(request, pk):
    """Bewerben (#14) mit dem Schritt „Wann würdest du arbeiten?“ (#141).

    GET zeigt die Schichten, POST sendet die Bewerbung.
    """
    posting = get_object_or_404(JobPosting.objects.select_related("company"), pk=pk)
    if CompanyMember.objects.filter(user=request.user).exists():
        raise PermissionDenied("Firmenkonten können sich nicht bewerben.")
    if request.method == "POST":
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        # get_or_create: Ein zweiter Klick legt keine zweite Bewerbung an.
        application, created = Application.objects.get_or_create(profile=profile, posting=posting)
        if created:
            application.attach_cv()  # Lebenslauf mitschicken (#38)
            copy_fixed_shifts(profile, posting)
            messages.success(
                request,
                format_html(
                    'Bewerbung gesendet. Deine Schichten stehen in deinem <a href="{}">Stundenplan</a>.',
                    reverse("timetable"),
                ),
            )
        return redirect("job_detail", pk=posting.pk)
    if posting.applications.filter(profile__user=request.user).exists():
        return redirect("job_detail", pk=posting.pk)  # schon beworben
    return render(request, "applications/apply.html", apply_step_context(request, posting))


def apply_step_context(request, posting):
    """Daten für die Seite „Wann würdest du arbeiten?“."""
    profile = StudentProfile.objects.filter(user=request.user).first()
    apply_home_commutes(profile, [posting])  # Fahrzeit vom Wohnort, wenn bekannt
    lectures = list(profile.lectures.all()) if profile else []
    context = {"posting": posting, "has_profile": profile is not None, "has_lectures": bool(lectures)}
    if posting.schedule == JobPosting.Schedule.FLEXIBLE:
        planned = list(profile.planned_shifts.filter(posting=posting)) if profile else []
        context.update(
            planned=planned,
            hours=planned_hours(planned),
            form=ApplyShiftForm(posting=posting, lectures=lectures, planned=planned),
        )
    else:
        buffer_minutes = posting.one_way_commute_minutes
        context["shift_rows"] = [
            {"label": shift_label(s.weekday, s.start, s.end), "collides": shift_collides(s, lectures, buffer_minutes)}
            for s in posting.shifts.all()
        ]
    return context


def copy_fixed_shifts(profile, posting):
    """Feste Schichten der Stelle als eigene Schichten speichern, ohne Duplikate."""
    if posting.schedule != JobPosting.Schedule.FIXED:
        return
    for shift in posting.shifts.all():
        PlannedShift.objects.get_or_create(
            profile=profile, posting=posting, weekday=shift.weekday, start=shift.start, end=shift.end
        )


@login_required
@require_POST
def apply_suggest(request, pk):
    """Schichten in die freien Blöcke legen (#141)."""
    posting = flexible_posting_for_student(request, pk)
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    apply_home_commutes(profile, [posting])
    slots, missing_minutes = suggest_shifts(
        posting, profile.lectures.all(), profile.planned_shifts.filter(posting=posting)
    )
    for slot in slots:
        PlannedShift.objects.create(profile=profile, posting=posting, weekday=slot.weekday, start=slot.start, end=slot.end)
    if slots:
        messages.success(request, f"{len(slots)} Schichten vorgeschlagen. Du kannst sie unten ändern oder entfernen.")
    if missing_minutes:
        hours = f"{missing_minutes / 60:.1f}".replace(".", ",").removesuffix(",0")
        messages.warning(request, f"In deinen freien Zeiten ist nicht genug Platz: {hours} h bleiben offen.")
    elif not slots:
        messages.info(request, "Alle Stunden sind schon verplant.")
    return redirect("apply", pk=posting.pk)


@login_required
@require_POST
def apply_shift_add(request, pk):
    """Eine Schicht von Hand hinzufügen (#141)."""
    posting = flexible_posting_for_student(request, pk)
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    form = ApplyShiftForm(
        request.POST,
        posting=posting,
        lectures=list(profile.lectures.all()),
        planned=list(profile.planned_shifts.filter(posting=posting)),
    )
    if form.is_valid():
        shift = PlannedShift.objects.create(profile=profile, posting=posting, **form.cleaned_data)
        messages.success(request, f"Schicht eingeplant: {shift_label(shift.weekday, shift.start, shift.end)}.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect("apply", pk=posting.pk)


@login_required
@require_POST
def apply_shift_delete(request, pk, shift_pk):
    """Eine Schicht wieder entfernen. Fremde Schichten sind nicht erreichbar (#141)."""
    shift = get_object_or_404(PlannedShift, pk=shift_pk, posting_id=pk, profile__user=request.user)
    shift.delete()
    messages.success(request, f"Schicht entfernt: {shift_label(shift.weekday, shift.start, shift.end)}.")
    return redirect("apply", pk=pk)


@login_required
def sent_cv(request, pk):
    """Der mit einer Bewerbung gesendete Lebenslauf (#38). Nur für die Bewerberin selbst und Admins."""
    application = get_object_or_404(Application, pk=pk)
    is_owner = application.profile.user_id == request.user.id
    if not (is_owner or request.user.is_staff) or not application.cv:
        raise Http404("Kein Lebenslauf.")
    return FileResponse(application.cv.open("rb"), content_type="application/pdf", filename="lebenslauf.pdf")
