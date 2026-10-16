"""Synthetic assertions exercise storage/evidence, never classification accuracy."""
import copy
import json
import socket

import pytest

from test_foundation_inputs import area, load
from app.job_analysis.foundation.inputs import InputRecord


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("external/service network prohibited")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


def record(**changes):
    return InputRecord.from_row("fixture", dict(id=1, source="synthetic", job_title="示例甲",
        raw_text="职责示例乙；协助示例丙；方向甲与方向乙；级别甲。", duties="职责示例乙") | changes)


def evidence(item, field="raw_text", quote="示例乙"):
    text = item.payload[field]
    start = text.index(quote)
    return dict(namespace=item.namespace, jd_id=item.jd_id, fingerprint=item.fingerprint,
                field=field, start=start, end=start + len(quote), quote=quote)


def decision(value=None, refs=None, state=None):
    return dict(state=state or ("known" if value else "unknown"), value=value,
                candidates=[], evidence=refs or [], reason="显式合成断言，非识别结果")


def taxonomy(**changes):
    return dict(schema_version="b30-taxonomy-1", revision="synthetic-v1", mode="synthetic_example",
        job_family=["family-a"], canonical_job=["role-a", "role-b", "role-c"],
        technology_tracks=["track-a", "track-b"], seniority=["level-a"]) | changes


def annotation(item=None):
    item = item or record()
    return dict(namespace=item.namespace, jd_id=item.jd_id, fingerprint=item.fingerprint,
        origin="synthetic_assertion", author="fixture-author", review_status="pending_review",
        job_family=decision(), canonical_job=decision(), technology_tracks=[],
        technology_tracks_status="unknown", seniority=decision(), auxiliary_roles=[],
        material_kind="undetermined", material_evidence=[], conflicts=[], notes="待产品规则确认")


def validated(item, data, config=None):
    from app.job_analysis.role_classification.validation import validate_annotation
    return validate_annotation(item, data, config or taxonomy())


def test_unknown_dimensions_and_empty_taxonomy_preserve_source():
    item = record()
    data = annotation(item)
    original = copy.deepcopy(data)
    empty = taxonomy(mode="empty", job_family=[], canonical_job=[], technology_tracks=[], seniority=[])
    result = validated(item, data, empty)
    assert result["annotation"] == original == data
    assert result["source_payload"] == item.payload
    assert result["title_evidence"]["quote"] == "示例甲"
    assert result["duties_evidence"]["quote"] == "职责示例乙"
    assert result["classification_complete"] is False
    assert result["semantic_validation"] == "not_performed"
    assert result["formal_statistics_eligible"] is False


def test_multi_tracks_seniority_and_primary_auxiliary_are_independent():
    item = record()
    data = annotation(item)
    data.update(job_family=decision("family-a", [evidence(item)]),
        canonical_job=decision("role-b", [evidence(item)]),
        seniority=decision("level-a", [evidence(item, quote="级别甲")]),
        technology_tracks_status="known", material_kind="hybrid_role",
        material_evidence=[evidence(item)],
        technology_tracks=[decision("track-a", [evidence(item, quote="方向甲")]),
                           decision("track-b", [evidence(item, quote="方向乙")])],
        auxiliary_roles=[dict(primary="role-b", role=decision("role-c", [evidence(item, quote="示例丙")]),
                              evidence=[evidence(item, quote="协助示例丙")])])
    body = validated(item, data)
    assert body["annotation"] == data
    assert body["classification_complete"] is False  # assertions are still pending review
    assert "vacancy_count" not in body


def test_multiple_positions_and_title_duties_conflict_remain_unresolved():
    item = record()
    data = annotation(item)
    data["material_kind"] = "possible_multiple_positions"
    data["material_evidence"] = [evidence(item)]
    data["canonical_job"] = decision(refs=[evidence(item, "job_title", "示例甲"), evidence(item)], state="unresolved")
    data["canonical_job"]["candidates"] = ["role-a", "role-b"]
    data["conflicts"] = [dict(dimension="canonical_job", title=evidence(item, "job_title", "示例甲"),
                             duties=evidence(item, "duties", "职责示例乙"), reason="标题职责不同，尚未裁决")]
    body = validated(item, data)
    assert body["annotation"]["conflicts"] == data["conflicts"]
    assert body["annotation"]["canonical_job"]["value"] is None
    assert body["requires_review"] is True
    assert "vacancy_count" not in body


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(jd_id="other"),
    lambda d: d.update(namespace="other"),
    lambda d: d.update(fingerprint="0" * 64),
    lambda d: d.update(review_status="approved"),
    lambda d: d.update(formal_statistics_eligible=True),
    lambda d: d["canonical_job"].update(state="known", value="role-a", evidence=[]),
    lambda d: d["canonical_job"].update(value="role-a"),
    lambda d: d["canonical_job"].update(candidates=["not-in-taxonomy"]),
    lambda d: d.update(technology_tracks_status="known"),
    lambda d: d.update(material_kind="possible_multiple_positions"),
])
def test_malformed_identity_states_and_unlicensed_values_rejected(mutation):
    item = record()
    data = annotation(item)
    mutation(data)
    with pytest.raises(ValueError):
        validated(item, data)


@pytest.mark.parametrize("change", [dict(jd_id="2"), dict(namespace="other"),
    dict(fingerprint="0" * 64), dict(start=999), dict(end=999), dict(start=True),
    dict(start=0, end=1), dict(quote="伪造"), dict(field="source"), dict(quote=" ")])
def test_foreign_or_fabricated_character_spans_rejected(change):
    item = record()
    ref = evidence(item) | change
    data = annotation(item)
    data["canonical_job"] = decision("role-a", [ref])
    with pytest.raises(ValueError):
        validated(item, data)


@pytest.mark.parametrize("config", [taxonomy(mode="production"), taxonomy(mode="empty"),
    taxonomy(canonical_job=["role-a", "role-a"]), taxonomy(seniority=[" "]),
    taxonomy(extra="unexpected")])
def test_taxonomy_cannot_claim_production_or_silently_normalize_invalid_values(config):
    with pytest.raises(ValueError):
        validated(record(), annotation(), config)


def test_conflict_cannot_keep_confirmed_value_and_auxiliary_needs_primary_link():
    item = record()
    data = annotation(item)
    data["canonical_job"] = decision("role-a", [evidence(item)])
    data["conflicts"] = [dict(dimension="canonical_job", title=evidence(item, "job_title", "示例甲"),
        duties=evidence(item, "duties", "职责示例乙"), reason="未解决")]
    with pytest.raises(ValueError):
        validated(item, data)
    data["conflicts"] = []
    data["auxiliary_roles"] = [dict(primary="role-b", role=decision("role-c", [evidence(item)]),
                                    evidence=[evidence(item)])]
    with pytest.raises(ValueError):
        validated(item, data)
