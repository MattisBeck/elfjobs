from collections import defaultdict
from datetime import time

import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.management import call_command

from accounts.models import StudentProfile
from jobs.management.commands.seed import DEMO_EMAIL, MAX_COURSES_PER_SEMESTER, NUM_STUDENTS
from studies.models import Course, StudyProgram
from timetable.models import LectureSlot

STUDI_SUFFIX = "@student.hpi.uni-potsdam.de"


def demo_students():
    return User.objects.filter(username__startswith="studi-", username__endswith=STUDI_SUFFIX)


@pytest.mark.django_db
def test_seed_creates_500_students_and_is_repeatable():
    call_command("seed")
    call_command("seed")

    assert demo_students().count() == NUM_STUDENTS == 500
    assert StudentProfile.objects.filter(user__in=demo_students()).count() == 500


@pytest.mark.django_db
def test_demo_students_can_log_in_with_demo_password():
    call_command("seed")

    user = authenticate(username="studi-042@student.hpi.uni-potsdam.de", password="test-passwort")
    assert user is not None
    assert user.email == user.username


@pytest.mark.django_db
def test_every_student_has_a_valid_non_overlapping_timetable():
    call_command("seed")

    by_profile = defaultdict(list)
    for slot in LectureSlot.objects.filter(profile__user__in=demo_students()):
        by_profile[slot.profile_id].append(slot)

    assert len(by_profile) == NUM_STUDENTS
    for slots in by_profile.values():
        slots.sort(key=lambda s: (s.weekday, s.start))
        for slot in slots:
            assert 0 <= slot.weekday <= 4
            assert time(8) <= slot.start < slot.end <= time(20)
        for first, second in zip(slots, slots[1:]):
            assert first.weekday != second.weekday or first.end <= second.start


@pytest.mark.django_db
def test_all_students_of_a_course_have_it_at_the_same_time():
    call_command("seed")

    times_by_title = defaultdict(set)
    for profile in StudentProfile.objects.filter(user__in=demo_students()).prefetch_related("lectures"):
        titles = {c.name for c in profile.courses.filter(semester=profile.semester)}
        for slot in profile.lectures.all():
            if slot.title in titles:
                times_by_title[(profile.study_program_id, slot.title)].add((slot.weekday, slot.start))
    assert times_by_title
    # Jedes Modul hat zwei feste Termine, egal wer es belegt.
    assert all(len(times) <= 2 for times in times_by_title.values())


@pytest.mark.django_db
def test_many_imported_modules_do_not_fill_the_whole_week():
    """Nach import_lehrplan hat ITSE im 2. Semester viele Wahlpflichtmodule."""
    itse = StudyProgram.objects.create(
        name="IT-Systems Engineering", abbreviation="ITSE", university="HPI", standard_semesters=6
    )
    for number in range(20):
        Course.objects.create(program=itse, name=f"Wahlpflichtmodul {number}", semester=2)

    call_command("seed")

    second_semester = StudentProfile.objects.filter(
        user__in=demo_students(), study_program=itse, semester=2
    )
    assert second_semester.exists()
    for profile in second_semester:
        assert profile.lectures.count() <= MAX_COURSES_PER_SEMESTER * 2


@pytest.mark.django_db
def test_seed_keeps_other_accounts_and_mia():
    other = User.objects.create_user(username="someone@hpi.de", password="x")

    call_command("seed")

    assert User.objects.filter(pk=other.pk).exists()
    assert User.objects.filter(username=DEMO_EMAIL).exists()
