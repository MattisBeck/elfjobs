"""Suchfilter (#71, #77): Stundenlohn ab (brutto), maximale Anreise, Stunden pro Woche, Entfernung auf der Karte."""

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


def test_wage_filter_uses_gross_wage(client, postings):
    response = client.get("/jobs/?min_lohn=17")

    # Fern bleibt (18 € brutto), obwohl der effektive Lohn nur 13,09 € ist.
    # Sortiert wird weiter nach effektivem Lohn.
    assert titles(response) == ["Hybrid", "Fern"]


def test_wage_filter_accepts_comma(client, postings):
    response = client.get("/jobs/?min_lohn=16,5")

    assert titles(response) == ["Hybrid", "Fern"]
    assert "ab 16,5 € brutto" in remove_chips(response)


@pytest.mark.parametrize("value", ["13.90", "13,9", "10", "0"])
def test_wage_at_or_below_legal_minimum_is_no_filter(client, postings, value):
    # Unter den gesetzlichen Mindestlohn darf keine Stelle fallen, ganz links am Regler heißt „egal“.
    response = client.get(f"/jobs/?min_lohn={value}")

    assert titles(response) == ["Hybrid", "Remote", "Nah", "Fern"]
    assert remove_chips(response) == {}
    assert parse_filters(QueryDict(f"min_lohn={value}")) == {}


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
    response = client.get(f"/jobs/karte/?{START}&min_lohn=17")

    assert titles(response, "nearby") == ["Hybrid", "Fern"]
    assert titles(response, "remote") == []


# Kombiniert

def test_filters_combine(client, postings):
    response = client.get("/jobs/?min_lohn=16&max_anreise=20")

    assert titles(response) == ["Nah"]
    assert "1 Stelle" in response.content.decode()


def test_filters_combine_with_chips_and_search(client, postings):
    response = client.get("/jobs/?filter=remote&min_stunden=10")
    assert titles(response) == ["Remote"]

    response = client.get("/jobs/?q=Firma&max_anreise=30&max_stunden=10")
    assert titles(response) == ["Nah"]


def test_count_line_counts_after_filters(client, postings):
    content = client.get("/jobs/?min_lohn=17").content.decode()

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


@pytest.mark.parametrize("query", ["min_lohn=-0", "min_lohn=1e-50", "min_lohn=0.001", "min_lohn=0", "min_stunden=-0"])
def test_zero_and_tiny_minimums_are_no_filter(client, postings, query):
    response = client.get(f"/jobs/?{query}")

    assert titles(response) == ["Hybrid", "Remote", "Nah", "Fern"]
    assert remove_chips(response) == {}


@pytest.mark.parametrize("value", ["-0", "1e-50", "0.0000"])
def test_zero_and_tiny_maximums_count_as_zero(client, postings, value):
    response = client.get(f"/jobs/?max_anreise={value}")

    assert titles(response) == ["Remote"]
    assert list(remove_chips(response)) == ["max. 0 min Anreise"]


@pytest.mark.parametrize("value", ["-0", "0"])
def test_zero_commute_slider_starts_at_zero_not_neutral(client, postings, value):
    form = client.get(f"/jobs/?max_anreise={value}").content.decode().split('class="filter-form"')[1].split("</form>")[0]

    # Der Regler steht auf 0 (nicht auf „egal“ = 60), das JS zeigt dann „max. 0 min“.
    assert 'name="max_anreise" min="0" max="60" step="5" value="0" data-neutral="60" data-text="max. {} min"' in form


def test_max_values_at_neutral_after_rounding_do_not_filter(client, postings):
    response = client.get("/jobs/?max_anreise=59.999&max_stunden=39.999")

    assert remove_chips(response) == {}


def test_parse_filters_rounds_to_two_decimals():
    get = QueryDict("min_lohn=15.499&max_anreise=-0&min_stunden=1e-50")

    assert parse_filters(get) == {"min_lohn": Decimal("15.50"), "max_anreise": Decimal("0")}
    assert str(parse_filters(get)["max_anreise"]) == "0.00"


# Entfernen-Chips

def test_remove_chips_drop_only_their_filter(client, postings):
    response = client.get("/jobs/?filter=kurzjob&q=Firma&min_lohn=15&max_anreise=30&min_stunden=10&max_stunden=20")

    assert remove_chips(response) == {
        "ab 15 € brutto": "/jobs/?filter=kurzjob&q=Firma&max_anreise=30&min_stunden=10&max_stunden=20",
        "max. 30 min Anreise": "/jobs/?filter=kurzjob&q=Firma&min_lohn=15&min_stunden=10&max_stunden=20",
        "10–20 h/Woche": "/jobs/?filter=kurzjob&q=Firma&min_lohn=15&max_anreise=30",
    }
    content = response.content.decode()
    assert 'aria-label="Filter ab 15 € brutto entfernen"' in content
    assert "✕" in content


def test_single_hour_bound_chips(client, postings):
    assert list(remove_chips(client.get("/jobs/?min_stunden=10"))) == ["ab 10 h/Woche"]
    assert list(remove_chips(client.get("/jobs/?max_stunden=20"))) == ["bis 20 h/Woche"]


def test_remove_chip_for_distance_keeps_start_point(client, postings):
    response = client.get(f"/jobs/karte/?{START}&max_km=5&min_lohn=14")

    assert remove_chips(response)["max. 5 km"] == f"/jobs/karte/?min_lohn=14&{START}"
    assert remove_chips(response)["ab 14 € brutto"] == f"/jobs/karte/?max_km=5&{START}"


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
    assert 'type="range" id="filter-min-lohn" name="min_lohn" min="13.9" max="25" step="0.1" value="15"' in form
    assert 'name="max_km"' in form
    assert '<details class="filter-panel" open>' in content


# Schieberegler

def test_sliders_start_at_url_values(client, postings):
    content = client.get(f"/jobs/karte/?{START}&min_lohn=14,5&max_anreise=30&max_km=10&min_stunden=10&max_stunden=20").content.decode()
    form = content.split('class="filter-form"')[1].split("</form>")[0]

    assert 'name="min_lohn" min="13.9" max="25" step="0.1" value="14.5" data-neutral="13.9" data-text="{} € brutto"' in form
    assert 'name="max_anreise" min="0" max="60" step="5" value="30" data-neutral="60"' in form
    assert 'name="max_km" min="1" max="30" step="1" value="10" data-neutral="30"' in form
    assert 'name="min_stunden" min="0" max="40" step="1" value="10" data-neutral="0"' in form
    assert 'name="max_stunden" min="0" max="40" step="1" value="20" data-neutral="40"' in form
    assert '<label for="filter-min-lohn">' in form


def test_sliders_start_neutral_without_filters(client, postings):
    form = client.get(f"/jobs/karte/?{START}").content.decode().split('class="filter-form"')[1].split("</form>")[0]

    assert 'name="min_lohn" min="13.9" max="25" step="0.1" value="13.9"' in form
    assert 'name="max_anreise" min="0" max="60" step="5" value="60"' in form
    assert 'name="max_km" min="1" max="30" step="1" value="30"' in form
    assert 'name="min_stunden" min="0" max="40" step="1" value="0"' in form
    assert 'name="max_stunden" min="0" max="40" step="1" value="40"' in form


@pytest.mark.parametrize("query", [
    "min_lohn=0", "max_anreise=60", "max_anreise=90", "min_stunden=0", "max_stunden=40", "max_stunden=45",
    "min_lohn=0&max_anreise=60&min_stunden=0&max_stunden=40",
])
def test_neutral_slider_values_do_not_filter(client, postings, query):
    response = client.get(f"/jobs/?{query}")

    assert titles(response) == ["Hybrid", "Remote", "Nah", "Fern"]
    assert remove_chips(response) == {}
    assert '<details class="filter-panel">' in response.content.decode()


