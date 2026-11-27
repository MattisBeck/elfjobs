"""JSON-Endpunkt für den Stundenplan im Kalender (#87): anlegen, verschieben, Länge ändern, löschen."""

import json
from datetime import time

import pytest
from django.contrib.auth.models import User

from accounts.models import StudentProfile
from jobs.models import Company, JobPosting, Shift
from timetable.models import LectureSlot


@pytest.fixture
def mia(db):
    user = User.objects.create_user("mia@student.hpi.uni-potsdam.de", first_name="Mia")
    StudentProfile.objects.create(user=user, semester=1)
    return user


@pytest.fixture
def lecture(mia):
    return LectureSlot.objects.create(
        profile=mia.profile, weekday=0, start=time(9, 15), end=time(12, 30), title="Mathematik I"
    )


def data(**overrides):
    values = {"title": "Programmiertechnik I", "weekday": "0", "start": "13:30", "end": "15:00"}
    values.update(overrides)
    return values


def test_create_returns_lecture_and_free_blocks(client, mia):
    client.force_login(mia)

    response = client.post("/stundenplan/termine/", data())

    assert response.status_code == 201
    body = response.json()
    assert body["lecture"] == {
        "id": LectureSlot.objects.get().pk,
        "title": "Programmiertechnik I",
        "weekday": 0,
        "start": "13:30",
        "end": "15:00",
    }
    assert LectureSlot.objects.get().profile == mia.profile
    # Montag ist jetzt 8–13:30 und 15–20 Uhr frei, die übrigen Tage ganz.
    monday = [block for block in body["free"] if block["weekday"] == 0]
    assert monday == [
        {"weekday": 0, "start": "08:00", "end": "13:30"},
        {"weekday": 0, "start": "15:00", "end": "20:00"},
    ]
    assert body["free_hours"] == 5 * 12 - 1.5


def test_move_to_other_day_and_time(client, mia, lecture):
    client.force_login(mia)

    response = client.post(f"/stundenplan/termine/{lecture.pk}/", data(
        title="Mathematik I", weekday="2", start="10:00", end="13:15"
    ))

    assert response.status_code == 200
    lecture.refresh_from_db()
    assert (lecture.weekday, lecture.start, lecture.end) == (2, time(10, 0), time(13, 15))
    assert response.json()["lecture"]["weekday"] == 2


def test_change_length_and_title(client, mia, lecture):
    client.force_login(mia)

    client.post(f"/stundenplan/termine/{lecture.pk}/", data(
        title="Mathe I (Übung)", weekday="0", start="09:15", end="13:00"
    ))

    lecture.refresh_from_db()
    assert lecture.end == time(13, 0)
    assert lecture.title == "Mathe I (Übung)"


def test_delete(client, mia, lecture):
    client.force_login(mia)

    response = client.post(f"/stundenplan/termine/{lecture.pk}/loeschen/")

    assert response.status_code == 200
    assert not LectureSlot.objects.exists()
    assert response.json()["free_hours"] == 5 * 12


def test_end_before_start_is_400_and_nothing_changes(client, mia, lecture):
    client.force_login(mia)

    created = client.post("/stundenplan/termine/", data(start="14:00", end="13:00"))
    moved = client.post(f"/stundenplan/termine/{lecture.pk}/", data(start="12:00", end="12:00"))

    assert created.status_code == 400
    assert "end" in created.json()["errors"]
    assert moved.status_code == 400
    assert LectureSlot.objects.count() == 1
    lecture.refresh_from_db()
    assert lecture.start == time(9, 15)


def test_missing_title_is_400(client, mia):
    client.force_login(mia)

    response = client.post("/stundenplan/termine/", data(title=""))

    assert response.status_code == 400
    assert "title" in response.json()["errors"]


def test_lectures_of_others_are_404(client, mia, lecture):
    other = User.objects.create_user("jan@student.hpi.uni-potsdam.de")
    StudentProfile.objects.create(user=other)
    client.force_login(other)

    assert client.post(f"/stundenplan/termine/{lecture.pk}/", data()).status_code == 404
    assert client.post(f"/stundenplan/termine/{lecture.pk}/loeschen/").status_code == 404
    lecture.refresh_from_db()
    assert lecture.title == "Mathematik I"


