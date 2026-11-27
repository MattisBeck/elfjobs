from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from accounts.models import ProfileSkill, StudentProfile
from jobs.models import Company, JobPosting, Tag
from studies.models import Course, StudyProgram
from studies.skills import skill_sources

MIA = "mia@student.hpi.uni-potsdam.de"


@pytest.fixture
def profile(db):
    program = StudyProgram.objects.create(
        name="IT-Systems Engineering", abbreviation="ITSE", university="HPI", standard_semesters=6
    )
    pt1 = Course.objects.create(program=program, name="Programmiertechnik I", short_name="PT1", semester=1)
    pt1.skills.add(Tag.objects.create(name="C-Grundlagen"), Tag.objects.create(name="Git"))
    user = User.objects.create_user("lena")
    profile = StudentProfile.objects.create(user=user, study_program=program, semester=1)
    profile.courses.add(pt1)
    return profile


def test_skill_sources_from_course_and_profile(profile):
    english = Tag.objects.create(name="Englisch")
    cv_skill = Tag.objects.create(name="Excel")
    git = Tag.objects.get(name="Git")
    ProfileSkill.objects.create(profile=profile, tag=english)
    ProfileSkill.objects.create(profile=profile, tag=cv_skill, source=ProfileSkill.Source.CV)
    # Steht auch im Modul: das Modul gewinnt.
    ProfileSkill.objects.create(profile=profile, tag=git)

    sources = skill_sources(profile)

    assert sources == {
        Tag.objects.get(name="C-Grundlagen").id: "aus PT1",
        git.id: "aus PT1",
        english.id: "aus deinem Profil",
        cv_skill.id: "aus deinem Lebenslauf",
    }


def test_course_without_short_name_uses_full_name(profile):
    course = Course.objects.create(program=profile.study_program, name="Mathematik I", semester=1)
    course.skills.add(Tag.objects.create(name="Logik"))
    profile.courses.add(course)

    assert skill_sources(profile)[Tag.objects.get(name="Logik").id] == "aus Mathematik I"


@pytest.mark.django_db
def test_mia_has_skills_from_pt1_without_own_input():
    call_command("seed")
    mia = StudentProfile.objects.get(user__username=MIA)

    sources = skill_sources(mia)

    for name in ["C-Grundlagen", "Memory Management"]:
        assert sources[Tag.objects.get(name=name).id] == "aus PT1"
        # Nicht selbst eingetragen, sondern aus dem Modul abgeleitet.
        assert not mia.profile_skills.filter(tag__name=name).exists()
    assert sources[Tag.objects.get(name="Python").id] == "aus deinem Profil"


@pytest.mark.django_db
def test_seed_creates_curriculum_and_postings_asking_for_c():
    call_command("seed")

    itse = StudyProgram.objects.get(university="HPI", abbreviation="ITSE")
    assert set(itse.courses.values_list("semester", flat=True)) == {1, 2, 3, 4}
    pt1 = itse.courses.get(short_name="PT1")
    assert pt1.name == "Programmiertechnik I"
    assert {"C-Grundlagen", "Memory Management"} <= set(pt1.skills.values_list("name", flat=True))
    assert "SQL" in itse.courses.get(name="Datenbanksysteme I").skills.values_list("name", flat=True)
    assert StudyProgram.objects.count() == 5
    assert JobPosting.objects.filter(tags__name="C-Grundlagen").exists()


@pytest.mark.django_db
def test_seed_keeps_course_choices_of_other_students():
    call_command("seed")
    user = User.objects.create_user("lena")
    profile = StudentProfile.objects.create(user=user, semester=3)
    profile.courses.set(Course.objects.filter(short_name="DBS1"))

    call_command("seed")

    assert list(profile.courses.values_list("short_name", flat=True)) == ["DBS1"]
    assert profile.courses.get().skills.filter(name="SQL").exists()


@pytest.mark.django_db
def test_seed_finds_course_with_old_short_name():
    """Ältere Datenbanken haben Modellierung I noch als MOD1, heute heißt das Kürzel MO."""
    call_command("seed")
    course = Course.objects.get(short_name="MO")
    course.short_name = "MOD1"
    course.save()

    call_command("seed")

    course.refresh_from_db()
    assert course.short_name == "MO"
    assert Course.objects.filter(name="Modellierung I").count() == 1


@pytest.mark.django_db
def test_job_detail_marks_skill_from_course_for_mia(client):
    call_command("seed")
    posting = JobPosting.objects.filter(tags__name="C-Grundlagen").first()
    client.login(username=MIA, password="test-passwort")

    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert "✓ C-Grundlagen · aus PT1" in content


def test_job_detail_without_login_shows_plain_skills(client, profile):
    company = Company.objects.create(name="Weihmann GbR", industry="Tech")
    posting = JobPosting.objects.create(
        company=company, title="Werkstudent*in Softwareentwicklung", kind=JobPosting.Kind.WORKING_STUDENT,
        workplace=JobPosting.Workplace.REMOTE, schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal("19.50"), hours_per_week=11,
    )
    posting.tags.add(Tag.objects.get(name="C-Grundlagen"), Tag.objects.create(name="Java"))

    content = client.get(f"/jobs/{posting.pk}/").content.decode()
    assert "C-Grundlagen" in content
    assert "✓" not in content

    client.force_login(profile.user)
    content = client.get(f"/jobs/{posting.pk}/").content.decode()
    assert "✓ C-Grundlagen · aus PT1" in content
    assert "✓ Java" not in content
