from datetime import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import StudentProfile
from jobs.models import Weekday

from .forms import IcsUploadForm, LectureSlotForm
from .free_time import free_blocks, free_hours
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
    blocks = free_blocks(lectures)
    # Pro Tag Termine und freie Blöcke gemeinsam nach Uhrzeit, wie in einem Kalender.
    days = []
    for weekday, label in Weekday.choices:
        entries = [{"lecture": l, "start": l.start} for l in lectures if l.weekday == weekday]
        entries += [{"free": b, "start": b.start} for b in blocks if b.weekday == weekday]
        entries.sort(key=lambda entry: entry["start"])
        days.append({
            "label": label,
            "entries": entries,
            "has_lectures": any("lecture" in entry for entry in entries),
        })
    return render(request, "timetable/timetable.html", {
        "days": days,
        "free_hours": free_hours(blocks),
        "form": form,
        "upload_form": upload_form,
    })


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
