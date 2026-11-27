import urllib.error
from email.message import Message
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import StudentProfile
from jobs.management.commands.seed import DEMO_EMAIL
from studies.models import Course, StudyProgram

FIXTURE = Path(__file__).parent / "fixtures" / "modulkatalog_itse.html"


def run_import(path=FIXTURE):
    out = StringIO()
    call_command("import_lehrplan", "itse", datei=str(path), stdout=out)
    return out.getvalue()


def skills(short_name):
    return sorted(Course.objects.get(short_name=short_name).skills.values_list("name", flat=True))


@pytest.mark.django_db
def test_imports_all_modules_from_saved_catalog():
    run_import()

    program = StudyProgram.objects.get(university="HPI", abbreviation="ITSE")
    assert program.courses.count() == 34
    assert Course.objects.get(short_name="PT1").name == "Programmiertechnik 1"
    assert Course.objects.get(short_name="SB2").name == "Datenbanksysteme"


@pytest.mark.django_db
def test_semester_from_study_plan():
    run_import()

    semesters = dict(Course.objects.values_list("short_name", "semester"))
    assert semesters["PT1"] == 1
    assert semesters["PT2"] == 2
    assert semesters["BS"] == 3
    assert semesters["SWT"] == 4
    assert semesters["SP1"] == 5
    assert semesters["SP2"] == 6
    assert semesters["SB2"] == 2  # Softwarebasis-Wahlpflichtmodul
    assert semesters["BPET-G"] == 4  # Vertiefungsgebiet Grundlagen
    assert semesters["BPET-V"] == 5  # Vertiefungsgebiet Vertiefung


@pytest.mark.django_db
def test_skills_from_keywords():
    run_import()

    assert skills("PT1") == ["C-Grundlagen", "Git", "Memory Management"]
    assert skills("SB2") == ["Datenmodellierung", "SQL"]
    assert skills("EW") == ["BWL"]


@pytest.mark.django_db
def test_unknown_modules_get_no_skills_and_are_listed():
    output = run_import()

    assert skills("MA3") == []
    assert "MA3 Mathematik 3" in output
    assert "SWA Softwarearchitektur" in output
    assert "PT1 Programmiertechnik 1" not in output


@pytest.mark.django_db
def test_second_run_creates_nothing_twice():
    run_import()
    run_import()

    assert StudyProgram.objects.filter(abbreviation="ITSE").count() == 1
    assert Course.objects.count() == 34
    assert skills("PT1") == ["C-Grundlagen", "Git", "Memory Management"]


@pytest.mark.django_db
def test_updates_course_from_seed_with_same_short_name():
    program = StudyProgram.objects.create(
        name="IT-Systems Engineering", abbreviation="ITSE", university="HPI", standard_semesters=6
    )
    seeded = Course.objects.create(program=program, name="Programmiertechnik I", short_name="PT1", semester=2)

    run_import()

    seeded.refresh_from_db()
    assert seeded.name == "Programmiertechnik 1"
    assert seeded.semester == 1


@pytest.mark.django_db
def test_foreign_page_raises_error(tmp_path):
    page = tmp_path / "fremd.html"
    page.write_text("<html><body><h1>Wartungsarbeiten</h1></body></html>", encoding="utf-8")

    with pytest.raises(CommandError, match="keine Module gefunden"):
        run_import(page)
    assert Course.objects.count() == 0


@pytest.mark.django_db
def test_empty_page_raises_error(tmp_path):
    page = tmp_path / "leer.html"
    page.write_text("", encoding="utf-8")

    with pytest.raises(CommandError, match="keine Module gefunden"):
        run_import(page)


def test_missing_file_raises_error(tmp_path):
    with pytest.raises(CommandError, match="lässt sich nicht lesen"):
        run_import(tmp_path / "gibt-es-nicht.html")


def test_unreachable_page_raises_error(monkeypatch):
    def offline(url, timeout):
        assert timeout == 10
        raise urllib.error.URLError("keine Verbindung")

    monkeypatch.setattr("urllib.request.urlopen", offline)

    with pytest.raises(CommandError, match="nicht erreichbar"):
        call_command("import_lehrplan", "itse", stdout=StringIO())


def fake_response(body, content_type):
    """Antwort wie von urlopen: lesbar, als with-Block nutzbar, mit Headern."""
    response = BytesIO(body)
    response.headers = Message()
    response.headers["Content-Type"] = content_type
    return response


@pytest.mark.django_db
def test_download_uses_charset_from_header(monkeypatch):
    page = "<summary><span> HPI-MO </span><span> - <strong>Modellierung für Größere</strong></span></summary>"
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda url, timeout: fake_response(page.encode("iso-8859-1"), "text/html; charset=ISO-8859-1"),
    )

    call_command("import_lehrplan", "itse", stdout=StringIO())

    assert Course.objects.get(short_name="MO").name == "Modellierung für Größere"


def test_broken_download_raises_error(monkeypatch):
    def broken(url, timeout):
        raise ConnectionResetError("Verbindung abgebrochen")

    monkeypatch.setattr("urllib.request.urlopen", broken)

    with pytest.raises(CommandError, match="nicht vollständig laden"):
        call_command("import_lehrplan", "itse", stdout=StringIO())


@pytest.mark.django_db
def test_seed_and_import_alternately_create_no_duplicates():
    """seed → import → seed → import: Jedes Kürzel gibt es danach nur einmal (Review #60)."""
    call_command("seed", stdout=StringIO())
    run_import()
    call_command("seed", stdout=StringIO())
    run_import()

    program = StudyProgram.objects.get(university="HPI", abbreviation="ITSE")
    short_names = list(program.courses.values_list("short_name", flat=True))
    assert len(short_names) == len(set(short_names))
    mia = StudentProfile.objects.get(user__username=DEMO_EMAIL)
    assert sorted(mia.courses.values_list("short_name", flat=True)) == ["MA1", "PT1"]
