import pytest


@pytest.fixture(autouse=True)
def demo_password(monkeypatch):
    """Der Seed braucht DEMO_PASSWORD. Tests sollen auch mit einer älteren .env laufen."""
    monkeypatch.setenv("DEMO_PASSWORD", "test-passwort")
