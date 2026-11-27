from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from accounts.models import ProfileSkill, StudentProfile
from jobs.models import Company, JobPosting, Tag
from studies.models import Course, StudyProgram
from studies.qualification import LEARNED, NOT_IN_STUDIES, UPCOMING, classify, skill_lookup, summary, verdict

MIA = "mia@student.hpi.uni-potsdam.de"


@pytest.fixture
def profile(db):
    """Lena, ITSE im 1. Semester, belegt PT1 (Git). SQL kommt im 3. Semester mit DBS1."""
    program = StudyProgram.objects.create(
        name="IT-Systems Engineering", abbreviation="ITSE", university="HPI", standard_semesters=6
    )
    pt1 = Course.objects.create(program=program, name="Programmiertechnik I", short_name="PT1", semester=1)
    pt1.skills.add(Tag.objects.create(name="Git"))
    dbs1 = Course.objects.create(program=program, name="Datenbanksysteme I", short_name="DBS1", semester=3)
    dbs1.skills.add(Tag.objects.create(name="SQL"))
    user = User.objects.create_user("lena")
    profile = StudentProfile.objects.create(user=user, study_program=program, semester=1)
    profile.courses.add(pt1)
    return profile


def make_posting(title, tags=(), wage="15.00"):
    company, _ = Company.objects.get_or_create(name="Testfirma", industry="Tech")
    posting = JobPosting.objects.create(
        company=company, title=title, kind=JobPosting.Kind.WORKING_STUDENT,
        workplace=JobPosting.Workplace.REMOTE, schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal(wage), hours_per_week=10,
    )
    posting.tags.add(*tags)
    return posting


def by_name(requirements):
    return {r["tag"].name: (r["status"], r["text"]) for r in requirements}


def test_classify_all_three_cases(profile):
    tags = [Tag.objects.get(name="Git"), Tag.objects.get(name="SQL"), Tag.objects.create(name="Kassieren")]

    requirements = classify(skill_lookup(profile), tags)

    assert by_name(requirements) == {
        "Git": (LEARNED, "aus PT1"),
        "SQL": (UPCOMING, "ab 3. Semester"),
        "Kassieren": (NOT_IN_STUDIES, ""),
    }
    assert summary(requirements) == "1 von 3 Anforderungen aus dem Studium"


def test_profile_skill_counts_as_learned(profile):
    english = Tag.objects.create(name="Englisch")
    sql = Tag.objects.get(name="SQL")
    ProfileSkill.objects.create(profile=profile, tag=english)
    # Schon selbst gelernt, obwohl es laut Lehrplan erst später kommt.
    ProfileSkill.objects.create(profile=profile, tag=sql, source=ProfileSkill.Source.CV)

    requirements = classify(skill_lookup(profile), [english, sql])

    assert by_name(requirements) == {
        "Englisch": (LEARNED, "aus deinem Profil"),
        "SQL": (LEARNED, "aus deinem Lebenslauf"),
    }
    assert summary(requirements) == "2 von 2 Anforderungen aus dem Studium"


def test_upcoming_uses_earliest_later_semester(profile):
    sql = Tag.objects.get(name="SQL")
    later = Course.objects.create(program=profile.study_program, name="Datenbanken II", semester=5)
    later.skills.add(sql)
    Course.objects.create(program=profile.study_program, name="Datenbanken 0", semester=2).skills.add(sql)

    assert skill_lookup(profile)[sql.id] == (UPCOMING, "ab 2. Semester")


def test_module_from_other_program_is_not_in_studies(profile):
    other = StudyProgram.objects.create(name="BWL", abbreviation="BWL", university="Uni Potsdam", standard_semesters=6)
    excel = Tag.objects.create(name="Excel")
    Course.objects.create(program=other, name="Allgemeine BWL", semester=2).skills.add(excel)

    assert by_name(classify(skill_lookup(profile), [excel])) == {"Excel": (NOT_IN_STUDIES, "")}


