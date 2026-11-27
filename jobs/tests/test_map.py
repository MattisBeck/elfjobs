from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from jobs.geo import BERLIN_MITTE, haversine_km, parse_start
from jobs.models import Company, JobPosting

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
