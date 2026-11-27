from datetime import time

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError

from accounts.models import StudentProfile
from jobs.management.commands.seed import DEMO_EMAIL, DEMO_LECTURES
from timetable.free_time import FreeBlock, free_blocks, free_hours
from timetable.models import LectureSlot


class Slot:
    """Termin ohne Datenbank, für die reinen Rechentests."""

    def __init__(self, weekday, start, end):
        self.weekday, self.start, self.end = weekday, start, end


def mia_slots():
    return [Slot(weekday, start, end) for weekday, start, end, _ in DEMO_LECTURES]


def test_free_blocks_for_mia_match_the_design_spec():
    blocks = free_blocks(mia_slots())

    assert [str(block) for block in blocks] == [
        "Mo 15:00–20:00",
        "Di 12:30–20:00",
        "Mi 12:30–20:00",
        "Do 08:00–13:30",
        "Do 17:00–20:00",
        "Fr 12:30–20:00",
    ]
    assert free_hours(blocks) == 36


def test_empty_day_is_free_from_8_to_20():
    assert free_blocks([])[0] == FreeBlock(0, time(8, 0), time(20, 0))
    assert free_hours(free_blocks([])) == 5 * 12


def test_gaps_shorter_than_two_hours_do_not_count():
    blocks = free_blocks([Slot(0, time(10, 0), time(12, 0)), Slot(0, time(13, 59), time(20, 0))])

    assert [str(b) for b in blocks if b.weekday == 0] == ["Mo 08:00–10:00"]


def test_overlapping_lectures_and_times_outside_the_day():
    blocks = free_blocks([
        Slot(2, time(7, 0), time(9, 0)),     # beginnt vor 8 Uhr
        Slot(2, time(12, 0), time(15, 0)),
        Slot(2, time(13, 0), time(14, 0)),   # liegt in der Vorlesung davor
        Slot(2, time(19, 0), time(22, 0)),   # endet nach 20 Uhr
    ])

    assert [str(b) for b in blocks if b.weekday == 2] == ["Mi 09:00–12:00", "Mi 15:00–19:00"]


@pytest.fixture
def mia(db):
    user = User.objects.create_user("mia@student.hpi.uni-potsdam.de", first_name="Mia")
    StudentProfile.objects.create(user=user, study_program="ITSE", semester=1)
    return user


def test_timetable_requires_login(client, db):
    response = client.get("/stundenplan/")

    assert response.status_code == 302
    assert response.url.startswith("/anmelden/")


def test_add_lecture_shows_it_with_free_blocks(client, mia):
    client.force_login(mia)

    response = client.post("/stundenplan/", {
        "title": "Mathematik I", "weekday": "0", "start": "09:15", "end": "12:30",
    })

    assert response.status_code == 302
    lecture = LectureSlot.objects.get()
    assert lecture.profile == mia.profile
    content = client.get("/stundenplan/").content.decode()
    assert "Mathematik I" in content
    assert "9:15–12:30" in content
    assert "frei 12:30–20:00" in content


def test_end_before_start_is_rejected(client, mia):
    client.force_login(mia)

    response = client.post("/stundenplan/", {
        "title": "Falsch", "weekday": "1", "start": "14:00", "end": "13:00",
    })

    assert response.status_code == 200
    assert "Das Ende muss nach dem Beginn liegen." in response.content.decode()
    assert not LectureSlot.objects.exists()


def test_edit_and_delete_own_lecture(client, mia):
    lecture = LectureSlot.objects.create(
        profile=mia.profile, weekday=0, start=time(9, 0), end=time(10, 0), title="PT1"
    )
    client.force_login(mia)

    client.post(f"/stundenplan/{lecture.pk}/", {
        "title": "Programmiertechnik I", "weekday": "0", "start": "09:00", "end": "11:00",
    })
    lecture.refresh_from_db()
    assert lecture.title == "Programmiertechnik I"
    assert lecture.end == time(11, 0)

    assert client.get(f"/stundenplan/{lecture.pk}/loeschen/").status_code == 405
    client.post(f"/stundenplan/{lecture.pk}/loeschen/")
    assert not LectureSlot.objects.exists()


def test_lectures_of_others_are_not_reachable(client, mia):
    other = User.objects.create_user("jan@student.hpi.uni-potsdam.de")
    other_profile = StudentProfile.objects.create(user=other)
    lecture = LectureSlot.objects.create(
        profile=other_profile, weekday=0, start=time(9, 0), end=time(10, 0), title="Fremd"
    )
    client.force_login(mia)

    assert client.get(f"/stundenplan/{lecture.pk}/").status_code == 404
    assert client.post(f"/stundenplan/{lecture.pk}/loeschen/").status_code == 404
    assert "Fremd" not in client.get("/stundenplan/").content.decode()
    assert LectureSlot.objects.filter(pk=lecture.pk).exists()


def test_lecture_must_end_after_start(mia):
    with pytest.raises(IntegrityError):
        LectureSlot.objects.create(profile=mia.profile, weekday=0, start=time(12, 0), end=time(11, 0), title="X")


@pytest.mark.django_db
def test_seed_gives_mia_her_timetable_and_stays_the_same():
    call_command("seed")
    call_command("seed")

    profile = StudentProfile.objects.get(user__username=DEMO_EMAIL)
    assert profile.lectures.count() == len(DEMO_LECTURES)
    assert free_hours(free_blocks(profile.lectures.all())) == 36


def test_day_lists_lectures_and_free_blocks_by_time(client, mia):
    LectureSlot.objects.create(profile=mia.profile, weekday=3, start=time(13, 30), end=time(17, 0), title="Übung")
    client.force_login(mia)

    content = client.get("/stundenplan/").content.decode()
    thursday = content[content.index('aria-label="Do"'):content.index('aria-label="Fr"')]

    assert thursday.index("frei 8:00–13:30") < thursday.index("Übung") < thursday.index("frei 17:00–20:00")
