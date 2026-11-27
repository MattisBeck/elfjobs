import threading
import time
from decimal import Decimal
from http.client import IncompleteRead
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from jobs.geo import BERLIN_MITTE, haversine_km, parse_start
from jobs.models import Company, JobPosting
from jobs.travel import START_POINTS, save_minutes

# Gekürzte echte Antwort der VBB-API, 35 min (wie in test_travel.py).
FIXTURE = Path(__file__).parent / "fixtures" / "vbb_journey.json"

ALEXANDERPLATZ = (52.5219, 13.4132)
POTSDAM_HBF = (52.3917, 13.0670)


def make_posting(title, workplace=JobPosting.Workplace.ONSITE, kind=JobPosting.Kind.SHORT_JOB, at=None):
    company, _ = Company.objects.get_or_create(name="Testfirma", industry="Tech")
    lat, lon = at if at else (None, None)
    return JobPosting.objects.create(
        company=company,
        title=title,
        kind=kind,
        workplace=workplace,
        schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal("16.00"),
        hours_per_week=10,
        latitude=Decimal(str(lat)) if lat is not None else None,
        longitude=Decimal(str(lon)) if lon is not None else None,
    )


@pytest.fixture
def postings(db):
    Workplace, Kind = JobPosting.Workplace, JobPosting.Kind
    return {
        "potsdam": make_posting("Potsdam", at=POTSDAM_HBF),
        "alex": make_posting("Alexanderplatz", at=ALEXANDERPLATZ),
        "spandau": make_posting("Spandau", kind=Kind.WORKING_STUDENT, at=(52.5345, 13.1976)),
        "remote": make_posting("Remote", workplace=Workplace.REMOTE, kind=Kind.WORKING_STUDENT),
    }


def titles(postings):
    return [posting.title for posting in postings]


def test_haversine_alexanderplatz_to_potsdam():
    assert haversine_km(*ALEXANDERPLATZ, *POTSDAM_HBF) == pytest.approx(27, abs=1)


def test_haversine_same_point_is_zero():
    assert haversine_km(*BERLIN_MITTE, *BERLIN_MITTE) == 0


@pytest.mark.parametrize("lat, lon", [
    (None, None), ("abc", "13.4"), ("52.5", ""), ("91", "13.4"), ("52.5", "-181"), ("nan", "13.4"), ("inf", "0"),
])
def test_parse_start_rejects_invalid_values(lat, lon):
    assert parse_start(lat, lon) is None


def test_parse_start_accepts_valid_values():
    assert parse_start("52.39", "13.07") == (52.39, 13.07)


def test_list_without_start_is_sorted_from_berlin_mitte(client, postings):
    response = client.get("/jobs/karte/")

    assert response.status_code == 200
    assert response.context["start"] == {"lat": BERLIN_MITTE[0], "lon": BERLIN_MITTE[1]}
    assert titles(response.context["nearby"]) == ["Alexanderplatz", "Spandau", "Potsdam"]


def test_list_is_sorted_from_start_point(client, postings):
    response = client.get("/jobs/karte/?lat=52.3917&lon=13.0670")

    assert response.status_code == 200
    assert titles(response.context["nearby"]) == ["Potsdam", "Spandau", "Alexanderplatz"]
    assert response.context["nearby"][0].distance_km == 0
    # Deutsches Komma in der Anzeige
    content = response.content.decode()
    assert "18,2 km" in content
    assert "27,6 km" in content


@pytest.mark.parametrize("query", ["lat=abc&lon=13", "lat=95&lon=13", "lat=52.5", "lat=52&lon=200"])
def test_invalid_start_falls_back_to_berlin_mitte(client, postings, query):
    response = client.get(f"/jobs/karte/?{query}")

    assert response.status_code == 200
    assert response.context["start"] == {"lat": BERLIN_MITTE[0], "lon": BERLIN_MITTE[1]}
    assert not response.context["has_start"]


def test_remote_postings_have_own_section_without_distance(client, postings):
    response = client.get("/jobs/karte/")

    assert titles(response.context["remote"]) == ["Remote"]
    assert "Remote" not in titles(response.context["nearby"])
    assert not hasattr(response.context["remote"][0], "distance_km")
    assert "Remote und ohne Adresse" in response.content.decode()


