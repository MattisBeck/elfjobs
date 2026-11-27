"""Suchfilter (#71): Mindestlohn, maximale Anreise, Stunden pro Woche, Entfernung auf der Karte."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection
from django.http import QueryDict
from django.test.utils import CaptureQueriesContext

from jobs.filters import MAP_FILTER_FIELDS, parse_filters
from jobs.models import Company, JobPosting

ALEXANDERPLATZ = (52.5219, 13.4132)
POTSDAM_HBF = (52.3917, 13.0670)
SPANDAU = (52.5345, 13.1976)
START = "lat=52.5219&lon=13.4132"


def make_posting(title, workplace, wage, hours, commute, at=None):
    company = Company.objects.create(name=f"Firma {title}", industry="Tech", commute_minutes=commute)
    lat, lon = at if at else (None, None)
    return JobPosting.objects.create(
        company=company,
        title=title,
        kind=JobPosting.Kind.SHORT_JOB,
        workplace=workplace,
        schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal(wage),
        hours_per_week=hours,
        latitude=Decimal(str(lat)) if lat is not None else None,
        longitude=Decimal(str(lon)) if lon is not None else None,
    )


@pytest.fixture
def postings(db):
    Workplace = JobPosting.Workplace
    return {
        # brutto 16 €, 2 Fahrten à 10 min: effektiv 14,77 €
        "nah": make_posting("Nah", Workplace.ONSITE, "16.00", 8, 10, ALEXANDERPLATZ),
        # brutto 18 €, 3 Fahrten à 45 min: effektiv 13,09 €
        "fern": make_posting("Fern", Workplace.ONSITE, "18.00", 12, 45, POTSDAM_HBF),
        # remote: keine Fahrt, effektiv 15,00 €, obwohl die Firma 60 min entfernt ist
        "remote": make_posting("Remote", Workplace.REMOTE, "15.00", 20, 60),
        # hybrid, 2 Fahrten à 25 min: effektiv 15,40 €
        "hybrid": make_posting("Hybrid", Workplace.HYBRID, "17.00", 16, 25, SPANDAU),
    }


def titles(response, key="postings"):
    return [posting.title for posting in response.context[key]]


def remove_chips(response):
    return {chip["label"]: chip["url"] for chip in response.context["chips"] if chip.get("remove")}


def test_effective_wages_of_fixture(postings):
    assert postings["nah"].effective_wage == Decimal("14.77")
    assert postings["fern"].effective_wage == Decimal("13.09")
    assert postings["remote"].effective_wage == Decimal("15.00")
    assert postings["hybrid"].effective_wage == Decimal("15.40")


# Jeder Filter einzeln

def test_without_filters_all_postings(client, postings):
    response = client.get("/jobs/")

    assert titles(response) == ["Hybrid", "Remote", "Nah", "Fern"]
    assert remove_chips(response) == {}


def test_min_wage_uses_effective_wage_not_gross(client, postings):
    response = client.get("/jobs/?min_lohn=15")

    # Fern (18 € brutto) und Nah (16 € brutto) fallen wegen der Fahrzeit raus.
    assert titles(response) == ["Hybrid", "Remote"]


def test_min_wage_accepts_comma(client, postings):
    response = client.get("/jobs/?min_lohn=15,4")

    assert titles(response) == ["Hybrid"]
    assert "ab 15,4 €" in remove_chips(response)


def test_max_commute_counts_remote_as_zero(client, postings):
    assert titles(client.get("/jobs/?max_anreise=30")) == ["Hybrid", "Remote", "Nah"]
    assert titles(client.get("/jobs/?max_anreise=0")) == ["Remote"]


def test_hours_range(client, postings):
    assert titles(client.get("/jobs/?min_stunden=10&max_stunden=16")) == ["Hybrid", "Fern"]
    assert titles(client.get("/jobs/?min_stunden=12")) == ["Hybrid", "Remote", "Fern"]
    assert titles(client.get("/jobs/?max_stunden=8")) == ["Nah"]


def test_max_distance_on_map(client, postings):
    response = client.get(f"/jobs/karte/?{START}&max_km=5")

    assert titles(response, "nearby") == ["Nah"]
    # Remote-Stellen haben keine Entfernung und bleiben im eigenen Abschnitt.
    assert titles(response, "remote") == ["Remote"]
    assert [marker["title"] for marker in response.context["markers"]] == ["Nah"]
    assert "1 Stelle mit Ort" in response.content.decode()

    response = client.get(f"/jobs/karte/?{START}&max_km=20")
    assert titles(response, "nearby") == ["Nah", "Hybrid"]


def test_max_distance_is_ignored_in_list(client, postings):
    response = client.get("/jobs/?max_km=5")

    assert titles(response) == ["Hybrid", "Remote", "Nah", "Fern"]
    assert remove_chips(response) == {}
    assert 'name="max_km"' not in response.content.decode()


def test_map_applies_list_filters(client, postings):
    response = client.get(f"/jobs/karte/?{START}&min_lohn=15")

    assert titles(response, "nearby") == ["Hybrid"]
    assert titles(response, "remote") == ["Remote"]


# Kombiniert

def test_filters_combine(client, postings):
    response = client.get("/jobs/?min_lohn=14&max_anreise=20")

    assert titles(response) == ["Remote", "Nah"]
    assert "2 Stellen" in response.content.decode()


def test_filters_combine_with_chips_and_search(client, postings):
    response = client.get("/jobs/?filter=remote&min_stunden=10")
    assert titles(response) == ["Remote"]

    response = client.get("/jobs/?q=Firma&max_anreise=30&max_stunden=10")
    assert titles(response) == ["Nah"]


def test_count_line_counts_after_filters(client, postings):
    content = client.get("/jobs/?min_lohn=15").content.decode()

    assert "2 Stellen" in content
    assert "4 Stellen" not in content


# Ungültige Werte

@pytest.mark.parametrize("query", [
    "min_lohn=abc", "min_lohn=-5", "min_lohn=", "min_lohn=nan", "min_lohn=inf", "min_lohn=1e999",
    "max_anreise=zehn", "max_anreise=-1", "min_stunden=-3", "max_stunden=x",
    "min_stunden=20&max_stunden=10",
])
def test_invalid_values_are_ignored(client, postings, query):
    response = client.get(f"/jobs/?{query}")

    assert response.status_code == 200
    assert titles(response) == ["Hybrid", "Remote", "Nah", "Fern"]
    assert remove_chips(response) == {}


@pytest.mark.parametrize("query", ["max_km=abc", "max_km=-1", "max_km=inf"])
def test_invalid_distance_is_ignored_on_map(client, postings, query):
    response = client.get(f"/jobs/karte/?{START}&{query}")

    assert response.status_code == 200
    assert titles(response, "nearby") == ["Nah", "Hybrid", "Fern"]


def test_parse_filters_returns_only_valid_values():
    get = QueryDict("min_lohn=15,50&max_anreise=abc&min_stunden=5&max_km=3")

    assert parse_filters(get) == {"min_lohn": Decimal("15.50"), "min_stunden": Decimal("5")}
    assert parse_filters(get, MAP_FILTER_FIELDS)["max_km"] == Decimal("3")


# Entfernen-Chips

def test_remove_chips_drop_only_their_filter(client, postings):
    response = client.get("/jobs/?filter=kurzjob&q=Firma&min_lohn=15&max_anreise=30&min_stunden=10&max_stunden=20")

    assert remove_chips(response) == {
        "ab 15 €": "/jobs/?filter=kurzjob&q=Firma&max_anreise=30&min_stunden=10&max_stunden=20",
        "max. 30 min Anreise": "/jobs/?filter=kurzjob&q=Firma&min_lohn=15&min_stunden=10&max_stunden=20",
        "10–20 h/Woche": "/jobs/?filter=kurzjob&q=Firma&min_lohn=15&max_anreise=30",
    }
    content = response.content.decode()
    assert 'aria-label="Filter ab 15 € entfernen"' in content
    assert "✕" in content


def test_single_hour_bound_chips(client, postings):
    assert list(remove_chips(client.get("/jobs/?min_stunden=10"))) == ["ab 10 h/Woche"]
    assert list(remove_chips(client.get("/jobs/?max_stunden=20"))) == ["bis 20 h/Woche"]


def test_remove_chip_for_distance_keeps_start_point(client, postings):
    response = client.get(f"/jobs/karte/?{START}&max_km=5&min_lohn=14")

    assert remove_chips(response)["max. 5 km"] == f"/jobs/karte/?min_lohn=14&{START}"
    assert remove_chips(response)["ab 14 €"] == f"/jobs/karte/?max_km=5&{START}"


# Filter bleiben erhalten

def test_kind_chips_keep_filters(client, postings):
    response = client.get("/jobs/?min_lohn=15&max_anreise=30")

    urls = {chip["label"]: chip["url"] for chip in response.context["chips"]}
    assert urls["Remote"] == "/jobs/?filter=remote&min_lohn=15&max_anreise=30"


def test_search_keeps_filters(client, postings):
    content = client.get("/jobs/?filter=kurzjob&min_lohn=15&q=Firma").content.decode()

    assert '<input type="hidden" name="filter" value="kurzjob">' in content
    assert '<input type="hidden" name="min_lohn" value="15">' in content
    # q ist das Suchfeld selbst und kommt nicht doppelt als verstecktes Feld.
    assert '<input type="hidden" name="q"' not in content.split('role="search"')[1].split("</form>")[0]


def test_search_on_map_keeps_filters_and_start(client, postings):
    content = client.get(f"/jobs/karte/?{START}&max_km=5&sortierung=entfernung").content.decode()
    search = content.split('role="search"')[1].split("</form>")[0]

    assert '<input type="hidden" name="max_km" value="5">' in search
    assert '<input type="hidden" name="lat" value="52.5219">' in search
    assert '<input type="hidden" name="lon" value="13.4132">' in search


def test_filter_form_keeps_chips_search_and_start(client, postings):
    content = client.get(f"/jobs/karte/?{START}&filter=kurzjob&q=Firma&min_lohn=15").content.decode()
    form = content.split('class="filter-form"')[1].split("</form>")[0]

    assert '<input type="hidden" name="filter" value="kurzjob">' in form
    assert '<input type="hidden" name="q" value="Firma">' in form
    assert '<input type="hidden" name="lat" value="52.5219">' in form
    assert 'name="min_lohn" min="0" step="0.01" inputmode="decimal" value="15"' in form
    assert 'name="max_km"' in form
    assert '<details class="filter-panel" open>' in content


def test_filter_panel_closed_without_filters(client, postings):
    content = client.get("/jobs/").content.decode()

    assert '<details class="filter-panel">' in content
    assert "Fahrzeit ist eingerechnet" in content


def test_detail_links_keep_filters(client, postings):
    pk = postings["remote"].pk
    content = client.get("/jobs/?min_lohn=15&max_stunden=20").content.decode()
    assert f'href="/jobs/{pk}/?min_lohn=15&amp;max_stunden=20"' in content

    response = client.get(f"/jobs/{pk}/?min_lohn=15&max_stunden=20")
    assert titles(response) == ["Hybrid", "Remote"]
    assert response.context["details_url"] == f"/jobs/{pk}/?min_lohn=15&max_stunden=20"
    assert f'href="/jobs/{postings["hybrid"].pk}/?min_lohn=15&amp;max_stunden=20"' in response.content.decode()


def test_map_links_keep_filters(client, postings):
    response = client.get(f"/jobs/karte/?{START}&min_lohn=14&max_km=20")

    sort_urls = {link["label"]: link["url"] for link in response.context["sort_links"]}
    assert sort_urls["Entfernung"] == f"/jobs/karte/?min_lohn=14&max_km=20&{START}"
    assert sort_urls["Anreisedauer"] == f"/jobs/karte/?min_lohn=14&max_km=20&{START}&sortierung=anreise"
    assert response.context["markers"][0]["url"] == f"/jobs/{postings['nah'].pk}/?min_lohn=14&max_km=20"


def test_travel_sorting_keeps_filters(client, postings):
    # Kein echtes Netz: Die Kartenseite fragt die API ohnehin nie (#74), urlopen würde scheitern.
    with patch("jobs.travel.urlopen", side_effect=AssertionError("kein API-Aufruf erwartet")):
        response = client.get(f"/jobs/karte/?{START}&sortierung=anreise&max_km=5")

    assert titles(response, "nearby") == ["Nah"]
    urls = {chip["label"]: chip["url"] for chip in response.context["chips"]}
    assert urls["Kurzjob"] == f"/jobs/karte/?filter=kurzjob&max_km=5&{START}&sortierung=anreise"


def test_list_links_to_map_with_filters(client, postings):
    content = client.get("/jobs/?min_lohn=15").content.decode()

    assert '<a href="/jobs/karte/?min_lohn=15">Auf der Karte ansehen</a>' in content


# Abfragen

@pytest.mark.parametrize("url", [
    "/jobs/?min_lohn=14&max_anreise=30&min_stunden=5&max_stunden=20",
    f"/jobs/karte/?{START}&min_lohn=14&max_anreise=30&max_km=50",
])
def test_query_count_does_not_grow_with_postings(client, postings, url):
    with CaptureQueriesContext(connection) as few:
        client.get(url)
    for number in range(10):
        make_posting(f"Weitere {number}", JobPosting.Workplace.ONSITE, "20.00", 10, 5, (52.5, 13.4))
    with CaptureQueriesContext(connection) as many:
        client.get(url)

    assert len(many) == len(few)
