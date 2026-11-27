from datetime import time
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import IntegrityError

from jobs.models import Company, JobPosting, Shift


@pytest.mark.django_db
def test_every_fixed_seed_posting_has_shifts_matching_its_hours():
    call_command("seed")

    fixed = JobPosting.objects.filter(schedule=JobPosting.Schedule.FIXED).prefetch_related("shifts")
    assert fixed.exists()
    for posting in fixed:
        shifts = list(posting.shifts.all())
        assert shifts, posting
        assert sum(shift.hours for shift in shifts) == posting.hours_per_week
        assert len({shift.weekday for shift in shifts}) == len(shifts)  # ein Tag, eine Schicht
        for shift in shifts:
            assert time(8, 0) <= shift.start < shift.end <= time(20, 0)


@pytest.mark.django_db
def test_flexible_seed_postings_have_no_shifts():
    call_command("seed")

    assert not Shift.objects.filter(posting__schedule=JobPosting.Schedule.FLEXIBLE).exists()


@pytest.mark.django_db
def test_design_example_gets_the_shifts_from_the_spec():
    call_command("seed")

    posting = JobPosting.objects.get(title="Promoter*in", company__name="Weihmann GbR", hours_per_week=7)
    assert [str(shift) for shift in posting.shifts.all()] == ["Di 15:00–18:30", "Mi 16:30–20:00"]


@pytest.mark.django_db
def test_shift_must_end_after_start():
    company = Company.objects.create(name="Testfirma", industry="Tech")
    posting = JobPosting.objects.create(
        company=company, title="Test", kind=JobPosting.Kind.SHORT_JOB,
        workplace=JobPosting.Workplace.ONSITE, schedule=JobPosting.Schedule.FIXED,
        hourly_wage=Decimal("15.00"), hours_per_week=4,
    )

    with pytest.raises(IntegrityError):
        Shift.objects.create(posting=posting, weekday=0, start=time(18, 0), end=time(14, 0))