def test_markers_contain_only_postings_with_location(client, postings):
    response = client.get("/jobs/karte/")

    data = response.context["markers"]
    assert sorted(marker["title"] for marker in data) == ["Alexanderplatz", "Potsdam", "Spandau"]
    alex = next(marker for marker in data if marker["title"] == "Alexanderplatz")
    assert alex["lat"] == ALEXANDERPLATZ[0]
    assert alex["url"] == f"/jobs/{postings['alex'].pk}/"
    assert alex["wage"] == f"{postings['alex'].effective_wage} €".replace(".", ",")
    assert 'id="map-markers"' in response.content.decode()


def test_marker_json_is_escaped(client, db):
    make_posting("</script><script>alert(1)</script>", at=ALEXANDERPLATZ)

    content = client.get("/jobs/karte/").content.decode()

    assert "</script><script>alert(1)" not in content
    assert "\\u003C/script\\u003E" in content


def test_filters_work_on_map(client, postings):
    response = client.get("/jobs/karte/?filter=werkstudent")

    assert titles(response.context["nearby"]) == ["Spandau"]
    assert titles(response.context["remote"]) == ["Remote"]
    assert [marker["title"] for marker in response.context["markers"]] == ["Spandau"]

    response = client.get("/jobs/karte/?q=Potsdam")
    assert titles(response.context["nearby"]) == ["Potsdam"]
    assert response.context["remote"] == []


def test_chips_stay_on_map_and_keep_start_point(client, postings):
    response = client.get("/jobs/karte/?filter=kurzjob&lat=52.39&lon=13.07")

    urls = {chip["label"]: chip["url"] for chip in response.context["chips"]}
    assert urls["Werkstudent"] == "/jobs/karte/?filter=kurzjob&filter=werkstudent&lat=52.39&lon=13.07"
    assert urls["Kurzjob"] == "/jobs/karte/?lat=52.39&lon=13.07"


def test_chips_without_start_point_have_no_lat_lon(client, postings):
    response = client.get("/jobs/karte/?lat=abc&lon=13")

    for chip in response.context["chips"]:
        assert "lat=" not in chip["url"]


def test_detail_links_keep_filters(client, postings):
    response = client.get("/jobs/karte/?filter=kurzjob")

    assert f'href="/jobs/{postings["alex"].pk}/?filter=kurzjob"' in response.content.decode()


def test_navigation_links_to_map(client, postings):
    map_page = client.get("/jobs/karte/").content.decode()
    list_page = client.get("/jobs/?filter=remote").content.decode()

    assert '<a href="/jobs/karte/" aria-current="page">Karte</a>' in map_page
    assert '<a href="/jobs/karte/?filter=remote">Auf der Karte ansehen</a>' in list_page


def test_query_count_does_not_grow_with_postings(client, postings):
    with CaptureQueriesContext(connection) as few:
        client.get("/jobs/karte/")
    for number in range(10):
        make_posting(f"Weitere {number}", at=(52.5 + number / 100, 13.4))
        make_posting(f"Remote {number}", workplace=JobPosting.Workplace.REMOTE)
    with CaptureQueriesContext(connection) as many:
        client.get("/jobs/karte/")

    assert len(many) == len(few)


# Anreisedauer (#22, #74): urlopen gemockt, kein echtes Netz. Die Seite liest nur aus
# TravelTime; der JSON-Endpunkt fragt fehlende Zeiten nach.

@pytest.fixture
def release():
    """Gibt hängende gemockte Anfragen am Testende frei, damit keine Threads übrig bleiben."""
    event = threading.Event()
    yield event
    event.set()


def save_for(postings, minutes_by_title, start=BERLIN_MITTE):
    """Speichert Anreisezeiten wie aus der API, je Titel einer Stelle."""
    for posting in postings.values():
        if posting.title in minutes_by_title:
            save_minutes(start, (posting.latitude, posting.longitude), minutes_by_title[posting.title])


def failing_urlopen(*args, **kwargs):
    raise AssertionError("Die Kartenseite darf die API nicht fragen.")


def test_distance_sorting_does_not_ask_api(client, postings):
    with patch("jobs.travel.urlopen") as mock_urlopen:
        response = client.get("/jobs/karte/")

    assert mock_urlopen.call_count == 0
    assert response.context["travel_hint"] == ""
    content = response.content.decode()
    assert "min mit ÖPNV" not in content
    assert "nachgeladen" not in content


