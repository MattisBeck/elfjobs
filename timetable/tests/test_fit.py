from datetime import time
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from accounts.models import StudentProfile
from jobs.management.commands.seed import DEMO_EMAIL
from jobs.models import Company, JobPosting, Shift
from timetable.fit import FLEXIBEL, KOLLIDIERT, PASST, TEILWEISE, posting_fit
from timetable.models import LectureSlot

MONDAY, TUESDAY, THURSDAY = 0, 1, 3


def make_posting(title="Stelle", shifts=(), workplace=JobPosting.Workplace.ONSITE, schedule=None):
    company, _ = Company.objects.get_or_create(name="Testfirma", industry="Tech")
    if schedule is None:
        schedule = JobPosting.Schedule.FIXED if shifts else JobPosting.Schedule.FLEXIBLE
    posting = JobPosting.objects.create(
        company=company, title=title, kind=JobPosting.Kind.SHORT_JOB, workplace=workplace,
        schedule=schedule, hourly_wage=Decimal("15.00"), hours_per_week=5,
    )
    for weekday, start, end in shifts:
        Shift.objects.create(posting=posting, weekday=weekday, start=start, end=end)
    return posting


class Slot:
    def __init__(self, weekday, start, end):
        self.weekday, self.start, self.end = weekday, start, end


# Montag 10:00-12:00, mit 30 min Puffer also 09:30-12:30.
LECTURE = [Slot(MONDAY, time(10, 0), time(12, 0))]


@pytest.mark.django_db
def test_fits_when_no_shift_collides():
    posting = make_posting(shifts=[(MONDAY, time(14, 0), time(17, 0)), (TUESDAY, time(10, 0), time(12, 0))])

    fit = posting_fit(posting, LECTURE)

    assert (fit.status, fit.colliding, fit.total) == (PASST, 0, 2)
    assert fit.text == "Passt in deine Woche"


@pytest.mark.django_db
def test_partial_and_wording_singular_and_plural():
    shifts = [(MONDAY, time(10, 30), time(11, 30))] + [(TUESDAY, time(h, 0), time(h + 1, 0)) for h in (14, 15, 16, 17)]
    one = posting_fit(make_posting(shifts=shifts), LECTURE)
    assert (one.status, one.colliding, one.total) == (TEILWEISE, 1, 5)
    assert one.text == "1 von 5 Schichten kollidiert"

    lectures = LECTURE + [Slot(TUESDAY, time(14, 0), time(15, 0))]
    two = posting_fit(make_posting(shifts=shifts), lectures)
    # Di 14:00-15:00 plus Puffer (13:30-15:30) trifft die Schichten 14 und 15 Uhr, dazu Montag.
    assert two.text == "3 von 5 Schichten kollidieren"


@pytest.mark.django_db
def test_all_shifts_collide():
    posting = make_posting(shifts=[(MONDAY, time(10, 0), time(11, 0)), (MONDAY, time(11, 0), time(12, 0))])

    fit = posting_fit(posting, LECTURE)

    assert (fit.status, fit.colliding, fit.total) == (KOLLIDIERT, 2, 2)
    assert fit.text == "Kollidiert mit Vorlesungen"


@pytest.mark.django_db
def test_flexible_posting_and_posting_without_shifts():
    flexible = posting_fit(make_posting(), LECTURE)
    assert flexible.status == FLEXIBEL
    assert flexible.text == "Flexible Zeiten, du wählst die Schichten"

    # Auch eine "feste" Stelle ohne eingetragene Schichten gilt als flexibel.
    no_shifts = make_posting(schedule=JobPosting.Schedule.FIXED)
    assert posting_fit(no_shifts, LECTURE).status == FLEXIBEL


@pytest.mark.django_db
def test_shift_starting_exactly_when_lecture_plus_buffer_ends_fits():
    # Vorlesung endet 12:00, Puffer 30 min, Schicht beginnt 12:30.
    assert posting_fit(make_posting(shifts=[(MONDAY, time(12, 30), time(14, 0))]), LECTURE).status == PASST


@pytest.mark.django_db
def test_shift_ending_exactly_when_lecture_minus_buffer_starts_fits():
    # Vorlesung beginnt 10:00, Puffer 30 min, Schicht endet 09:30.
    assert posting_fit(make_posting(shifts=[(MONDAY, time(8, 0), time(9, 30))]), LECTURE).status == PASST


@pytest.mark.django_db
def test_buffer_is_applied_on_both_sides():
    # 10 min nach Vorlesungsende bzw. 10 min vor Vorlesungsbeginn: kollidiert wegen des Puffers.
    after = make_posting(shifts=[(MONDAY, time(12, 10), time(14, 0))])
    before = make_posting(shifts=[(MONDAY, time(8, 0), time(9, 50))])

    assert posting_fit(after, LECTURE).status == KOLLIDIERT
    assert posting_fit(before, LECTURE).status == KOLLIDIERT


@pytest.mark.django_db
def test_remote_has_no_buffer_but_hybrid_has():
    shifts = [(MONDAY, time(12, 10), time(14, 0))]
    remote = make_posting(shifts=shifts, workplace=JobPosting.Workplace.REMOTE)
    hybrid = make_posting(shifts=shifts, workplace=JobPosting.Workplace.HYBRID)

    assert posting_fit(remote, LECTURE).status == PASST
    assert posting_fit(hybrid, LECTURE).status == KOLLIDIERT
    # Eine echte Überschneidung kollidiert auch remote.
    overlapping = make_posting(shifts=[(MONDAY, time(11, 0), time(13, 0))], workplace=JobPosting.Workplace.REMOTE)
    assert posting_fit(overlapping, LECTURE).status == KOLLIDIERT


