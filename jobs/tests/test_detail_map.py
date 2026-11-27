import json
import re
from decimal import Decimal

from django.contrib.auth import get_user_model

from accounts.models import StudentProfile
from jobs.models import Company, JobPosting
from jobs.travel import save_minutes, travel_start

ALEXANDERPLATZ = (52.5219, 13.4132)
HOME = (52.4000, 13.0600)


def make_posting(title="Kasse", workplace=JobPosting.Workplace.ONSITE, at=ALEXANDERPLATZ, company="Testfirma"):
    company, _ = Company.objects.get_or_create(name=company, industry="Tech")
    return JobPosting.objects.create(
        company=company,
        title=title,
        kind=JobPosting.Kind.SHORT_JOB,
        workplace=workplace,
        schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal("16.00"),
        hours_per_week=10,
        latitude=Decimal(str(at[0])) if at else None,
        longitude=Decimal(str(at[1])) if at else None,
    )


def map_data(response):
    """Die json_script-Daten des Kartenfensters, oder None, wenn es keine Karte gibt."""
    match = re.search(
        r'<script id="detail-map-data" type="application/json">(.*?)</script>',
        response.content.decode(),
        re.S,
    )
    return json.loads(match.group(1)) if match else None


def test_posting_with_location_has_one_marker(client, db):
    posting = make_posting()

    response = client.get(f"/jobs/{posting.pk}/")

    assert 'id="detail-map"' in response.content.decode()
    data = map_data(response)
    assert (data["lat"], data["lon"]) == ALEXANDERPLATZ
    assert data["home"] is None
    assert data["map_url"] == "/jobs/karte/?lat=52.5219&lon=13.4132"


def test_remote_posting_has_no_map(client, db):
    posting = make_posting(workplace=JobPosting.Workplace.REMOTE, at=None)

    response = client.get(f"/jobs/{posting.pk}/")

    assert 'id="detail-map"' not in response.content.decode()
    assert map_data(response) is None


def test_posting_without_location_has_no_map(client, db):
    posting = make_posting(at=None)

    assert map_data(client.get(f"/jobs/{posting.pk}/")) is None


def test_remote_posting_with_coordinates_has_no_map(client, db):
    posting = make_posting(workplace=JobPosting.Workplace.REMOTE)

    assert map_data(client.get(f"/jobs/{posting.pk}/")) is None


def test_detail_map_data_is_escaped(client, db):
    posting = make_posting(title="</script><script>alert(1)</script>", company="</script>Firma")

    content = client.get(f"/jobs/{posting.pk}/").content.decode()

    assert "</script><script>alert(1)" not in content
    assert "\\u003C/script\\u003E" in content


def student(home=HOME):
    user = get_user_model().objects.create_user("lena")
    profile = StudentProfile.objects.create(user=user)
    if home:
        profile.home_latitude, profile.home_longitude = Decimal(str(home[0])), Decimal(str(home[1]))
        profile.save()
    return user


def test_logged_in_student_with_home_gets_second_marker(client, db):
    posting = make_posting()
    client.force_login(student())

    data = map_data(client.get(f"/jobs/{posting.pk}/"))

    assert data["home"] == {"lat": HOME[0], "lon": HOME[1]}
    assert data["travel"] == ""


def test_student_without_home_gets_no_second_marker(client, db):
    posting = make_posting()
    client.force_login(student(home=None))

    assert map_data(client.get(f"/jobs/{posting.pk}/"))["home"] is None


def test_travel_time_only_from_cache(client, db, monkeypatch):
    posting = make_posting()
    client.force_login(student())

    def no_network(*args, **kwargs):
        raise AssertionError("keine Netzwerkabfrage erlaubt")

    monkeypatch.setattr("jobs.travel.urlopen", no_network)
    assert map_data(client.get(f"/jobs/{posting.pk}/"))["travel"] == ""

    save_minutes(travel_start(HOME), (float(posting.latitude), float(posting.longitude)), 35)
    assert map_data(client.get(f"/jobs/{posting.pk}/"))["travel"] == "ca. 35 min mit ÖPNV"