def test_sorted_by_travel_minutes(client, postings):
    save_for(postings, {"Alexanderplatz": 40, "Spandau": 25, "Potsdam": 30})
    with patch("jobs.travel.urlopen", side_effect=failing_urlopen):
        response = client.get("/jobs/karte/?sortierung=anreise")

    assert titles(response.context["nearby"]) == ["Spandau", "Potsdam", "Alexanderplatz"]
    assert response.context["travel_hint"] == ""
    assert response.context["travel_url"] == ""
    content = response.content.decode()
    assert "ca. 25 min mit ÖPNV" in content
    assert "sortiert nach Anreisedauer" in content
    assert "für die 20 nächsten Stellen nach Luftlinie nachgeladen" in content
    spandau = next(marker for marker in response.context["markers"] if marker["title"] == "Spandau")
    assert spandau["travel"] == "ca. 25 min mit ÖPNV"


def test_equal_minutes_sorted_by_distance(client, postings):
    save_for(postings, {"Alexanderplatz": 30, "Spandau": 30, "Potsdam": 30})
    response = client.get("/jobs/karte/?sortierung=anreise")

    assert titles(response.context["nearby"]) == ["Alexanderplatz", "Spandau", "Potsdam"]


def test_postings_without_minutes_come_last_by_distance(client, postings):
    wedding = make_posting("Wedding", at=(52.55, 13.36))
    save_for(postings, {"Potsdam": 30})
    response = client.get("/jobs/karte/?sortierung=anreise")

    # Potsdam mit Minuten zuerst, die übrigen nach Luftlinie ab Berlin-Mitte.
    assert titles(response.context["nearby"]) == ["Potsdam", "Alexanderplatz", "Wedding", "Spandau"]
    assert response.context["travel_hint"] == "Anreisedauer fehlt noch für einige Stellen, diese nach Luftlinie."
    # Die fehlenden Stellen nach Luftlinie, für den JSON-Endpunkt.
    missing = f"{postings['alex'].pk}%2C{wedding.pk}%2C{postings['spandau'].pk}"
    assert response.context["travel_url"] == f"/jobs/karte/anreise.json?lat=52.52&lon=13.405&stellen={missing}"
    assert 'id="travel-url"' in response.content.decode()


def test_no_connection_counts_as_known(client, postings):
    save_for(postings, {"Alexanderplatz": None, "Spandau": None, "Potsdam": 30})
    response = client.get("/jobs/karte/?sortierung=anreise")

    assert titles(response.context["nearby"]) == ["Potsdam", "Alexanderplatz", "Spandau"]
    assert response.context["travel_url"] == ""


def test_page_never_waits_for_api(client, postings, release):
    """Auch wenn die API hängt: Die Seite fragt sie nicht und ist sofort da (#74)."""
    def hanging_urlopen(*args, **kwargs):
        release.wait(10)
        raise TimeoutError("timed out")

    with patch("jobs.travel.urlopen", side_effect=hanging_urlopen) as mock_urlopen:
        began = time.monotonic()
        response = client.get("/jobs/karte/?sortierung=anreise")
        elapsed = time.monotonic() - began

    assert elapsed < 1
    assert mock_urlopen.call_count == 0
    # Ohne gespeicherte Zeiten: nach Luftlinie, mit Hinweis.
    assert titles(response.context["nearby"]) == ["Alexanderplatz", "Spandau", "Potsdam"]
    content = response.content.decode()
    assert "Anreisedauer fehlt noch für einige Stellen, diese nach Luftlinie." in content
    assert "min mit ÖPNV" not in content
    assert "0,6 km" in content


def test_at_most_20_postings_are_missing(client, db):
    for number in range(25):
        make_posting(f"Stelle {number:02}", at=(52.40 + number / 100, 13.4))
    response = client.get("/jobs/karte/?sortierung=anreise")

    ids = response.context["travel_url"].split("stellen=")[1].split("%2C")
    assert len(ids) == 20


