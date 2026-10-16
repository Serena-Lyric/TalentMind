"""Explicit synthetic claims only; no taxonomy or semantic truth is inferred."""
from copy import deepcopy
import socket

import pytest

from test_foundation_inputs import area, load


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("network prohibited")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


def catalog():
    return dict(schema_version="b32-catalog-1", revision="empty-v1", formal_jobs=[])


def source(area, **changes):
    row = dict(id=1, source="synthetic", job_title="甲岗", duties="负责甲系统交付；负责乙系统交付。",
               raw_text="公司介绍：曾做甲系统。\n核心职责：负责甲系统交付；负责乙系统交付。\n不负责销售。")
    return load(area, [row | changes])


def evidence(record, field="duties", quote="负责甲系统交付"):
    text = record.payload[field]
    start = text.index(quote)
    return dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
                field=field, start=start, end=start + len(quote), quote=quote)


def candidate(record, identity="candidate-a", **changes):
    return dict(id=identity, raw_name="甲岗", proposed_name="合成甲岗", kind="job",
        origin="synthetic_assertion", proposer="fixture-author", synthetic_only=True,
        responsibility="core", family_candidates=["software_engineering", "data_ai"],
        review_status="pending_review", unresolved_reason="合成主张，粒度待确认",
        name_evidence=changes.get("name_evidence") or [evidence(record, "job_title", "甲岗")], evidence=[evidence(record)]) | changes


def submission(record, candidates=None, relations=None, **changes):
    return dict(schema_version="b32-submission-1", revision="claims-v1", mode="synthetic_only",
        annotations=[dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
            candidates=[candidate(record)] if candidates is None else candidates,
            relations=[] if relations is None else relations, material_kind="undetermined",
            material_evidence=[], conflicts=[], notes="合成标注，仅验证基础") | changes])


def validate(batch, marks=None, config=None):
    from app.job_analysis.role_classification.governance.validation import validate_submission
    return validate_submission(batch, marks if marks is not None else submission(batch.records[0]),
                               catalog() if config is None else config)


def test_empty_formal_catalog_and_synthetic_claim_stay_separate(area):
    batch = source(area)
    body = validate(batch)[0]
    assert body["formal_jobs"] == []
    assert body["candidates"][0]["synthetic_only"] is True
    assert body["candidates"][0]["family_candidates"] == ["software_engineering", "data_ai"]
    assert body["primary_job"] == dict(state="unresolved", value=None, candidates=["candidate-a"])
    assert body["classification_complete"] is body["formal_statistics_eligible"] is False
    assert body["formal_admitted"] is False
    assert body["source_payload"] == batch.records[0].payload
    contexts = {e["field"]: e["quote"] for e in body["candidates"][0]["evidence_context"]}
    assert contexts["duties"] == batch.records[0].payload["duties"]


@pytest.mark.parametrize("change", [dict(id=""), dict(id=" padded "), dict(id="a/b"),
    dict(id="中文"), dict(proposer="  "), dict(unresolved_reason=" "), dict(raw_name="不存在"),
    dict(name_evidence=[]), dict(evidence=[]), dict(family_candidates=["foreign"]),
    dict(family_candidates=["data_ai", "data_ai"]), dict(review_status="reviewed_accepted"),
    dict(origin="model_approved"), dict(synthetic_only=False), dict(proposed_name="  ")])
def test_invalid_claims_are_rejected(area, change):
    batch = source(area)
    with pytest.raises(ValueError):
        validate(batch, submission(batch.records[0], [candidate(batch.records[0], **change)]))


@pytest.mark.parametrize("bad", ["formal", "duplicate", "extra", "credential"])
def test_formal_admission_duplicate_ids_and_unexpected_fields_fail(area, bad):
    batch = source(area)
    marks, config = submission(batch.records[0]), catalog()
    if bad == "formal":
        config["formal_jobs"] = ["不能发布"]
    elif bad == "duplicate":
        marks["annotations"][0]["candidates"] *= 2
    elif bad == "extra":
        marks["annotations"][0]["vacancy_count"] = 2
    else:
        marks["api_key"] = "prohibited"
    with pytest.raises(ValueError):
        validate(batch, marks, config)


@pytest.mark.parametrize("field,value", [("jd_id", "2"), ("namespace", "other"),
    ("fingerprint", "0" * 64), ("start", 1), ("end", 1), ("quote", "伪造"), ("field", "missing")])
def test_evidence_identity_and_exact_offsets_are_checked(area, field, value):
    batch = source(area)
    marks = submission(batch.records[0])
    marks["annotations"][0]["candidates"][0]["evidence"][0][field] = value
    with pytest.raises(ValueError):
        validate(batch, marks)


def test_multiple_core_claims_remain_unresolved_without_deciding_material_kind(area):
    batch = source(area)
    item = batch.records[0]
    second = candidate(item, "candidate-b", proposed_name="合成乙岗", evidence=[evidence(item, quote="负责乙系统交付")])
    body = validate(batch, submission(item, [candidate(item), second]))[0]
    assert body["primary_job"]["candidates"] == ["candidate-a", "candidate-b"]
    assert body["primary_job"]["state"] == "unresolved" and body["primary_job"]["value"] is None
    assert "multiple_core_claims" in body["reasons"]
    assert body["material_kind"] == "undetermined"
    assert body["name_audit"][0]["candidate_ids"] == ["candidate-a", "candidate-b"]
    assert "vacancy_count" not in body


