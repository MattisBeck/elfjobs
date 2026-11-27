from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command

from jobs.models import Company, JobPosting, TravelTime
from jobs.travel import START_POINTS

# Gekürzte echte Antwort der VBB-API, 35 min.
FIXTURE = Path(__file__).parent / "fixtures" / "vbb_journey.json"


@pytest.fixture
def postings(db):
    company = Company.objects.create(name="Testfirma", industry="Tech")

    def make(title, lat=None, lon=None):
        return JobPosting.objects.create(
            company=company, title=title, kind=JobPosting.Kind.SHORT_JOB,
            workplace=JobPosting.Workplace.ONSITE, schedule=JobPosting.Schedule.FLEXIBLE,
            hourly_wage=Decimal("16.00"), hours_per_week=10,
            latitude=Decimal(lat) if lat else None, longitude=Decimal(lon) if lon else None,
        )

    # Zwei Stellen am selben Ort (nach Rundung), eine woanders, eine ohne Ort.
    return [
        make("A", "52.500100", "13.400000"),
        make("B", "52.500200", "13.400000"),
        make("C", "52.450000", "13.300000"),
        make("Remote"),
    ]


def warm(*args):
    """Führt den Befehl ohne Pause aus, mit gemockter API. Gibt (Ausgabe, urlopen-Mock) zurück."""
    out = StringIO()
    with patch("jobs.management.commands.warm_travel_cache.sleep"), \
            patch("jobs.travel.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = FIXTURE.read_bytes()
        call_command("warm_travel_cache", *args, stdout=out)
    return out.getvalue(), mock_urlopen


def test_warms_each_destination_once_per_start_point(postings):
    output, mock_urlopen = warm()

    # 2 Ziele (A und B liegen zusammen) für jeden festen Startpunkt.
    assert mock_urlopen.call_count == 2 * len(START_POINTS)
    assert TravelTime.objects.count() == 2 * len(START_POINTS)
    assert "HPI / Griebnitzsee: 2 Ziele offen" in output
    assert f"{2 * len(START_POINTS)} Anreisezeiten gespeichert, 0 Fehler" in output


def test_only_one_start_point(postings):
    output, mock_urlopen = warm("--startpunkt", "berlin-hbf")

    assert mock_urlopen.call_count == 2
    assert "Berlin Hbf" in output
    assert "HPI" not in output


def test_skips_fresh_entries_and_refreshes_old_ones(postings):
    warm("--startpunkt", "hpi")
    TravelTime.objects.filter(dest_lat=Decimal("52.450")).update(
        fetched_at=TravelTime.objects.first().fetched_at - timedelta(days=8)
    )

    output, mock_urlopen = warm("--startpunkt", "hpi")

    assert mock_urlopen.call_count == 1
    assert "1 Ziele offen, 2 Stellen schon gespeichert" in output


def test_errors_are_counted_not_saved(postings):
    out = StringIO()
    with patch("jobs.management.commands.warm_travel_cache.sleep"), \
            patch("jobs.travel.urlopen", side_effect=TimeoutError("timed out")):
        call_command("warm_travel_cache", "--startpunkt", "hpi", stdout=out)

    assert not TravelTime.objects.exists()
    assert "0 Anreisezeiten gespeichert, 2 Fehler" in out.getvalue()


def test_stops_after_errors_in_a_row(postings):
    company = postings[0].company
    for number in range(10):
        JobPosting.objects.create(
            company=company, title=f"Weitere {number}", kind=JobPosting.Kind.SHORT_JOB,
            workplace=JobPosting.Workplace.ONSITE, schedule=JobPosting.Schedule.FLEXIBLE,
            hourly_wage=Decimal("16.00"), hours_per_week=10,
            latitude=Decimal("52.3") + Decimal(number) / 100, longitude=Decimal("13.5"),
        )
    out = StringIO()
    with patch("jobs.management.commands.warm_travel_cache.sleep"), \
            patch("jobs.travel.urlopen", side_effect=TimeoutError("timed out")) as mock_urlopen:
        call_command("warm_travel_cache", stdout=out)

    # 12 Ziele je Startpunkt, aber nach 5 Fehlern ist ganz Schluss (auch für die übrigen Startpunkte).
    assert mock_urlopen.call_count == 5
    assert "5 Fehler hintereinander" in out.getvalue()


def test_ctrl_c_keeps_what_was_saved(postings):
    out = StringIO()
    # Strg+C während der Pause nach der ersten Anfrage.
    with patch("jobs.management.commands.warm_travel_cache.sleep", side_effect=KeyboardInterrupt), \
            patch("jobs.travel.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = FIXTURE.read_bytes()
        call_command("warm_travel_cache", stdout=out)

    assert TravelTime.objects.count() == 1
    assert "Abgebrochen." in out.getvalue()
