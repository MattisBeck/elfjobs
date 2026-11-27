"""Heatmap für Firmen (#67): Wann haben Studierende mit passenden Skills Zeit?"""

from datetime import time

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from accounts.models import ProfileSkill, StudentProfile
from companies.availability import MIN_COUNT, availability
from companies.models import CompanyMember
from jobs.management.commands.seed import DEMO_COMPANY_EMAIL
from jobs.models import Company, Tag, Weekday
from studies.models import Course, StudyProgram
from timetable.models import LectureSlot


def make_student(name, lectures=((Weekday.MONDAY, time(10), time(12)),), tags=(), courses=()):
    user = User.objects.create_user(f"{name.lower()}@student.hpi.uni-potsdam.de", first_name=name)
    profile = StudentProfile.objects.create(user=user)
    for weekday, start, end in lectures:
        LectureSlot.objects.create(profile=profile, weekday=weekday, start=start, end=end, title="Mathe")
    for tag in tags:
        ProfileSkill.objects.create(profile=profile, tag=tag)
    profile.courses.set(courses)
    return profile


def cell(rows, weekday, hour):
    """Zelle für Wochentag und Stunde, z. B. cell(rows, Weekday.MONDAY, 9) für Mo 9–10 Uhr."""
    row = next(row for row in rows if row["start"] == time(hour))
    return row["cells"][weekday]


@pytest.fixture
def company_client(client, db):
    company = Company.objects.create(name="Bäckerei Krume", industry="Gastronomie", commute_minutes=30)
    user = User.objects.create_user("jobs@baeckerei-krume.example")
    CompanyMember.objects.create(user=user, company=company)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_lecture_with_buffer_blocks_slots():
    make_student("Lena")  # Mo 10–12 Uhr, mit 30 min Puffer also 9:30–12:30 belegt

    rows, total = availability([], buffer_minutes=30)

    assert total == 1
    assert len(rows) == 12  # 8 bis 20 Uhr
    assert cell(rows, Weekday.MONDAY, 8)["count"] == 1  # endet um 9, Puffer beginnt um 9:30
    assert cell(rows, Weekday.MONDAY, 9)["count"] == 0  # Puffer vor der Vorlesung
    assert cell(rows, Weekday.MONDAY, 11)["count"] == 0  # Vorlesung
    assert cell(rows, Weekday.MONDAY, 12)["count"] == 0  # Puffer nach der Vorlesung
    assert cell(rows, Weekday.MONDAY, 13)["count"] == 1
    assert cell(rows, Weekday.TUESDAY, 10)["count"] == 1  # andere Tage sind frei


@pytest.mark.django_db
def test_without_buffer_only_the_lecture_blocks():
    make_student("Lena")

    rows, _ = availability([], buffer_minutes=0)

    assert cell(rows, Weekday.MONDAY, 9)["count"] == 1
    assert cell(rows, Weekday.MONDAY, 10)["count"] == 0
    assert cell(rows, Weekday.MONDAY, 12)["count"] == 1


@pytest.mark.django_db
def test_only_students_with_all_chosen_skills_count():
    git, sql = Tag.objects.create(name="Git"), Tag.objects.create(name="SQL")
    program = StudyProgram.objects.create(name="ITSE", abbreviation="ITSE", university="HPI", standard_semesters=6)
    pt1 = Course.objects.create(program=program, name="Programmiertechnik I", short_name="PT1", semester=1)
    pt1.skills.add(git)
    make_student("Both", tags=[sql], courses=[pt1])  # Git aus dem Modul, SQL aus dem Profil
    make_student("Gitonly", courses=[pt1])
    make_student("Sqlonly", tags=[sql])
    make_student("Nobody")

    assert availability([git, sql], 0)[1] == 1
    assert availability([git], 0)[1] == 2
    assert availability([], 0)[1] == 4


@pytest.mark.django_db
def test_students_without_timetable_do_not_count():
    make_student("Lena", lectures=())

    rows, total = availability([], 0)

    assert total == 0
    assert cell(rows, Weekday.TUESDAY, 10)["count"] == 0


@pytest.mark.django_db
def test_small_counts_are_hidden():
    for number in range(MIN_COUNT - 1):
        make_student(f"Studi{number}")

    rows, _ = availability([], 0)

    free = cell(rows, Weekday.TUESDAY, 10)
    assert free["count"] == MIN_COUNT - 1
    assert free["label"] == f"weniger als {MIN_COUNT} frei"
    assert free["short"] == f"< {MIN_COUNT}"
    assert free["level"] == 0  # auch die Farbe verrät nichts

    make_student("Noch")
    rows, _ = availability([], 0)
    assert cell(rows, Weekday.TUESDAY, 10)["label"] == f"{MIN_COUNT} frei"


def test_only_company_accounts_see_the_page(client, db):
    assert client.get("/firma/verfuegbarkeit/").url.startswith("/firma/anmelden/")

    student = make_student("Lena")
    client.force_login(student.user)
    assert client.get("/firma/verfuegbarkeit/").status_code == 403


def test_page_shows_counts_but_no_names(company_client):
    git = Tag.objects.create(name="Git")
    for name in ["Annegret", "Bartholomaeus", "Cordula"]:
        make_student(name, tags=[git])

    content = company_client.get("/firma/verfuegbarkeit/", {"skills": [git.pk]}).content.decode()

    assert "3 frei" in content
    assert '<th scope="col">Mo</th>' in content
    assert '<th scope="row">08:00–09:00</th>' in content
    for name in ["Annegret", "Bartholomaeus", "Cordula", "annegret@"]:
        assert name not in content


def test_skill_picker_summary_shows_chosen_skills(company_client):
    """Die Auswahl ist zugeklappt (#109), oben steht, welche Skills gewählt sind."""
    git = Tag.objects.create(name="Git")
    sql = Tag.objects.create(name="SQL")

    without = company_client.get("/firma/verfuegbarkeit/").content.decode()
    chosen = company_client.get("/firma/verfuegbarkeit/", {"skills": [git.pk, sql.pk]}).content.decode()

    assert '<details class="skill-picker">' in without
    assert "alle Studierenden" in without
    assert "Git, SQL" in chosen
    assert "alle Studierenden" not in chosen


def test_company_home_links_to_heatmap(company_client):
    assert 'href="/firma/verfuegbarkeit/"' in company_client.get("/firma/").content.decode()


@pytest.mark.django_db
def test_page_with_seed_data_needs_few_queries(client, django_assert_max_num_queries):
    call_command("seed")
    client.force_login(User.objects.get(username=DEMO_COMPANY_EMAIL))
    git = Tag.objects.get(name="Git")

    with django_assert_max_num_queries(15):
        response = client.get("/firma/verfuegbarkeit/", {"skills": [git.pk]})

    assert response.status_code == 200
    assert "frei" in response.content.decode()
