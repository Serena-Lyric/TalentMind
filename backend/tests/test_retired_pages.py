"""Retired overview routes must not survive as direct API entry points."""
from app.main import app


def test_dashboard_api_is_not_registered():
    assert not any(route.path.startswith('/api/dashboard') for route in app.routes)
