from decimal import Decimal

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from jobs.management.commands.seed import COMPANIES_WITH_LOGO, seed_logo_path
from jobs.models import Company, JobPosting, company_initials

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><script>alert(1)</script></svg>'
# Nur die ersten Bytes zählen für die Prüfung, der Rest ist Füllmaterial.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 20
# media_root kommt aus conftest.py (autouse, temporärer Ordner).


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
    # Detail: groß, ebenfalls dekorativ, weil der Name direkt daneben steht.
    assert '<span class="company-logo company-logo-large company-logo-initials" aria-hidden="true">HF</span>' in detail_content
    assert "<img class=\"company-logo" not in list_content + detail_content


@pytest.mark.django_db
def test_company_with_static_logo_shows_img(client):
    posting = make_posting(logo_static="logos/weihmann-gbr.svg")

    list_content = client.get("/jobs/").content.decode()
    detail_content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert '<img class="company-logo company-logo-small" src="/static/logos/weihmann-gbr.svg" alt="">' in list_content
    assert (
        '<img class="company-logo company-logo-large" src="/static/logos/weihmann-gbr.svg" alt="">'
    ) in detail_content


@pytest.mark.django_db
def test_uploaded_logo_wins_over_static_logo_and_is_served_by_own_view(client, media_root):
    company = Company.objects.create(name="Bauer", industry="Bank", logo_static="logos/bauer.svg")
    company.logo.save("bauer.png", SimpleUploadedFile("bauer.png", PNG))

    assert company.logo_url == f"/firmen/{company.pk}/logo"
    assert (media_root / "logos" / "bauer.png").exists()

    response = client.get(company.logo_url)
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert b"".join(response.streaming_content) == PNG


@pytest.mark.django_db
@pytest.mark.parametrize("filename, content, content_type", [
    ("logo.jpg", JPEG, "image/jpeg"),
    ("logo.webp", WEBP, "image/webp"),
])
def test_logo_view_sets_content_type(client, filename, content, content_type):
    company = Company.objects.create(name="Bauer", industry="Bank")
    company.logo.save(filename, SimpleUploadedFile(filename, content))

    assert client.get(f"/firmen/{company.pk}/logo")["Content-Type"] == content_type


@pytest.mark.django_db
def test_logo_view_is_404_without_upload(client):
    company = Company.objects.create(name="Bauer", industry="Bank", logo_static="logos/bauer.svg")

    assert client.get(f"/firmen/{company.pk}/logo").status_code == 404
    assert client.get("/firmen/999999/logo").status_code == 404


@pytest.mark.django_db
def test_media_is_not_served_directly(client, media_root):
    """Unter MEDIA_ROOT liegen auch private Dateien (Lebensläufe), deshalb keine /media/-Route."""
    company = Company.objects.create(name="Bauer", industry="Bank")
    company.logo.save("bauer.png", SimpleUploadedFile("bauer.png", PNG))

    assert client.get("/media/logos/bauer.png").status_code == 404
    assert not hasattr(settings, "MEDIA_URL") or settings.MEDIA_URL in ("", "/")


@pytest.mark.django_db
def test_company_without_any_logo_has_no_logo_url():
    assert Company.objects.create(name="Bauer", industry="Bank").logo_url is None


@pytest.mark.django_db
@pytest.mark.parametrize("filename, content", [
    ("logo.svg", SVG),  # SVG kann Skripte enthalten, Upload nie
    ("logo.gif", PNG),
    ("logo.exe", PNG),
    ("logo.png.html", PNG),
    ("logo", PNG),
    ("logo.png", SVG),  # umbenannte SVG: falsche Magic Bytes
    ("logo.png", JPEG),  # Endung passt nicht zum Inhalt
    ("logo.jpg", PNG),
    ("logo.webp", b"RIFF\x10\x00\x00\x00WAVEfmt " + b"\x00" * 20),
])
def test_upload_with_wrong_extension_or_content_is_rejected(filename, content):
    company = Company(name="Bauer", industry="Bank", logo=SimpleUploadedFile(filename, content))

    with pytest.raises(ValidationError) as error:
        company.full_clean()

    assert "logo" in error.value.message_dict


@pytest.mark.django_db
def test_upload_larger_than_1_mb_is_rejected():
    big = PNG + b"\x00" * (1024 * 1024)
    company = Company(name="Bauer", industry="Bank", logo=SimpleUploadedFile("logo.png", big))

    with pytest.raises(ValidationError) as error:
        company.full_clean()

    assert "1 MB" in str(error.value.message_dict["logo"])


@pytest.mark.django_db
@pytest.mark.parametrize("filename, content", [
    ("logo.png", PNG), ("logo.PNG", PNG), ("logo.jpg", JPEG), ("logo.jpeg", JPEG), ("logo.webp", WEBP),
])
def test_upload_with_allowed_extension_and_content_is_accepted(filename, content):
    Company(name="Bauer", industry="Bank", logo=SimpleUploadedFile(filename, content)).full_clean()


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
