from decimal import Decimal

import pytest
from django.core.management import call_command

from jobs.management.commands.seed import KINDS, ONSITE_ONLY_TITLES
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
        assert 14 <= posting.hourly_wage <= 17


@pytest.mark.django_db
def test_seed_pays_at_least_minimum_wage():
    call_command("seed")

    assert not JobPosting.objects.filter(hourly_wage__lt=Decimal("13.90")).exists()


@pytest.mark.django_db
def test_seed_onsite_jobs_are_never_remote():
    # Ein Tippfehler in ONSITE_ONLY_TITLES würde den Test sonst unbemerkt grün lassen.
    assert ONSITE_ONLY_TITLES <= set(KINDS[JobPosting.Kind.SHORT_JOB]["titles"])
    call_command("seed")

    remote_onsite_jobs = JobPosting.objects.filter(
        title__in=ONSITE_ONLY_TITLES
    ).exclude(workplace=JobPosting.Workplace.ONSITE)
    assert not remote_onsite_jobs.exists()


@pytest.mark.django_db
def test_seed_keeps_the_examples_from_the_design_spec():
    """docs/design.md und die Issues rechnen mit diesen Stellen, der Seed darf sie nicht verlieren."""
    call_command("seed")

    def exists(title, company, workplace, schedule, hours, wage):
        return JobPosting.objects.filter(
            title=title, company__name__startswith=company, workplace=workplace,
            schedule=schedule, hours_per_week=hours, hourly_wage=Decimal(wage),
        ).exists()

    assert exists("Promoter*in", "Weihmann", "onsite", "fixed", 7, "16.00")
    assert exists("Werkstudent*in Controlling", "Bauer", "onsite", "fixed", 10, "15.00")
    assert exists("Aushilfe Lager", "Holsten", "onsite", "flexible", 11, "14.00")
    assert exists("Werkstudent*in Softwareentwicklung", "Weihmann", "remote", "flexible", 11, "19.50")
