from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command

from jobs.models import Company, Fair, JobPosting, Tag


@pytest.fixture
def posting(db):
    fair = Fair.objects.create(name="Jobmesse Potsdam", date=date(2099, 3, 11), location="Potsdam")
    company = Company.objects.create(name="Weihmann GbR", industry="Handel")
    company.fairs.add(fair)
    posting = JobPosting.objects.create(
        company=company,
        title="Promoter*in",
        description="Du sprichst Leute an.",
        kind=JobPosting.Kind.SHORT_JOB,
        workplace=JobPosting.Workplace.HYBRID,
        schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal("16.00"),
        hours_per_week=7,
    )
    posting.tags.add(Tag.objects.create(name="Englisch"))
    return posting


def test_details_tab_shows_posting(client, posting):
    response = client.get(f"/jobs/{posting.pk}/")

    assert response.status_code == 200
    assert response.context["view"] == "details"
    content = response.content.decode()
    for text in [
        "Promoter*in", "Weihmann GbR · Handel", "Kurzjob", "Hybrid", "7 h pro Woche",
        "Du sprichst Leute an.", "Englisch", "Flexibel, du planst selbst",
        "Jobmesse Potsdam, 11.03.2099", "16,00 €", "Merken", "Mit Profil bewerben",
    ]:
        assert text in content


def test_week_tab_is_selected_by_query(client, posting):
    response = client.get(f"/jobs/{posting.pk}/?ansicht=woche")

    assert response.context["view"] == "woche"
    assert response.context["week_url"] == f"/jobs/{posting.pk}/?ansicht=woche"


def test_tabs_and_back_link_keep_filters(client, posting):
    response = client.get(f"/jobs/{posting.pk}/?filter=kurzjob")

    assert response.context["week_url"] == f"/jobs/{posting.pk}/?filter=kurzjob&ansicht=woche"
    assert 'href="/jobs/?filter=kurzjob"' in response.content.decode()


def test_list_column_marks_selected_posting(client, posting):
    response = client.get(f"/jobs/{posting.pk}/")

    assert response.context["selected_pk"] == posting.pk
    assert "is-selected" in response.content.decode()


def test_every_seed_posting_has_a_detail_page(client, db):
    call_command("seed")

    for pk in JobPosting.objects.values_list("pk", flat=True):
        assert client.get(f"/jobs/{pk}/").status_code == 200


def test_unknown_posting_is_404(client, db):
    assert client.get("/jobs/999999/").status_code == 404


def test_fairs_in_one_box_and_only_upcoming(client, posting):
    company = posting.company
    company.fairs.add(Fair.objects.create(name="Karrieretag Berlin", date=date(2099, 4, 22), location="Berlin"))
    company.fairs.add(Fair.objects.create(name="Alte Messe", date=date(2020, 1, 1), location="Berlin"))

    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert content.count('class="fair-box"') == 1
    assert "Karrieretag Berlin, 22.04.2099" in content
    assert "Alte Messe" not in content


def test_chips_on_detail_page_keep_the_posting_open(client, posting):
    response = client.get(f"/jobs/{posting.pk}/?q=promoter")

    by_label = {chip["label"]: chip for chip in response.context["chips"]}
    assert by_label["Kurzjob"]["url"] == f"/jobs/{posting.pk}/?filter=kurzjob&q=promoter"
    assert response.context["week_url"] == f"/jobs/{posting.pk}/?q=promoter&ansicht=woche"


def test_week_view_is_kept_by_filter_form_chips_and_search(client, posting):
    response = client.get(f"/jobs/{posting.pk}/?ansicht=woche&min_lohn=10")
    content = response.content.decode()
    form = content.split('class="filter-form"')[1].split("</form>")[0]
    search = content.split('role="search"')[1].split("</form>")[0]

    assert '<input type="hidden" name="ansicht" value="woche">' in form
    assert '<input type="hidden" name="ansicht" value="woche">' in search
    by_label = {chip["label"]: chip["url"] for chip in response.context["chips"]}
    assert by_label["Kurzjob"] == f"/jobs/{posting.pk}/?filter=kurzjob&min_lohn=10&ansicht=woche"
    assert by_label["ab 10 €"] == f"/jobs/{posting.pk}/?ansicht=woche"
    # Die Tabs setzen die Ansicht selbst.
    assert response.context["details_url"] == f"/jobs/{posting.pk}/?min_lohn=10"
    assert response.context["week_url"] == f"/jobs/{posting.pk}/?min_lohn=10&ansicht=woche"


def test_details_view_adds_no_hidden_view_field(client, posting):
    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert 'name="ansicht"' not in content


def test_unknown_view_falls_back_to_details(client, posting):
    response = client.get(f"/jobs/{posting.pk}/?ansicht=quatsch")

    assert response.context["view"] == "details"


def test_fixed_schedule_is_shown(client, posting):
    posting.schedule = JobPosting.Schedule.FIXED
    posting.save()

    assert "Feste Zeiten" in client.get(f"/jobs/{posting.pk}/").content.decode()


def test_only_one_h1_on_detail_page(client, posting):
    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert content.count("<h1") == 1
