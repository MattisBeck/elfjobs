"""Firmen-Login (#66): Firmen legen ihre Stellen selbst an und bearbeiten sie."""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from accounts.models import StudentProfile
from companies.models import CompanyMember
from jobs.management.commands.seed import DEMO_COMPANY, DEMO_COMPANY_EMAIL
from jobs.models import Company, JobPosting, Tag

PASSWORD = "ein-sicheres-passwort-42"


def signup(client, email="jobs@baeckerei-krume.example", company="Bäckerei Krume"):
    return client.post("/firma/registrieren/", {
        "email": email, "first_name": "Kim", "last_name": "Krume",
        "company_name": company, "industry": "Gastronomie",
        "password1": PASSWORD, "password2": PASSWORD,
    })


def posting_data(**overrides):
    data = {
        "title": "Aushilfe Verkauf", "kind": JobPosting.Kind.SHORT_JOB,
        "workplace": JobPosting.Workplace.ONSITE, "address": "Brandenburger Str. 1, 14467 Potsdam",
        "hours_per_week": "8", "hourly_wage": "15.50", "schedule": JobPosting.Schedule.FIXED,
        "description": "Brötchen verkaufen.",
        "shifts-TOTAL_FORMS": "3", "shifts-INITIAL_FORMS": "0",
        "shifts-MIN_NUM_FORMS": "0", "shifts-MAX_NUM_FORMS": "1000",
        "shifts-0-weekday": "1", "shifts-0-start": "16:00", "shifts-0-end": "20:00",
    }
    data.update(overrides)
    return data


@pytest.fixture
def company_client(client, db):
    signup(client)
    return client


def test_signup_creates_company_and_logs_in(client, db):
    response = signup(client)

    assert response.status_code == 302
    assert response.url == "/firma/"
    member = CompanyMember.objects.get(user__username="jobs@baeckerei-krume.example")
    assert (member.company.name, member.company.industry) == ("Bäckerei Krume", "Gastronomie")
    assert "Bäckerei Krume" in client.get("/firma/").content.decode()


def test_signup_rejects_existing_mail(client, db):
    signup(client)
    client.post("/abmelden/")

    response = signup(client, email="Jobs@Baeckerei-Krume.example")

    assert response.status_code == 200
    assert "Mit dieser Mail gibt es schon ein Konto." in response.content.decode()


def test_company_login_leads_to_company_area(client, db):
    signup(client)
    client.post("/abmelden/")

    response = client.post("/firma/anmelden/", {"username": "JOBS@baeckerei-krume.example", "password": PASSWORD})

    assert response.status_code == 302
    assert response.url == "/firma/"


def test_create_posting_appears_in_job_list(company_client):
    python = Tag.objects.create(name="Kassieren")

    response = company_client.post("/firma/stellen/neu/", posting_data(tags=[python.pk]))

    assert response.status_code == 302
    posting = JobPosting.objects.get(title="Aushilfe Verkauf")
    assert posting.company.name == "Bäckerei Krume"
    assert posting.hourly_wage == Decimal("15.50")
    assert [(s.weekday, s.start.hour, s.end.hour) for s in posting.shifts.all()] == [(1, 16, 20)]
    assert list(posting.tags.values_list("name", flat=True)) == ["Kassieren"]
    company_client.post("/abmelden/")
    assert "Aushilfe Verkauf" in [p.title for p in company_client.get("/jobs/").context["postings"]]


def test_fixed_schedule_needs_a_shift(company_client):
    response = company_client.post("/firma/stellen/neu/", posting_data(**{
        "shifts-0-weekday": "", "shifts-0-start": "", "shifts-0-end": "",
    }))

    assert response.status_code == 200
    assert "mindestens eine Schicht" in response.content.decode()
    assert not JobPosting.objects.exists()


def test_flexible_posting_without_shifts(company_client):
    response = company_client.post("/firma/stellen/neu/", posting_data(**{
        "schedule": JobPosting.Schedule.FLEXIBLE, "workplace": JobPosting.Workplace.REMOTE, "address": "",
        "shifts-0-weekday": "", "shifts-0-start": "", "shifts-0-end": "",
    }))

    assert response.status_code == 302
    assert JobPosting.objects.get().shifts.count() == 0


def test_shift_must_end_after_start(company_client):
    response = company_client.post("/firma/stellen/neu/", posting_data(**{"shifts-0-end": "15:00"}))

    assert response.status_code == 200
    assert not JobPosting.objects.exists()


def test_edit_own_posting(company_client):
    company_client.post("/firma/stellen/neu/", posting_data())
    posting = JobPosting.objects.get()
    shift = posting.shifts.get()

    response = company_client.post(f"/firma/stellen/{posting.pk}/", posting_data(**{
        "title": "Aushilfe Verkauf (Fr)", "shifts-INITIAL_FORMS": "1",
        "shifts-0-id": str(shift.pk), "shifts-0-weekday": "4", "shifts-0-start": "08:00", "shifts-0-end": "12:00",
    }))

    assert response.status_code == 302
    posting.refresh_from_db()
    assert posting.title == "Aushilfe Verkauf (Fr)"
    assert [(s.weekday, s.start.hour) for s in posting.shifts.all()] == [(4, 8)]


def test_foreign_posting_is_404(company_client):
    other = Company.objects.create(name="Andere Firma", industry="Tech")
    foreign = JobPosting.objects.create(
        company=other, title="Fremd", kind=JobPosting.Kind.SHORT_JOB, workplace=JobPosting.Workplace.REMOTE,
        schedule=JobPosting.Schedule.FLEXIBLE, hourly_wage=Decimal("15"), hours_per_week=5,
    )

    assert company_client.get(f"/firma/stellen/{foreign.pk}/").status_code == 404
    assert company_client.post(f"/firma/stellen/{foreign.pk}/", posting_data(title="Gekapert")).status_code == 404
    foreign.refresh_from_db()
    assert foreign.title == "Fremd"
    assert "Fremd" not in company_client.get("/firma/").content.decode()


def test_students_and_guests_stay_out(client, db):
    assert client.get("/firma/").url.startswith("/firma/anmelden/")
    assert client.get("/firma/stellen/neu/").url.startswith("/firma/anmelden/")

    student = User.objects.create_user("lena@student.hpi.uni-potsdam.de", password=PASSWORD)
    StudentProfile.objects.create(user=student)
    client.force_login(student)
    assert client.get("/firma/").status_code == 403
    assert client.get("/firma/stellen/neu/").status_code == 403


def test_header_links_company_to_company_area(company_client):
    content = company_client.get("/jobs/").content.decode()

    assert 'class="profile-button" href="/firma/"' in content


@pytest.mark.django_db
def test_seed_creates_demo_company_account(client):
    call_command("seed")
    call_command("seed")  # zweimal: Konto bleibt, Firma wird neu verknüpft

    member = CompanyMember.objects.get(user__username=DEMO_COMPANY_EMAIL)
    assert member.company.name == DEMO_COMPANY
    assert client.login(username=DEMO_COMPANY_EMAIL, password="test-passwort")
    content = client.get("/firma/").content.decode()
    assert "Promoter*in" in content
