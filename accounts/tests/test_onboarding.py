"""Onboarding nach der Registrierung (#35): Skills, Stundenplan, Art des Jobs, alles überspringbar."""

import re

import pytest
from django.contrib.auth.models import User

from accounts.models import ProfileSkill, StudentProfile
from accounts.tests.test_accounts import itse, signup_data  # noqa: F401 (Fixture)
from jobs.models import Tag

EMAIL = "lena.kraus@student.hpi.uni-potsdam.de"


@pytest.fixture
def new_user(client, itse, mailoutbox):  # noqa: F811
    """Frisch registriert und über den Link aus der Mail bestätigt."""
    client.post("/registrieren/", signup_data())
    path = re.search(r"https?://[^/\s]+(/konto/bestaetigen/\S+/)", mailoutbox[0].body).group(1)
    response = client.get(path)
    assert response.url == "/willkommen/"
    return User.objects.get(username=EMAIL)


@pytest.fixture
def existing_user(client, itse):  # noqa: F811
    user = User.objects.create_user("mia", email="mia@student.hpi.uni-potsdam.de", password="pw-12345678")
    StudentProfile.objects.create(user=user, study_program=itse, semester=1)
    client.force_login(user)
    return user


def test_new_account_lands_in_onboarding_step_one(client, new_user):
    content = client.get("/willkommen/").content.decode()

    assert "Schritt 1 von 3" in content
    assert "Überspringen" in content


def test_existing_account_does_not_land_in_onboarding(client, itse):  # noqa: F811
    User.objects.create_user("mia", email="mia@student.hpi.uni-potsdam.de", password="pw-12345678")

    response = client.post("/anmelden/", {"username": "mia", "password": "pw-12345678"})

    assert response.status_code == 302
    assert "willkommen" not in response.url
    assert "Weiter mit dem Onboarding" not in client.get("/jobs/").content.decode()


def test_step_one_saves_skills_and_goes_to_timetable_step(client, new_user):
    excel = Tag.objects.create(name="Excel")

    response = client.post("/willkommen/", {"skills": [excel.pk]})

    assert response.url == "/willkommen/stundenplan/"
    assert ProfileSkill.objects.filter(profile__user=new_user, tag=excel).exists()


def test_step_one_can_be_skipped(client, new_user):
    response = client.post("/willkommen/", {"ueberspringen": "1"})

    assert response.url == "/willkommen/stundenplan/"
    assert not ProfileSkill.objects.filter(profile__user=new_user).exists()


def test_timetable_step_links_to_timetable_and_shows_way_back(client, new_user):
    content = client.get("/willkommen/stundenplan/").content.decode()

    assert "Schritt 2 von 3" in content
    assert 'href="/stundenplan/"' in content
    assert 'href="/willkommen/jobart/"' in content
    # Wer zwischendurch den Stundenplan einträgt, findet zurück ins Onboarding.
    assert 'href="/willkommen/jobart/"' in client.get("/stundenplan/").content.decode()


def test_last_step_opens_job_list_with_chosen_filters(client, new_user):
    response = client.post("/willkommen/jobart/", {"filter": ["kurzjob", "remote", "kaputt"]})

    assert response.url == "/jobs/?filter=kurzjob&filter=remote"
    # Danach ist das Onboarding vorbei, der Hinweis in der Kopfzeile verschwindet.
    assert "Weiter mit dem Onboarding" not in client.get("/jobs/").content.decode()


def test_last_step_can_be_skipped(client, new_user):
    response = client.post("/willkommen/jobart/", {"ueberspringen": "1"})

    assert response.url == "/jobs/"


def test_onboarding_needs_login(client, itse):  # noqa: F811
    response = client.get("/willkommen/")

    assert response.status_code == 302
    assert "/anmelden/" in response.url


def test_existing_user_can_still_open_onboarding_by_hand(client, existing_user):
    assert client.get("/willkommen/").status_code == 200
