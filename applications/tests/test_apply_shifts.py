from datetime import time
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from accounts.models import StudentProfile
from applications.models import Application
from applications.shifts import suggest_shifts
from companies.models import CompanyMember
from jobs.models import Company, JobPosting, Shift
from timetable.fit import shift_collides
from timetable.free_time import free_blocks, to_minutes
from timetable.models import LectureSlot, PlannedShift


def make_posting(schedule=JobPosting.Schedule.FLEXIBLE, hours=10, workplace=JobPosting.Workplace.REMOTE):
    company = Company.objects.create(name="Weihmann GbR", industry="Handel")
    return JobPosting.objects.create(
        company=company,
        title="Werkstudent*in Data",
        description="Du wertest Daten aus.",
        kind=JobPosting.Kind.WORKING_STUDENT,
        workplace=workplace,
        schedule=schedule,
        hourly_wage=Decimal("16.00"),
        hours_per_week=hours,
    )


class Lecture:
    """Ein Termin ohne Datenbank, wie ihn suggest_shifts erwartet."""

    def __init__(self, weekday, start, end):
        self.weekday, self.start, self.end = weekday, start, end


@pytest.fixture
def student(db):
    user = User.objects.create_user("mia@student.hpi.uni-potsdam.de", first_name="Mia")
    return StudentProfile.objects.create(user=user)


@pytest.fixture
def student_client(client, student):
    client.force_login(student.user)
    return client


def apply_url(posting):
    return f"/jobs/{posting.pk}/bewerben/"


def minutes(slot):
    return to_minutes(slot.end) - to_minutes(slot.start)


# --- suggest_shifts ---


@pytest.mark.django_db
def test_suggestion_reaches_hours_and_respects_limits():
    posting = make_posting(hours=10)
    lectures = [Lecture(0, time(10, 0), time(12, 0)), Lecture(2, time(8, 0), time(16, 0))]

    slots, missing = suggest_shifts(posting, lectures, [])

    assert missing == 0
    assert sum(minutes(s) for s in slots) == 10 * 60
    blocks = free_blocks(lectures)
    for slot in slots:
        assert minutes(slot) <= 4 * 60
        assert time(8, 0) <= slot.start < slot.end <= time(20, 0)
        assert slot.start.minute in (0, 30) and slot.end.minute in (0, 30)
        assert any(b.weekday == slot.weekday and b.start <= slot.start and slot.end <= b.end for b in blocks)
        assert not shift_collides(slot, lectures, 0)


@pytest.mark.django_db
def test_suggestion_keeps_commute_buffer_to_lectures():
    posting = make_posting(hours=8, workplace=JobPosting.Workplace.ONSITE)
    posting.company.commute_minutes = 30
    posting.company.save()
    buffer_minutes = posting.one_way_commute_minutes
    assert buffer_minutes > 0
    lectures = [Lecture(day, time(10, 0), time(12, 0)) for day in range(5)]

    slots, _ = suggest_shifts(posting, lectures, [])

    assert slots
    for slot in slots:
        assert not shift_collides(slot, lectures, buffer_minutes)


@pytest.mark.django_db
def test_suggestion_spreads_over_days_and_is_deterministic():
    posting = make_posting(hours=8)

    first, _ = suggest_shifts(posting, [], [])
    second, _ = suggest_shifts(posting, [], [])

    assert first == second
    assert len({slot.weekday for slot in first}) == 2  # 4 h + 4 h auf zwei Tage


@pytest.mark.django_db
def test_suggestion_with_too_little_room_returns_part_and_missing_minutes():
    posting = make_posting(hours=10)
    # Nur Montag 8-10 Uhr frei, sonst Vorlesungen den ganzen Tag.
    lectures = [Lecture(0, time(10, 0), time(20, 0))] + [Lecture(day, time(8, 0), time(20, 0)) for day in range(1, 5)]

    slots, missing = suggest_shifts(posting, lectures, [])

    assert [(s.weekday, s.start, s.end) for s in slots] == [(0, time(8, 0), time(10, 0))]
    assert missing == 8 * 60


@pytest.mark.django_db
def test_suggestion_counts_existing_shifts():
    posting = make_posting(hours=6)
    existing = [Lecture(0, time(8, 0), time(12, 0))]  # schon geplant: 4 h

    slots, missing = suggest_shifts(posting, [], existing)

    assert missing == 0
    assert sum(minutes(s) for s in slots) == 2 * 60
    assert all(not (s.weekday == 0 and s.start < time(12, 0)) for s in slots)


# --- Seite und Senden ---


def test_get_page_for_flexible_posting(student_client):
    posting = make_posting()

    content = student_client.get(apply_url(posting)).content.decode()

    assert "Vorschlag: Schichten in meine freien Blöcke legen" in content
    assert "Bewerbung senden" in content
    assert "Stundenplan" in content  # Hinweis ohne Vorlesungen
    assert not Application.objects.exists()


def test_get_page_without_profile_still_works(client, db):
    user = User.objects.create_user("neu@student.hpi.uni-potsdam.de")
    client.force_login(user)
    posting = make_posting()

    assert client.get(apply_url(posting)).status_code == 200
    assert not StudentProfile.objects.filter(user=user).exists()


