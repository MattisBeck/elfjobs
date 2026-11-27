"""Bewertungen für Arbeitgeber (#32): Studierende bewerten Firmen, bei denen sie sich beworben haben."""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError

from accounts.models import StudentProfile
from applications.models import Application
from companies.models import CompanyMember
from jobs.models import Company, JobPosting
from reviews.models import Review


def make_posting(title, company, wage="16.00"):
    # Remote: effektiver Lohn = Bruttolohn.
    return JobPosting.objects.create(
        company=company, title=title, kind=JobPosting.Kind.SHORT_JOB,
        workplace=JobPosting.Workplace.REMOTE, schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal(wage), hours_per_week=5,
    )


def make_student(name):
    return StudentProfile.objects.create(user=User.objects.create_user(name))


@pytest.fixture
def company(db):
    return Company.objects.create(name="Weihmann GbR", industry="Handel")


@pytest.fixture
def posting(company):
    return make_posting("Kassierer*in", company)


@pytest.fixture
def student(db):
    return make_student("mia")


@pytest.fixture
def applied(student, posting):
    Application.objects.create(profile=student, posting=posting)
    return student


def review_url(company):
    return f"/firmen/{company.pk}/bewerten/"


def test_student_with_application_can_review(client, applied, company, posting):
    client.force_login(applied.user)

    response = client.post(review_url(company), {
        "stars": 4, "text": "Nettes Team.", "next": f"/jobs/{posting.pk}/",
    })

    assert response.status_code == 302
    assert response.url == f"/jobs/{posting.pk}/"
    review = Review.objects.get()
    assert (review.profile, review.company, review.stars, review.text) == (applied, company, 4, "Nettes Team.")


def test_no_review_without_application(client, student, company):
    client.force_login(student.user)

    response = client.post(review_url(company), {"stars": 5, "text": "Super"})

    assert response.status_code == 403
    assert not Review.objects.exists()


def test_application_at_other_company_does_not_count(client, applied):
    other = Company.objects.create(name="Andere GmbH", industry="Tech")
    client.force_login(applied.user)

    response = client.post(review_url(other), {"stars": 5, "text": "Super"})

    assert response.status_code == 403
    assert not Review.objects.exists()


def test_one_review_per_person_and_company(client, applied, company):
    client.force_login(applied.user)

    client.post(review_url(company), {"stars": 2, "text": "Erst so lala."})
    client.post(review_url(company), {"stars": 5, "text": "Doch super."})

    # Ein zweites Absenden ändert die eigene Bewertung, statt eine zweite anzulegen.
    review = Review.objects.get()
    assert (review.stars, review.text) == (5, "Doch super.")


def test_database_allows_only_one_review_per_person_and_company(applied, company):
    Review.objects.create(profile=applied, company=company, stars=3, text="Okay")

    with pytest.raises(IntegrityError):
        Review.objects.create(profile=applied, company=company, stars=4, text="Nochmal")


@pytest.mark.parametrize("stars", [0, 6])
def test_stars_must_be_between_1_and_5(client, applied, company, stars):
    client.force_login(applied.user)

    client.post(review_url(company), {"stars": stars, "text": "Text"})

    assert not Review.objects.exists()


def test_text_is_required(client, applied, company):
    client.force_login(applied.user)

    client.post(review_url(company), {"stars": 4, "text": ""})

    assert not Review.objects.exists()


def test_login_required(client, company):
    response = client.post(review_url(company), {"stars": 4, "text": "Text"})

    assert response.status_code == 302
    assert "next=" in response.url
    assert not Review.objects.exists()


def test_company_account_cannot_review(client, company):
    user = User.objects.create_user("firma")
    CompanyMember.objects.create(user=user, company=company)
    client.force_login(user)

    response = client.post(review_url(company), {"stars": 5, "text": "Wir sind toll"})

    assert response.status_code == 403
    assert not Review.objects.exists()


def test_unsafe_next_falls_back_to_job_list(client, applied, company):
    client.force_login(applied.user)

    response = client.post(review_url(company), {"stars": 4, "text": "Gut", "next": "https://example.com/"})

    assert response.url == "/jobs/"


# Anzeige im Stellendetail und in der Liste


def add_review(company, stars, name, text="Text"):
    return Review.objects.create(profile=make_student(name), company=company, stars=stars, text=text)


