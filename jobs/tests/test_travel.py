import json
import threading
import time
from datetime import timedelta
from decimal import Decimal
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from jobs.models import JobPosting, TravelTime
from jobs.travel import (
    START_POINTS,
    cached_travel_times,
    fetch_travel_times,
    save_minutes,
    travel_minutes,
    travel_start,
)

# Alle Tests hier speichern in TravelTime, brauchen also die Test-Datenbank.
pytestmark = pytest.mark.django_db

# Gekürzte echte Antwort der VBB-API: Berlin Hbf -> HPI (Griebnitzsee), 35 min.
FIXTURE = Path(__file__).parent / "fixtures" / "vbb_journey.json"

# Wedding: kein fester Startpunkt in der Nähe, wird nur gerundet.
WEDDING = (52.549, 13.359)
HPI = (52.394, 13.133)


def api_answers(mock_urlopen, body):
    """Lässt das gemockte urlopen mit body (bytes) antworten."""
    mock_urlopen.return_value.__enter__.return_value.read.return_value = body


def fixture_body():
    return FIXTURE.read_bytes()


@patch("jobs.travel.urlopen")
def test_minutes_from_first_journey(mock_urlopen):
    api_answers(mock_urlopen, fixture_body())

    assert travel_minutes(WEDDING, HPI) == 35


@patch("jobs.travel.urlopen")
def test_request_uses_coordinates_and_timeout(mock_urlopen, settings):
    settings.TRAVEL_API_URL = "https://example.test"
    settings.TRAVEL_API_TIMEOUT = 3
    api_answers(mock_urlopen, fixture_body())

    travel_minutes(WEDDING, HPI)

    request = mock_urlopen.call_args.args[0]
    assert request.full_url.startswith("https://example.test/journeys?")
    assert "from.latitude=52.549" in request.full_url
    assert "to.longitude=13.133" in request.full_url
    assert "results=1" in request.full_url
    assert mock_urlopen.call_args.kwargs["timeout"] == 3


@patch("jobs.travel.urlopen")
def test_start_is_rounded_before_sending(mock_urlopen):
    api_answers(mock_urlopen, fixture_body())

    travel_minutes((52.549123, 13.358876), HPI)

    request = mock_urlopen.call_args.args[0]
    assert "from.latitude=52.549&" in request.full_url
    assert "from.longitude=13.359&" in request.full_url


def test_start_near_fixed_point_snaps_to_it():
    _label, hpi = START_POINTS["hpi"]

    # Etwa 200 m neben dem HPI: rastet ein. Weit weg: nur gerundet.
    assert travel_start((hpi[0] + 0.0015, hpi[1] + 0.001)) == hpi
    assert travel_start((52.549123, 13.358876)) == (52.549, 13.359)


@patch("jobs.travel.urlopen")
def test_planned_times_when_realtime_missing(mock_urlopen):
    data = json.loads(fixture_body())
    data["journeys"][0]["legs"][0]["departure"] = None
    data["journeys"][0]["legs"][-1]["arrival"] = None
    api_answers(mock_urlopen, json.dumps(data).encode())

    assert travel_minutes(WEDDING, HPI) == 35


@pytest.mark.parametrize("error", [
    TimeoutError("timed out"),
    HTTPError("https://x", 503, "Service Unavailable", {}, None),
    URLError("no network"),
    IncompleteRead(b"{"),  # http.client.HTTPException
    AttributeError("'list' object has no attribute 'get'"),
])
def test_api_errors_give_none_and_are_not_saved(error):
    with patch("jobs.travel.urlopen", side_effect=error):
        assert travel_minutes(WEDDING, HPI) is None

    assert not TravelTime.objects.exists()


@pytest.mark.parametrize("body", [b"<html>kein JSON</html>", b'{"journeys": [{"legs": []}]}', b"[]"])
@patch("jobs.travel.urlopen")
def test_broken_answers_give_none(mock_urlopen, body):
    api_answers(mock_urlopen, body)

    assert travel_minutes(WEDDING, HPI) is None
    assert not TravelTime.objects.exists()


@patch("jobs.travel.urlopen")
def test_no_connection_is_saved(mock_urlopen):
    api_answers(mock_urlopen, b'{"journeys": []}')

    assert travel_minutes(WEDDING, HPI) is None
    assert travel_minutes(WEDDING, HPI) is None

    assert mock_urlopen.call_count == 1
    assert TravelTime.objects.get().minutes is None


