from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management import call_command

from accounts.models import StudentProfile
from applications.models import Application
from companies.models import CompanyMember
from jobs.management.commands.seed import DEMO_EMAIL
from jobs.models import Company, JobPosting


def make_posting(title="Werkstudent*in Data", company_name="Weihmann GbR"):
    company = Company.objects.create(name=company_name, industry="Handel")
    return JobPosting.objects.create(
        company=company,
        title=title,
        description="Du wertest Daten aus.",
        kind=JobPosting.Kind.WORKING_STUDENT,
        workplace=JobPosting.Workplace.HYBRID,
        schedule=JobPosting.Schedule.FLEXIBLE,
        hourly_wage=Decimal("16.00"),
        hours_per_week=10,
    )


@pytest.fixture
def posting(db):
    return make_posting()


@pytest.fixture
def student(db):
    user = User.objects.create_user("mia@student.hpi.uni-potsdam.de", first_name="Mia")
    return StudentProfile.objects.create(user=user)


@pytest.fixture
def student_client(client, student):
    client.force_login(student.user)
    return client


def apply_url(posting):
    return f"/jobs/{posting.pk}/bewerben/"


def test_student_can_apply(student_client, student, posting):
    response = student_client.post(apply_url(posting))

    assert response.status_code == 302
    assert response.url == f"/jobs/{posting.pk}/"
    application = Application.objects.get()
    assert application.profile == student
    assert application.posting == posting
    assert application.status == Application.Status.SENT


def test_anonymous_is_sent_to_login(client, posting):
    response = client.post(apply_url(posting))

    assert response.status_code == 302
    assert response.url.startswith("/anmelden/")
    assert not Application.objects.exists()


def test_company_account_gets_403_and_no_button(client, posting):
    user = User.objects.create_user("jobs@weihmann.example")
    CompanyMember.objects.create(user=user, company=posting.company)
    client.force_login(user)

    response = client.post(apply_url(posting))

    assert response.status_code == 403
    assert not Application.objects.exists()
    assert "Mit Profil bewerben" not in client.get(f"/jobs/{posting.pk}/").content.decode()


def test_applying_twice_keeps_one_application(student_client, posting):
    student_client.post(apply_url(posting))
    response = student_client.post(apply_url(posting))

    assert response.status_code == 302
    assert Application.objects.count() == 1


def test_get_shows_step_and_changes_nothing(student_client, posting):
    response = student_client.get(apply_url(posting))

    assert response.status_code == 200
    assert "Wann würdest du arbeiten?" in response.content.decode()
    assert not Application.objects.exists()


def test_detail_shows_disabled_button_after_applying(student_client, posting):
    content = student_client.get(f"/jobs/{posting.pk}/").content.decode()
    assert "Mit Profil bewerben" in content
    assert f'href="/jobs/{posting.pk}/bewerben/"' in content

    content = student_client.post(apply_url(posting), follow=True).content.decode()

    assert "Mit Profil bewerben" not in content
    assert "✓ Beworben am" in content
    assert "disabled" in content
    # Der Merken-Knopf bleibt.
    assert "Merken" in content


def test_profile_lists_only_own_applications(student_client, student, posting):
    other_posting = make_posting(title="Kellner*in", company_name="Café Rot")
    other = StudentProfile.objects.create(user=User.objects.create_user("tom@student.hpi.uni-potsdam.de"))
    Application.objects.create(profile=student, posting=posting)
    Application.objects.create(profile=other, posting=other_posting)

    content = student_client.get("/profil/").content.decode()

    assert "Meine Bewerbungen" in content
    assert "Werkstudent*in Data" in content
    assert "Weihmann GbR" in content
    assert "Gesendet" in content
    assert "Kellner*in" not in content


def test_profile_without_applications_shows_hint(student_client):
    content = student_client.get("/profil/").content.decode()

    assert "Meine Bewerbungen" in content
    assert "Noch keine. Im Stellendetail bewirbst du dich" in content


@pytest.mark.django_db
def test_seed_gives_mia_two_applications():
    call_command("seed")
    call_command("seed")

    applications = Application.objects.filter(profile__user__username=DEMO_EMAIL)
    assert applications.count() == 2
    assert all(a.posting.kind == JobPosting.Kind.WORKING_STUDENT for a in applications)


# Lebenslauf mitschicken (#38)

CV = b"%PDF-1.4\n% Mias Lebenslauf\n%%EOF\n"


def give_cv(profile, content=CV):
    profile.cv_file.save("lebenslauf.pdf", ContentFile(content))


def cv_url(application):
    return f"/bewerbungen/{application.pk}/lebenslauf.pdf"


def test_apply_sends_copy_of_cv(student_client, student, posting):
    give_cv(student)

    student_client.post(apply_url(posting))

    application = Application.objects.get()
    assert application.cv.read() == CV
    # Eine Kopie: Ersetzt Mia ihren Lebenslauf später, bleibt der gesendete erhalten.
    assert application.cv.name != student.cv_file.name
    give_cv(student, CV + b"neu")
    application.cv.open()
    assert application.cv.read() == CV


def test_apply_without_cv_sends_none(student_client, posting):
    student_client.post(apply_url(posting))

    assert not Application.objects.get().cv


def test_applicant_and_admin_can_open_sent_cv(student_client, student, posting, client, admin_user):
    give_cv(student)
    student_client.post(apply_url(posting))
    application = Application.objects.get()

    response = student_client.get(cv_url(application))
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == CV

    client.force_login(admin_user)
    assert client.get(cv_url(application)).status_code == 200


def test_others_cannot_open_sent_cv(student_client, student, posting, client):
    give_cv(student)
    student_client.post(apply_url(posting))
    application = Application.objects.get()

    tom = User.objects.create_user("tom@student.hpi.uni-potsdam.de")
    client.force_login(tom)
    assert client.get(cv_url(application)).status_code == 404

    company_user = User.objects.create_user("jobs@weihmann.example")
    CompanyMember.objects.create(user=company_user, company=posting.company)
    client.force_login(company_user)
    assert client.get(cv_url(application)).status_code == 404

    client.logout()
    assert client.get(cv_url(application)).status_code == 302


def test_admin_shows_cv_link_on_application(student_client, student, posting, client, admin_user):
    give_cv(student)
    student_client.post(apply_url(posting))
    application = Application.objects.get()
    client.force_login(admin_user)

    content = client.get(f"/admin/applications/application/{application.pk}/change/").content.decode()

    assert cv_url(application) in content
    assert "/media/" not in content


def test_profile_links_sent_cv(student_client, student, posting):
    give_cv(student)
    student_client.post(apply_url(posting))
    application = Application.objects.get()

    assert cv_url(application) in student_client.get("/profil/").content.decode()


@pytest.mark.django_db
def test_seed_attaches_cv_to_mias_applications():
    call_command("seed")
    call_command("seed")

    applications = Application.objects.filter(profile__user__username=DEMO_EMAIL)
    assert all(a.cv and a.cv.read().startswith(b"%PDF-") for a in applications)
