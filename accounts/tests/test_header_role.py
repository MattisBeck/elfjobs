import pytest
from django.contrib.auth.models import User

from companies.models import Company, CompanyMember


@pytest.fixture
def student(db):
    return User.objects.create_user("lena", password="pw", first_name="Lena", last_name="Kraus")


@pytest.fixture
def company_user(db):
    company = Company.objects.create(name="Beispiel Labs GmbH", industry="Tech")
    user = User.objects.create_user("firma", password="pw")
    CompanyMember.objects.create(user=user, company=company)
    return user


def test_student_sees_studi_badge(client, student):
    client.force_login(student)

    html = client.get("/", follow=True).content.decode()

    assert "Studi" in html
    assert 'role-badge role-badge-student' in html
    assert "Firma</span>" not in html


def test_company_sees_firma_badge_and_name(client, company_user):
    client.force_login(company_user)

    html = client.get("/", follow=True).content.decode()

    assert 'role-badge role-badge-company">Firma' in html
    assert "Beispiel Labs GmbH" in html
    assert "site-header-company" in html
    assert "role-badge-student" not in html


def test_anonymous_sees_no_badge(client, db):
    html = client.get("/", follow=True).content.decode()

    assert "role-badge" not in html
    assert "site-header-company" not in html