@pytest.mark.django_db
def test_other_weekdays_do_not_interfere():
    lectures = [Slot(MONDAY, time(8, 0), time(20, 0)), Slot(THURSDAY, time(8, 0), time(10, 0))]
    posting = make_posting(shifts=[(TUESDAY, time(9, 0), time(12, 0)), (THURSDAY, time(11, 0), time(13, 0))])

    # Do 11:00 liegt 60 min nach Vorlesungsende, Di hat keine Vorlesung.
    assert posting_fit(posting, lectures).status == PASST


@pytest.mark.django_db
def test_no_lectures_means_everything_fits():
    assert posting_fit(make_posting(shifts=[(MONDAY, time(9, 0), time(12, 0))]), []).status == PASST


# --- Stellenliste ---


@pytest.fixture
def mia(db):
    user = User.objects.create_user("mia", password="pw")
    profile = StudentProfile.objects.create(user=user)
    LectureSlot.objects.create(profile=profile, weekday=MONDAY, start=time(10, 0), end=time(12, 0), title="Mathe")
    return user


@pytest.fixture
def four_postings(db):
    return {
        "fits": make_posting("Passt", shifts=[(MONDAY, time(14, 0), time(16, 0))]),
        "partial": make_posting("Teils", shifts=[(MONDAY, time(10, 0), time(11, 0)), (TUESDAY, time(10, 0), time(11, 0))]),
        "collides": make_posting("Kollidiert", shifts=[(MONDAY, time(11, 0), time(12, 0))]),
        "flexible": make_posting("Flexibel"),
    }


def titles(response):
    return sorted(p.title for p in response.context["postings"])


def chip_labels(response):
    return [chip["label"] for chip in response.context["chips"]]


def test_logged_in_list_is_filtered_by_default_and_shows_fit_text(client, mia, four_postings):
    client.force_login(mia)

    response = client.get("/jobs/")

    assert titles(response) == ["Flexibel", "Passt"]
    assert "Passt in deine Woche" in response.content.decode()
    assert response.context["chips"][0]["label"] == "Passt in meinen Plan"
    assert response.context["chips"][0]["active"]


def test_plan_chip_can_be_switched_off_and_on(client, mia, four_postings):
    client.force_login(mia)

    chip = client.get("/jobs/").context["chips"][0]
    assert chip["url"] == "/jobs/?plan=aus"

    off = client.get(chip["url"])
    assert titles(off) == ["Flexibel", "Kollidiert", "Passt", "Teils"]
    content = off.content.decode()
    assert "1 von 2 Schichten kollidiert" in content
    assert "Kollidiert mit Vorlesungen" in content
    assert not off.context["chips"][0]["active"]
    assert off.context["chips"][0]["url"] == "/jobs/"


def test_plan_off_is_kept_by_other_chips_and_detail_links(client, mia, four_postings):
    client.force_login(mia)

    response = client.get("/jobs/?plan=aus&q=t")

    by_label = {chip["label"]: chip for chip in response.context["chips"]}
    assert by_label["Kurzjob"]["url"] == "/jobs/?filter=kurzjob&q=t&plan=aus"
    assert f'href="/jobs/{four_postings["fits"].pk}/?q=t&amp;plan=aus"' in response.content.decode()


def test_plan_chip_combines_with_other_filters(client, mia, four_postings):
    client.force_login(mia)
    make_posting("Remote Flexibel", workplace=JobPosting.Workplace.REMOTE)

    response = client.get("/jobs/?filter=remote")

    assert titles(response) == ["Remote Flexibel"]


def test_logged_out_has_no_chip_no_fit_and_full_list(client, four_postings):
    response = client.get("/jobs/")

    assert len(titles(response)) == 4
    assert "Passt in meinen Plan" not in chip_labels(response)
    assert "fit-dot" not in response.content.decode()
    assert client.get("/jobs/?plan=aus").status_code == 200


def test_logged_in_user_without_profile_gets_no_chip(client, four_postings):
    client.force_login(User.objects.create_user("ohne", password="pw"))

    response = client.get("/jobs/")

    assert len(titles(response)) == 4
    assert "Passt in meinen Plan" not in chip_labels(response)


def test_detail_page_uses_the_same_filter(client, mia, four_postings):
    client.force_login(mia)

    response = client.get(f'/jobs/{four_postings["collides"].pk}/')

    assert response.status_code == 200
    assert titles(response) == ["Flexibel", "Passt"]


def test_query_count_does_not_grow_with_postings(client, mia, django_assert_max_num_queries):
    client.force_login(mia)
    two_shifts = [(MONDAY, time(14, 0), time(16, 0)), (TUESDAY, time(14, 0), time(16, 0))]
    for i in range(3):
        make_posting(f"A{i}", shifts=two_shifts)
    with django_assert_max_num_queries(8):
        client.get("/jobs/?plan=aus")

    for i in range(30):
        make_posting(f"B{i}", shifts=two_shifts)
    with django_assert_max_num_queries(8):
        client.get("/jobs/?plan=aus")


def test_seed_example_fits_mia_and_all_statuses_occur(client, db):
    call_command("seed")
    client.force_login(User.objects.get(username=DEMO_EMAIL))

    response = client.get("/jobs/?plan=aus")

    fits = {(p.title, p.company.name, p.hours_per_week): p.fit for p in response.context["postings"]}
    assert fits[("Promoter*in", "Weihmann GbR", 7)].status == PASST
    assert {fit.status for fit in fits.values()} == {PASST, TEILWEISE, KOLLIDIERT, FLEXIBEL}
