"""Login, Registrierung und „Mail erneut senden“ normalisieren die Mail gleich (#129)."""

import pytest
from django.contrib.auth.models import User

from accounts.forms import LoginForm, normalize_email
from accounts.tests.test_accounts import itse, signup_data  # noqa: F401 (Fixture)

EMAIL = "mia.schulz@student.hpi.uni-potsdam.de"
PASSWORD = "ein-sicheres-passwort-42"
MAIL_ERROR = "Das ist keine gültige Mail-Adresse. Steckt ein Leerzeichen drin?"


@pytest.fixture
def mia(db):
    return User.objects.create_user(EMAIL, email=EMAIL, password=PASSWORD)


@pytest.mark.parametrize("raw", [
    f" {EMAIL} ",
    f"\t{EMAIL}\t",
    f"\u00a0{EMAIL}\u00a0",  # geschütztes Leerzeichen
    f"\u200b{EMAIL}\u200b",  # Zero-Width-Space aus Copy-Paste
    f"\ufeff {EMAIL}\n",
    EMAIL.upper(),
])
def test_normalize_email(raw):
    assert normalize_email(raw) == EMAIL


@pytest.mark.parametrize("raw", [
    f" {EMAIL} ",
    f"\t{EMAIL}",
    f"\u00a0{EMAIL}\u00a0",
    f"\u200b{EMAIL}",
    "Mia.Schulz@Student.HPI.uni-potsdam.de",
])
def test_login_with_messy_mail(client, mia, raw):
    response = client.post("/anmelden/", {"username": raw, "password": PASSWORD})

    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(mia.pk)


@pytest.mark.parametrize("raw", ["mia @student.hpi.uni-potsdam.de", "mia.schulz", "mia@"])
def test_login_with_invalid_mail_shows_mail_error(client, mia, raw):
    response = client.post("/anmelden/", {"username": raw, "password": PASSWORD})

    assert response.status_code == 200
    assert MAIL_ERROR in response.content.decode()
    # Nicht die allgemeine Meldung „Mail oder Passwort falsch“.
    assert response.context["form"].non_field_errors() == []
    assert "_auth_user_id" not in client.session


def test_password_is_not_stripped(client, db):
    User.objects.create_user(EMAIL, email=EMAIL, password=" mit leerzeichen ")

    assert client.post("/anmelden/", {"username": EMAIL, "password": "mit leerzeichen"}).status_code == 200
    assert client.post("/anmelden/", {"username": EMAIL, "password": " mit leerzeichen "}).status_code == 302


def test_company_account_can_still_log_in(client, db):
    email = "weihmann@firma.elfjobs.local"
    User.objects.create_user(email, email=email, password=PASSWORD)

    response = client.post("/anmelden/", {"username": f" {email.upper()}\u00a0", "password": PASSWORD})

    assert response.status_code == 302


def test_login_field_is_email_input():
    widget = LoginForm().fields["username"].widget

    assert widget.input_type == "email"
    assert widget.attrs["autocomplete"] == "email"


def test_signup_normalizes_mail(client, itse, mailoutbox):  # noqa: F811
    response = client.post("/registrieren/", signup_data(email="\u00a0Lena.Kraus@student.hpi.uni-potsdam.de\u200b"))

    assert response.status_code == 302
    assert User.objects.filter(username="lena.kraus@student.hpi.uni-potsdam.de").exists()


def test_signup_with_space_in_mail_shows_mail_error(client, itse):  # noqa: F811
    response = client.post("/registrieren/", signup_data(email="lena @student.hpi.uni-potsdam.de"))

    assert response.status_code == 200
    assert MAIL_ERROR in response.content.decode()


def test_resend_normalizes_mail(client, db, mailoutbox):
    User.objects.create_user(EMAIL, email=EMAIL, password=PASSWORD, is_active=False)

    client.post("/registrieren/bestaetigen/", {"email": f"\u00a0{EMAIL.upper()}\u200b"})

    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [EMAIL]

