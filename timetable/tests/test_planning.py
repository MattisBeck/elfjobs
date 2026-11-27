"""Eigene Schichten bei flexiblen Stellen (#11): in freie Blöcke legen, Stunden zählen, wieder löschen."""

from datetime import time
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from accounts.models import StudentProfile
from jobs.models import Company, JobPosting
from timetable.models import LectureSlot, PlannedShift
from timetable.free_time import free_blocks
from timetable.planning import planned_hours
from timetable.week import week_view


@pytest.fixture
def posting(db):
    company = Company.objects.create(name="Holsten Förster", industry="Logistik", commute_minutes=20)
    return JobPosting.objects.create(
        company=company, title="Aushilfe Lager", kind="short_job", workplace="onsite",
        schedule="flexible", hours_per_week=11, hourly_wage=Decimal("14.00"),
    )


@pytest.fixture
def profile(db):
    """Montag 9:15–12:30 und 13:30–15:00 Vorlesung, frei ist Mo 15–20 Uhr und Di–Fr ganztags."""
    profile = StudentProfile.objects.create(user=User.objects.create_user("mia", password="pw-12345678"))
    LectureSlot.objects.create(profile=profile, weekday=0, start=time(9, 15), end=time(12, 30), title="Mathematik I")
    LectureSlot.objects.create(profile=profile, weekday=0, start=time(13, 30), end=time(15), title="PT1")
    return profile


def plan(profile, posting, weekday, start, end):
    return PlannedShift.objects.create(profile=profile, posting=posting, weekday=weekday, start=start, end=end)


def add(client, posting, weekday, start, end):
    return client.post(
        f"/jobs/{posting.pk}/schichten/", {"weekday": weekday, "start": start, "end": end}, follow=True
    )


# Anlegen


@pytest.mark.django_db
def test_shift_inside_free_block_is_saved(client, posting, profile):
    client.force_login(profile.user)

    response = add(client, posting, 0, "15:00", "18:00")

    shift = PlannedShift.objects.get()
    assert (shift.profile, shift.posting, shift.weekday, shift.start, shift.end) == (
        profile, posting, 0, time(15), time(18)
    )
    assert response.redirect_chain[-1][0] == f"/jobs/{posting.pk}/?ansicht=woche"
    assert "Schicht eingeplant: Mo 15:00–18:00" in response.content.decode()


@pytest.mark.django_db
def test_shift_outside_free_block_is_rejected(client, posting, profile):
    client.force_login(profile.user)

    response = add(client, posting, 0, "12:00", "14:00")

    assert not PlannedShift.objects.exists()
    assert "in einem freien Block liegen" in response.content.decode()


@pytest.mark.django_db
def test_shift_overlapping_own_shift_is_rejected(client, posting, profile):
    plan(profile, posting, 0, time(15), time(18))
    client.force_login(profile.user)

    add(client, posting, 0, "17:00", "19:00")

    assert PlannedShift.objects.count() == 1


@pytest.mark.django_db
def test_end_before_start_is_rejected(client, posting, profile):
    client.force_login(profile.user)

    response = add(client, posting, 1, "12:00", "10:00")

    assert not PlannedShift.objects.exists()
    assert "Ende muss nach dem Beginn" in response.content.decode()


@pytest.mark.django_db
def test_more_hours_than_the_posting_has_are_rejected(client, posting, profile):
    plan(profile, posting, 1, time(8), time(16))  # 8 von 11 h
    client.force_login(profile.user)

    response = add(client, posting, 2, "8:00", "12:00")

    assert PlannedShift.objects.count() == 1
    assert "mehr als 11 h verplant" in response.content.decode()


@pytest.mark.django_db
def test_fixed_postings_have_no_own_shifts(client, posting, profile):
    posting.schedule = "fixed"
    posting.save()
    client.force_login(profile.user)

    assert add(client, posting, 0, "15:00", "18:00").status_code == 404


@pytest.mark.django_db
def test_planning_needs_login(client, posting):
    response = client.post(f"/jobs/{posting.pk}/schichten/", {"weekday": 0, "start": "15:00", "end": "18:00"})

    assert response.status_code == 302
    assert response.url.startswith("/anmelden/")


# Löschen


