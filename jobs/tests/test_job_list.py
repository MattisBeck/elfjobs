from decimal import Decimal

import pytest

from jobs.models import Company, JobPosting


def make_posting(title, kind, workplace, wage):
    company, _ = Company.objects.get_or_create(name="Testfirma", industry="Tech")
    return JobPosting.objects.create(
        company=company,
        title=title,
        kind=kind,
        workplace=workplace,
        schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal(wage),
        hours_per_week=10,
    )


@pytest.fixture
def postings(db):
    Kind, Workplace = JobPosting.Kind, JobPosting.Workplace
    return {
        "student_remote": make_posting("Werkstudent Remote", Kind.WORKING_STUDENT, Workplace.REMOTE, "20.00"),
        "student_onsite": make_posting("Werkstudent Vor Ort", Kind.WORKING_STUDENT, Workplace.ONSITE, "18.00"),
        "short_remote": make_posting("Kurzjob Remote", Kind.SHORT_JOB, Workplace.REMOTE, "15.00"),
        "short_onsite": make_posting("Kurzjob Vor Ort", Kind.SHORT_JOB, Workplace.ONSITE, "16.50"),
    }


def titles(response):
    return [p.title for p in response.context["postings"]]


def test_lists_all_postings_sorted_by_wage(client, postings):
    response = client.get("/jobs/")

    assert titles(response) == [
        "Werkstudent Remote", "Werkstudent Vor Ort", "Kurzjob Vor Ort", "Kurzjob Remote",
    ]
    content = response.content.decode()
    assert "4 Stellen" in content
    assert "20,00 €" in content


def test_filter_by_kind(client, postings):
    response = client.get("/jobs/?filter=kurzjob")

    assert titles(response) == ["Kurzjob Vor Ort", "Kurzjob Remote"]


def test_two_kinds_show_both(client, postings):
    response = client.get("/jobs/?filter=werkstudent&filter=kurzjob")

    assert len(titles(response)) == 4


def test_remote_combines_with_kind(client, postings):
    response = client.get("/jobs/?filter=kurzjob&filter=remote")

    assert titles(response) == ["Kurzjob Remote"]


def test_unknown_filter_is_ignored(client, postings):
    response = client.get("/jobs/?filter=quatsch")

    assert len(titles(response)) == 4


def test_chip_links_toggle_filters(client, postings):
    chips = client.get("/jobs/?filter=remote").context["chips"]

    by_label = {chip["label"]: chip for chip in chips}
    assert by_label["Remote"]["active"]
    assert by_label["Remote"]["url"] == "/jobs/"
    assert by_label["Kurzjob"]["url"] == "/jobs/?filter=remote&filter=kurzjob"


def test_rows_link_to_detail(client, postings):
    content = client.get("/jobs/").content.decode()

    assert f'href="/jobs/{postings["short_onsite"].pk}/"' in content


def test_detail_page_and_404(client, postings):
    assert client.get(f'/jobs/{postings["short_onsite"].pk}/').status_code == 200
    assert client.get("/jobs/999999/").status_code == 404
