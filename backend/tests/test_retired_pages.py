"""Retired overview routes must not survive as direct API entry points."""
from app.main import app


def test_dashboard_api_is_not_registered():
    assert not any(route.path.startswith('/api/dashboard') for route in app.routes)


def test_unconsumed_catalog_writes_are_retired_but_edit_and_export_remain():
    routes = {(method, route.path) for route in app.routes for method in getattr(route, 'methods', [])}
    assert not routes.intersection({('POST', '/api/jobs'), ('DELETE', '/api/jobs/{job_id}'),
                                    ('POST', '/api/jobs/batch-delete'), ('POST', '/api/jobs/import')})
    assert {('PUT', '/api/jobs/{job_id}'), ('GET', '/api/jobs/export')} <= routes