@pytest.mark.django_db
def test_own_shift_can_be_deleted(client, posting, profile):
    shift = plan(profile, posting, 0, time(15), time(18))
    client.force_login(profile.user)

    response = client.post(f"/jobs/{posting.pk}/schichten/{shift.pk}/loeschen/")

    assert response.status_code == 302
    assert not PlannedShift.objects.exists()


@pytest.mark.django_db
def test_shifts_of_others_cannot_be_deleted(client, posting, profile):
    shift = plan(profile, posting, 0, time(15), time(18))
    client.force_login(User.objects.create_user("jonas", password="pw-12345678"))

    response = client.post(f"/jobs/{posting.pk}/schichten/{shift.pk}/loeschen/")

    assert response.status_code == 404
    assert PlannedShift.objects.exists()


# Stunden und Wochenansicht


@pytest.mark.django_db
def test_planned_hours_add_up(posting, profile):
    shifts = [plan(profile, posting, 0, time(15), time(18)), plan(profile, posting, 1, time(9, 30), time(10))]

    assert planned_hours(shifts) == 3.5


@pytest.mark.django_db
def test_week_shows_open_free_blocks_and_own_shifts(posting, profile):
    own = plan(profile, posting, 0, time(15), time(18))

    week = week_view(posting, list(profile.lectures.all()), planned=[own])

    monday = {(block["kind"], block["time"]) for block in week["days"][0]["blocks"]}
    assert ("own", "15:00–18:00") in monday
    assert ("free", "18:00–20:00") in monday
    assert ("free", "15:00–20:00") not in monday
    assert ("free", "8:00–20:00") in {(block["kind"], block["time"]) for block in week["days"][1]["blocks"]}


@pytest.mark.django_db
def test_week_without_planning_shows_no_free_blocks(posting, profile):
    week = week_view(posting, list(profile.lectures.all()))

    assert all(block["kind"] != "free" for day in week["days"] for block in day["blocks"])


@pytest.mark.django_db
def test_detail_page_shows_planned_hours_and_free_block_links(client, posting, profile):
    plan(profile, posting, 0, time(15), time(18))
    client.force_login(profile.user)

    page = client.get(f"/jobs/{posting.pk}/?ansicht=woche").content.decode()

    assert "3 von 11 h verplant" in page
    assert "frei=0-1800" in page
    assert "Deine Schicht" in page


@pytest.mark.django_db
def test_choosing_a_free_block_prefills_up_to_four_hours(client, posting, profile):
    client.force_login(profile.user)

    form = client.get(f"/jobs/{posting.pk}/?ansicht=woche&frei=1-0800").context["planning"]["form"]

    assert form.initial == {"weekday": 1, "start": time(8), "end": time(12)}


@pytest.mark.django_db
def test_prefill_stops_at_the_open_hours(client, posting, profile):
    plan(profile, posting, 2, time(8), time(17))  # 9 von 11 h, offen sind 2 h
    client.force_login(profile.user)

    form = client.get(f"/jobs/{posting.pk}/?ansicht=woche&frei=1-0800").context["planning"]["form"]

    assert form.initial["end"] == time(10)


@pytest.mark.django_db
def test_unknown_free_block_shows_no_form(client, posting, profile):
    client.force_login(profile.user)

    response = client.get(f"/jobs/{posting.pk}/?ansicht=woche&frei=0-1200")

    assert response.context["planning"]["form"] is None


@pytest.mark.django_db
def test_seed_gives_mia_two_own_shifts_one_fits_and_one_collides():
    from django.core.management import call_command

    from jobs.management.commands.seed import DEMO_EMAIL
    from timetable.conflicts import shift_conflicts

    call_command("seed")
    call_command("seed")

    mia = StudentProfile.objects.get(user__username=DEMO_EMAIL)
    fits, collides = mia.planned_shifts.order_by("-weekday")  # Di 15–18, Mo 13–16
    assert fits.posting.schedule == "flexible"
    lectures = list(mia.lectures.all())
    assert any(
        block.weekday == fits.weekday and block.start <= fits.start and fits.end <= block.end
        for block in free_blocks(lectures)
    )
    # Die zweite Schicht zeigt in der Demo den Konflikt (#140).
    shifts = list(mia.planned_shifts.select_related("posting__company"))
    conflicts = shift_conflicts(shifts, lectures)
    assert list(conflicts) == [collides.pk]
    assert "kollidiert mit Programmiertechnik I" in conflicts[collides.pk]
