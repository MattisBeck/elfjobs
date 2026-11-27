from datetime import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import StudentProfile
from jobs.models import Weekday
from jobs.travel import apply_home_commutes

from .columns import overlaps, side_by_side
from .forms import IcsUploadForm, LectureSlotForm
from .conflicts import shift_conflicts
from .free_time import DAY_END, DAY_START, free_blocks, free_hours, to_minutes
from .ics import IcsError, parse_ics
from .models import LectureSlot


def current_profile(request):
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    return profile


@login_required
def timetable(request):
    """Mein Stundenplan: Termine pro Tag, freie Blöcke und ein Formular für neue Termine."""
    profile = current_profile(request)
    if request.method == "POST":
        form = LectureSlotForm(request.POST)
        if form.is_valid():
            lecture = form.save(commit=False)
            lecture.profile = profile
            lecture.save()
            messages.success(request, f"{lecture.title} eingetragen.")
            return redirect("timetable")
    else:
        form = LectureSlotForm()
    return render_timetable(request, profile, form, IcsUploadForm())


def render_timetable(request, profile, form, upload_form):
    lectures = list(profile.lectures.all())
    shifts = planned_shifts(profile)
    # Frei ist, was weder Vorlesung noch eigene Schicht ist (#140).
    blocks = free_blocks(lectures + shifts)
    conflicts = shift_conflicts(shifts, lectures)
    for shift in shifts:
        shift.conflict_text = "; ".join(conflicts.get(shift.pk, []))
    # Pro Tag Termine und freie Blöcke gemeinsam nach Uhrzeit, wie in einem Kalender.
    days = []
    for weekday, label in Weekday.choices:
        entries = [{"lecture": l, "start": l.start} for l in lectures if l.weekday == weekday]
        entries += [{"free": b, "start": b.start} for b in blocks if b.weekday == weekday]
        entries += [{"shift": s, "start": s.start} for s in shifts if s.weekday == weekday]
        entries.sort(key=lambda entry: entry["start"])
        days.append({
            "label": label,
            "entries": entries,
            "has_lectures": any("lecture" in entry for entry in entries),
            "has_items": any("free" not in entry for entry in entries),
        })
    return render(request, "timetable/timetable.html", {
        "days": days,
        "free_hours": free_hours(blocks),
        "shifts": shifts,
        "conflict_shifts": [shift for shift in shifts if shift.conflict_text],
        "form": form,
        "upload_form": upload_form,
        "outside": [lecture for lecture in sorted(lectures, key=lambda l: (l.weekday, l.start)) if not in_grid(lecture)],
        # Daten für das Wochenraster zum Ziehen (#87, static/js/timetable.js). Das Raster zeigt
        # 8–20 Uhr; was nicht ganz hineinpasst, steht darunter mit Ändern und Löschen (#123).
        "calendar": {
            **calendar_state(lectures, shifts),
            "lectures": [lecture_json(lecture) for lecture in lectures if in_grid(lecture)],
            # Eigene Schichten (#140): nur anzeigen, nicht ziehbar. Ändern und Löschen geht bei der Stelle.
            "shifts": [shift_json(shift) for shift in shifts],
            "urls": {
                "create": reverse("lecture_api_create"),
                # Platzhalter 0 ersetzt das JavaScript durch die ID des Termins.
                "update": reverse("lecture_api_update", args=[0]),
                "delete": reverse("lecture_api_delete", args=[0]),
            },
        },
    })


def planned_shifts(profile):
    """Eigene Schichten (#11) mit Stelle und Firma. Die Fahrzeit vom Wohnort wie bei der Passung (#53)."""
    shifts = list(profile.planned_shifts.select_related("posting__company"))
    postings = {shift.posting_id: shift.posting for shift in shifts}
    apply_home_commutes(profile, list(postings.values()))
    for shift in shifts:
        shift.posting = postings[shift.posting_id]
    return shifts


def shift_json(shift):
    return {
        "id": shift.pk,
        "title": shift.posting.title,
        "company": shift.posting.company.name,
        "weekday": shift.weekday,
        "start": shift.start.strftime("%H:%M"),
        "end": shift.end.strftime("%H:%M"),
        "url": reverse("job_detail", args=[shift.posting_id]) + "?ansicht=woche",
        "conflict": shift.conflict_text,
    }


# JSON-Endpunkte für das Wochenraster (#87). Gleiche Regeln wie das Formular:
# LectureSlotForm prüft die Zeiten, und geändert werden nur eigene Termine.


def in_grid(lecture):
    """Liegt der Termin ganz im Raster von 8 bis 20 Uhr? Sonst würde er dort verschwinden
    oder beim Verschieben still auf 8 Uhr gesetzt (#123)."""
    return DAY_START <= lecture.start and lecture.end <= DAY_END


def lecture_json(lecture):
    return {
        "id": lecture.pk,
        "title": lecture.title,
        "weekday": lecture.weekday,
        "start": lecture.start.strftime("%H:%M"),
        "end": lecture.end.strftime("%H:%M"),
    }