@patch("jobs.travel.urlopen")
def test_shifted_start_comes_from_cache(mock_urlopen):
    api_answers(mock_urlopen, fixture_body())

    assert travel_minutes(WEDDING, HPI) == 35
    # Etwa 40 m daneben, gleich nach Rundung auf 3 Stellen.
    assert travel_minutes((52.5493, 13.3588), HPI) == 35

    assert mock_urlopen.call_count == 1
    assert TravelTime.objects.count() == 1


@patch("jobs.travel.urlopen")
def test_errors_are_retried(mock_urlopen):
    mock_urlopen.side_effect = TimeoutError("timed out")
    assert travel_minutes(WEDDING, HPI) is None

    mock_urlopen.side_effect = None
    api_answers(mock_urlopen, fixture_body())
    assert travel_minutes(WEDDING, HPI) == 35

    assert mock_urlopen.call_count == 2


@patch("jobs.travel.urlopen")
def test_entries_older_than_7_days_count_as_missing(mock_urlopen):
    save_minutes(WEDDING, HPI, 50)
    TravelTime.objects.update(fetched_at=TravelTime.objects.get().fetched_at - timedelta(days=8))
    api_answers(mock_urlopen, fixture_body())

    assert cached_travel_times(WEDDING, [located_posting(1, HPI)]) == {}
    assert travel_minutes(WEDDING, HPI) == 35
    assert mock_urlopen.call_count == 1
    assert TravelTime.objects.get().minutes == 35


def located_posting(id, at=None):
    """Ungespeicherte Stelle, reicht für die Funktionen hier. Ohne at an einem eigenen Ort."""
    lat, lon = at or (Decimal("52.400") + Decimal(id) / 100, Decimal("13.100"))
    return JobPosting(id=id, latitude=Decimal(str(lat)), longitude=Decimal(str(lon)))


@patch("jobs.travel.urlopen")
def test_cached_travel_times_never_asks_api(mock_urlopen):
    save_minutes(WEDDING, (52.41, 13.1), 20)
    save_minutes(WEDDING, (52.42, 13.1), None)
    postings = [located_posting(1), located_posting(2), located_posting(3), JobPosting(id=4)]

    assert cached_travel_times(WEDDING, postings) == {1: 20, 2: None}
    assert mock_urlopen.call_count == 0


@patch("jobs.travel.urlopen")
def test_fetch_travel_times_asks_only_missing(mock_urlopen):
    save_minutes(WEDDING, (52.41, 13.1), 20)
    api_answers(mock_urlopen, fixture_body())
    # Stellen 2 und 3 am selben Ort: eine Anfrage reicht.
    postings = [located_posting(1), located_posting(2), located_posting(3, (52.42, 13.1)), JobPosting(id=4)]

    times = fetch_travel_times(WEDDING, postings)

    assert times == {1: 20, 2: 35, 3: 35}
    assert mock_urlopen.call_count == 1
    assert TravelTime.objects.count() == 2


@pytest.fixture
def release():
    """Gibt hängende gemockte Anfragen am Testende frei, damit keine Threads übrig bleiben."""
    event = threading.Event()
    yield event
    event.set()


def slow_api(slow_latitude, release):
    """Ersatz für urlopen: Ziele mit slow_latitude hängen bis zu 10 s, die anderen antworten sofort."""
    def fake_urlopen(request, timeout):
        if f"to.latitude={slow_latitude}&" in request.full_url:
            release.wait(10)
            raise TimeoutError("timed out")
        response = MagicMock()
        response.__enter__.return_value.read.return_value = fixture_body()
        return response
    return fake_urlopen


def test_fetch_travel_times_keeps_budget_with_partial_result(release):
    postings = [located_posting(1), located_posting(2), located_posting(3)]

    with patch("jobs.travel.urlopen", side_effect=slow_api(52.42, release)):
        began = time.monotonic()
        times = fetch_travel_times(WEDDING, postings, budget=0.5)
        elapsed = time.monotonic() - began

    assert elapsed < 1.5
    assert times == {1: 35, 3: 35}
    assert TravelTime.objects.count() == 2
