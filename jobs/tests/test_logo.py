import pytest
from django.conf import settings
from django.contrib.auth.models import User

LOGO_IMG = 'src="/static/img/elfjobs-logo.svg" alt="elfjobs"'
FAVICON = '<link rel="icon" type="image/svg+xml" href="/static/img/elfjobs-mark.svg">'


@pytest.mark.django_db
def test_job_list_shows_logo_and_favicon(client):
    content = client.get("/jobs/").content.decode()

    assert LOGO_IMG in content
    assert FAVICON in content


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/anmelden/", "/registrieren/"])
def test_login_and_signup_show_large_logo(client, url):
    content = client.get(url).content.decode()

    assert 'class="form-logo" ' + LOGO_IMG in content


@pytest.mark.django_db
def test_admin_shows_mark_and_name(client):
    admin = User.objects.create_superuser("chefin", password="geheim-test-123")
    client.force_login(admin)

    content = client.get("/admin/").content.decode()

    assert "/static/img/elfjobs-mark.svg" in content
    assert "elfjobs" in content
    assert "Django-Verwaltung" not in content


@pytest.mark.parametrize("name", ["elfjobs-logo.svg", "elfjobs-mark.svg"])
def test_logo_files_exist_without_scripts(name):
    path = settings.BASE_DIR / "static" / "img" / name

    content = path.read_text()
    assert content.startswith("<svg")
    assert "<title>elfjobs</title>" in content
    assert "<script" not in content
