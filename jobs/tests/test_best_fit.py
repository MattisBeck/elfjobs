"""Sortierung „Passt am besten“ (#42): Stundenplan, dann Lehrplan, dann effektiver Lohn."""

from datetime import time
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from accounts.models import StudentProfile
from jobs.models import Company, JobPosting, Shift, Tag
from studies.models import Course, StudyProgram
from timetable.models import LectureSlot

MONDAY, TUESDAY = 0, 1


def make_posting(title, wage, tags=(), shifts=()):
    # Remote: keine Fahrzeit, also effektiver Lohn = Bruttolohn und kein Puffer um Vorlesungen.
    company, _ = Company.objects.get_or_create(name="Testfirma", industry="Tech")
    posting = JobPosting.objects.create(
        company=company, title=title, kind=JobPosting.Kind.SHORT_JOB,
        workplace=JobPosting.Workplace.REMOTE,
        schedule=JobPosting.Schedule.FIXED if shifts else JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal(wage), hours_per_week=5,
    )
    posting.tags.add(*tags)
    for weekday, start, end in shifts:
        Shift.objects.create(posting=posting, weekday=weekday, start=start, end=end)
    return posting


@pytest.fixture
def student(db):
    """Lena: ITSE 1. Semester, kann Git (PT1), SQL kommt erst; Vorlesung Montag 10-12."""
    program = StudyProgram.objects.create(
        name="IT-Systems Engineering", abbreviation="ITSE", university="HPI", standard_semesters=6
    )
    pt1 = Course.objects.create(program=program, name="Programmiertechnik I", short_name="PT1", semester=1)
    git = Tag.objects.create(name="Git")
    pt1.skills.add(git)
    sql = Tag.objects.create(name="SQL")
    user = User.objects.create_user("lena")
    profile = StudentProfile.objects.create(user=user, study_program=program, semester=1)
    profile.courses.add(pt1)
    LectureSlot.objects.create(profile=profile, weekday=MONDAY, start=time(10), end=time(12), title="PT1")

    collides = [(MONDAY, time(10), time(11))]
    fits = [(TUESDAY, time(10), time(11))]
    make_posting("Kollidiert", "30.00", [git], collides)
    make_posting("Teilweise", "25.00", [git], collides + fits)
    make_posting("Halb gelernt", "20.00", [git, sql], fits)
    make_posting("Gelernt", "15.00", [git], fits)
    make_posting("Flexibel ohne Anforderungen", "16.00")
    return user


def titles(response):
    return [posting.title for posting in response.context["postings"]]


def test_best_fit_is_default_for_students(client, student):
    client.force_login(student)

    response = client.get("/jobs/?plan=aus")

    # 1. Stundenplan (passt/flexibel vor teilweise vor kollidiert),
    # 2. Anteil gelernter Anforderungen, 3. effektiver Lohn.
    assert titles(response) == [
        "Flexibel ohne Anforderungen", "Gelernt", "Halb gelernt", "Teilweise", "Kollidiert",
    ]
    assert "sortiert nach" in response.content.decode()


def test_wage_sorting_still_selectable(client, student):
    client.force_login(student)

    response = client.get("/jobs/?plan=aus&reihenfolge=lohn")

    assert titles(response) == [
        "Kollidiert", "Teilweise", "Halb gelernt", "Flexibel ohne Anforderungen", "Gelernt",
    ]


def test_sort_links_keep_filters(client, student):
    client.force_login(student)

    response = client.get("/jobs/?plan=aus&filter=kurzjob")

    links = {link["label"]: (link["url"], link["active"]) for link in response.context["filter_form"]["sort_links"]}
    assert links == {
        "Passt am besten": ("/jobs/?filter=kurzjob&plan=aus", True),
        "Effektiver Lohn": ("/jobs/?filter=kurzjob&plan=aus&reihenfolge=lohn", False),
        "Bewertung": ("/jobs/?filter=kurzjob&plan=aus&reihenfolge=bewertung", False),
    }
    # Gewählter Lohn bleibt in den Links zu den Stellen erhalten.
    content = client.get("/jobs/?reihenfolge=lohn").content.decode()
    assert "reihenfolge=lohn" in content.split('class="job-rows"')[1]


def test_tie_is_broken_by_title(client, student):
    client.force_login(student)
    make_posting("B gleich", "16.00")
    make_posting("A gleich", "16.00")

    response = client.get("/jobs/?plan=aus")

    assert titles(response)[:3] == ["A gleich", "B gleich", "Flexibel ohne Anforderungen"]


def test_logged_out_sorts_by_wage_without_best_fit(client, student):
    response = client.get("/jobs/?reihenfolge=passt")

    assert titles(response) == [
        "Kollidiert", "Teilweise", "Halb gelernt", "Flexibel ohne Anforderungen", "Gelernt",
    ]
    # Ohne Lehrplan kein „Passt am besten“, aber Lohn und Bewertung (#32).
    labels = [link["label"] for link in response.context["filter_form"]["sort_links"]]
    assert labels == ["Effektiver Lohn", "Bewertung"]