@pytest.mark.parametrize("query", ["max_km=30", "max_km=50"])
def test_neutral_distance_does_not_filter(client, postings, query):
    response = client.get(f"/jobs/karte/?{START}&{query}")

    assert titles(response, "nearby") == ["Nah", "Hybrid", "Fern"]
    assert remove_chips(response) == {}


def test_neutral_slider_values_are_left_out_of_links(client, postings):
    response = client.get("/jobs/?min_lohn=0&max_anreise=60&min_stunden=10")

    urls = {chip["label"]: chip["url"] for chip in response.context["chips"]}
    assert urls["Remote"] == "/jobs/?filter=remote&min_stunden=10"


def test_values_beyond_slider_range_still_filter(client, postings):
    response = client.get("/jobs/?min_lohn=15,1")
    assert titles(response) == ["Hybrid", "Nah", "Fern"]

    response = client.get("/jobs/?min_lohn=40")
    assert titles(response) == []
    assert "ab 40 € brutto" in remove_chips(response)


def test_filter_panel_closed_without_filters(client, postings):
    content = client.get("/jobs/").content.decode()

    assert '<details class="filter-panel">' in content
    assert "Ganz links: alle Stellen ab Mindestlohn" in content


def test_detail_links_keep_filters(client, postings):
    pk = postings["nah"].pk
    content = client.get("/jobs/?min_lohn=16&max_stunden=16").content.decode()
    assert f'href="/jobs/{pk}/?min_lohn=16&amp;max_stunden=16"' in content

    response = client.get(f"/jobs/{pk}/?min_lohn=16&max_stunden=16")
    assert titles(response) == ["Hybrid", "Nah", "Fern"]
    assert response.context["details_url"] == f"/jobs/{pk}/?min_lohn=16&max_stunden=16"
    assert f'href="/jobs/{postings["hybrid"].pk}/?min_lohn=16&amp;max_stunden=16"' in response.content.decode()


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


def test_max_commute_on_map_uses_travel_minutes_when_sorted_by_travel(client, postings):
    # Nah: Firma sagt 10 min, ÖPNV 45 min. Fern: Firma sagt 45 min, ÖPNV 25 min.
    # Hybrid hat keine ÖPNV-Minuten und bleibt bei der Firmenfahrzeit (25 min).
    minutes = {postings["nah"].id: 45, postings["fern"].id: 25}
    with patch("jobs.views.travel_times", return_value=minutes):
        response = client.get(f"/jobs/karte/?{START}&sortierung=anreise&max_anreise=30")

    assert titles(response, "nearby") == ["Fern", "Hybrid"]
    assert titles(response, "remote") == ["Remote"]
    assert [marker["title"] for marker in response.context["markers"]] == ["Fern", "Hybrid"]


def test_max_commute_on_map_uses_company_time_without_travel_sorting(client, postings):
    with patch("jobs.views.travel_times") as mock_travel_times:
        response = client.get(f"/jobs/karte/?{START}&max_anreise=30")

    assert mock_travel_times.call_count == 0
    assert titles(response, "nearby") == ["Nah", "Hybrid"]


def test_max_commute_help_text_on_map_only(client, postings):
    hint = "Bei Sortierung nach Anreisedauer die ÖPNV-Zeit, sonst die Fahrzeit der Firma."

    assert hint in client.get("/jobs/karte/").content.decode()
    assert hint not in client.get("/jobs/").content.decode()


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


def test_wage_slider_starts_at_legal_minimum(client, postings):
    content = client.get("/jobs/").content.decode()
    form = content.split('class="filter-form"')[1].split("</form>")[0]

    assert "Stundenlohn ab" in form
    assert "Mindestlohn (€ pro Stunde)" not in form
    assert 'type="range" id="filter-min-lohn" name="min_lohn" min="13.9" max="25" step="0.1" value="13.9"' in form


def test_wage_slider_grows_for_higher_values(client, postings):
    content = client.get("/jobs/?min_lohn=40").content.decode()

    assert 'type="range" id="filter-min-lohn" name="min_lohn" min="13.9" max="40" step="0.1" value="40"' in content
