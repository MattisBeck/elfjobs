from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import StudentProfile
from jobs.models import Weekday

from .forms import LectureSlotForm
from .free_time import free_blocks, free_hours
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
