"""Abmelden in der Kopfzeile für Studierende und Firmen (#118)."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from companies.models import CompanyMember
from jobs.models import Company

LOGOUT_FORM = f'<form method="post" action="{reverse("logout")}" class="logout-header">'


@pytest.fixture
def student(db):
    return User.objects.create_user("julia@student.hpi.uni-potsdam.de")


@pytest.fixture
def company_user(db):
    company = Company.objects.create(name="Bäckerei Krume", industry="Gastronomie")
    user = User.objects.create_user("jobs@baeckerei-krume.example")
    CompanyMember.objects.create(user=user, company=company)
    return user


@pytest.mark.parametrize("path", ["/jobs/", "/jobs/messen/"])
def test_student_sees_logout_on_every_page(client, student, path):
    client.force_login(student)

    assert LOGOUT_FORM in client.get(path).content.decode()


def test_company_sees_logout_in_company_area(client, company_user):
    client.force_login(company_user)

    assert LOGOUT_FORM in client.get(reverse("company_home")).content.decode()


@pytest.mark.django_db
def test_anonymous_sees_login_instead_of_logout(client):
    content = client.get("/jobs/").content.decode()

    assert LOGOUT_FORM not in content
    assert "Anmelden" in content


def test_logout_ends_the_session_and_goes_to_job_list(client, company_user):
    client.force_login(company_user)

    response = client.post(reverse("logout"))

    assert response.status_code == 302
    assert response.url == reverse("job_list")
    assert "_auth_user_id" not in client.session
