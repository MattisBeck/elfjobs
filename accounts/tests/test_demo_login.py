"""Demo-Login (#148): Anmelden ohne Passwort, nur mit DEMO_LOGIN."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import StudentProfile
from companies.models import CompanyMember
from jobs.models import Company

DEMO_URL = "/anmelden/demo/"
MIA = "mia@student.hpi.uni-potsdam.de"


@pytest.fixture(autouse=True)
def demo_on(settings):
    settings.DEMO_LOGIN = True


@pytest.fixture
def mia(db):
    user = User.objects.create_user(MIA, email=MIA, first_name="Mia", last_name="Sommer")
    StudentProfile.objects.create(user=user)
    return user


@pytest.fixture
def student(db):
    user = User.objects.create_user("studi-001", email="studi-001@student.hpi.uni-potsdam.de")
    StudentProfile.objects.create(user=user)
    return user


@pytest.fixture
def company_user(db):
    company = Company.objects.create(name="Bäckerei Krume", industry="Gastronomie")
    user = User.objects.create_user("jobs@baeckerei-krume.example", email="jobs@baeckerei-krume.example")
    CompanyMember.objects.create(user=user, company=company)
    return user


def logged_in_id(client):
    return client.session.get("_auth_user_id")


def test_student_page_shows_dropdown_with_mia_first(client, student, mia, company_user):
    html = client.get(reverse("login")).content.decode()

    assert "Demo-Login" in html
    assert html.index("Mia Sommer – " + MIA) < html.index("studi-001@student.hpi.uni-potsdam.de")
    assert "jobs@baeckerei-krume.example" not in html


def test_company_page_shows_dropdown(client, student, company_user):
    html = client.get(reverse("company_login")).content.decode()

    assert "Demo-Login" in html
    assert "Bäckerei Krume – jobs@baeckerei-krume.example" in html
    assert "studi-001@student" not in html


def test_dropdown_hidden_when_off(client, settings, student, company_user):
    settings.DEMO_LOGIN = False

    assert "Demo-Login" not in client.get(reverse("login")).content.decode()
    assert "Demo-Login" not in client.get(reverse("company_login")).content.decode()


def test_staff_not_in_dropdown(client, student):
    staff = User.objects.create_user("chef@student.hpi.uni-potsdam.de", email="chef@student.hpi.uni-potsdam.de", is_staff=True)
    StudentProfile.objects.create(user=staff)

    assert "chef@student" not in client.get(reverse("login")).content.decode()


def test_student_login_redirects_to_job_list(client, student):
    response = client.post(DEMO_URL, {"kind": "student", "user_id": student.pk})

    assert response.status_code == 302
    assert response.url == reverse("job_list")
    assert logged_in_id(client) == str(student.pk)


def test_student_login_follows_safe_next(client, student):
    response = client.post(DEMO_URL, {"kind": "student", "user_id": student.pk, "next": "/profil/"})

    assert response.url == "/profil/"


def test_student_login_ignores_foreign_next(client, student):
    response = client.post(DEMO_URL, {"kind": "student", "user_id": student.pk, "next": "https://evil.example/"})

    assert response.url == reverse("job_list")


def test_company_login_redirects_to_company_home(client, company_user):
    response = client.post(DEMO_URL, {"kind": "company", "user_id": company_user.pk})

    assert response.status_code == 302
    assert response.url == reverse("company_home")
    assert logged_in_id(client) == str(company_user.pk)


def test_404_when_off(client, settings, student):
    settings.DEMO_LOGIN = False

    response = client.post(DEMO_URL, {"kind": "student", "user_id": student.pk})

    assert response.status_code == 404
    assert logged_in_id(client) is None


@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_staff_and_superuser_rejected(client, flag, db):
    user = User.objects.create_user("admin@student.hpi.uni-potsdam.de", **{flag: True})
    StudentProfile.objects.create(user=user)

    response = client.post(DEMO_URL, {"kind": "student", "user_id": user.pk})

    assert response.status_code == 404
    assert logged_in_id(client) is None


def test_inactive_user_rejected(client, student):
    student.is_active = False
    student.save()

    assert client.post(DEMO_URL, {"kind": "student", "user_id": student.pk}).status_code == 404


def test_student_id_rejected_as_company(client, student):
    assert client.post(DEMO_URL, {"kind": "company", "user_id": student.pk}).status_code == 404
    assert logged_in_id(client) is None


def test_company_id_rejected_as_student(client, company_user):
    assert client.post(DEMO_URL, {"kind": "student", "user_id": company_user.pk}).status_code == 404
    assert logged_in_id(client) is None


def test_get_not_allowed(client, student):
    assert client.get(DEMO_URL).status_code == 405