def test_without_semester_nothing_is_upcoming(profile):
    profile.semester = None
    profile.save()

    assert skill_lookup(profile) == {Tag.objects.get(name="Git").id: (LEARNED, "aus PT1")}


def test_single_requirement_in_singular(profile):
    requirements = classify(skill_lookup(profile), [Tag.objects.get(name="Git")])

    assert summary(requirements) == "1 von 1 Anforderung aus dem Studium"


def test_posting_without_requirements_has_no_hint(profile):
    requirements = classify(skill_lookup(profile), [])

    assert requirements == []
    assert summary(requirements) == ""


# Ansichten


def test_detail_shows_classification(client, profile):
    posting = make_posting("Werkstudent*in Daten", [
        Tag.objects.get(name="Git"), Tag.objects.get(name="SQL"), Tag.objects.create(name="Kassieren"),
    ])
    client.force_login(profile.user)

    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert '<li class="tag tag-learned">✓ Git · aus PT1</li>' in content
    assert '<li class="tag tag-upcoming">SQL · ab 3. Semester</li>' in content
    assert '<li class="tag tag-missing">Kassieren</li>' in content
    # Die Liste daneben zeigt den Hinweis auch.
    assert "1 von 3 Anforderungen aus dem Studium" in content


def test_list_shows_hint_only_for_postings_with_requirements(client, profile):
    make_posting("Mit Anforderungen", [Tag.objects.get(name="Git"), Tag.objects.get(name="SQL")])
    make_posting("Ohne Anforderungen")
    client.force_login(profile.user)

    response = client.get("/jobs/")

    hints = {p.title: p.skill_hint for p in response.context["postings"]}
    assert hints == {"Mit Anforderungen": "1 von 2 Anforderungen aus dem Studium", "Ohne Anforderungen": ""}
    assert response.content.decode().count('class="job-row-skills"') == 1


def test_without_login_no_classification(client, profile):
    posting = make_posting("Werkstudent*in Daten", [Tag.objects.get(name="Git"), Tag.objects.get(name="SQL")])

    content = client.get(f"/jobs/{posting.pk}/").content.decode()
    list_content = client.get("/jobs/").content.decode()

    assert '<li class="tag">Git</li>' in content
    assert "ab 3. Semester" not in content
    assert "Anforderungen aus dem Studium" not in content
    assert "Anforderungen aus dem Studium" not in list_content


def test_user_without_profile_sees_no_classification(client, profile):
    posting = make_posting("Werkstudent*in Daten", [Tag.objects.get(name="Git")])
    client.force_login(User.objects.create_user("firma"))

    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert '<li class="tag">Git</li>' in content
    assert "Anforderungen aus dem Studium" not in content


def test_list_queries_do_not_grow_with_postings(client, profile, django_assert_max_num_queries):
    git, sql = Tag.objects.get(name="Git"), Tag.objects.get(name="SQL")
    client.force_login(profile.user)
    make_posting("Stelle 0", [git, sql])
    client.get("/jobs/")  # Sitzung und Cache aufwärmen

    with django_assert_max_num_queries(20) as few:
        client.get("/jobs/")
    for number in range(1, 30):
        make_posting(f"Stelle {number}", [git, sql])
    with django_assert_max_num_queries(len(few.captured_queries)):
        response = client.get("/jobs/")
    assert len(response.context["postings"]) == 30


@pytest.mark.django_db
def test_mia_sees_sql_from_third_semester(client):
    call_command("seed")
    mia = StudentProfile.objects.get(user__username=MIA)
    assert mia.study_program.abbreviation == "ITSE" and mia.semester == 1
    posting = JobPosting.objects.filter(tags__name="SQL").order_by("id").first()
    client.login(username=MIA, password="test-passwort")

    response = client.get(f"/jobs/{posting.pk}/")

    assert '<li class="tag tag-upcoming">SQL · ab 3. Semester</li>' in response.content.decode()
    hints = [p.skill_hint for p in response.context["postings"] if p.tags.all()]
    assert hints and all(hint.endswith(" aus dem Studium") for hint in hints)


