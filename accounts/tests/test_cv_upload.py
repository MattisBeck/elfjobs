import os

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.forms import CV_MAX_SIZE
from accounts.models import StudentProfile

PDF = b"%PDF-1.4\n% Lebenslauf\n%%EOF\n"


def pdf_upload(content=PDF, name="lebenslauf.pdf"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@pytest.fixture
def lena(db):
    return StudentProfile.objects.create(user=User.objects.create_user("lena@student.hpi.uni-potsdam.de"))


@pytest.fixture
def lena_client(client, lena):
    client.force_login(lena.user)
    return client


def upload(client, file):
    return client.post("/profil/lebenslauf/hochladen/", {"cv_file": file}, follow=True)


def test_upload_pdf_stores_file_outside_repo(lena_client, lena, media_root):
    response = upload(lena_client, pdf_upload())

    lena.refresh_from_db()
    assert lena.cv_file
    assert lena.cv_file.name.startswith("lebenslaeufe/")
    assert lena.cv_file.path.startswith(str(media_root))
    assert lena.cv_file.read() == PDF
    assert "Lebenslauf gespeichert." in response.content.decode()


def test_own_cv_can_be_downloaded(lena_client, lena):
    upload(lena_client, pdf_upload())

    response = lena_client.get("/profil/lebenslauf.pdf")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content) == PDF


def test_uploaded_cv_wins_over_sample(lena_client, lena):
    lena.cv_sample = StudentProfile.CvSample.JULIA
    lena.save()
    upload(lena_client, pdf_upload())

    response = lena_client.get("/profil/lebenslauf.pdf")

    assert b"".join(response.streaming_content) == PDF


@pytest.mark.parametrize("name, content", [
    ("lebenslauf.docx", b"PK\x03\x04 word"),
    ("lebenslauf.pdf", b"PK\x03\x04 kein PDF"),  # Endung passt, Inhalt nicht
    ("bild.png", b"%PDF-1.4 als png"),  # Inhalt passt, Endung nicht
])
def test_other_file_types_are_rejected(lena_client, lena, name, content):
    response = upload(lena_client, pdf_upload(content, name))

    lena.refresh_from_db()
    assert not lena.cv_file
    assert "Bitte lade eine PDF-Datei hoch." in response.content.decode()


def test_too_large_file_is_rejected(lena_client, lena):
    big = PDF + b"0" * CV_MAX_SIZE

    response = upload(lena_client, pdf_upload(big))

    lena.refresh_from_db()
    assert not lena.cv_file
    assert "höchstens 5 MB" in response.content.decode()


def test_replacing_deletes_old_file(lena_client, lena):
    upload(lena_client, pdf_upload())
    lena.refresh_from_db()
    old_path = lena.cv_file.path

    upload(lena_client, pdf_upload(PDF + b"neu"))

    lena.refresh_from_db()
    assert lena.cv_file.read() == PDF + b"neu"
    assert lena.cv_file.path != old_path
    assert not os.path.exists(old_path)


def test_delete_removes_file(lena_client, lena):
    upload(lena_client, pdf_upload())
    lena.refresh_from_db()
    path = lena.cv_file.path

    response = lena_client.post("/profil/lebenslauf/loeschen/", follow=True)

    lena.refresh_from_db()
    assert not lena.cv_file
    assert not os.path.exists(path)
    assert "Lebenslauf gelöscht." in response.content.decode()


def test_cv_url_shows_only_own_cv(client, lena_client, lena):
    upload(lena_client, pdf_upload())
    tom = StudentProfile.objects.create(user=User.objects.create_user("tom@student.hpi.uni-potsdam.de"))
    client.force_login(tom.user)

    response = client.get("/profil/lebenslauf.pdf")

    # Tom hat keinen Lebenslauf, Lenas bekommt er nicht.
    assert response.status_code == 404


def test_cv_is_not_served_under_media(lena_client, lena, client):
    upload(lena_client, pdf_upload())
    lena.refresh_from_db()
    client.logout()

    assert client.get(f"/media/{lena.cv_file.name}").status_code == 404


def test_anonymous_cannot_upload(client, db):
    response = client.post("/profil/lebenslauf/hochladen/", {"cv_file": pdf_upload()})

    assert response.status_code == 302
    assert response.url.startswith("/anmelden/")


def test_profile_shows_upload_form(lena_client):
    content = lena_client.get("/profil/").content.decode()

    assert 'enctype="multipart/form-data"' in content
    assert 'action="/profil/lebenslauf/hochladen/"' in content
