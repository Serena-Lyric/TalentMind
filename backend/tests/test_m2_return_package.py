from app.integration.m2_package import load_return_package, package_summary
from app.integration.validate_exchange import validate_return_package


def test_full_m2_return_package_is_consistent():
    package = load_return_package()
    summary = package_summary(package)
    assert summary["definitions"] == 719
    assert summary["unique_definition_ids"] == 719
    assert summary["skill_job_ids"] == 719
    assert summary["change_logs"] == 243
    assert set(summary["sources"]) == {"boss", "hn", "liepin", "linkedin", "zhaopin"}


def test_full_m2_return_package_validation():
    result = validate_return_package()
    assert result["ok"] is True
    assert not result["errors"]
