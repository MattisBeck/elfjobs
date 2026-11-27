from decimal import Decimal

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from jobs.management.commands.seed import COMPANIES_WITH_LOGO, seed_logo_path
from jobs.models import Company, JobPosting, company_initials

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>'


@pytest.fixture
def media_root(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def make_posting(company_name="Weihmann GbR", **company_fields):
    company = Company.objects.create(name=company_name, industry="Handel", **company_fields)
    return JobPosting.objects.create(
        company=company,
        title="Promoter*in",
        kind=JobPosting.Kind.SHORT_JOB,
        workplace=JobPosting.Workplace.ONSITE,
        schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal("16.00"),
        hours_per_week=7,
        latitude=Decimal("52.5219"),
        longitude=Decimal("13.4132"),
    )


@pytest.mark.parametrize("name, initials", [
    ("Bauer", "B"),
    ("Weihmann GbR", "W"),
    ("Holsten Förster AG & Co. OHG", "HF"),
    ("Müller & Schmidt", "MS"),
    ("  Hartmann   Meister KG ", "HM"),
    ("albers-werner e.V.", "AW"),
    ("Öko Ünal Ärzte", "ÖÜ"),
    ("GmbH", "G"),  # nur eine Rechtsform: dann doch deren Buchstabe
    ("& 123", "?"),
    ("", "?"),
])
def test_company_initials(name, initials):
    assert company_initials(name) == initials


@pytest.mark.django_db
def test_company_without_logo_shows_initials_in_list_and_detail(client):
    posting = make_posting("Holsten Förster AG & Co. OHG")

    list_content = client.get("/jobs/").content.decode()
    detail_content = client.get(f"/jobs/{posting.pk}/").content.decode()

    # Liste: dekorativ, der Name steht daneben.
    assert '<span class="company-logo company-logo-small company-logo-initials" aria-hidden="true">HF</span>' in list_content
    # Detail: groß und mit Firmenname für Screenreader.
    assert (
        '<span class="company-logo company-logo-large company-logo-initials" role="img" '
        'aria-label="Holsten Förster AG &amp; Co. OHG">HF</span>'
    ) in detail_content
    assert "<img class=\"company-logo" not in list_content + detail_content


@pytest.mark.django_db
def test_company_with_static_logo_shows_img(client):
    posting = make_posting(logo_static="logos/weihmann-gbr.svg")

    list_content = client.get("/jobs/").content.decode()
    detail_content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert '<img class="company-logo company-logo-small" src="/static/logos/weihmann-gbr.svg" alt="">' in list_content
    assert (
        '<img class="company-logo company-logo-large" src="/static/logos/weihmann-gbr.svg" alt="Weihmann GbR">'
    ) in detail_content


@pytest.mark.django_db
def test_uploaded_logo_wins_over_static_logo(media_root):
    company = Company.objects.create(name="Bauer", industry="Bank", logo_static="logos/bauer.svg")
    company.logo.save("bauer.svg", SimpleUploadedFile("bauer.svg", SVG))

    assert company.logo_url == "/media/logos/bauer.svg"
    assert (media_root / "logos" / "bauer.svg").exists()


@pytest.mark.django_db
def test_company_without_any_logo_has_no_logo_url():
    assert Company.objects.create(name="Bauer", industry="Bank").logo_url is None


@pytest.mark.django_db
@pytest.mark.parametrize("filename", ["logo.gif", "logo.exe", "logo.svg.html", "logo"])
def test_upload_with_wrong_extension_is_rejected(media_root, filename):
    company = Company(name="Bauer", industry="Bank", logo=SimpleUploadedFile(filename, SVG))

    with pytest.raises(ValidationError) as error:
        company.full_clean()

    assert "logo" in error.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("filename", ["logo.svg", "logo.png", "logo.JPG", "logo.jpeg", "logo.webp"])
def test_upload_with_allowed_extension_is_accepted(media_root, filename):
    Company(name="Bauer", industry="Bank", logo=SimpleUploadedFile(filename, SVG)).full_clean()


@pytest.mark.django_db
def test_admin_offers_logo_upload(client):
    client.force_login(User.objects.create_superuser("chefin", password="geheim-test-123"))

    content = client.get("/admin/jobs/company/add/").content.decode()

    assert 'enctype="multipart/form-data"' in content
    assert 'type="file" name="logo"' in content


@pytest.mark.django_db
def test_map_markers_contain_logo_or_initials(client):
    make_posting("Weihmann GbR", logo_static="logos/weihmann-gbr.svg")
    make_posting("Ritter")

    markers = {marker["company"]: marker for marker in client.get("/jobs/karte/").context["markers"]}

    assert markers["Weihmann GbR"]["logo_url"] == "/static/logos/weihmann-gbr.svg"
    assert markers["Ritter"]["logo_url"] is None
    assert markers["Ritter"]["initials"] == "R"


def test_map_popup_builds_logo_without_inner_html():
    template = (settings.BASE_DIR / "jobs" / "templates" / "jobs" / "job_map.html").read_text()

    assert "innerHTML" not in template
    assert "logo.textContent = marker.initials" in template


@pytest.mark.parametrize("name", COMPANIES_WITH_LOGO)
def test_seed_logo_files_exist_without_scripts(name):
    path = settings.BASE_DIR / "static" / seed_logo_path(name)
    content = path.read_text()

    assert content.startswith("<svg")
    assert "<script" not in content
    assert "http" not in content.replace("http://www.w3.org/2000/svg", "")


@pytest.mark.django_db
def test_seed_gives_some_companies_a_logo_and_leaves_others_with_initials():
    call_command("seed")
    logos = dict(Company.objects.values_list("name", "logo_static"))

    # Jede Firma aus der Liste gibt es im Seed wirklich, sonst wäre ein Logo umsonst.
    assert {name: path for name, path in logos.items() if path} == {
        name: seed_logo_path(name) for name in COMPANIES_WITH_LOGO
    }
    assert logos["Holsten Förster AG & Co. OHG"] == "logos/holsten-forster-ag-co-ohg.svg"
    # Mehrere Firmen bleiben ohne Logo, damit der Initialen-Platzhalter in der Demo zu sehen ist.
    assert len(logos) - len(COMPANIES_WITH_LOGO) >= 5
