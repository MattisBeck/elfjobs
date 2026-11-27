from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from jobs.models import Company, JobPosting


def make_posting(**fields):
    company = Company.objects.create(name="Weihmann GbR", industry="Handel")
    return JobPosting.objects.create(
        company=company,
        title="Promoter*in",
        kind=JobPosting.Kind.SHORT_JOB,
        workplace=JobPosting.Workplace.ONSITE,
        schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal("16.00"),
        hours_per_week=7,
        **fields,
    )


@pytest.mark.django_db
def test_has_location_needs_both_coordinates():
    assert not make_posting().has_location
    assert not make_posting(latitude=Decimal("52.5")).has_location
    assert make_posting(latitude=Decimal("52.5"), longitude=Decimal("13.4")).has_location


@pytest.mark.django_db
def test_seed_puts_onsite_and_hybrid_postings_around_berlin():
    call_command("seed")

    onsite = JobPosting.objects.exclude(workplace=JobPosting.Workplace.REMOTE)
    assert onsite.exists()
    for posting in onsite:
        assert posting.has_location
        assert posting.address
        assert Decimal("52.2") <= posting.latitude <= Decimal("52.8")
        assert Decimal("12.9") <= posting.longitude <= Decimal("13.9")

    for posting in JobPosting.objects.filter(workplace=JobPosting.Workplace.REMOTE):
        assert not posting.has_location
        assert posting.address == ""


@pytest.mark.django_db
def test_seed_locations_are_the_same_every_time():
    def locations():
        return list(
            JobPosting.objects.order_by("title", "company__name", "hours_per_week", "hourly_wage", "id")
            .values_list("title", "company__name", "address", "latitude", "longitude")
        )

    call_command("seed")
    first = locations()
    call_command("seed")

    assert locations() == first


@pytest.mark.django_db
def test_admin_change_page_shows_location_fields(client):
    admin = User.objects.create_superuser("admin", "admin@example.com", "test-passwort")
    client.force_login(admin)
    posting = make_posting(address="Kastanienallee 32, 10435 Berlin")

    response = client.get(f"/admin/jobs/jobposting/{posting.pk}/change/")

    assert response.status_code == 200
    content = response.content.decode()
    for name in ["address", "latitude", "longitude"]:
        assert f'name="{name}"' in content
    assert "Kastanienallee 32, 10435 Berlin" in content


@pytest.mark.django_db
def test_job_detail_shows_address_only_when_set(client):
    with_address = make_posting(address="Kastanienallee 32, 10435 Berlin")
    content = client.get(f"/jobs/{with_address.pk}/").content.decode()
    assert "Adresse" in content
    assert "Kastanienallee 32, 10435 Berlin" in content

    without_address = make_posting()
    content = client.get(f"/jobs/{without_address.pk}/").content.decode()
    assert "<dt>Adresse</dt>" not in content