def test_logged_out_is_403_and_nothing_changes(client, lecture):
    assert client.post("/stundenplan/termine/", data()).status_code == 403
    assert client.post(f"/stundenplan/termine/{lecture.pk}/", data()).status_code == 403
    assert client.post(f"/stundenplan/termine/{lecture.pk}/loeschen/").status_code == 403
    assert LectureSlot.objects.count() == 1


def test_only_post(client, mia, lecture):
    client.force_login(mia)

    assert client.get("/stundenplan/termine/").status_code == 405
    assert client.get(f"/stundenplan/termine/{lecture.pk}/loeschen/").status_code == 405


def test_page_has_data_for_the_calendar(client, mia, lecture):
    client.force_login(mia)

    response = client.get("/stundenplan/")

    content = response.content.decode()
    assert 'id="timetable-data"' in content
    data_json = json.loads(content.split('id="timetable-data" type="application/json">')[1].split("</script>")[0])
    assert data_json["lectures"] == [
        {"id": lecture.pk, "title": "Mathematik I", "weekday": 0, "start": "09:15", "end": "12:30"}
    ]
    assert data_json["urls"]["create"] == "/stundenplan/termine/"
    assert "js/timetable.js" in content
    # Ohne JavaScript bleiben Liste und Formular (#7).
    assert "Termin hinzufügen" in content


def test_fit_uses_lectures_from_the_calendar(client, mia):
    # „Passt in meinen Plan“ rechnet mit den Terminen, egal wie sie angelegt wurden.
    company = Company.objects.create(name="Testfirma", industry="Tech", commute_minutes=0)
    posting = JobPosting.objects.create(
        company=company, title="Montagsschicht", kind=JobPosting.Kind.SHORT_JOB,
        workplace=JobPosting.Workplace.ONSITE, hours_per_week=2, hourly_wage=15,
        schedule=JobPosting.Schedule.FIXED,
    )
    Shift.objects.create(posting=posting, weekday=0, start=time(10, 0), end=time(11, 0))
    client.force_login(mia)

    def status():
        return client.get(f"/jobs/{posting.pk}/").context["posting"].fit.status

    assert status() == "passt"
    client.post("/stundenplan/termine/", data(title="Mathe", start="09:00", end="12:00"))
    assert status() == "kollidiert"


def test_lectures_outside_the_grid_stay_reachable(client, mia, lecture):
    # Must-fix aus dem Review von #120 (#123): Das Raster zeigt 8–20 Uhr. Termine, die nicht ganz
    # hineinpassen, würden dort verschwinden oder still auf 8 Uhr geklemmt. Sie stehen deshalb
    # unter dem Raster mit Ändern und Löschen und landen nicht in den Daten fürs Raster.
    late = LectureSlot.objects.create(profile=mia.profile, weekday=0, start=time(20, 30), end=time(21, 30), title="Abendkurs")
    early = LectureSlot.objects.create(profile=mia.profile, weekday=2, start=time(7, 0), end=time(9, 0), title="Frühsport")
    client.force_login(mia)

    content = client.get("/stundenplan/").content.decode()

    data_json = json.loads(content.split('id="timetable-data" type="application/json">')[1].split("</script>")[0])
    assert [item["title"] for item in data_json["lectures"]] == ["Mathematik I"]
    outside = content[content.index('class="tt-outside"'):content.index('id="timetable-data"')]
    assert "Außerhalb von 8–20 Uhr" in outside
    assert "Mo 20:30–21:30" in outside and "Abendkurs" in outside
    assert "Mi 7:00–9:00" in outside and "Frühsport" in outside
    for item in (late, early):
        assert f'href="/stundenplan/{item.pk}/"' in outside
        assert f'action="/stundenplan/{item.pk}/loeschen/"' in outside
    assert "Mathematik I" not in outside


def test_no_outside_list_when_everything_fits(client, mia, lecture):
    client.force_login(mia)

    assert 'class="tt-outside"' not in client.get("/stundenplan/").content.decode()
