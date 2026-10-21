import importlib.util
from pathlib import Path


def load_conftest():
    path = Path(__file__).with_name("conftest.py")
    spec = importlib.util.spec_from_file_location("talentmind_test_conftest", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load tests/conftest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Item:
    def __init__(self, *, integration: bool):
        self.integration = integration
        self.markers = []

    def get_closest_marker(self, name: str):
        return object() if self.integration and name == "integration" else None

    def add_marker(self, marker):
        self.markers.append(marker)


def test_integration_is_skipped_without_explicit_isolated_opt_in(monkeypatch):
    conftest = load_conftest()
    monkeypatch.delenv("TALENTMIND_ALLOW_INTEGRATION", raising=False)
    integration = Item(integration=True)
    unit = Item(integration=False)

    conftest.pytest_collection_modifyitems(None, [integration, unit])

    assert integration.markers and integration.markers[0].name == "skip"
    assert unit.markers == []


def test_integration_can_run_only_with_explicit_isolated_opt_in(monkeypatch):
    conftest = load_conftest()
    monkeypatch.setenv("TALENTMIND_ALLOW_INTEGRATION", "1")
    integration = Item(integration=True)

    conftest.pytest_collection_modifyitems(None, [integration])

    assert integration.markers == []