def test_get_page_redirects_when_already_applied(student_client, student):
    posting = make_posting()
    Application.objects.create(profile=student, posting=posting)

    response = student_client.get(apply_url(posting))

    assert response.status_code == 302
    assert response.url == f"/jobs/{posting.pk}/"


def test_get_page_forbidden_for_company_and_login_for_anonymous(client, db):
    posting = make_posting()
    assert client.get(apply_url(posting)).url.startswith("/anmelden/")
    user = User.objects.create_user("jobs@weihmann.example")
    CompanyMember.objects.create(user=user, company=posting.company)
    client.force_login(user)

    assert client.get(apply_url(posting)).status_code == 403
    assert client.post(f"{apply_url(posting)}vorschlag/").status_code == 403


def test_suggest_button_creates_shifts_in_free_blocks(student_client, student):
    posting = make_posting(hours=6)
    LectureSlot.objects.create(profile=student, weekday=0, start=time(8, 0), end=time(14, 0), title="PT1")

    response = student_client.post(f"{apply_url(posting)}vorschlag/")

    assert response.status_code == 302
    assert response.url == apply_url(posting)
    shifts = list(PlannedShift.objects.filter(profile=student, posting=posting))
    assert sum(minutes(s) for s in shifts) == 6 * 60
    assert not Application.objects.exists()
    content = student_client.get(apply_url(posting)).content.decode()
    assert "6 von 6 h verplant" in content


def test_suggest_warns_when_room_is_short(student_client, student):
    posting = make_posting(hours=12)
    for day in range(5):
        LectureSlot.objects.create(profile=student, weekday=day, start=time(10, 0), end=time(20, 0), title="X")

    content = student_client.post(f"{apply_url(posting)}vorschlag/", follow=True).content.decode()

    assert "nicht genug Platz: 2 h bleiben offen" in content
    assert PlannedShift.objects.filter(profile=student).count() == 5  # Mo-Fr je 8-10 Uhr


def test_manual_add_and_delete(student_client, student):
    posting = make_posting(hours=10)

    student_client.post(f"{apply_url(posting)}schicht/", {"weekday": 1, "start": "09:00", "end": "11:00"})
    shift = PlannedShift.objects.get(profile=student)
    assert (shift.weekday, shift.start, shift.end) == (1, time(9, 0), time(11, 0))

    # Zu viele Stunden werden abgelehnt.
    student_client.post(f"{apply_url(posting)}schicht/", {"weekday": 2, "start": "08:00", "end": "20:00"})
    assert PlannedShift.objects.count() == 1

    response = student_client.post(f"{apply_url(posting)}schicht/{shift.pk}/entfernen/")
    assert response.status_code == 302
    assert not PlannedShift.objects.exists()


def test_cannot_delete_foreign_shift(student_client, db):
    posting = make_posting()
    other = StudentProfile.objects.create(user=User.objects.create_user("x@student.hpi.uni-potsdam.de"))
    shift = PlannedShift.objects.create(profile=other, posting=posting, weekday=0, start=time(9, 0), end=time(11, 0))

    response = student_client.post(f"{apply_url(posting)}schicht/{shift.pk}/entfernen/")

    assert response.status_code == 404
    assert PlannedShift.objects.count() == 1


def test_sending_flexible_keeps_planned_shifts_and_shows_message(student_client, student):
    posting = make_posting(hours=4)
    PlannedShift.objects.create(profile=student, posting=posting, weekday=0, start=time(9, 0), end=time(13, 0))

    response = student_client.post(apply_url(posting), follow=True)

    assert Application.objects.filter(profile=student, posting=posting).count() == 1
    assert PlannedShift.objects.filter(profile=student).count() == 1
    content = response.content.decode()
    assert "Bewerbung gesendet. Deine Schichten stehen in deinem" in content
    assert 'href="/stundenplan/"' in content


def fixed_posting():
    posting = make_posting(schedule=JobPosting.Schedule.FIXED, hours=6)
    Shift.objects.create(posting=posting, weekday=0, start=time(9, 0), end=time(12, 0))
    Shift.objects.create(posting=posting, weekday=2, start=time(14, 0), end=time(17, 0))
    return posting


def test_fixed_page_marks_colliding_shift(student_client, student):
    posting = fixed_posting()
    LectureSlot.objects.create(profile=student, weekday=0, start=time(10, 0), end=time(11, 0), title="PT1")

    content = student_client.get(apply_url(posting)).content.decode()

    assert content.count("kollidiert mit deiner Vorlesung") == 1
    assert "Mo 09:00–12:00" in content
    assert "Vorschlag:" not in content


def test_sending_fixed_copies_shifts_without_duplicates(student_client, student):
    posting = fixed_posting()

    student_client.post(apply_url(posting))
    student_client.post(apply_url(posting))

    assert Application.objects.count() == 1
    copied = PlannedShift.objects.filter(profile=student, posting=posting)
    assert [(s.weekday, s.start, s.end) for s in copied] == [(0, time(9, 0), time(12, 0)), (2, time(14, 0), time(17, 0))]


def test_suggest_not_available_for_fixed_posting(student_client):
    posting = fixed_posting()

    assert student_client.post(f"{apply_url(posting)}vorschlag/").status_code == 404
