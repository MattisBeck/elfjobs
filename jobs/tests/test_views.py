import pytest
from django.contrib.auth.models import User


def test_home_redirects_to_job_list(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.url == "/jobs/"


@pytest.mark.django_db
def test_job_list_renders_header(client):
    response = client.get("/jobs/")

    assert response.status_code == 200
    assert "base.html" in [t.name for t in response.templates]
    assert "Anmelden" in response.content.decode()


@pytest.mark.django_db
def test_header_shows_logged_in_user(client):
    user = User.objects.create_user("mia", first_name="Mia", last_name="Schulz")
    client.force_login(user)

    content = client.get("/jobs/").content.decode()

    assert "Mia Schulz" in content
    assert "Anmelden" not in content
