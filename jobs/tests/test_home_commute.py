"""Fahrzeit vom Wohnort (#53): Geocoding beim Speichern, ÖPNV-Zeit oder Luftlinie, Einsatz in Lohn und Passung.

Kein Test ruft eine echte API auf: Geocoding und VBB sind gemockt.
"""

import json
from datetime import time
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from accounts.geocode import geocode
from accounts.models import StudentProfile
from jobs.models import Company, JobPosting, Shift
from jobs.travel import apply_home_commutes, home_commute_minutes, save_minutes
from timetable.fit import KOLLIDIERT, PASST, posting_fit
from timetable.models import LectureSlot

POTSDAM_HBF = (52.392, 13.067)
# Etwa 5 km östlich (13.067 + 0.0735 Grad Länge ≈ 5 km auf diesem Breitengrad).
FIVE_KM_EAST = (52.392, 13.1405)


@pytest.fixture
def company(db):
    return Company.objects.create(name="Weihmann GbR", industry="Tech", commute_minutes=30)


def make_posting(company, workplace="onsite", location=FIVE_KM_EAST):
    return JobPosting.objects.create(
        company=company, title="Promoter*in", kind="short_job", workplace=workplace,
        hours_per_week=4, hourly_wage=Decimal("16.00"),
        latitude=location[0] if location else None, longitude=location[1] if location else None,
    )


@pytest.fixture
def profile(db):
    user = User.objects.create_user("mia", password="pw-12345678")
    return StudentProfile.objects.create(
        user=user, home_town="Potsdam", home_latitude=Decimal(POTSDAM_HBF[0]), home_longitude=Decimal(POTSDAM_HBF[1]),
    )


# Geocoding


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return json.dumps(self.body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_geocode_returns_coordinates():
    with patch("accounts.geocode.urlopen", return_value=FakeResponse([{"lat": "52.39", "lon": "13.06"}])) as urlopen:
        assert geocode("Potsdam") == (52.39, 13.06)
    request = urlopen.call_args.args[0]
    assert "q=Potsdam" in request.full_url
    assert request.get_header("User-agent") == "elfjobs-prototype"


def test_geocode_unknown_place_or_error_gives_none():
    with patch("accounts.geocode.urlopen", return_value=FakeResponse([])):
        assert geocode("Gibtsnicht") is None
    with patch("accounts.geocode.urlopen", side_effect=TimeoutError):
        assert geocode("Potsdam") is None


@pytest.mark.django_db
def test_saving_profile_geocodes_changed_home_town(client, profile):
    client.force_login(profile.user)
    with patch("accounts.views.geocode", return_value=(52.4, 13.1)) as fake_geocode, \
            patch("accounts.views.warm_home_commutes") as warm:
        client.post("/profil/", {"first_name": "Mia", "last_name": "", "home_town": "Potsdam-Babelsberg"})

    fake_geocode.assert_called_once_with("Potsdam-Babelsberg")
    warm.assert_called_once()
    profile.refresh_from_db()
    assert profile.home == (52.4, 13.1)


@pytest.mark.django_db
def test_unknown_home_town_clears_coordinates_and_explains(client, profile):
    client.force_login(profile.user)
    with patch("accounts.views.geocode", return_value=None):
        response = client.post(
            "/profil/", {"first_name": "Mia", "last_name": "", "home_town": "Gibtsnicht"}, follow=True
        )

    profile.refresh_from_db()
    assert profile.home is None
    assert "haben wir auf der Karte nicht gefunden" in response.content.decode()


@pytest.mark.django_db
def test_unchanged_home_town_does_not_geocode(client, profile):
    client.force_login(profile.user)
    with patch("accounts.views.geocode") as fake_geocode:
        client.post("/profil/", {"first_name": "Mia", "last_name": "", "home_town": "Potsdam"})

    fake_geocode.assert_not_called()


# Fahrzeit


@pytest.mark.django_db
def test_cached_public_transport_time_wins(company):
    posting = make_posting(company)
    save_minutes(POTSDAM_HBF, FIVE_KM_EAST, 12)

    assert home_commute_minutes(POTSDAM_HBF, [posting]) == {posting.id: 12}


@pytest.mark.django_db
def test_without_cache_falls_back_to_straight_line(company):
    posting = make_posting(company)

    minutes = home_commute_minutes(POTSDAM_HBF, [posting])[posting.id]

    # 10 min + 5 km × 1,5 min ≈ 18 min
    assert 17 <= minutes <= 19


@pytest.mark.django_db
def test_straight_line_estimate_stays_realistic_on_long_distances(company):
    """Review #105: Potsdam Hbf → Berlin-Mitte (etwa 26 km) darf nicht 100 min dauern."""
    posting = make_posting(company, location=(52.520, 13.405))

    minutes = home_commute_minutes(POTSDAM_HBF, [posting])[posting.id]

    assert 45 <= minutes <= 55


@pytest.mark.django_db
def test_no_connection_in_cache_falls_back_to_straight_line(company):
    posting = make_posting(company)
    save_minutes(POTSDAM_HBF, FIVE_KM_EAST, None)

    assert 17 <= home_commute_minutes(POTSDAM_HBF, [posting])[posting.id] <= 19


@pytest.mark.django_db
def test_remote_and_postings_without_location_keep_their_defaults(company, profile):
    remote = make_posting(company, workplace="remote", location=None)
    nowhere = make_posting(company, location=None)

    apply_home_commutes(profile, [remote, nowhere])

    assert remote.one_way_commute_minutes == 0
    assert nowhere.one_way_commute_minutes == 30


@pytest.mark.django_db
def test_effective_wage_uses_home_commute(company, profile):
    posting = make_posting(company)
    Shift.objects.create(posting=posting, weekday=0, start=time(14), end=time(18))
    company_wage = posting.effective_wage
    save_minutes(POTSDAM_HBF, FIVE_KM_EAST, 10)

    apply_home_commutes(profile, [posting])

    assert posting.one_way_commute_minutes == 10
    # 4 h Arbeit, 1 Fahrt à 2 × 10 min: 16 € × 4 / (4 + 1/3) = 14,77 €
    assert posting.effective_wage == Decimal("14.77")
    assert posting.effective_wage > company_wage


@pytest.mark.django_db
def test_fit_uses_home_commute_as_buffer(company, profile):
    """Schicht 15 min nach der Vorlesung: kollidiert mit 30 min Puffer der Firma, passt mit 10 min vom Wohnort."""
    posting = make_posting(company)
    Shift.objects.create(posting=posting, weekday=0, start=time(11, 45), end=time(15, 45))
    lectures = [LectureSlot.objects.create(profile=profile, title="PT1", weekday=0, start=time(9, 15), end=time(11, 30))]

    assert posting_fit(posting, lectures).status == KOLLIDIERT

    save_minutes(POTSDAM_HBF, FIVE_KM_EAST, 10)
    apply_home_commutes(profile, [posting])

    assert posting_fit(posting, lectures).status == PASST


@pytest.mark.django_db
def test_job_list_shows_home_based_wage_only_for_logged_in_with_home(client, company, profile):
    posting = make_posting(company)
    Shift.objects.create(posting=posting, weekday=0, start=time(14), end=time(18))
    save_minutes(POTSDAM_HBF, FIVE_KM_EAST, 10)

    logged_out = client.get("/jobs/").context["postings"][0]
    client.force_login(profile.user)
    logged_in = client.get("/jobs/?plan=aus").context["postings"][0]

    assert logged_out.one_way_commute_minutes == 30
    assert logged_in.one_way_commute_minutes == 10
    assert logged_in.effective_wage == Decimal("14.77")