@pytest.mark.parametrize("kind", ["technology_stack", "mature_composite_candidate", "job"])
def test_technology_composite_and_multiple_position_claims_never_create_formal_jobs(area, kind):
    batch = source(area, job_title="Java / 合成全栈岗")
    item = batch.records[0]
    claim = candidate(item, raw_name="Java", kind=kind, name_evidence=[evidence(item, "job_title", "Java")])
    body = validate(batch, submission(item, [claim], material_kind="possible_multiple_positions",
        material_evidence=[evidence(item, "job_title", "Java / 合成全栈岗")]))[0]
    assert body["candidates"][0]["kind"] == kind
    assert body["formal_jobs"] == [] and body["primary_job"]["value"] is None
    assert body["material_kind"] == "possible_multiple_positions"
    assert "vacancies" not in body and "vacancy_count" not in body


@pytest.mark.parametrize("kind", ["synonym", "related_to", "specialization_of", "technology_direction_of", "possible_composite_of"])
def test_relations_are_pending_claims_without_merging_or_mapping(area, kind):
    batch = source(area)
    item = batch.records[0]
    claims = [candidate(item), candidate(item, "candidate-b", proposed_name="合成乙岗")]
    relation = dict(id="relation-a", source_id="candidate-a", target_id="candidate-b", kind=kind,
        proposer="fixture-author", basis="合成关系待复核", evidence=[evidence(item)], review_status="pending_review")
    body = validate(batch, submission(item, claims, [relation]))[0]
    assert len(body["candidates"]) == 2 and body["relations"][0]["kind"] == kind
    assert body["relations"][0]["mapping_active"] is False
    assert body["formal_jobs"] == []


@pytest.mark.parametrize("change", [dict(id=""), dict(source_id="missing"), dict(target_id="candidate-a"),
    dict(kind="merge"), dict(evidence=[]), dict(proposer="  "), dict(basis=" ")])
def test_invalid_relation_targets_and_attribution_fail(area, change):
    batch = source(area)
    item = batch.records[0]
    relation = dict(id="relation-a", source_id="candidate-a", target_id="candidate-b", kind="related_to",
        proposer="fixture-author", basis="待核查", evidence=[evidence(item)], review_status="pending_review") | change
    with pytest.raises(ValueError):
        validate(batch, submission(item, [candidate(item), candidate(item, "candidate-b")], [relation]))


def test_conflicting_synonym_targets_are_audited_instead_of_last_wins(area):
    batch = source(area)
    item = batch.records[0]
    claims = [candidate(item, f"candidate-{x}", proposed_name=f"合成{x}岗") for x in "abc"]
    relations = [dict(id=f"relation-{x}", source_id="candidate-a", target_id=f"candidate-{x}",
        kind="synonym", proposer="author", basis="未验证", evidence=[evidence(item)], review_status="pending_review") for x in "bc"]
    body = validate(batch, submission(item, claims, relations))[0]
    assert body["relation_audit"] == [dict(reason="multiple_synonym_targets", source_id="candidate-a",
                                         target_ids=["candidate-b", "candidate-c"])]
    assert len(body["relations"]) == 2


def test_explicit_title_duty_conflict_and_dangerous_context_remain_claims(area):
    batch = source(area)
    item = batch.records[0]
    conflict = dict(title=evidence(item, "job_title", "甲岗"), duties=evidence(item, quote="负责乙系统交付"), reason="标题与职责冲突")
    claim = candidate(item, evidence=[evidence(item, "raw_text", "曾做甲系统"), evidence(item, "raw_text", "不负责销售")])
    body = validate(batch, submission(item, [claim], conflicts=[conflict]))[0]
    assert body["conflicts"] == [conflict]
    assert "title_duty_conflict" in body["reasons"]
    assert body["primary_job"]["state"] == "unresolved"
    assert body["semantic_validation"] == "not_performed"
    contexts = {e["field"]: e["quote"] for e in body["candidates"][0]["evidence_context"]}
    assert contexts["raw_text"].startswith("公司介绍：")


def test_missing_annotations_are_explicit_empty_candidates(area):
    batch = source(area)
    marks = submission(batch.records[0])
    marks["annotations"] = []
    body = validate(batch, marks)[0]
    assert body["candidates"] == [] and body["primary_job"]["state"] == "unknown"
    assert "not_submitted" in body["reasons"]


def test_foreign_duplicate_annotations_and_conflict_field_roles_fail(area):
    batch = source(area)
    for change in ("foreign", "duplicate", "conflict"):
        marks = submission(batch.records[0])
        if change == "foreign":
            marks["annotations"][0]["jd_id"] = "2"
        elif change == "duplicate":
            marks["annotations"] *= 2
        else:
            ref = evidence(batch.records[0])
            marks["annotations"][0]["conflicts"] = [dict(title=ref, duties=ref, reason="bad roles")]
        with pytest.raises(ValueError):
            validate(batch, deepcopy(marks))
