import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command

from accounts.models import ProfileSkill, StudentProfile
from jobs.models import Tag
from studies.models import Course, StudyProgram


def test_profile_requires_login(client):
    response = client.get("/profil/")

    assert response.status_code == 302
    assert response.url.startswith("/anmelden/")


@pytest.fixture
def itse(db):
    program = StudyProgram.objects.create(
        name="IT-Systems Engineering", abbreviation="ITSE", university="HPI", standard_semesters=6
    )
    Course.objects.create(program=program, name="Programmiertechnik I", short_name="PT1", semester=1)
    Course.objects.create(program=program, name="Datenbanksysteme I", short_name="DBS1", semester=3)
    Course.objects.create(program=program, name="Softwaretechnik II", short_name="SWT2", semester=4)
    return program


def signup_data(**overrides):
    data = {
        "email": "Lena.Kraus@student.hpi.uni-potsdam.de",
        "first_name": "Lena",
        "last_name": "Kraus",
        "study_program": StudyProgram.objects.get(abbreviation="ITSE").pk,
        "semester": "3",
        "password1": "ein-sicheres-passwort-42",
        "password2": "ein-sicheres-passwort-42",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_signup_with_uni_mail_creates_user_with_profile_and_logs_in(client, itse):
    response = client.post("/registrieren/", signup_data())

    assert response.status_code == 302
    assert response.url == "/profil/"
    user = User.objects.get(username="lena.kraus@student.hpi.uni-potsdam.de")
    assert user.email == "lena.kraus@student.hpi.uni-potsdam.de"
    assert user.profile.summary == "ITSE · 3. Semester"
    # Vorauswahl: alle Module bis zum aktuellen Semester.
    assert sorted(user.profile.courses.values_list("short_name", flat=True)) == ["DBS1", "PT1"]
    assert client.get("/profil/").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("email", [
    "lena@gmail.com",
    "lena@uni-potsdam.de",  # Uni Potsdam ja, aber zum Start nur das HPI
    "lena@fakehpi.de",  # nur echte Subdomains zählen
    "lena@hpi.de.example.com",
])
def test_signup_rejects_non_uni_mail(client, itse, email):
    response = client.post("/registrieren/", signup_data(email=email))

    assert response.status_code == 200
    assert "Bitte registriere dich mit deiner Uni-Mail." in response.content.decode()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_signup_requires_study_program(client, itse):
    response = client.post("/registrieren/", signup_data(study_program=""))

    assert response.status_code == 200
    assert not User.objects.exists()


@pytest.mark.django_db
def test_signup_rejects_existing_mail(client, itse):
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
def test_profile_can_be_saved_and_shows_in_header(client, itse):
    user = User.objects.create_user("lena", password="x")
    StudentProfile.objects.create(user=user)
    python = Tag.objects.create(name="Python")
    pt1 = itse.courses.get(short_name="PT1")
    client.force_login(user)

    response = client.post("/profil/", {
        "first_name": "Lena",
        "last_name": "Kraus",
        "study_program": itse.pk,
        "semester": "3",
        "home_town": "Berlin",
        "skills": [python.pk],
        "courses": [pt1.pk],
    })

    assert response.status_code == 302
    profile = StudentProfile.objects.get(user=user)
    assert (profile.study_program, profile.semester, profile.home_town) == (itse, 3, "Berlin")
    assert list(profile.skills.all()) == [python]
    assert ProfileSkill.objects.get(profile=profile).source == "profil"
    assert list(profile.courses.all()) == [pt1]
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
    assert profile.study_program.name == "IT-Systems Engineering"
    assert sorted(profile.courses.values_list("short_name", flat=True)) == ["MA1", "PT1"]


@pytest.mark.django_db
def test_seed_without_demo_password_stops(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD")

    with pytest.raises(CommandError, match="DEMO_PASSWORD"):
        call_command("seed")


@pytest.mark.django_db
def test_profile_preselects_courses_up_to_current_semester(client, itse):
    user = User.objects.create_user("lena")
    StudentProfile.objects.create(user=user, study_program=itse, semester=3)
    client.force_login(user)

    form = client.get("/profil/").context["profile_form"]

    initial = sorted(course.short_name for course in form.initial["courses"])
    assert initial == ["DBS1", "PT1"]
    # Zur Auswahl stehen alle Module des Studiengangs, auch spätere.
    assert form.fields["courses"].queryset.count() == 3


@pytest.mark.django_db
def test_profile_keeps_chosen_courses_without_preselection(client, itse):
    user = User.objects.create_user("lena")
    profile = StudentProfile.objects.create(user=user, study_program=itse, semester=3)
    profile.courses.set(itse.courses.filter(short_name="SWT2"))
    client.force_login(user)

    form = client.get("/profil/").context["profile_form"]

    assert [course.short_name for course in form.initial["courses"]] == ["SWT2"]


@pytest.mark.django_db
def test_profile_form_keeps_skills_from_cv(client, itse):
    """Speichern im Profil ändert nur die Skills mit Quelle „profil“, nicht die aus dem Lebenslauf."""
    user = User.objects.create_user("lena")
    profile = StudentProfile.objects.create(user=user, study_program=itse, semester=1)
    excel = Tag.objects.create(name="Excel")
    python = Tag.objects.create(name="Python")
    ProfileSkill.objects.create(profile=profile, tag=excel, source=ProfileSkill.Source.CV)
    ProfileSkill.objects.create(profile=profile, tag=python, source=ProfileSkill.Source.PROFILE)
    client.force_login(user)

    client.post("/profil/", {
        "first_name": "Lena", "last_name": "", "study_program": itse.pk, "semester": "1",
        "home_town": "", "skills": [], "courses": [],
    })

    assert list(profile.profile_skills.values_list("tag__name", "source")) == [("Excel", "lebenslauf")]


@pytest.mark.django_db
def test_changing_study_program_drops_courses_of_old_program(client, itse):
    wi = StudyProgram.objects.create(
        name="Wirtschaftsinformatik", abbreviation="WI", university="Uni Potsdam", standard_semesters=6
    )
    user = User.objects.create_user("lena")
    profile = StudentProfile.objects.create(user=user, study_program=itse, semester=1)
    pt1 = itse.courses.get(short_name="PT1")
    profile.courses.add(pt1)
    client.force_login(user)

    response = client.post("/profil/", {
        "first_name": "Lena", "last_name": "", "study_program": wi.pk, "semester": "1",
        "home_town": "", "courses": [pt1.pk],
    })

    assert response.status_code == 302
    profile.refresh_from_db()
    assert profile.study_program == wi
    assert not profile.courses.exists()
