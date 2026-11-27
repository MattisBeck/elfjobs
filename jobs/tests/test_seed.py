import pytest
from django.core.management import call_command

from jobs.models import Company, Fair, JobPosting, Tag


@pytest.mark.django_db
def test_seed_can_run_twice_and_creates_demo_data():
    call_command("seed")
    call_command("seed")

    assert Fair.objects.count() == 5
    assert Company.objects.count() == 20
    assert Tag.objects.count() == 15
    assert JobPosting.objects.count() == 200


@pytest.mark.django_db
def test_seed_creates_plausible_hours_and_wages():
    call_command("seed")

    for posting in JobPosting.objects.filter(kind=JobPosting.Kind.WORKING_STUDENT):
        assert 10 <= posting.hours_per_week <= 20
        assert 15 <= posting.hourly_wage <= 22

    for posting in JobPosting.objects.filter(kind=JobPosting.Kind.SHORT_JOB):
        assert 3 <= posting.hours_per_week <= 12
        assert 13 <= posting.hourly_wage <= 17
