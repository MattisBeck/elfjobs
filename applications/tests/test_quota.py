"""Freemium (#62): höchstens 3 Bewerbungen pro Kalenderwoche (Mo–So, Zeitzone Europe/Berlin)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from applications.models import Application
from applications.quota import WEEKLY_APPLICATION_LIMIT, applications_left, week_start
from applications.tests.test_applications import apply_url, make_posting, student, student_client  # noqa: F401 (Fixtures)

BERLIN = ZoneInfo("Europe/Berlin")
# Mittwoch, 25. November 2026, 12 Uhr
WEDNESDAY = datetime(2026, 11, 25, 12, 0, tzinfo=BERLIN)
NEXT_MONDAY = datetime(2026, 11, 30, 0, 5, tzinfo=BERLIN)


@pytest.fixture
def frozen_now(monkeypatch):
    """Setzt die Uhr fest; gilt auch für ``applied_at`` (auto_now_add)."""

    def freeze(moment):
        monkeypatch.setattr("django.utils.timezone.now", lambda: moment)

    freeze(WEDNESDAY)
    return freeze


@pytest.fixture
def postings(db):
    return [make_posting(title=f"Stelle {i}", company_name=f"Firma {i}") for i in range(5)]


def test_limit_is_three():
    assert WEEKLY_APPLICATION_LIMIT == 3


def test_week_starts_monday_midnight_in_berlin():
    monday = datetime(2026, 11, 23, 0, 0, tzinfo=BERLIN)

    assert week_start(WEDNESDAY) == monday
    assert week_start(monday) == monday
    # Sonntag kurz vor Mitternacht gehört noch zur alten Woche.
    assert week_start(datetime(2026, 11, 29, 23, 59, tzinfo=BERLIN)) == monday
    # Montag 0:30 in Berlin ist Sonntag 23:30 UTC, zählt aber schon zur neuen Woche.
    assert week_start(datetime(2026, 11, 29, 23, 30, tzinfo=ZoneInfo("UTC"))) == datetime(2026, 11, 30, 0, 0, tzinfo=BERLIN)


def test_third_application_ok_fourth_rejected(frozen_now, student_client, student, postings):
    for posting in postings[:3]:
        response = student_client.post(apply_url(posting))
        assert response.status_code == 302

    assert Application.objects.filter(profile=student).count() == 3
    assert applications_left(student) == 0

    response = student_client.post(apply_url(postings[3]))

    assert response.status_code == 302
    assert response.url == f"/jobs/{postings[3].pk}/"
    assert Application.objects.filter(profile=student).count() == 3
    assert not Application.objects.filter(posting=postings[3]).exists()


def test_next_week_three_free_again(frozen_now, student_client, student, postings):
    for posting in postings[:3]:
        student_client.post(apply_url(posting))
    assert applications_left(student) == 0

    frozen_now(NEXT_MONDAY)

    assert applications_left(student) == WEEKLY_APPLICATION_LIMIT
    student_client.post(apply_url(postings[3]))
    assert Application.objects.filter(posting=postings[3]).exists()


def test_old_applications_do_not_count(frozen_now, student, postings):
    Application.objects.create(profile=student, posting=postings[0])
    # Sonntag der Vorwoche, 23:59
    Application.objects.filter(posting=postings[0]).update(applied_at=datetime(2026, 11, 22, 23, 59, tzinfo=BERLIN))
    Application.objects.create(profile=student, posting=postings[1])

    assert applications_left(student) == 2


def test_detail_shows_remaining_count(frozen_now, student_client, postings):
    student_client.post(apply_url(postings[0]))

    content = student_client.get(f"/jobs/{postings[1].pk}/").content.decode()

    assert "Mit Profil bewerben" in content
    assert "Noch 2 von 3 Bewerbungen diese Woche" in content


def test_detail_disables_button_when_quota_used(frozen_now, student_client, postings):
    for posting in postings[:3]:
        student_client.post(apply_url(posting))

    content = student_client.get(f"/jobs/{postings[3].pk}/").content.decode()

    assert f'action="/jobs/{postings[3].pk}/bewerben/"' not in content
    assert "disabled" in content
    assert "Diese Woche schon 3 von 3 Bewerbungen gesendet" in content
    assert "Ab Montag wieder möglich" in content


def test_already_applied_posting_still_shows_sent(frozen_now, student_client, postings):
    for posting in postings[:3]:
        student_client.post(apply_url(posting))

    content = student_client.get(f"/jobs/{postings[0].pk}/").content.decode()

    assert "✓ Beworben am" in content
    assert "Ab Montag wieder möglich" not in content


def test_anonymous_sees_no_quota(client, postings):
    content = client.get(f"/jobs/{postings[0].pk}/").content.decode()

    assert "Mit Profil bewerben" in content
    assert "Bewerbungen diese Woche" not in content
