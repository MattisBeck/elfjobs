from datetime import time
from decimal import Decimal

import pytest
from django.core.management import call_command

from jobs.models import Company, JobPosting, Shift

Workplace, Schedule = JobPosting.Workplace, JobPosting.Schedule


def make_posting(workplace, schedule, wage, hours, commute, shifts=0):
    company = Company.objects.create(name="Testfirma", industry="Handel", commute_minutes=commute)
    posting = JobPosting.objects.create(
        company=company, title="Test", kind=JobPosting.Kind.SHORT_JOB, workplace=workplace,
        schedule=schedule, hourly_wage=Decimal(wage), hours_per_week=hours,
    )
    for weekday in range(shifts):
        Shift.objects.create(posting=posting, weekday=weekday, start=time(14), end=time(16))
    return posting


# Beispiele aus docs/design.md, Abschnitt „Effektiver Stundenlohn“
@pytest.mark.django_db
@pytest.mark.parametrize("workplace, schedule, wage, hours, commute, shifts, trips, effective", [
    (Workplace.ONSITE, Schedule.FIXED, "16.00", 7, 18, 2, 2, "13.66"),     # Promoter*in
    (Workplace.ONSITE, Schedule.FIXED, "15.00", 10, 12, 3, 3, "13.39"),    # Controlling
    (Workplace.ONSITE, Schedule.FLEXIBLE, "14.00", 11, 35, 0, 3, "10.62"),  # Aushilfe Lager
    (Workplace.REMOTE, Schedule.FLEXIBLE, "19.50", 11, 20, 0, 0, "19.50"),  # Softwareentwicklung
])
def test_design_examples(workplace, schedule, wage, hours, commute, shifts, trips, effective):
    posting = make_posting(workplace, schedule, wage, hours, commute, shifts)

    assert posting.trips_per_week == trips
    assert posting.effective_wage == Decimal(effective)


@pytest.mark.django_db
def test_hybrid_counts_half_of_the_trips_rounded_up():
    assert make_posting(Workplace.HYBRID, Schedule.FIXED, "16.00", 7, 18, shifts=3).trips_per_week == 2
    assert make_posting(Workplace.HYBRID, Schedule.FLEXIBLE, "16.00", 7, 18).trips_per_week == 1


@pytest.mark.django_db
def test_monthly_wage_and_minijob_limit():
    promoter = make_posting(Workplace.ONSITE, Schedule.FIXED, "16.00", 7, 18, 2)
    controlling = make_posting(Workplace.ONSITE, Schedule.FIXED, "15.00", 10, 12, 3)

    assert promoter.monthly_wage == 485  # 484,96
    assert promoter.is_minijob
    assert controlling.monthly_wage == 650  # 649,50, kaufmännisch aufgerundet
    assert not controlling.is_minijob


@pytest.mark.django_db
def test_list_is_sorted_by_effective_wage(client):
    far = make_posting(Workplace.ONSITE, Schedule.FLEXIBLE, "18.00", 4, 60)  # 1 Fahrt, 2 h Fahrzeit: 18 × 4 / 6 = 12,00
    remote = make_posting(Workplace.REMOTE, Schedule.FLEXIBLE, "15.00", 4, 60)  # effektiv 15,00

    response = client.get("/jobs/")

    assert list(response.context["postings"]) == [remote, far]
    content = response.content.decode()
    assert "sortiert nach effektivem Stundenlohn" in content
    assert "12,00 €" in content and "brutto 18,00 €" in content


@pytest.mark.django_db
def test_detail_shows_wage_calculation(client):
    posting = make_posting(Workplace.ONSITE, Schedule.FIXED, "16.00", 7, 18, 2)

    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    for text in ["16,00 €", "1,2 h", "2 × hin und zurück, je 18 min", "13,66 €", "≈ 485 €",
                 "unter der Minijob-Grenze (603 €)"]:
        assert text in content


@pytest.mark.django_db
def test_seed_examples_have_the_effective_wages_from_the_spec():
    call_command("seed")

    def effective(title, company, hours):
        posting = JobPosting.objects.prefetch_related("shifts").get(
            title=title, company__name=company, hours_per_week=hours, workplace=Workplace.ONSITE,
        )
        return posting.effective_wage

    assert effective("Promoter*in", "Weihmann GbR", 7) == Decimal("13.66")
    assert effective("Werkstudent*in Controlling", "Bauer", 10) == Decimal("13.39")
    assert effective("Aushilfe Lager", "Holsten Förster AG & Co. OHG", 11) == Decimal("10.62")


@pytest.mark.django_db
def test_zero_hours_do_not_break_the_list(client):
    # Im Admin lässt sich eine Stelle mit 0 Stunden anlegen; die Liste darf daran nicht abstürzen.
    posting = make_posting(Workplace.ONSITE, Schedule.FLEXIBLE, "15.00", 0, 20)

    assert posting.effective_wage == Decimal("15.00")
    assert client.get("/jobs/").status_code == 200