# Urteil „Du bist qualifiziert“ (#86)


def test_verdict_all_learned(profile):
    requirements = classify(skill_lookup(profile), [Tag.objects.get(name="Git")])

    assert verdict(requirements) == {"level": "kannst", "label": "✓ Du bist qualifiziert", "detail": ""}


def test_verdict_rest_comes_in_studies(profile):
    requirements = classify(skill_lookup(profile), [Tag.objects.get(name="Git"), Tag.objects.get(name="SQL")])

    assert verdict(requirements) == {
        "level": "bald",
        "label": "✓ Passt zu deinem Studium",
        "detail": "Den Rest lernst du noch: SQL ab 3. Semester.",
    }


def test_verdict_none_when_something_is_not_in_studies(profile):
    requirements = classify(skill_lookup(profile), [Tag.objects.get(name="Git"), Tag.objects.create(name="Kassieren")])

    assert verdict(requirements) is None


def test_verdict_without_requirements(profile):
    assert verdict([]) == {"level": "kannst", "label": "✓ Keine Vorkenntnisse nötig", "detail": ""}


def test_profile_skill_counts_for_verdict(profile):
    excel = Tag.objects.create(name="Excel")
    ProfileSkill.objects.create(profile=profile, tag=excel)

    requirements = classify(skill_lookup(profile), [excel])

    assert verdict(requirements)["level"] == "kannst"


def test_list_and_detail_show_verdict_badge(client, profile):
    can = make_posting("Kann ich", [Tag.objects.get(name="Git")])
    make_posting("Bald", [Tag.objects.get(name="Git"), Tag.objects.get(name="SQL")])
    make_posting("Fremd", [Tag.objects.create(name="Kassieren")])
    client.force_login(profile.user)

    response = client.get("/jobs/")
    badges = {p.title: (p.verdict or {}).get("label") for p in response.context["postings"]}
    assert badges == {"Kann ich": "✓ Du bist qualifiziert", "Bald": "✓ Passt zu deinem Studium", "Fremd": None}
    content = response.content.decode()
    assert '<span class="fit-badge fit-badge-kannst">✓ Du bist qualifiziert</span>' in content
    assert '<span class="fit-badge fit-badge-bald">✓ Passt zu deinem Studium</span>' in content

    detail = client.get(f"/jobs/{can.pk}/").content.decode()
    head = detail.split('class="job-detail-head"')[1].split("</header>")[0]
    assert '<p class="fit-badge fit-badge-kannst">✓ Du bist qualifiziert</p>' in head


def test_detail_explains_what_comes_later(client, profile):
    posting = make_posting("Bald", [Tag.objects.get(name="Git"), Tag.objects.get(name="SQL")])
    client.force_login(profile.user)

    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert "Den Rest lernst du noch: SQL ab 3. Semester." in content


def test_no_verdict_without_login_or_profile(client, profile):
    posting = make_posting("Kann ich", [Tag.objects.get(name="Git")])

    assert "fit-badge" not in client.get("/jobs/").content.decode()
    assert "fit-badge" not in client.get(f"/jobs/{posting.pk}/").content.decode()

    client.force_login(User.objects.create_user("firma"))
    assert "fit-badge" not in client.get("/jobs/").content.decode()
    assert "fit-badge" not in client.get(f"/jobs/{posting.pk}/").content.decode()


def test_map_shows_verdict_badge(client, profile):
    make_posting("Kann ich", [Tag.objects.get(name="Git")])
    client.force_login(profile.user)

    content = client.get("/jobs/karte/").content.decode()

    assert '<span class="fit-badge fit-badge-kannst">✓ Du bist qualifiziert</span>' in content


@pytest.mark.django_db
def test_mia_can_do_at_least_one_seed_job(client):
    call_command("seed")
    client.login(username=MIA, password="test-passwort")

    response = client.get("/jobs/")

    labels = [p.verdict["label"] for p in response.context["postings"] if p.verdict]
    assert "✓ Du bist qualifiziert" in labels
