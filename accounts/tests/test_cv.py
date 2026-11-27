import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from fpdf import FPDF
from pypdf import PdfWriter

from accounts.cv import cv_suggestions, find_skills, read_pdf_text
from accounts.models import ProfileSkill, StudentProfile
from jobs.models import Tag
from studies.skills import skill_sources


def write_text_pdf(path, text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, text)
    pdf.output(str(path))
    return path


def names(tags):
    return [tag.name for tag in tags]


@pytest.fixture
def tags(db):
    return {name: Tag.objects.create(name=name) for name in ["Python", "Excel", "Englisch", "SQL", "Java"]}


@pytest.fixture
def lena(db):
    user = User.objects.create_user("lena")
    return StudentProfile.objects.create(user=user)


@pytest.mark.django_db
def test_pdf_with_synonyms_gives_python_excel_and_english(tmp_path, tags):
    path = write_text_pdf(tmp_path / "cv.pdf", "Kenntnisse: Python, MS Excel, Englisch (C1)")

    assert names(find_skills(read_pdf_text(path))) == ["Englisch", "Excel", "Python"]


@pytest.mark.django_db
def test_matching_uses_whole_words_and_ignores_case(tags):
    Tag.objects.create(name="Informatik")

    found = find_skills("studiere wirtschaftsinformatik, kann PYTHON3 und english, javascript nicht")

    # „Informatik“ steckt nicht in „Wirtschaftsinformatik“, „Java“ nicht in „javascript“.
    assert names(found) == ["Englisch", "Python"]


@pytest.mark.django_db
def test_synonyms_never_create_tags(tags):
    find_skills("Buchführung, PowerPoint, Instagram")

    assert not Tag.objects.filter(name__in=["Buchhaltung", "Präsentieren", "Social Media"]).exists()


@pytest.mark.django_db
def test_pdf_without_text_gives_no_suggestions(tmp_path, tags):
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    path = tmp_path / "scan.pdf"
    writer.write(path)

    assert read_pdf_text(path).strip() == ""
    assert find_skills(read_pdf_text(path)) == []


@pytest.mark.django_db
def test_broken_pdf_gives_no_suggestions(tmp_path, tags):
    path = tmp_path / "kaputt.pdf"
    path.write_bytes(b"kein PDF")

    assert read_pdf_text(path) == ""


@pytest.mark.django_db
def test_scanned_sample_cv_gives_no_suggestions_and_page_still_works(client, lena, tags):
    client.force_login(lena.user)

    client.post("/profil/lebenslauf/", {"cv_sample": "scan-ohne-text"})
    response = client.get("/profil/")

    assert response.status_code == 200
    assert response.context["cv_new_skills"] == []
    assert "keine Skills gefunden" in response.content.decode()


@pytest.mark.django_db
def test_suggestions_count_only_after_accepting(client, lena, tags):
    client.force_login(lena.user)

    response = client.post("/profil/lebenslauf/", {"cv_sample": "mia-itse"})

    assert response.status_code == 302
    lena.refresh_from_db()
    assert lena.cv_sample == "mia-itse"
    page = client.get("/profil/")
    assert names(page.context["cv_new_skills"]) == ["Englisch", "Excel", "Python"]
    assert "Aus deinem Lebenslauf: Englisch, Excel, Python" in page.content.decode()
    # Vorschläge allein sind noch keine Skills.
    assert skill_sources(lena) == {}

    client.post("/profil/lebenslauf/uebernehmen/", {"skills": [tags["Python"].id, tags["Excel"].id]})

    assert skill_sources(lena) == {
        tags["Python"].id: "aus deinem Lebenslauf",
        tags["Excel"].id: "aus deinem Lebenslauf",
    }
    new, existing = cv_suggestions(lena)
    assert names(new) == ["Englisch"]
    assert [(tag.name, source) for tag, source in existing] == [
        ("Excel", "aus deinem Lebenslauf"), ("Python", "aus deinem Lebenslauf"),
    ]


