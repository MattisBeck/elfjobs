from decimal import Decimal
from xml.etree import ElementTree

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from jobs.models import Company, JobPosting

SVG = "{http://www.w3.org/2000/svg}"


def make_posting(title="Promoter*in", company_name="Weihmann GbR", **company_fields):
    company = Company.objects.create(name=company_name, industry="Handel", **company_fields)
    return JobPosting.objects.create(
        company=company,
        title=title,
        kind=JobPosting.Kind.SHORT_JOB,
        workplace=JobPosting.Workplace.HYBRID,
        schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal("16.00"),
        hours_per_week=7,
    )


def svg_text(root):
    """Sichtbarer Text des SVG, ohne <title> (das wäre doppelt)."""
    return " ".join(
        "".join(node.itertext()) for node in root.iter(f"{SVG}text")
    )


@pytest.mark.django_db
def test_sharepic_for_every_seed_posting(client):
    call_command("seed")

    postings = JobPosting.objects.all()
    assert postings.exists()
    for posting in postings:
        response = client.get(f"/jobs/{posting.pk}/sharepic.svg")
        assert response.status_code == 200
        root = ElementTree.fromstring(response.content)
        assert root.tag == f"{SVG}svg"
        assert root.get("width") == "1080" and root.get("height") == "1080"


@pytest.mark.django_db
def test_sharepic_shows_posting_data_and_headers(client):
    posting = make_posting()

    response = client.get(f"/jobs/{posting.pk}/sharepic.svg")

    assert response["Content-Type"] == "image/svg+xml"
    assert response["Content-Disposition"] == f'inline; filename="elfjobs-{posting.pk}.svg"'
    # default-src 'none' verbietet auch Skripte, sandbox zusätzlich.
    assert "default-src 'none'" in response["Content-Security-Policy"]
    assert "sandbox" in response["Content-Security-Policy"]
    text = svg_text(ElementTree.fromstring(response.content))
    for part in ["Promoter*in", "Weihmann GbR", "16,00 €", "7 h pro Woche", "Kurzjob"]:
        assert part in text


@pytest.mark.django_db
def test_sharepic_download(client):
    posting = make_posting()

    response = client.get(f"/jobs/{posting.pk}/sharepic.svg?download=1")

    assert response["Content-Disposition"] == f'attachment; filename="elfjobs-{posting.pk}.svg"'


@pytest.mark.django_db
def test_sharepic_escapes_title_and_company(client):
    posting = make_posting(
        title='<script>alert(1)</script> & "Co"', company_name="Böse & <b>Söhne</b>"
    )

    response = client.get(f"/jobs/{posting.pk}/sharepic.svg")

    content = response.content.decode()
    assert "<script>" not in content
    assert "<b>" not in content
    root = ElementTree.fromstring(response.content)
    assert not list(root.iter(f"{SVG}script"))
    text = svg_text(root)
    assert "<script>alert(1)</script>" in text
    assert "Böse & <b>Söhne</b>" in text


@pytest.mark.django_db
def test_sharepic_wraps_long_title(client):
    posting = make_posting(title="Werkstudent*in Softwareentwicklung " * 5)

    response = client.get(f"/jobs/{posting.pk}/sharepic.svg")

    root = ElementTree.fromstring(response.content)
    lines = [span.text for span in root.iter(f"{SVG}tspan") if span.get("y")]
    assert len(lines) == 3
    assert all(len(line) <= 22 for line in lines)
    assert lines[-1].endswith("…")


@pytest.mark.django_db
def test_sharepic_404_for_unknown_posting(client):
    assert client.get("/jobs/999999/sharepic.svg").status_code == 404


@pytest.mark.parametrize("field, url", [
    ("instagram_url", "https://instagram.com/beispiel"),
    ("instagram_url", "https://www.instagram.com/beispiel/"),
    ("linkedin_url", "https://www.linkedin.com/company/beispiel"),
    ("tiktok_url", "https://www.tiktok.com/@beispiel"),
])
def test_valid_social_links(field, url):
    company = Company(name="Beispiel", industry="Tech", **{field: url})

    company.full_clean(exclude=["fairs"])


@pytest.mark.parametrize("field, url", [
    ("instagram_url", "http://instagram.com/beispiel"),
    ("instagram_url", "https://instagram.com.evil.example/beispiel"),
    ("instagram_url", "https://evil.example/instagram.com"),
    ("instagram_url", "https://instagram.com@evil.example/"),
    ("instagram_url", "https://www.linkedin.com/company/beispiel"),
    ("linkedin_url", "https://de.linkedin.com.example/"),
    ("linkedin_url", "javascript:alert(1)"),
    ("tiktok_url", "javascript://tiktok.com/%0aalert(1)"),
    ("tiktok_url", "ftp://tiktok.com/@beispiel"),
])
def test_invalid_social_links(field, url):
    company = Company(name="Beispiel", industry="Tech", **{field: url})

    with pytest.raises(ValidationError) as error:
        company.full_clean(exclude=["fairs"])
    assert field in error.value.message_dict


@pytest.mark.django_db
def test_admin_form_rejects_wrong_domain(admin_client):
    response = admin_client.post("/admin/jobs/company/add/", {
        "name": "Beispiel", "industry": "Tech", "commute_minutes": 10,
        "instagram_url": "https://tiktok.com/@beispiel",
    })

    assert response.status_code == 200
    assert "Bitte einen https-Link auf instagram.com angeben." in response.content.decode()
    assert not Company.objects.exists()


@pytest.mark.django_db
def test_detail_shows_only_set_links(client):
    posting = make_posting(instagram_url="https://www.instagram.com/beispiel")

    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert (
        '<a href="https://www.instagram.com/beispiel" target="_blank" rel="noopener noreferrer">Instagram</a>'
        in content
    )
    assert ">LinkedIn</a>" not in content
    assert ">TikTok</a>" not in content
    assert f'href="/jobs/{posting.pk}/sharepic.svg"' in content


@pytest.mark.django_db
def test_detail_without_links_has_no_link_list(client):
    posting = make_posting()

    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert "im Netz" not in content
    assert "Sharepic" in content
