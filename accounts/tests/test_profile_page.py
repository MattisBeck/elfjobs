"""Profilseite (#156): Kopf mit Studiengang, Kennzahlen und aufklappbare Module und Skills."""

import pytest
from django.contrib.auth.models import User

from accounts.models import StudentProfile
from studies.models import StudyProgram


@pytest.fixture
def student_client(client, db):
    user = User.objects.create_user(
        "lea@student.hpi.uni-potsdam.de", email="lea@student.hpi.uni-potsdam.de", first_name="Lea", last_name="Berg"
    )
    program = StudyProgram.objects.create(
        name="Data Engineering", abbreviation="DE", university="HPI", standard_semesters=6
    )
    StudentProfile.objects.create(user=user, study_program=program, semester=3, home_town="Potsdam")
    client.force_login(user)
    return client


def test_profile_header_shows_name_program_and_town(student_client):
    content = student_client.get("/profil/").content.decode()

    assert "<h1>Lea Berg</h1>" in content
    assert "Data Engineering" in content
    assert "3. Semester" in content
    assert "Potsdam" in content


def test_profile_shows_stats_and_collapsible_sections(student_client):
    content = student_client.get("/profil/").content.decode()

    assert 'class="profile-stats"' in content
    assert "Bewerbungen" in content
    assert '<details id="module"' in content
    assert '<details id="skills"' in content
    assert "Speichern" in content


def test_profile_without_name_falls_back_to_title(client, db):
    user = User.objects.create_user("x@student.hpi.uni-potsdam.de", email="x@student.hpi.uni-potsdam.de")
    client.force_login(user)

    content = client.get("/profil/").content.decode()

    assert "<h1>Mein Profil</h1>" in content
    assert "Studiengang fehlt noch" in content
