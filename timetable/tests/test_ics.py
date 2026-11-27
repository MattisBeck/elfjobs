"""Stundenplan als ICS-Datei hochladen (#43)."""

from datetime import time
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import StudentProfile
from timetable.ics import IcsError, parse_ics
from timetable.models import LectureSlot

FIXTURE = Path(__file__).parent / "fixtures" / "stundenplan.ics"


def test_weekly_events_become_slots_and_others_are_skipped():
    slots, skipped = parse_ics(FIXTURE.read_bytes())

    assert slots == [
        {"weekday": 0, "start": time(9, 15), "end": time(10, 45), "title": "Programmiertechnik I"},
        {"weekday": 1, "start": time(11, 0), "end": time(12, 30), "title": "Mathematik I"},
        # 12:00 UTC im Oktober (Sommerzeit) = 14:00 in Potsdam
        {"weekday": 2, "start": time(14, 0), "end": time(15, 30), "title": "Übung Datenbanken"},
        {"weekday": 3, "start": time(11, 0), "end": time(12, 30), "title": "Mathematik I"},
    ]
    # Samstag, Einzeltermin (Klausur), ganztägig (Feiertag)
    assert skipped == 3


def test_broken_file_gives_understandable_error():
    with pytest.raises(IcsError, match="keine Kalenderdatei"):
        parse_ics(b"Das ist kein Kalender")


def test_calendar_without_weekly_events_says_so():
    ics = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
    assert parse_ics(ics) == ([], 0)


@pytest.fixture
def profile(client, db):
    user = User.objects.create_user("mia", password="pw-12345678")
    profile = StudentProfile.objects.create(user=user)
    client.force_login(user)
    return profile


def upload(client, content=None):
    data = FIXTURE.read_bytes() if content is None else content
    return client.post("/stundenplan/import/", {"datei": SimpleUploadedFile("plan.ics", data, "text/calendar")})


def test_upload_shows_preview_without_saving(client, profile):
    response = upload(client)

    assert response.status_code == 302
    preview = client.get(response.url).content.decode()
    assert "4 Termine gefunden, 3 übersprungen" in preview
    assert "Programmiertechnik I" in preview
    assert not LectureSlot.objects.exists()


def test_confirm_adds_slots_and_keeps_existing(client, profile):
    LectureSlot.objects.create(profile=profile, weekday=4, start=time(8), end=time(9), title="Alt")
    upload(client)

    response = client.post("/stundenplan/import/vorschau/", follow=True)

    assert profile.lectures.count() == 5
    assert "4 Termine übernommen, 3 übersprungen" in response.content.decode()


def test_confirm_can_replace_existing(client, profile):
    LectureSlot.objects.create(profile=profile, weekday=4, start=time(8), end=time(9), title="Alt")
    upload(client)

    client.post("/stundenplan/import/vorschau/", {"ersetzen": "1"})

    assert sorted(profile.lectures.values_list("title", flat=True)) == [
        "Mathematik I", "Mathematik I", "Programmiertechnik I", "Übung Datenbanken",
    ]


def test_broken_upload_shows_error_on_timetable(client, profile):
    response = upload(client, b"kaputt")

    assert response.status_code == 200
    assert "keine Kalenderdatei" in response.content.decode()


def test_preview_without_upload_goes_back(client, profile):
    response = client.get("/stundenplan/import/vorschau/")

    assert response.status_code == 302
    assert response.url == "/stundenplan/"


def test_timetable_page_has_upload_form(client, profile):
    content = client.get("/stundenplan/").content.decode()

    assert 'action="/stundenplan/import/"' in content
    assert 'enctype="multipart/form-data"' in content
