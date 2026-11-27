"""Uni-Mail bestätigen (#31): Konto erst nach Klick auf den Link aus der Mail aktiv."""

import re
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator

from accounts.tests.test_accounts import itse, signup_data  # noqa: F401 (Fixture)

EMAIL = "lena.kraus@student.hpi.uni-potsdam.de"
PASSWORD = "ein-sicheres-passwort-42"


@pytest.fixture
def signed_up(client, itse, mailoutbox):  # noqa: F811
    client.post("/registrieren/", signup_data())
    return User.objects.get(username=EMAIL)


def confirm_path(mail):
    return re.search(r"https?://[^/\s]+(/konto/bestaetigen/\S+/)", mail.body).group(1)


def test_signup_sends_mail_and_account_is_inactive(client, signed_up, mailoutbox):
    assert not signed_up.is_active
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [EMAIL]
    assert "Bestätige deine Uni-Mail" in mailoutbox[0].subject
    assert confirm_path(mailoutbox[0])
    # Nicht eingeloggt, die Wartesseite nennt die Adresse.
    assert client.get("/profil/").status_code == 302
    assert EMAIL in client.get("/registrieren/bestaetigen/").content.decode()


def test_no_login_without_confirmation(client, signed_up):
    response = client.post("/anmelden/", {"username": EMAIL, "password": PASSWORD})

    assert response.status_code == 200
    assert "Bitte bestätige zuerst deine Uni-Mail" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_wrong_password_for_inactive_account_gives_normal_error(client, signed_up):
    response = client.post("/anmelden/", {"username": EMAIL, "password": "falsch"})

    assert "Bitte bestätige zuerst" not in response.content.decode()


def test_valid_link_activates_and_logs_in(client, signed_up, mailoutbox):
    response = client.get(confirm_path(mailoutbox[0]))

    assert response.status_code == 302
    assert response.url == "/profil/"
    signed_up.refresh_from_db()
    assert signed_up.is_active
    assert client.get("/profil/").status_code == 200


def test_link_works_only_once(client, signed_up, mailoutbox):
    path = confirm_path(mailoutbox[0])
    client.get(path)
    client.post("/abmelden/")

    response = client.get(path)

    assert response.status_code == 400
    assert "ungültig oder abgelaufen" in response.content.decode()


def test_manipulated_link_is_rejected(client, signed_up, mailoutbox):
    path = confirm_path(mailoutbox[0])
    uid = path.split("/")[3]

    for bad in [f"/konto/bestaetigen/{uid}/falsch-123/", "/konto/bestaetigen/xyz/falsch-123/"]:
        response = client.get(bad)
        assert response.status_code == 400
        assert "ungültig oder abgelaufen" in response.content.decode()
    signed_up.refresh_from_db()
    assert not signed_up.is_active


def test_expired_link_is_rejected(client, signed_up, mailoutbox):
    path = confirm_path(mailoutbox[0])
    later = datetime.now() + timedelta(days=4)  # gültig sind 3 Tage (PASSWORD_RESET_TIMEOUT)

    with patch.object(default_token_generator, "_now", return_value=later):
        response = client.get(path)

    assert response.status_code == 400
    signed_up.refresh_from_db()
    assert not signed_up.is_active


def test_resend_mail(client, signed_up, mailoutbox):
    response = client.post("/registrieren/bestaetigen/", {"email": EMAIL})

    assert response.status_code == 302
    assert len(mailoutbox) == 2
    assert confirm_path(mailoutbox[1])
    client.get(confirm_path(mailoutbox[1]))
    signed_up.refresh_from_db()
    assert signed_up.is_active


@pytest.mark.parametrize("email", ["unbekannt@student.hpi.uni-potsdam.de", "kein-mail"])
def test_resend_reveals_nothing_for_unknown_mail(client, signed_up, mailoutbox, email):
    response = client.post("/registrieren/bestaetigen/", {"email": email})

    assert response.status_code == 302
    assert len(mailoutbox) == 1


def test_resend_does_nothing_for_active_account(client, mailoutbox, db):
    User.objects.create_user(EMAIL, email=EMAIL, password=PASSWORD)

    client.post("/registrieren/bestaetigen/", {"email": EMAIL})

    assert mailoutbox == []
