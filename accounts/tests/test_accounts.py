import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command

from accounts.models import StudentProfile
from jobs.models import Tag


def test_profile_requires_login(client):
    response = client.get("/profil/")

    assert response.status_code == 302
    assert response.url.startswith("/anmelden/")


def signup_data(**overrides):
    data = {
        "email": "Lena.Kraus@student.hpi.uni-potsdam.de",
        "first_name": "Lena",
        "last_name": "Kraus",
        "study_program": "ITSE",
        "semester": "3",
        "password1": "ein-sicheres-passwort-42",
        "password2": "ein-sicheres-passwort-42",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_signup_with_uni_mail_creates_user_with_profile_and_logs_in(client):
    response = client.post("/registrieren/", signup_data())

    assert response.status_code == 302
    assert response.url == "/profil/"
    user = User.objects.get(username="lena.kraus@student.hpi.uni-potsdam.de")
    assert user.email == "lena.kraus@student.hpi.uni-potsdam.de"
    assert user.profile.summary == "ITSE · 3. Semester"
    assert client.get("/profil/").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("email", [
    "lena@gmail.com",
    "lena@uni-potsdam.de",  # Uni Potsdam ja, aber zum Start nur das HPI
    "lena@fakehpi.de",  # nur echte Subdomains zählen
    "lena@hpi.de.example.com",
])
def test_signup_rejects_non_uni_mail(client, email):
    response = client.post("/registrieren/", signup_data(email=email))

    assert response.status_code == 200
    assert "Bitte registriere dich mit deiner Uni-Mail." in response.content.decode()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_signup_requires_study_program(client):
    response = client.post("/registrieren/", signup_data(study_program=""))

    assert response.status_code == 200
    assert not User.objects.exists()


@pytest.mark.django_db
def test_signup_rejects_existing_mail(client):
    client.post("/registrieren/", signup_data())
    client.post("/abmelden/")

    response = client.post("/registrieren/", signup_data(email="lena.kraus@student.hpi.uni-potsdam.de"))

    assert "Mit dieser Mail gibt es schon ein Konto." in response.content.decode()
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_login_with_uni_mail_ignores_case(client):
    User.objects.create_user("lena@hpi.de", password="ein-sicheres-passwort-42")

    response = client.post("/anmelden/", {"username": "Lena@HPI.de", "password": "ein-sicheres-passwort-42"})

    assert response.status_code == 302
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_profile_can_be_saved_and_shows_in_header(client):
    user = User.objects.create_user("lena", password="x")
    StudentProfile.objects.create(user=user)
    python = Tag.objects.create(name="Python")
    client.force_login(user)

    response = client.post("/profil/", {
        "first_name": "Lena",
        "last_name": "Kraus",
        "study_program": "ITSE",
        "semester": "3",
        "home_town": "Berlin",
        "skills": [python.pk],
    })

    assert response.status_code == 302
    profile = StudentProfile.objects.get(user=user)
    assert (profile.study_program, profile.semester, profile.home_town) == ("ITSE", 3, "Berlin")
    assert list(profile.skills.all()) == [python]
    content = client.get("/jobs/").content.decode()
    assert "Lena Kraus" in content
    assert "ITSE · 3. Semester" in content


@pytest.mark.django_db
def test_profile_page_creates_missing_profile(client):
    user = User.objects.create_user("admin-ohne-profil")
    client.force_login(user)

    assert client.get("/profil/").status_code == 200
    assert StudentProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_logout_needs_post(client):
    user = User.objects.create_user("lena")
    client.force_login(user)

    response = client.post("/abmelden/")

    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_seed_creates_demo_student_mia(client):
    call_command("seed")
    call_command("seed")  # zweimal: Mia wird aktualisiert, nicht doppelt angelegt

    assert client.login(username="mia@student.hpi.uni-potsdam.de", password="test-passwort")
    profile = StudentProfile.objects.get(user__username="mia@student.hpi.uni-potsdam.de")
    assert profile.summary == "ITSE · 1. Semester"
    assert profile.home_town == "Potsdam"
    assert sorted(profile.skills.values_list("name", flat=True)) == ["Englisch", "Informatik", "Python"]


@pytest.mark.django_db
def test_seed_without_demo_password_stops(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD")

    with pytest.raises(CommandError, match="DEMO_PASSWORD"):
        call_command("seed")