def test_detail_shows_average_count_and_texts(client, company, posting):
    add_review(company, 5, "a", "Sehr faire Schichtplanung.")
    add_review(company, 4, "b")

    response = client.get(f"/jobs/{posting.pk}/")

    content = response.content.decode()
    assert "4,5" in content
    assert "2 Bewertungen" in content
    assert "Sehr faire Schichtplanung." in content


def test_detail_without_reviews(client, posting):
    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert "Noch keine Bewertungen" in content


def test_detail_shows_form_only_after_application(client, student, posting):
    client.force_login(student.user)
    assert "review-form" not in client.get(f"/jobs/{posting.pk}/").content.decode()

    Application.objects.create(profile=student, posting=posting)

    assert "review-form" in client.get(f"/jobs/{posting.pk}/").content.decode()


def test_application_at_another_posting_of_same_company_allows_review(client, student, company, posting):
    other = make_posting("Lager", company)
    Application.objects.create(profile=student, posting=other)
    client.force_login(student.user)

    assert "review-form" in client.get(f"/jobs/{posting.pk}/").content.decode()


def test_job_list_shows_rating(client, company, posting):
    add_review(company, 3, "a")
    add_review(company, 4, "b")
    add_review(company, 4, "c")

    response = client.get("/jobs/")

    row = response.context["postings"][0]
    assert row.rating == {"average": pytest.approx(11 / 3), "count": 3}
    assert "3,7" in response.content.decode()


# Sortierung „nach Bewertung“


def titles(response):
    return [posting.title for posting in response.context["postings"]]


@pytest.fixture
def rated(db):
    good = Company.objects.create(name="Gut", industry="Tech")
    okay = Company.objects.create(name="Okay", industry="Tech")
    popular = Company.objects.create(name="Beliebt", industry="Tech")
    unrated = Company.objects.create(name="Neu", industry="Tech")
    make_posting("Gut bewertet", good, "14.00")
    make_posting("Mittel bewertet", okay, "20.00")
    make_posting("Gut und oft bewertet", popular, "13.00")
    make_posting("Ohne Bewertung", unrated, "30.00")
    add_review(good, 5, "g1")
    add_review(good, 4, "g2")
    add_review(okay, 3, "o1")
    add_review(popular, 5, "p1")
    add_review(popular, 4, "p2")
    add_review(popular, 5, "p3")
    add_review(popular, 4, "p4")


def test_sort_by_rating(client, rated):
    response = client.get("/jobs/?reihenfolge=bewertung")

    # Durchschnitt, bei Gleichstand mehr Bewertungen zuerst, Firmen ohne Bewertung am Ende.
    assert titles(response) == ["Gut und oft bewertet", "Gut bewertet", "Mittel bewertet", "Ohne Bewertung"]


def test_default_is_still_wage_when_logged_out(client, rated):
    response = client.get("/jobs/")

    assert titles(response) == ["Ohne Bewertung", "Mittel bewertet", "Gut bewertet", "Gut und oft bewertet"]


def test_rating_sort_link_for_everyone(client, rated):
    response = client.get("/jobs/?filter=kurzjob")

    links = {link["label"]: (link["url"], link["active"]) for link in response.context["filter_form"]["sort_links"]}
    assert links == {
        "Effektiver Lohn": ("/jobs/?filter=kurzjob", True),
        "Bewertung": ("/jobs/?filter=kurzjob&reihenfolge=bewertung", False),
    }
    # Gewählte Sortierung bleibt in den Links zu den Stellen erhalten.
    content = client.get("/jobs/?reihenfolge=bewertung").content.decode()
    assert "reihenfolge=bewertung" in content.split('class="job-rows"')[1]


# Seed


@pytest.mark.django_db
def test_seed_creates_reviews_only_with_applications():
    call_command("seed")
    first = sorted(Review.objects.values_list("profile__user__username", "company__name", "stars", "text"))
    call_command("seed")
    second = sorted(Review.objects.values_list("profile__user__username", "company__name", "stars", "text"))

    assert len(first) >= 20
    assert first == second
    assert Review.objects.values("company").distinct().count() >= 5
    for review in Review.objects.all():
        assert Application.objects.filter(profile=review.profile, posting__company=review.company).exists()
