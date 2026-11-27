"""Konflikte eigener Schichten (#140): mit Vorlesungen (inkl. Fahrzeit-Puffer) und mit anderen Schichten."""

from datetime import time
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from accounts.models import StudentProfile
from companies.models import CompanyMember
from jobs.models import Company, JobPosting
from timetable.conflicts import shift_conflicts
from timetable.models import LectureSlot, PlannedShift


pytestmark = pytest.mark.django_db


def make_posting(title="Aushilfe Lager", company_name="Holsten Förster", commute=20, workplace="onsite"):
    company = Company.objects.create(name=company_name, industry="Logistik", commute_minutes=commute)
    return JobPosting.objects.create(
        company=company, title=title, kind="short_job", workplace=workplace,
        schedule="flexible", hours_per_week=11, hourly_wage=Decimal("14.00"),
    )


@pytest.fixture
def profile(db):
    """Montag 9:15–12:30 Mathematik I."""
    profile = StudentProfile.objects.create(user=User.objects.create_user("mia", password="pw-12345678"))
    LectureSlot.objects.create(profile=profile, weekday=0, start=time(9, 15), end=time(12, 30), title="Mathematik I")
    return profile


def plan(profile, posting, weekday, start, end):
    return PlannedShift.objects.create(profile=profile, posting=posting, weekday=weekday, start=start, end=end)


def conflicts(profile):
    shifts = list(profile.planned_shifts.select_related("posting__company"))
    return shift_conflicts(shifts, list(profile.lectures.all()))


def test_shift_overlapping_lecture_collides(profile):
    shift = plan(profile, make_posting(), 0, time(12), time(15))

    assert conflicts(profile) == {shift.pk: ["kollidiert mit Mathematik I"]}


def test_commute_buffer_extends_the_lecture(profile):
    # Vorlesung endet 12:30, Fahrzeit 20 Minuten: Wer um 12:40 anfängt, kommt nicht rechtzeitig.
    shift = plan(profile, make_posting(commute=20), 0, time(12, 40), time(15))

    assert conflicts(profile) == {shift.pk: ["kollidiert mit Mathematik I"]}


def test_shift_starting_exactly_when_buffer_ends_is_free(profile):
    plan(profile, make_posting(commute=20), 0, time(12, 50), time(15))

    assert conflicts(profile) == {}


def test_shift_ending_exactly_when_buffer_starts_is_free(profile):
    # Vorlesung beginnt 9:15, minus 20 Minuten Fahrzeit = 8:55.
    plan(profile, make_posting(commute=20), 0, time(8), time(8, 55))

    assert conflicts(profile) == {}


def test_remote_posting_has_no_buffer(profile):
    plan(profile, make_posting(commute=45, workplace="remote"), 0, time(12, 31), time(15))

    assert conflicts(profile) == {}


def test_other_day_is_no_conflict(profile):
    plan(profile, make_posting(), 1, time(9), time(12))

    assert conflicts(profile) == {}


def test_two_overlapping_shifts_flag_each_other(profile):
    first = plan(profile, make_posting("Promoter*in", "Weihmann GbR"), 2, time(14), time(17))
    second = plan(profile, make_posting("Aushilfe Lager", "Holsten Förster"), 2, time(16), time(19))

    assert conflicts(profile) == {
        first.pk: ["überschneidet sich mit Aushilfe Lager (Holsten Förster)"],
        second.pk: ["überschneidet sich mit Promoter*in (Weihmann GbR)"],
    }


def test_back_to_back_shifts_are_no_conflict(profile):
    # Zwischen zwei eigenen Schichten gibt es keinen Puffer.
    posting = make_posting()
    plan(profile, posting, 2, time(14), time(16))
    plan(profile, posting, 2, time(16), time(18))

    assert conflicts(profile) == {}


def test_shift_can_collide_with_lecture_and_shift(profile):
    first = plan(profile, make_posting(), 0, time(11), time(14))
    second = plan(profile, make_posting("Promoter*in", "Weihmann GbR"), 0, time(13), time(15))

    result = conflicts(profile)
    assert result[first.pk] == [
        "kollidiert mit Mathematik I",
        "überschneidet sich mit Promoter*in (Weihmann GbR)",
    ]
    assert "überschneidet sich mit Aushilfe Lager (Holsten Förster)" in result[second.pk]


# Seite /stundenplan/


