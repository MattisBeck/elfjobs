"""Job-Alerts (#34): Filter speichern, neue passende Stellen als Hinweis in der Kopfzeile."""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from alerts.models import JobAlert
from jobs.models import Company, JobPosting, Tag


def make_posting(title, kind=JobPosting.Kind.SHORT_JOB, wage="15.00", tags=()):
    company, _ = Company.objects.get_or_create(name="Testfirma", industry="Tech")
    posting = JobPosting.objects.create(
        company=company, title=title, kind=kind, workplace=JobPosting.Workplace.REMOTE,
        schedule=JobPosting.Schedule.FLEXIBLE, hourly_wage=Decimal(wage), hours_per_week=5,
    )
    posting.tags.add(*tags)
    return posting


@pytest.fixture
def lena(client, db):
    user = User.objects.create_user("lena@student.hpi.uni-potsdam.de")
    client.force_login(user)
    return user


def save_alert(client, query):
    return client.post("/alerts/neu/", {"query": query})


def test_save_alert_from_current_filters(client, lena):
    response = save_alert(client, "filter=kurzjob&q=Python&min_lohn=15")

    assert response.status_code == 302
    alert = JobAlert.objects.get(user=lena)
    assert alert.query == "filter=kurzjob&q=Python&min_lohn=15"
    assert alert.label == "Kurzjob · „Python“ · ab 15 € brutto"


def test_job_list_offers_saving_the_filters(client, lena):
    content = client.get("/jobs/?filter=kurzjob&q=Python").content.decode()

    assert 'action="/alerts/neu/"' in content
    assert 'name="query" value="filter=kurzjob&amp;q=Python"' in content


def test_new_matching_posting_shows_hint(client, lena):
    python = Tag.objects.create(name="Python")
    make_posting("Alt mit Python", tags=[python])
    save_alert(client, "filter=kurzjob&q=Python")

    make_posting("Neu mit Python", tags=[python])
    make_posting("Neu Aushilfe Lager")
    make_posting("Neu Werkstudent mit Python", kind=JobPosting.Kind.WORKING_STUDENT, tags=[python])

    content = client.get("/jobs/").content.decode()
    assert "1 neue passende Stelle" in content
    alerts_page = client.get("/alerts/")
    assert [(a.label, a.new_count) for a in alerts_page.context["alerts"]] == [("Kurzjob · „Python“", 1)]


def test_number_filters_count_for_alerts(client, lena):
    save_alert(client, "min_lohn=16")

    make_posting("Zu wenig", wage="15.00")
    make_posting("Genug", wage="17.00")

    assert "1 neue passende Stelle" in client.get("/jobs/").content.decode()


def test_viewing_alert_clears_hint_and_opens_list(client, lena):
    save_alert(client, "q=Lager")
    make_posting("Aushilfe Lager")
    make_posting("Lagerhelfer*in")
    assert "2 neue passende Stellen" in client.get("/jobs/").content.decode()
    alert = JobAlert.objects.get()

    response = client.post(f"/alerts/{alert.pk}/ansehen/")

    assert response.status_code == 302
    assert response.url == "/jobs/?q=Lager"
    assert "neue passende" not in client.get("/jobs/").content.decode()


def test_delete_alert(client, lena):
    save_alert(client, "q=Lager")
    alert = JobAlert.objects.get()

    client.post(f"/alerts/{alert.pk}/loeschen/")

    assert not JobAlert.objects.exists()


def test_foreign_alerts_are_404(client, lena, db):
    other = User.objects.create_user("felix@student.hpi.uni-potsdam.de")
    alert = JobAlert.objects.create(user=other, query="q=Lager", label="„Lager“")

    assert client.post(f"/alerts/{alert.pk}/ansehen/").status_code == 404
    assert client.post(f"/alerts/{alert.pk}/loeschen/").status_code == 404
    assert JobAlert.objects.filter(pk=alert.pk).exists()


def test_logged_out_has_no_hint_and_no_save_button(client, db):
    content = client.get("/jobs/").content.decode()

    assert "neue passende" not in content
    assert 'action="/alerts/neu/"' not in content
    assert client.get("/alerts/").status_code == 302


def test_save_needs_post_and_login(client, db):
    assert client.post("/alerts/neu/", {"query": "q=x"}).status_code == 302
    assert not JobAlert.objects.exists()


def test_hint_has_short_form_for_phones(client, lena):
    """Auf dem Handy steht nur „1 neue“, der Rest ist ausblendbar und steht im Tooltip (#124)."""
    save_alert(client, "q=Lager")
    make_posting("Aushilfe Lager")

    content = client.get("/jobs/").content.decode()

    assert '1 neue<span class="alert-hint-long"> passende Stelle</span>' in content
    assert 'title="1 neue passende Stelle"' in content