@patch("jobs.management.commands.warm_travel_cache.sleep")
def test_after_warming_map_asks_no_api(mock_sleep, client, postings):
    with patch("jobs.travel.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = FIXTURE.read_bytes()
        call_command("warm_travel_cache", "--startpunkt", "hpi", stdout=StringIO())
    _label, hpi = START_POINTS["hpi"]

    # Klick etwa 150 m neben dem HPI: rastet auf den festen Startpunkt ein.
    with patch("jobs.travel.urlopen", side_effect=failing_urlopen):
        response = client.get(f"/jobs/karte/?sortierung=anreise&lat={hpi[0] + 0.001}&lon={hpi[1] + 0.001}")

    assert [posting.travel_minutes for posting in response.context["nearby"]] == [35, 35, 35]
    assert response.context["travel_url"] == ""
    assert response.context["travel_hint"] == ""


def test_sort_links_keep_start_and_filters(client, postings):
    response = client.get("/jobs/karte/?filter=kurzjob&q=a&lat=52.39&lon=13.07&sortierung=anreise")

    links = {link["label"]: link for link in response.context["sort_links"]}
    assert links["Entfernung"]["url"] == "/jobs/karte/?filter=kurzjob&q=a&lat=52.39&lon=13.07"
    assert links["Anreisedauer"]["url"] == (
        "/jobs/karte/?filter=kurzjob&q=a&lat=52.39&lon=13.07&sortierung=anreise"
    )
    assert links["Anreisedauer"]["active"]
    assert not links["Entfernung"]["active"]
    # Filter-Chips behalten die Sortierung.
    urls = {chip["label"]: chip["url"] for chip in response.context["chips"]}
    assert urls["Remote"] == (
        "/jobs/karte/?filter=kurzjob&filter=remote&q=a&lat=52.39&lon=13.07&sortierung=anreise"
    )


# JSON-Endpunkt /jobs/karte/anreise.json (#74)

def travel_json_url(*postings):
    ids = ",".join(str(posting.pk) for posting in postings)
    return f"/jobs/karte/anreise.json?lat=52.52&lon=13.405&stellen={ids}"


def test_travel_json_fetches_and_saves(client, postings):
    with patch("jobs.travel.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = FIXTURE.read_bytes()
        response = client.get(travel_json_url(postings["alex"], postings["spandau"], postings["remote"]))

    assert response.status_code == 200
    assert response.json() == {str(postings["alex"].pk): 35, str(postings["spandau"].pk): 35}
    assert mock_urlopen.call_count == 2
    # Danach kommt die Karte für diese Stellen ohne API aus.
    with patch("jobs.travel.urlopen", side_effect=failing_urlopen):
        page = client.get("/jobs/karte/?sortierung=anreise")
    assert [posting.travel_minutes for posting in page.context["nearby"]] == [35, 35, None]


def test_travel_json_keeps_budget_with_partial_result(client, postings, release, monkeypatch):
    monkeypatch.setattr("jobs.travel.TRAVEL_BUDGET_SECONDS", 0.5)
    potsdam_lat = round(float(postings["potsdam"].latitude), 3)

    def fake_urlopen(request, timeout):
        if f"to.latitude={potsdam_lat}&" in request.full_url:
            release.wait(10)
            raise TimeoutError("timed out")
        response = MagicMock()
        response.__enter__.return_value.read.return_value = FIXTURE.read_bytes()
        return response

    with patch("jobs.travel.urlopen", side_effect=fake_urlopen):
        began = time.monotonic()
        response = client.get(travel_json_url(postings["alex"], postings["potsdam"], postings["spandau"]))
        elapsed = time.monotonic() - began

    assert elapsed < 1.5
    assert response.json() == {str(postings["alex"].pk): 35, str(postings["spandau"].pk): 35}


@pytest.mark.parametrize("error", [IncompleteRead(b"{"), AttributeError("unerwartetes JSON")])
def test_travel_json_api_errors_give_no_500(client, postings, error):
    with patch("jobs.travel.urlopen", side_effect=error):
        response = client.get(travel_json_url(postings["alex"]))

    assert response.status_code == 200
    assert response.json() == {}


def test_travel_json_without_start_is_400(client, postings):
    response = client.get(f"/jobs/karte/anreise.json?lat=abc&stellen={postings['alex'].pk}")

    assert response.status_code == 400


def test_travel_json_asks_at_most_20_postings(client, db):
    created = [make_posting(f"Stelle {number:02}", at=(52.40 + number / 100, 13.4)) for number in range(25)]
    with patch("jobs.travel.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"journeys": []}'
        response = client.get(travel_json_url(*created) + ",abc")

    assert response.status_code == 200
    assert mock_urlopen.call_count == 20
