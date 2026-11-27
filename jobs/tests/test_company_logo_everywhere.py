"""Firmenlogo überall (#149): Wo ein Firmenname steht, steht direkt davor das Logo oder die Initialen."""

import re
from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from accounts.models import StudentProfile
from applications.models import Application
from companies.models import CompanyMember
from jobs.models import Company, Fair, JobPosting
from timetable.models import LectureSlot, PlannedShift

NAME = "Weihmann GbR"
# Initialen-Platzhalter oder Bild, direkt gefolgt vom Firmennamen (ggf. nach einem Pfeil oder "bei ").
LOGO_BEFORE_NAME = re.compile(r'class="company-logo [^>]*>(?:W</span>)?\s*' + NAME)


@pytest.fixture
def company(db):
    return Company.objects.create(name=NAME, industry="Handel")


@pytest.fixture
def posting(company):
    return JobPosting.objects.create(
        company=company, title="Promoter*in", kind=JobPosting.Kind.SHORT_JOB,
        workplace=JobPosting.Workplace.ONSITE, schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal("16.00"), hours_per_week=7,
    )


@pytest.fixture
def profile(db):
    user = User.objects.create_user("mia@student.hpi.uni-potsdam.de", password="pw-12345678")
    return StudentProfile.objects.create(user=user)


def assert_logo_before_name(content):
    assert LOGO_BEFORE_NAME.search(content), content


def test_profile_application_list(client, profile, posting):
    Application.objects.create(profile=profile, posting=posting)
    client.force_login(profile.user)
    assert_logo_before_name(client.get("/profil/").content.decode())


def test_apply_page(client, profile, posting):
    client.force_login(profile.user)
    assert_logo_before_name(client.get(f"/jobs/{posting.pk}/bewerben/").content.decode())


@pytest.mark.parametrize("path", ["/firma/", "/firma/verfuegbarkeit/", "/firma/stellen/neu/"])
def test_company_pages(client, company, path):
    user = User.objects.create_user("chef@weihmann.example", password="pw-12345678")
    CompanyMember.objects.create(user=user, company=company)
    client.force_login(user)
    assert_logo_before_name(client.get(path).content.decode())


def test_fair_list(client, company):
    fair = Fair.objects.create(name="Jobmesse", date=timezone.localdate() + timedelta(days=3), location="Potsdam")
    fair.companies.add(company)
    assert_logo_before_name(client.get(reverse("fair_list")).content.decode())


def test_job_detail_reviews_and_social_links(client, company, posting):
    company.instagram_url = "https://instagram.com/weihmann"
    company.save()
    content = client.get(f"/jobs/{posting.pk}/").content.decode()
    assert content.count("company-logo") >= 3  # Kopf, Bewertungen, Social Media
    assert re.search(r'company-logo[^>]*>(?:W</span>)?\s*Weihmann GbR im Netz', content)
    assert re.search(r'Bewertungen für <span class="company-logo', content)


def test_logo_image_when_company_has_one(client, company, posting, settings):
    company.logo_static = "seed/logos/test.svg"
    company.save()
    content = client.get(f"/jobs/{posting.pk}/").content.decode()
    assert '<img class="company-logo company-logo-small"' in content


def test_timetable_conflict_list_and_shift_row(client, profile, posting):
    LectureSlot.objects.create(profile=profile, weekday=0, start=time(9), end=time(12), title="Mathematik I")
    PlannedShift.objects.create(profile=profile, posting=posting, weekday=0, start=time(10), end=time(11))
    client.force_login(profile.user)
    content = client.get("/stundenplan/").content.decode()
    assert len(LOGO_BEFORE_NAME.findall(content)) >= 1
    assert "shift-conflicts" in content


def test_timetable_json_has_logo_data(client, profile, posting):
    PlannedShift.objects.create(profile=profile, posting=posting, weekday=1, start=time(10), end=time(11))
    client.force_login(profile.user)
    content = client.get("/stundenplan/").content.decode()
    assert '"initials": "W"' in content
    assert '"logo_url"' in content
