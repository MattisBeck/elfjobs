"""Tab „In meiner Woche“ (#10): Kalender Mo–Fr, 8–20 Uhr, Vorlesungen und Schichten."""

from datetime import time
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from accounts.models import StudentProfile
from jobs.models import Company, JobPosting, Shift
from timetable.fit import shift_collides
from timetable.models import LectureSlot
from timetable.week import week_view


@pytest.fixture
def posting(db):
    company = Company.objects.create(name="Weihmann GbR", industry="Tech", commute_minutes=0)
    posting = JobPosting.objects.create(
        company=company, title="Promoter*in", kind="short_job", workplace="onsite",
        schedule="fixed", hours_per_week=7, hourly_wage=Decimal("16.00"),
    )
    Shift.objects.create(posting=posting, weekday=1, start=time(15, 0), end=time(18, 30))
    Shift.objects.create(posting=posting, weekday=2, start=time(16, 30), end=time(20, 0))
    return posting


def lecture(weekday, start, end, title="PT1"):
    return LectureSlot(weekday=weekday, start=start, end=end, title=title)


def blocks(week, weekday):
    return week["days"][weekday]["blocks"]


def test_week_has_five_days_and_axis_every_two_hours(posting):
    week = week_view(posting, [])

    assert [day["label"] for day in week["days"]] == ["Mo", "Di", "Mi", "Do", "Fr"]
    assert [mark["label"] for mark in week["hours"]] == ["8", "10", "12", "14", "16", "18", "20"]
    assert week["hours"][0]["top"] == "0.0000"
    assert week["hours"][-1]["top"] == "100.0000"


def test_shift_position_in_percent_of_eight_to_twenty(posting):
    tuesday = blocks(week_view(posting, []), 1)

    assert tuesday == [{
        "kind": "shift", "label": "Schicht", "time": "15:00–18:30",
        # 15 Uhr = 7 von 12 Stunden, 3,5 Stunden lang
        "top": "58.3333", "height": "29.1667",
        "left": "0.0000", "width": "100.0000",
    }]


def test_lectures_grey_and_colliding_shift_red(posting):
    week = week_view(posting, [lecture(2, time(16, 0), time(17, 30), "Mathematik I")])

    wednesday = blocks(week, 2)
    assert [(b["kind"], b["label"]) for b in wednesday] == [("lecture", "Mathematik I"), ("conflict", "Konflikt")]
    assert blocks(week, 1)[0]["kind"] == "shift"


def test_colliding_shift_stands_next_to_the_lecture_which_stays_visible(posting):
    """#135: Die Schicht liegt nicht mehr über der Vorlesung, beide teilen sich die Breite."""
    week = week_view(posting, [lecture(2, time(16, 0), time(17, 30), "Mathematik I")])

    math, conflict = blocks(week, 2)
    assert (math["kind"], math["left"], math["width"]) == ("lecture", "0.0000", "50.0000")
    assert (conflict["kind"], conflict["left"], conflict["width"]) == ("conflict", "50.0000", "50.0000")
    assert math["conflict"] is True


def test_lecture_without_collision_keeps_full_width_and_no_mark(posting):
    week = week_view(posting, [lecture(0, time(9, 15), time(12, 30))])

    (monday,) = blocks(week, 0)
    assert (monday["left"], monday["width"], monday["conflict"]) == ("0.0000", "100.0000", False)


def test_conflict_only_through_commute_buffer_marks_lecture_but_keeps_full_width(posting):
    posting.company.commute_minutes = 30
    posting.company.save()
    # Vorlesung endet 16:15, Schicht Mi beginnt 16:30: kein Überlappen, aber der Weg fehlt.
    week = week_view(posting, [lecture(2, time(14, 45), time(16, 15))])

    math, conflict = blocks(week, 2)
    assert conflict["kind"] == "conflict"
    assert math["conflict"] is True
    assert math["width"] == conflict["width"] == "100.0000"


def test_detail_page_places_overlapping_blocks_side_by_side(client, posting):
    user = User.objects.create_user("lea@student.hpi.uni-potsdam.de")
    profile = StudentProfile.objects.create(user=user, semester=1)
    LectureSlot.objects.create(profile=profile, weekday=2, start=time(16, 0), end=time(17, 30), title="Mathematik I")
    client.force_login(user)

    html = client.get(f"/jobs/{posting.pk}/?ansicht=woche").content.decode()

    assert "week-lecture week-lecture-conflict" in html
    assert "--left: 0.0000%; --width: 50.0000%" in html
    assert "--left: 50.0000%; --width: 50.0000%" in html
    assert "Kollidiert mit einer Schicht" in html


def test_blocks_outside_eight_to_twenty_are_clipped():
    week_lecture = lecture(0, time(7, 0), time(9, 0))
    company = Company(name="X", industry="Y")
    posting = JobPosting(company=company, schedule="flexible", workplace="onsite")

    monday = week_view(posting, [week_lecture], shifts=[])["days"][0]["blocks"]

    assert monday[0]["top"] == "0.0000"
    assert monday[0]["height"] == "8.3333"
    assert monday[0]["time"] == "7:00–9:00"


@pytest.mark.django_db
def test_detail_tab_shows_week_for_mia_like_the_canvas(client):
    """docs/design.md: Promoter*in bei Weihmann GbR, Di 15:00–18:30 und Mi 16:30–20:00, für Mia."""
    call_command("seed")
    mia = User.objects.get(username="mia@student.hpi.uni-potsdam.de")
    # Ohne Wohnort, damit die Fahrzeit die Annahme der Firma aus docs/design.md ist.
    StudentProfile.objects.filter(user=mia).update(home_latitude=None, home_longitude=None)
    posting = JobPosting.objects.get(title="Promoter*in", company__name="Weihmann GbR", hours_per_week=7)
    client.force_login(mia)

    response = client.get(f"/jobs/{posting.pk}/?ansicht=woche")

    week = response.context["week"]
    shifts = [(day["label"], b["kind"], b["time"]) for day in week["days"] for b in day["blocks"] if b["kind"] != "lecture"]
    lectures = list(mia.profile.lectures.all())
    buffer = posting.company.commute_minutes
    expected_kinds = {
        shift.weekday: "conflict" if shift_collides(shift, lectures, buffer) else "shift"
        for shift in posting.shifts.all()
    }
    assert [(label, kind) for label, kind, _ in shifts] == [
        ("Di", expected_kinds[1]), ("Mi", expected_kinds[2])
    ]
    assert [t for _, _, t in shifts] == ["15:00–18:30", "16:30–20:00"]
    content = response.content.decode()
    assert 'class="week-block week-lecture"' in content
    assert "Die Wochenansicht ist noch in Arbeit" not in content
    assert f'fit-{response.context["posting"].fit.status}' in content


@pytest.mark.django_db
def test_week_without_login_shows_shifts_and_hint(client, posting):
    content = client.get(f"/jobs/{posting.pk}/?ansicht=woche").content.decode()

    assert 'class="week-block week-shift"' in content
    assert "week-lecture" not in content
    assert "Melde dich an" in content
