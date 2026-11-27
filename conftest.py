import pytest


@pytest.fixture(autouse=True)
def demo_password(monkeypatch):
    """Der Seed braucht DEMO_PASSWORD. Tests sollen auch mit einer älteren .env laufen."""
    monkeypatch.setenv("DEMO_PASSWORD", "test-passwort")


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Uploads (z. B. Firmenlogos) landen in einem temporären Ordner, nicht im Repo."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT
