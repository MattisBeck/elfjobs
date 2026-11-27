from decimal import Decimal

import pytest

from jobs.models import Company, JobPosting, Tag


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

    assert titles(response) == titles(client.get("/jobs/"))


def test_filter_working_students_only(client, postings):
    response = client.get("/jobs/?filter=werkstudent")

    assert titles(response) == ["Werkstudent Remote", "Werkstudent Vor Ort"]


def test_working_student_and_remote(client, postings):
    response = client.get("/jobs/?filter=werkstudent&filter=remote")

    assert titles(response) == ["Werkstudent Remote"]


def test_known_and_unknown_filters_mixed(client, postings):
    response = client.get("/jobs/?filter=remote&filter=quatsch")

    assert titles(response) == ["Werkstudent Remote", "Kurzjob Remote"]


def test_empty_result(client, db):
    content = client.get("/jobs/").content.decode()

    assert "0 Stellen" in content
    assert "Keine Stellen für diese Filter." in content


def test_singular_for_one_posting(client, db):
    make_posting("Einzige Stelle", JobPosting.Kind.SHORT_JOB, JobPosting.Workplace.ONSITE, "15.00")

    assert "1 Stelle<" in client.get("/jobs/").content.decode()


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


def test_search_matches_title_company_and_tag(client, postings):
    postings["short_remote"].tags.add(Tag.objects.create(name="Python"))

    assert titles(client.get("/jobs/?q=vor ort")) == ["Werkstudent Vor Ort", "Kurzjob Vor Ort"]
    assert len(titles(client.get("/jobs/?q=testfirma"))) == 4
    assert titles(client.get("/jobs/?q=python")) == ["Kurzjob Remote"]


def test_search_combines_with_filters_and_chips_keep_it(client, postings):
    response = client.get("/jobs/?filter=werkstudent&q=remote")

    assert titles(response) == ["Werkstudent Remote"]
    by_label = {chip["label"]: chip for chip in response.context["chips"]}
    assert by_label["Werkstudent"]["url"] == "/jobs/?q=remote"


def test_jobs_nav_is_current_on_detail_page(client, postings):
    content = client.get(f'/jobs/{postings["short_onsite"].pk}/').content.decode()

    assert 'aria-current="page">Jobs</a>' in content
