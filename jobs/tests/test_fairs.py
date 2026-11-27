from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from jobs.models import Company, Fair, JobPosting

PASSWORD = "test-passwort"


def make_user(email="julia@student.hpi.uni-potsdam.de"):
    return get_user_model().objects.create_user(username=email, email=email, password=PASSWORD)


def make_fair(name, days_from_today, location="Potsdam"):
    return Fair.objects.create(
        name=name, date=timezone.localdate() + timedelta(days=days_from_today), location=location
    )


def make_posting(company, title):
    return JobPosting.objects.create(
        company=company, title=title, kind="short_job", workplace="onsite",
        hours_per_week=8, hourly_wage=15,
    )


@pytest.mark.django_db
def test_fair_list_shows_upcoming_fairs_by_date_without_past_ones(client):
    make_fair("Karrieretag später", 30)
    make_fair("Jobmesse heute", 0)
    make_fair("Messe von gestern", -1)

    response = client.get(reverse("fair_list"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Messe von gestern" not in content
    assert content.index("Jobmesse heute") < content.index("Karrieretag später")


@pytest.mark.django_db
def test_fair_shows_companies_with_their_open_postings(client):
    fair = make_fair("Campus Recruiting Day", 10)
    company = Company.objects.create(name="Weihmann GbR", industry="Tech")
    company.fairs.add(fair)
    posting = make_posting(company, "Werkstudent Python")
    Company.objects.create(name="Nicht dabei AG", industry="Bank")

    content = client.get(reverse("fair_list")).content.decode()

    assert "Weihmann GbR" in content
    assert reverse("job_detail", args=[posting.pk]) in content
    assert "Nicht dabei AG" not in content


@pytest.mark.django_db
def test_logged_out_visitors_see_no_attend_button_and_cannot_attend(client):
    fair = make_fair("Jobmesse", 5)

    content = client.get(reverse("fair_list")).content.decode()
    response = client.post(reverse("fair_attend", args=[fair.pk]))

    assert "Ich gehe hin" not in content
    assert response.status_code == 302
    assert reverse("login") in response.url
    assert fair.visitors.count() == 0


@pytest.mark.django_db
def test_attend_toggles_and_shows_in_my_list(client):
    user = make_user()
    fair = make_fair("Jobmesse", 5)
    client.force_login(user)

    client.post(reverse("fair_attend", args=[fair.pk]))
    content = client.get(reverse("fair_list")).content.decode()
    assert fair.visitors.filter(pk=user.pk).exists()
    assert "Du gehst hin" in content

    client.post(reverse("fair_attend", args=[fair.pk]))
    assert not fair.visitors.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_profile_lists_only_my_upcoming_fairs(client):
    user = make_user()
    mine = make_fair("Meine Messe", 3)
    past = make_fair("Vorbei-Messe", -3)
    make_fair("Fremde Messe", 4)
    mine.visitors.add(user)
    past.visitors.add(user)
    client.force_login(user)

    content = client.get(reverse("profile")).content.decode()

    assert "Meine Messe" in content
    assert "Vorbei-Messe" not in content
    assert "Fremde Messe" not in content


@pytest.mark.django_db
def test_header_links_to_fairs(client):
    content = client.get(reverse("job_list")).content.decode()

    assert f'href="{reverse("fair_list")}"' in content


@pytest.mark.django_db
def test_seed_lets_mia_attend_a_fair():
    call_command("seed")

    mia = get_user_model().objects.get(username="mia@student.hpi.uni-potsdam.de")
    assert list(mia.fairs.values_list("name", flat=True)) == ["Jobmesse Potsdam 2027"]


@pytest.mark.django_db
def test_fair_shows_three_postings_per_company_and_links_the_rest(client):
    fair = make_fair("Jobmesse", 5)
    company = Company.objects.create(name="Weihmann GbR", industry="Tech")
    company.fairs.add(fair)
    for number in range(1, 6):
        make_posting(company, f"Stelle {number}")

    content = client.get(reverse("fair_list")).content.decode()

    assert "Stelle 3" in content
    assert "Stelle 4" not in content
    assert "+2 weitere" in content
    assert f'{reverse("job_list")}?q=Weihmann%20GbR' in content


@pytest.mark.django_db
def test_fair_head_counts_companies_and_shows_them_as_tiles(client):
    """Firmen stehen als Kacheln im Raster, im Kopf steht ihre Anzahl (#111)."""
    one = make_fair("Kleine Messe", 5)
    two = make_fair("Große Messe", 6)
    Company.objects.create(name="Allein GmbH", industry="Tech").fairs.add(one)
    for name in ["Erste AG", "Zweite AG"]:
        Company.objects.create(name=name, industry="Bank").fairs.add(two)

    content = client.get(reverse("fair_list")).content.decode()

    assert "· 1 Firma</p>" in content
    assert "· 2 Firmen</p>" in content
    assert content.count('<div class="fair-companies">') == 2