def calendar_layout(lectures, shifts):
    """Wo jeder Termin und jede eigene Schicht im Raster steht (#135, #146).

    Ergebnis: zwei Dicts, weil Vorlesungen und Schichten eigene IDs haben, die gleich sein können.
    - layout: {Vorlesungs-ID: {"left", "width", "overlaps"}}, "overlaps" sind die Titel der
      Vorlesungen, mit denen sie sich überschneidet.
    - shift_layout: {Schicht-ID: {"left", "width"}}. Den Konflikttext hat die Schicht schon (#140).
    Was sich überschneidet, steht nebeneinander, auch eine Schicht neben einer Vorlesung
    (gleiche Regel wie „In meiner Woche“).
    """
    layout = {}
    shift_layout = {}
    for weekday in Weekday.values:
        day = [lecture for lecture in lectures if lecture.weekday == weekday and in_grid(lecture)]
        day_shifts = [shift for shift in shifts if shift.weekday == weekday]
        spans = [(to_minutes(item.start), to_minutes(item.end)) for item in day + day_shifts]
        positions = side_by_side(spans)
        for lecture, span, position in zip(day, spans, positions):
            layout[str(lecture.pk)] = {
                **position,
                "overlaps": [
                    other.title for other, other_span in zip(day, spans)
                    if other is not lecture and overlaps(span, other_span)
                ],
            }
        for shift, position in zip(day_shifts, positions[len(day):]):
            shift_layout[str(shift.pk)] = position
    return layout, shift_layout


def calendar_state(lectures, shifts):
    """Freie Blöcke, Stunden und Spalten nach einer Änderung, damit das Raster sie neu zeichnen kann.

    Eigene Schichten (#140) belegen Zeit wie Vorlesungen und stehen in denselben Spalten (#146).
    """
    lectures = list(lectures)
    shifts = list(shifts)
    blocks = free_blocks(lectures + shifts)
    layout, shift_layout = calendar_layout(lectures, shifts)
    return {
        "layout": layout,
        "shift_layout": shift_layout,
        "free": [
            {"weekday": b.weekday, "start": b.start.strftime("%H:%M"), "end": b.end.strftime("%H:%M")}
            for b in blocks
        ],
        "free_hours": free_hours(blocks),
    }


def api_login_required(view):
    """Wie login_required, aber für fetch: 403 statt Weiterleitung zur Anmeldung."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"errors": {"__all__": ["Bitte melde dich an."]}}, status=403)
        return view(request, *args, **kwargs)
    return wrapper


def save_lecture(request, lecture, status):
    form = LectureSlotForm(request.POST, instance=lecture)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    lecture = form.save()
    state = calendar_state(lecture.profile.lectures.all(), lecture.profile.planned_shifts.all())
    return JsonResponse({"lecture": lecture_json(lecture), **state}, status=status)


@require_POST
@api_login_required
def lecture_api_create(request):
    return save_lecture(request, LectureSlot(profile=current_profile(request)), status=201)


@require_POST
@api_login_required
def lecture_api_update(request, pk):
    lecture = get_object_or_404(LectureSlot, pk=pk, profile=current_profile(request))
    return save_lecture(request, lecture, status=200)


@require_POST
@api_login_required
def lecture_api_delete(request, pk):
    profile = current_profile(request)
    get_object_or_404(LectureSlot, pk=pk, profile=profile).delete()
    return JsonResponse(calendar_state(profile.lectures.all(), profile.planned_shifts.all()))


@login_required
def lecture_edit(request, pk):
    lecture = get_object_or_404(LectureSlot, pk=pk, profile=current_profile(request))
    form = LectureSlotForm(request.POST or None, instance=lecture)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{lecture.title} geändert.")
        return redirect("timetable")
    return render(request, "timetable/lecture_form.html", {"form": form, "lecture": lecture})


@login_required
@require_POST
def lecture_delete(request, pk):
    lecture = get_object_or_404(LectureSlot, pk=pk, profile=current_profile(request))
    lecture.delete()
    messages.success(request, f"{lecture.title} gelöscht.")
    return redirect("timetable")


# Stundenplan als ICS-Datei (#43): hochladen → Vorschau → übernehmen.
# Die gelesenen Termine liegen bis zum Übernehmen in der Session, Uhrzeiten als „HH:MM“.


@login_required
@require_POST
def ics_upload(request):
    form = IcsUploadForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            slots, skipped = parse_ics(form.cleaned_data["datei"].read())
        except IcsError as error:
            form.add_error("datei", str(error))
        else:
            if not slots:
                form.add_error("datei", "In der Datei steht kein wöchentlicher Termin von Montag bis Freitag.")
            else:
                request.session["ics_import"] = {
                    "slots": [
                        {**slot, "start": slot["start"].strftime("%H:%M"), "end": slot["end"].strftime("%H:%M")}
                        for slot in slots
                    ],
                    "skipped": skipped,
                }
                return redirect("ics_preview")
    # Die Stundenplan-Seite zeigt die Fehlermeldung am Upload-Feld.
    return render_timetable(request, current_profile(request), LectureSlotForm(), form)


@login_required
def ics_preview(request):
    data = request.session.get("ics_import")
    if not data:
        return redirect("timetable")
    slots = [
        {**slot, "start": time.fromisoformat(slot["start"]), "end": time.fromisoformat(slot["end"]),
         "day": Weekday(slot["weekday"]).label}
        for slot in data["slots"]
    ]
    if request.method == "POST":
        profile = current_profile(request)
        if request.POST.get("ersetzen"):
            profile.lectures.all().delete()
        LectureSlot.objects.bulk_create(
            LectureSlot(profile=profile, weekday=s["weekday"], start=s["start"], end=s["end"], title=s["title"])
            for s in slots
        )
        del request.session["ics_import"]
        messages.success(request, f"{len(slots)} Termine übernommen, {data['skipped']} übersprungen.")
        return redirect("timetable")
    return render(request, "timetable/ics_preview.html", {"slots": slots, "skipped": data["skipped"]})
