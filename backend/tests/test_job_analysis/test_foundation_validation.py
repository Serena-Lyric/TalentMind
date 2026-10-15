import pytest

from test_foundation_inputs import area, jd, load


def spec(**change):
    from app.job_analysis.foundation.models import AnalyzerSpec
    return AnalyzerSpec(extractor="fixture-v1", prompt="none", model="offline", configuration="fixture-v1", **change)


def claim(**change):
    return dict(kind="skill", name="Python", requirement="unclassified", evidence=dict(
        namespace="fixture", jd_id="1", field="raw_text", quote="Use Python"), verified=True) | change


def response(facts=None, coverage="complete"):
    return dict(coverage=coverage, facts=[claim()] if facts is None else facts)


def validate(area, output):
    from app.job_analysis.foundation.validation import validate_response
    return validate_response(output, load(area, [jd()]).records[0], {"python": "python"})


def test_version_requires_complete_dependencies_and_has_separate_identity():
    from app.job_analysis.foundation.models import AnalyzerSpec, analysis_version
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AnalyzerSpec(extractor="v1")
    a = analysis_version("v1", spec(), [{"canonical": "python"}])
    assert a.key == analysis_version("v1", spec(), [{"canonical": "python"}]).key
    assert a.key != analysis_version("v2", spec(), [{"canonical": "python"}]).key
    assert a.key != analysis_version("v1", spec(), [{"canonical": "sql"}]).key
    assert a.manifest["dependencies"]["validator"]


@pytest.mark.parametrize("field", ["extractor", "prompt", "model", "configuration"])
def test_analyzer_dependency_changes_invalidate(field):
    from app.job_analysis.foundation.models import analysis_version
    a = spec()
    b = a.model_copy(update={field: "v2"})
    assert analysis_version("v1", a, []).key != analysis_version("v1", b, []).key


def test_substring_validation_ignores_model_verified_and_retains_mapping(area):
    result = validate(area, response())
    fact = result["facts"][0]
    assert result["status"] == "completed"
    assert fact["evidence_status"] == "matched"
    assert fact["canonical_name"] == "python"
    assert fact["location"] == {"field": "raw_text", "start": 0, "end": 10}
    assert fact["semantic_status"] == "unreviewed"


@pytest.mark.parametrize("evidence,reason", [(None, "missing_evidence"),
    (dict(namespace="fixture", jd_id="2", field="raw_text", quote="Use Python"), "foreign_jd"),
    (dict(namespace="other", jd_id="1", field="raw_text", quote="Use Python"), "foreign_jd"),
    (dict(namespace="fixture", jd_id="1", field="raw_text", quote="Use SQL"), "quote_not_found"),
    (dict(namespace="fixture", jd_id="1", field="raw_text", quote=""), "missing_evidence")])
def test_missing_or_cross_jd_evidence_never_verified(area, evidence, reason):
    result = validate(area, response([claim(evidence=evidence)]))
    assert result["status"] == "partial"
    assert result["facts"][0]["evidence_status"] == reason
    assert result["facts"][0]["location"] is None


def test_partial_facts_preserved_and_unknown_not_admitted(area):
    result = validate(area, response([claim(), claim(name="FutureTool"), claim(evidence=None)]))
    assert result["status"] == "partial" and len(result["facts"]) == 3
    assert result["facts"][0]["evidence_status"] == "matched"
    assert result["facts"][1]["governance"] == "candidate"
    assert result["facts"][1]["claim"]["name"] == "FutureTool"


def test_incomplete_differs_from_completed_zero(area):
    assert validate(area, response([], "incomplete"))["status"] == "partial"
    complete = validate(area, response([]))
    assert complete["status"] == "completed" and complete["facts"] == []
    assert validate(area, None)["status"] == "failed"


@pytest.mark.parametrize("value", [None, "", "not JSON", "{}", '{"coverage":"complete","facts":null}',
    '{"coverage":"complete","facts":[],"facts":[]}', dict(facts=[]),
    dict(coverage="complete", facts=[], api_key="secret"), {1: "invalid key"}])
def test_bad_response_cannot_produce_verified_facts(area, value):
    result = validate(area, value)
    assert result["status"] == "failed" and result["facts"] == []


def test_bad_single_fact_does_not_discard_good_fact(area):
    result = validate(area, response([claim(), {"name": 123}]))
    assert result["status"] == "partial"
    assert result["facts"][0]["evidence_status"] == "matched"
    assert result["facts"][1]["evidence_status"] == "invalid_structure"


def test_legacy_binary_claim_never_becomes_five_state_semantics(area):
    fact = validate(area, response([claim(requirement="legacy_required")]))["facts"][0]
    assert fact["requirement"] == "legacy_required"
    assert fact["semantic_status"] == "unreviewed"