@pytest.mark.django_db
def test_existing_skills_are_not_suggested_again(lena, tags):
    ProfileSkill.objects.create(profile=lena, tag=tags["Python"], source=ProfileSkill.Source.PROFILE)
    lena.cv_sample = StudentProfile.CvSample.MIA
    lena.save()

    new, existing = cv_suggestions(lena)

    assert names(new) == ["Englisch", "Excel"]
    assert [(tag.name, source) for tag, source in existing] == [("Python", "aus deinem Profil")]


@pytest.mark.django_db
def test_accept_ignores_tags_that_are_not_suggested(client, lena, tags):
    client.force_login(lena.user)
    client.post("/profil/lebenslauf/", {"cv_sample": "mia-itse"})

    # SQL steht nicht in Mias Lebenslauf.
    client.post("/profil/lebenslauf/uebernehmen/", {"skills": [tags["SQL"].id, tags["Python"].id]})

    assert list(lena.skills.values_list("name", flat=True)) == ["Python"]


@pytest.mark.django_db
def test_switching_cv_recomputes_suggestions_and_keeps_accepted_skills(client, lena, tags):
    client.force_login(lena.user)
    client.post("/profil/lebenslauf/", {"cv_sample": "mia-itse"})
    client.post("/profil/lebenslauf/uebernehmen/", {"skills": [tags["Excel"].id]})

    client.post("/profil/lebenslauf/", {"cv_sample": "jonas-wirtschaftsinformatik"})

    lena.refresh_from_db()
    new, _ = cv_suggestions(lena)
    assert names(new) == ["Englisch", "Java", "Python", "SQL"]
    assert list(lena.profile_skills.values_list("tag__name", "source")) == [("Excel", "lebenslauf")]


@pytest.mark.django_db
def test_cv_views_need_post(client, lena):
    client.force_login(lena.user)

    assert client.get("/profil/lebenslauf/").status_code == 405
    assert client.get("/profil/lebenslauf/uebernehmen/").status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/profil/lebenslauf.pdf", "/profil/lebenslauf/", "/profil/lebenslauf/uebernehmen/"])
def test_cv_views_require_login(client, url):
    response = client.post(url) if url.endswith("/") else client.get(url)

    assert response.status_code == 302
    assert response.url.startswith("/anmelden/")


@pytest.mark.django_db
def test_cv_pdf_only_serves_own_cv(client, lena):
    lena.cv_sample = StudentProfile.CvSample.MIA
    lena.save()
    other = User.objects.create_user("tom")
    StudentProfile.objects.create(user=other)

    client.force_login(lena.user)
    response = client.get("/profil/lebenslauf.pdf")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content).startswith(b"%PDF")

    # Tom hat keinen Lebenslauf gewählt und kommt so auch nicht an Lenas.
    client.force_login(other)
    assert client.get("/profil/lebenslauf.pdf").status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("sample", [s for s in StudentProfile.CvSample if s != StudentProfile.CvSample.SCAN])
def test_every_sample_cv_gives_at_least_two_suggestions(sample):
    call_command("seed")
    user = User.objects.create_user(f"test-{sample}")
    profile = StudentProfile.objects.create(user=user, cv_sample=sample)

    new, existing = cv_suggestions(profile)

    assert existing == []
    assert len(new) >= 2


@pytest.mark.django_db
def test_seed_gives_mia_a_cv_without_accepted_skills():
    call_command("seed")

    mia = StudentProfile.objects.get(user__username="mia@student.hpi.uni-potsdam.de")
    assert mia.cv_sample == "mia-itse"
    assert not mia.profile_skills.filter(source=ProfileSkill.Source.CV).exists()
    new, existing = cv_suggestions(mia)
    assert names(new) == ["Excel", "HTML/CSS", "JavaScript", "Linux", "Teamfähigkeit"]
    assert sorted(tag.name for tag, _ in existing) == ["Englisch", "Git", "Python"]
