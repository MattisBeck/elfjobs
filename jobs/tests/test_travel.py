import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest
from django.core.cache import cache

from jobs.models import JobPosting
from jobs.travel import MAX_TRAVEL_REQUESTS, travel_minutes, travel_times

# Gekürzte echte Antwort der VBB-API: Berlin Hbf -> HPI (Griebnitzsee), 35 min.
FIXTURE = Path(__file__).parent / "fixtures" / "vbb_journey.json"

HAUPTBAHNHOF = (52.525, 13.369)
HPI = (52.394, 13.133)


@pytest.fixture(autouse=True)
def empty_cache():
    cache.clear()
    yield
    cache.clear()


def api_answers(mock_urlopen, body):
    """Lässt das gemockte urlopen mit body (bytes) antworten."""
    mock_urlopen.return_value.__enter__.return_value.read.return_value = body


def fixture_body():
    return FIXTURE.read_bytes()


@patch("jobs.travel.urlopen")
def test_minutes_from_first_journey(mock_urlopen):
    api_answers(mock_urlopen, fixture_body())

    assert travel_minutes(HAUPTBAHNHOF, HPI) == 35


@patch("jobs.travel.urlopen")
def test_request_uses_coordinates_and_timeout(mock_urlopen, settings):
    settings.TRAVEL_API_URL = "https://example.test"
    settings.TRAVEL_API_TIMEOUT = 3
    api_answers(mock_urlopen, fixture_body())

    travel_minutes(HAUPTBAHNHOF, HPI)

    request = mock_urlopen.call_args.args[0]
    assert request.full_url.startswith("https://example.test/journeys?")
    assert "from.latitude=52.525" in request.full_url
    assert "to.longitude=13.133" in request.full_url
    assert "results=1" in request.full_url
    assert mock_urlopen.call_args.kwargs["timeout"] == 3


@patch("jobs.travel.urlopen")
def test_planned_times_when_realtime_missing(mock_urlopen):
    data = json.loads(fixture_body())
    data["journeys"][0]["legs"][0]["departure"] = None
    data["journeys"][0]["legs"][-1]["arrival"] = None
    api_answers(mock_urlopen, json.dumps(data).encode())

    assert travel_minutes(HAUPTBAHNHOF, HPI) == 35


@patch("jobs.travel.urlopen", side_effect=TimeoutError("timed out"))
def test_timeout_gives_none(mock_urlopen):
    assert travel_minutes(HAUPTBAHNHOF, HPI) is None


@patch("jobs.travel.urlopen")
def test_http_error_gives_none(mock_urlopen):
    mock_urlopen.side_effect = HTTPError("https://x", 503, "Service Unavailable", {}, None)

    assert travel_minutes(HAUPTBAHNHOF, HPI) is None


@patch("jobs.travel.urlopen", side_effect=URLError("no network"))
def test_network_error_gives_none(mock_urlopen):
    assert travel_minutes(HAUPTBAHNHOF, HPI) is None


@patch("jobs.travel.urlopen")
def test_broken_json_gives_none(mock_urlopen):
    api_answers(mock_urlopen, b"<html>kein JSON</html>")

    assert travel_minutes(HAUPTBAHNHOF, HPI) is None


@patch("jobs.travel.urlopen")
def test_unexpected_format_gives_none(mock_urlopen):
    api_answers(mock_urlopen, b'{"journeys": [{"legs": []}]}')

    assert travel_minutes(HAUPTBAHNHOF, HPI) is None


@patch("jobs.travel.urlopen")
def test_no_connection_gives_none(mock_urlopen):
    api_answers(mock_urlopen, b'{"journeys": []}')

    assert travel_minutes(HAUPTBAHNHOF, HPI) is None


@patch("jobs.travel.urlopen")
def test_second_call_comes_from_cache(mock_urlopen):
    api_answers(mock_urlopen, fixture_body())

    assert travel_minutes(HAUPTBAHNHOF, HPI) == 35
    # Etwas andere Koordinaten, gleich nach Rundung auf 3 Stellen.
    assert travel_minutes((52.5251, 13.3689), HPI) == 35

    assert mock_urlopen.call_count == 1


@patch("jobs.travel.urlopen")
def test_no_connection_is_cached(mock_urlopen):
    api_answers(mock_urlopen, b'{"journeys": []}')

    assert travel_minutes(HAUPTBAHNHOF, HPI) is None
    assert travel_minutes(HAUPTBAHNHOF, HPI) is None

    assert mock_urlopen.call_count == 1


@patch("jobs.travel.urlopen")
def test_errors_are_not_cached(mock_urlopen):
    mock_urlopen.side_effect = TimeoutError("timed out")
    assert travel_minutes(HAUPTBAHNHOF, HPI) is None

    mock_urlopen.side_effect = None
    api_answers(mock_urlopen, fixture_body())
    assert travel_minutes(HAUPTBAHNHOF, HPI) == 35

    assert mock_urlopen.call_count == 2


def posting(id, latitude=None, longitude=None):
    """Ungespeicherte Stelle, reicht für travel_times (braucht keine Datenbank)."""
    return JobPosting(id=id, latitude=latitude, longitude=longitude)


def located_posting(id):
    # Jede Stelle an einem eigenen Ort, damit der Cache nicht greift.
    return posting(id, Decimal("52.400") + Decimal(id) / 100, Decimal("13.100"))


@patch("jobs.travel.urlopen")
def test_travel_times_returns_minutes_per_posting(mock_urlopen):
    api_answers(mock_urlopen, fixture_body())

    times = travel_times(HAUPTBAHNHOF, [located_posting(1), located_posting(2)])

    assert times == {1: 35, 2: 35}


@patch("jobs.travel.urlopen")
def test_travel_times_asks_at_most_limit_postings(mock_urlopen):
    api_answers(mock_urlopen, fixture_body())
    postings = [located_posting(id) for id in range(1, 31)]

    times = travel_times(HAUPTBAHNHOF, postings, limit=5)

    assert mock_urlopen.call_count == 5
    assert sorted(times) == [1, 2, 3, 4, 5]


@patch("jobs.travel.urlopen")
def test_travel_times_default_limit(mock_urlopen):
    api_answers(mock_urlopen, fixture_body())
    postings = [located_posting(id) for id in range(1, 31)]

    travel_times(HAUPTBAHNHOF, postings)

    assert mock_urlopen.call_count == MAX_TRAVEL_REQUESTS == 20


@patch("jobs.travel.urlopen")
def test_travel_times_skips_postings_without_location(mock_urlopen):
    api_answers(mock_urlopen, fixture_body())
    postings = [posting(1), located_posting(2), posting(3), located_posting(4)]

    times = travel_times(HAUPTBAHNHOF, postings, limit=2)

    assert mock_urlopen.call_count == 2
    assert times == {2: 35, 4: 35}


@patch("jobs.travel.urlopen")
def test_travel_times_leaves_out_failed_postings(mock_urlopen):
    mock_urlopen.side_effect = URLError("no network")

    assert travel_times(HAUPTBAHNHOF, [located_posting(1)]) == {}
