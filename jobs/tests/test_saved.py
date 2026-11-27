import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.urls import reverse

from companies.models import CompanyMember
from jobs.management.commands.seed import DEMO_EMAIL
from jobs.models import Company, JobPosting, SavedPosting


def make_user(email="julia@student.hpi.uni-potsdam.de"):
    return get_user_model().objects.create_user(username=email, email=email, password="test-passwort")


def make_company(name="Bäckerei Krume"):
    return Company.objects.create(name=name, industry="Gastronomie")


def make_posting(title="Promoter*in", company=None):
    return JobPosting.objects.create(
        company=company or make_company(), title=title, kind="short_job", workplace="onsite",
        hours_per_week=8, hourly_wage=15,
    )


@pytest.mark.django_db
def test_save_requires_login(client):
    posting = make_posting()

    response = client.post(reverse("job_save", args=[posting.pk]))

    assert response.status_code == 302
    assert reverse("login") in response.url
    assert not SavedPosting.objects.exists()


@pytest.mark.django_db
def test_anonymous_detail_shows_merken_as_login_link(client):
    posting = make_posting()

    content = client.get(reverse("job_detail", args=[posting.pk])).content.decode()

    assert f'{reverse("login")}?next=' in content
    assert 'action="' + reverse("job_save", args=[posting.pk]) not in content


@pytest.mark.django_db
def test_save_and_unsave_toggle(client):
    user = make_user()
    posting = make_posting()
    client.force_login(user)
    url = reverse("job_save", args=[posting.pk])

    response = client.post(url)
    assert response.status_code == 302
    assert response.url == reverse("job_detail", args=[posting.pk])
    assert SavedPosting.objects.filter(user=user, posting=posting).exists()
    detail = client.get(reverse("job_detail", args=[posting.pk])).content.decode()
    assert 'aria-pressed="true">Gemerkt</button>' in detail

    client.post(url)
    assert not SavedPosting.objects.filter(user=user, posting=posting).exists()
    detail = client.get(reverse("job_detail", args=[posting.pk])).content.decode()
    assert 'aria-pressed="false">Merken</button>' in detail


@pytest.mark.django_db
def test_save_needs_post(client):
    client.force_login(make_user())
    posting = make_posting()

    assert client.get(reverse("job_save", args=[posting.pk])).status_code == 405


@pytest.mark.django_db
def test_company_account_cannot_save(client):
    company = make_company()
    posting = make_posting(company=company)
    user = make_user("jobs@baeckerei-krume.example")
    CompanyMember.objects.create(user=user, company=company)
    client.force_login(user)

    assert client.post(reverse("job_save", args=[posting.pk])).status_code == 403
    assert client.get(reverse("saved_list")).status_code == 403
    assert not SavedPosting.objects.exists()
    # Kein Knopf und kein Eintrag in der Navigation.
    content = client.get(reverse("job_detail", args=[posting.pk])).content.decode()
    assert ">Merken<" not in content
    assert ">Gemerkt" not in content


@pytest.mark.django_db
def test_saving_twice_is_impossible():
    user = make_user()
    posting = make_posting()
    SavedPosting.objects.create(user=user, posting=posting)

    with pytest.raises(IntegrityError):
        SavedPosting.objects.create(user=user, posting=posting)


@pytest.mark.django_db
def test_redirects_to_safe_next(client):
    client.force_login(make_user())
    posting = make_posting()
    next_url = reverse("job_detail", args=[posting.pk]) + "?filter=kurzjob"

    response = client.post(reverse("job_save", args=[posting.pk]), {"next": next_url})

    assert response.url == next_url


@pytest.mark.django_db
@pytest.mark.parametrize("next_url", ["https://evil.example/", "//evil.example/", "javascript:alert(1)"])
def test_ignores_unsafe_next(client, next_url):
    client.force_login(make_user())
    posting = make_posting()

    response = client.post(reverse("job_save", args=[posting.pk]), {"next": next_url})

    assert response.url == reverse("job_detail", args=[posting.pk])


@pytest.mark.django_db
def test_saved_list_shows_only_own_postings(client):
    user = make_user()
    other = make_user("justus@student.hpi.uni-potsdam.de")
    company = make_company()
    mine = make_posting("Meine Stelle", company)
    theirs = make_posting("Fremde Stelle", company)
    make_posting("Nicht gemerkt", company)
    SavedPosting.objects.create(user=user, posting=mine)
    SavedPosting.objects.create(user=other, posting=theirs)
    client.force_login(user)

    response = client.get(reverse("saved_list"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Meine Stelle" in content
    assert "Fremde Stelle" not in content
    assert "Nicht gemerkt" not in content
    assert reverse("job_detail", args=[mine.pk]) in content


@pytest.mark.django_db
def test_saved_list_empty_state(client):
    client.force_login(make_user())

    content = client.get(reverse("saved_list")).content.decode()

    assert "Noch nichts gemerkt" in content


@pytest.mark.django_db
def test_saved_list_requires_login(client):
    response = client.get(reverse("saved_list"))

    assert response.status_code == 302
    assert reverse("login") in response.url


@pytest.mark.django_db
def test_navigation_shows_counter_for_students(client):
    user = make_user()
    company = make_company()
    for title in ["Erste", "Zweite"]:
        SavedPosting.objects.create(user=user, posting=make_posting(title, company))
    client.force_login(user)

    content = client.get(reverse("fair_list")).content.decode()

    assert f'<a href="{reverse("saved_list")}">Gemerkt · 2</a>' in content


@pytest.mark.django_db
def test_navigation_without_saved_postings_has_no_counter(client):
    client.force_login(make_user())

    content = client.get(reverse("fair_list")).content.decode()

    assert f'<a href="{reverse("saved_list")}">Gemerkt</a>' in content


@pytest.mark.django_db
def test_navigation_shows_saved_disabled_for_anonymous(client):
    content = client.get(reverse("fair_list")).content.decode()

    assert reverse("saved_list") not in content
    assert '<span aria-disabled="true">Gemerkt</span>' in content


@pytest.mark.django_db
def test_seed_gives_mia_two_saved_postings():
    call_command("seed")
    call_command("seed")

    saved = SavedPosting.objects.filter(user__username=DEMO_EMAIL).order_by("posting_id")
    assert saved.count() == 2
    assert [entry.posting for entry in saved] == list(JobPosting.objects.order_by("id")[:2])