@pytest.fixture
def mia_client(client, profile):
    client.force_login(profile.user)
    return client


def test_page_shows_shift_and_conflict_summary(mia_client, profile):
    posting = make_posting("Promoter*in", "Weihmann GbR")
    plan(profile, posting, 0, time(12), time(15))

    html = mia_client.get("/stundenplan/").content.decode()

    assert "1 Schicht im Konflikt" in html
    assert "kollidiert mit Mathematik I" in html
    assert "Promoter*in" in html and "Weihmann GbR" in html
    assert f"/jobs/{posting.pk}/?ansicht=woche" in html


def test_page_counts_several_conflicts(mia_client, profile):
    posting = make_posting()
    plan(profile, posting, 0, time(12), time(15))
    plan(profile, posting, 0, time(9), time(10))

    assert "2 Schichten im Konflikt" in mia_client.get("/stundenplan/").content.decode()


def test_page_without_conflict_has_no_hint(mia_client, profile):
    plan(profile, make_posting(), 2, time(14), time(17))

    html = mia_client.get("/stundenplan/").content.decode()

    assert "Aushilfe Lager" in html  # die Schicht steht trotzdem da
    assert "im Konflikt" not in html
    assert "kollidiert mit" not in html
    assert "shift-row-conflict" not in html


def test_page_without_shifts_has_no_hint(mia_client):
    assert "im Konflikt" not in mia_client.get("/stundenplan/").content.decode()


def test_shifts_are_in_json_for_the_grid(mia_client, profile):
    posting = make_posting("Promoter*in", "Weihmann GbR")
    shift = plan(profile, posting, 0, time(12), time(15))

    response = mia_client.get("/stundenplan/")

    assert response.context["calendar"]["shifts"] == [{
        "id": shift.pk, "title": "Promoter*in", "company": "Weihmann GbR", "weekday": 0,
        "start": "12:00", "end": "15:00", "url": f"/jobs/{posting.pk}/?ansicht=woche",
        "conflict": "kollidiert mit Mathematik I",
    }]
    assert 'id="timetable-data"' in response.content.decode()


def test_other_students_shifts_are_not_shown(mia_client):
    other = StudentProfile.objects.create(user=User.objects.create_user("tom", password="pw-12345678"))
    plan(other, make_posting("Geheime Stelle"), 0, time(12), time(15))

    response = mia_client.get("/stundenplan/")

    assert response.context["calendar"]["shifts"] == []
    assert "Geheime Stelle" not in response.content.decode()


# Reiter „Stundenplan“ in der Kopfzeile


def nav(response):
    html = response.content.decode()
    return html[html.index('<nav class="main-nav"'):html.index("</nav>")]


def test_nav_tab_is_visible_for_students_and_active_on_timetable(mia_client):
    html = nav(mia_client.get("/stundenplan/"))

    assert 'href="/stundenplan/" aria-current="page">Stundenplan' in html
    assert html.index("Gemerkt") < html.index("Stundenplan") < html.index("Messen")


def test_nav_tab_is_not_active_on_other_pages(mia_client):
    html = nav(mia_client.get("/jobs/"))

    assert "Stundenplan" in html
    assert 'aria-current="page">Stundenplan' not in html


def test_nav_tab_is_hidden_for_anonymous(client, db):
    assert "Stundenplan" not in nav(client.get("/jobs/"))


def test_nav_tab_is_hidden_for_companies(client, db):
    company = Company.objects.create(name="Weihmann GbR", industry="Marketing", commute_minutes=10)
    user = User.objects.create_user("firma", password="pw-12345678")
    CompanyMember.objects.create(user=user, company=company)
    client.force_login(user)

    assert "Stundenplan" not in nav(client.get("/jobs/"))


def test_free_blocks_leave_out_own_shifts(profile):
    """Freie Blöcke und freie Stunden im Stundenplan zählen eigene Schichten als belegt."""
    from timetable.views import calendar_state

    before = calendar_state(profile.lectures.all(), [])
    plan(profile, make_posting(), 1, time(15), time(18))
    after = calendar_state(profile.lectures.all(), profile.planned_shifts.all())
    tuesday = [block for block in after["free"] if block["weekday"] == 1]
    assert all(block["end"] <= "15:00" or block["start"] >= "18:00" for block in tuesday)
    assert after["free_hours"] < before["free_hours"]
