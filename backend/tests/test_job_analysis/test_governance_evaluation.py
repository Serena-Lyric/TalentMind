"""Hand-counted calculator oracles, deliberately wrong predictions and annotation guards."""
import copy
import json
from pathlib import Path

import pytest

from test_foundation_inputs import area


def fact(name, start, end, quote, **values):
    return dict(name=name, evidence=dict(field="raw_text", start=start, end=end, quote=quote), **values)


def observations(**values):
    return dict(skills=[], non_skills=[], candidates=[], groups=[]) | values


def benchmark():
    return dict(schema_version="b22-benchmark-1", dataset_id="calculator-fixture", corpus_kind="synthetic",
        reference=dict(method="synthetic_test_oracle", review_status="pending_human_review", reviewer=None,
                       legal_use=None, version="v1", note="Codex handwritten mathematical test oracle; not human truth"),
        samples=[dict(id="one", input_row=dict(id=1, source="synthetic", job_title="工程师",
            raw_text="Java Python 本科 UnlistedLang"), annotations=observations(skills=[
                fact("java", 0, 4, "Java", state="required", category="technical_skill"),
                fact("python", 5, 11, "Python", state="preferred", category="technical_skill")],
                non_skills=[fact("education", 12, 14, "本科")], candidates=[fact("UnlistedLang", 15, 27, "UnlistedLang")]))])


def test_hand_counted_precision_recall_omissions_false_positives_states_and_categories():
    from app.job_analysis.governance.evaluation import evaluate
    data = benchmark()
    prediction = observations(skills=[fact("java", 0, 4, "Java", state="preferred", category="soft_skill"),
                                     fact("education", 12, 14, "本科", state="required", category="technical_skill")])
    report = evaluate(data, {"one": prediction})
    extraction = report["skills"]
    assert extraction["tp"] == 1 and extraction["predicted"] == extraction["expected"] == 2
    assert extraction["precision"]["value"] == extraction["recall"]["value"] == 0.5
    assert report["diagnostics"]["missed_skills"][0]["name"] == "python"
    assert report["diagnostics"]["spurious_skills"][0]["name"] == "education"
    assert report["states"]["confusion"]["required"]["preferred"] == 1
    assert report["states"]["confusion"]["preferred"]["__missing__"] == 1
    assert report["states"]["per_class"]["required"]["recall"]["value"] == 0
    assert report["required_false_positive"]["numerator"] == report["required_false_positive"]["denominator"] == 1
    assert report["skill_categories"]["confusion"]["technical_skill"]["soft_skill"] == 1
    assert report["non_skill_as_skill"]["numerator"] == 1
    assert report["mode"] == "synthetic_program_check" and not report["quality_claim_allowed"]


def test_zero_denominators_and_uncovered_classes_are_undefined():
    from app.job_analysis.governance.evaluation import evaluate
    data = benchmark(); data["samples"][0]["annotations"] = observations()
    report = evaluate(data, {"one": observations()})
    for ratio in [report["skills"]["precision"], report["skills"]["recall"], report["required_false_positive"],
                  report["groups"]["precision"], report["candidate_admission_risk"],
                  report["states"]["per_class"]["not_required"]["recall"]]:
        assert ratio["value"] is None and ratio["status"] == "undefined_zero_denominator"
    assert report["states"]["per_class"]["not_required"]["expected"] == 0
    assert report["coverage"]["human_reviewed_samples"] == 0


def test_duplicate_predictions_are_false_positives_not_extra_true_positives():
    from app.job_analysis.governance.evaluation import evaluate
    truth = benchmark()["samples"][0]["annotations"]
    prediction = copy.deepcopy(truth); prediction["skills"].append(copy.deepcopy(truth["skills"][0]))
    result = evaluate(benchmark(), {"one": prediction})
    assert result["skills"]["tp"] == 2 and result["skills"]["predicted"] == 3
    assert result["skills"]["precision"]["value"] == pytest.approx(2 / 3)


def test_program_evidence_location_check_is_separate_from_fact_correspondence():
    from app.job_analysis.governance.evaluation import evaluate
    truth = benchmark()["samples"][0]["annotations"]
    prediction = copy.deepcopy(truth)
    prediction["skills"][0]["name"] = "mysql"  # quotation is locatable, meaning is wrong
    prediction["skills"][1]["evidence"]["quote"] = "forged"
    report = evaluate(benchmark(), {"one": prediction})
    assert report["program_evidence"]["offset_valid"]["value"] == 0.75
    assert report["program_evidence"]["fact_correspondence"]["value"] == 0.75
    assert report["skills"]["tp"] == 1
    mysql = next(c for c in report["program_evidence"]["checks"] if c["name"] == "mysql")
    assert mysql["offset_valid"] is True
    assert mysql["matches_reference_fact"] is False


def test_any_all_and_member_states_are_evaluated_independently():
    from app.job_analysis.governance.evaluation import evaluate
    data = benchmark()
    group = dict(relation="any_of", state="required", members=["java", "python"],
                 member_states={"java": "mentioned", "python": "mentioned"},
                 evidence=dict(field="raw_text", start=0, end=11, quote="Java Python"))
    data["samples"][0]["annotations"]["groups"] = [group]
    prediction = copy.deepcopy(data["samples"][0]["annotations"])
    prediction["groups"][0]["relation"] = "all_of"
    prediction["groups"][0]["member_states"]["java"] = "required"
    report = evaluate(data, {"one": prediction})
    assert report["groups"]["tp"] == 0
    assert report["group_member_states"]["numerator"] == 1
    assert report["group_member_states"]["denominator"] == 2


def test_candidate_extraction_and_both_forms_of_illegal_admission_are_counted():
    from app.job_analysis.governance.evaluation import evaluate
    data = benchmark(); truth = data["samples"][0]["annotations"]
    prediction = copy.deepcopy(truth)
    prediction["candidates"][0]["formal_admitted"] = True
    prediction["skills"].append(fact("UnlistedLang", 15, 27, "UnlistedLang", state="required"))
    report = evaluate(data, {"one": prediction})
    assert report["candidates"]["tp"] == 1
    assert report["candidate_admission_risk"]["numerator"] == 1
    assert report["unknown_promoted_to_skill"] == 1


@pytest.mark.parametrize("tamper", ["missing_annotations", "duplicate_sample", "invalid_gold_quote", "model_truth", "real_without_human", "real_without_rights"])
def test_unreviewed_truth_or_bad_annotations_are_rejected(tamper):
    from app.job_analysis.governance.evaluation import evaluate
    data = benchmark()
    if tamper == "missing_annotations":
        del data["samples"][0]["annotations"]
    elif tamper == "duplicate_sample":
        data["samples"].append(copy.deepcopy(data["samples"][0]))
    elif tamper == "invalid_gold_quote":
        data["samples"][0]["annotations"]["skills"][0]["evidence"]["quote"] = "forged"
    elif tamper == "model_truth":
        data["reference"]["method"] = "model_output"
    else:
        data["corpus_kind"] = "real"
        if tamper == "real_without_rights":
            data["reference"].update(method="human_annotation", review_status="human_reviewed", reviewer="fixture-human")
    with pytest.raises(ValueError):
        evaluate(data, {})


def test_real_quality_report_requires_explicit_human_and_legal_use_attestation():
    from app.job_analysis.governance.evaluation import evaluate
    data = benchmark(); data["corpus_kind"] = "real"
    data["reference"].update(method="human_annotation", review_status="human_reviewed", reviewer="fixture-human",
                             legal_use="Synthetic test of the attestation gate; this is not a real corpus")
    report = evaluate(data, {"one": data["samples"][0]["annotations"]})
    assert report["mode"] == "human_reviewed_corpus_evaluation"
    assert report["quality_claim_allowed"] is True
    assert report["quality_threshold"] is None


def test_reader_rejects_duplicate_json_keys_and_no_silent_missing_predictions(area):
    from app.job_analysis.governance.evaluation import load_benchmark, evaluate
    path = area / "annotations.json"
    path.write_text('{"schema_version":"b22-benchmark-1","schema_version":"other"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_benchmark(path)
    report = evaluate(benchmark(), {})
    assert report["coverage"]["missing_prediction_samples"] == ["one"]
    assert report["skills"]["recall"]["value"] == 0
    with pytest.raises(ValueError):
        evaluate(benchmark(), {"unknown-sample": observations()})


def test_committed_synthetic_fixture_is_pending_human_review_and_roundtrips():
    from app.job_analysis.governance.evaluation import load_benchmark, evaluate
    path = Path(__file__).resolve().parents[1] / "fixtures/governance/synthetic-reference.v1.json"
    data = load_benchmark(path)
    assert data["reference"]["review_status"] == "pending_human_review"
    assert len(data["samples"]) >= 8
    report = evaluate(data, {s["id"]: s["annotations"] for s in data["samples"]})
    assert report["skills"]["precision"]["value"] == 1
    assert report["skills"]["recall"]["value"] == 1
    assert not report["quality_claim_allowed"]


def test_saved_governance_predictions_are_separate_from_reference_and_cannot_swap_inputs(area):
    from app.job_analysis.governance.evaluation import project_predictions, evaluate
    from app.job_analysis.governance.runner import execute
    from app.job_analysis.governance.store import GovernanceStore
    from test_governance import stage_b2
    _, old = stage_b2(area, ["Java 或 Python 至少掌握一种。"])
    with GovernanceStore(area / "state.sqlite3") as store:
        report = execute(store, old["run_id"])
    data = benchmark(); data["dataset_id"] = "fixture"
    data["samples"][0].update(input_row=dict(id=1, source="synthetic-1", job_title="工程师",
        raw_text="Java 或 Python 至少掌握一种。", dup_group="same-job", cross_source=1))
    data["samples"][0]["annotations"] = observations(skills=[
        fact("java", 0, 4, "Java", state="mentioned", category="technical_skill"),
        fact("python", 7, 13, "Python", state="mentioned", category="technical_skill")], groups=[
        dict(relation="any_of", state="required", members=["java", "python"], member_states={"java": "mentioned", "python": "mentioned"},
             evidence=dict(field="raw_text", start=0, end=20, quote="Java 或 Python 至少掌握一种"))])
    predictions = project_predictions(report, data)
    assert predictions["one"]["skills"][0]["state"] == "mentioned"
    result = evaluate(data, predictions)
    assert result["groups"]["tp"] == 1
    assert result["group_member_states"]["value"] == 1
    data["samples"][0]["input_row"]["raw_text"] = "different source"
    with pytest.raises(ValueError):
        project_predictions(report, data)


def test_evaluate_cli_exports_separate_prediction_reference_and_checks(area):
    import subprocess
    import sys
    from app.job_analysis.governance.evaluation import load_benchmark
    from app.job_analysis.foundation.inputs import read_snapshot
    from app.job_analysis.semantics.store import SemanticStore
    from app.job_analysis.semantics.runner import execute as b2
    from app.job_analysis.governance.store import GovernanceStore
    from app.job_analysis.governance.runner import execute
    root = Path(__file__).resolve().parents[2]
    source = Path(__file__).resolve().parents[1] / "fixtures/governance/synthetic-reference.v1.json"
    data = load_benchmark(source)
    path = area / "input.json"; path.write_text(json.dumps([s["input_row"] for s in data["samples"]]), encoding="utf-8")
    with SemanticStore(area / "state.sqlite3") as store:
        old = b2(store, read_snapshot(path, data["dataset_id"]))
    with GovernanceStore(area / "state.sqlite3") as store:
        report = execute(store, old["run_id"])
    cli = subprocess.run([sys.executable, "-m", "app.job_analysis.governance", "evaluate", "--state", str(area / "state.sqlite3"),
        "--run", report["run_id"], "--benchmark", str(source), "--output", str(area / "evaluation")], cwd=root, capture_output=True, text=True)
    assert cli.returncode == 0, cli.stderr
    metadata = json.loads(cli.stdout)
    artifact = json.loads((area / "evaluation" / (metadata["evaluation_id"] + ".json")).read_text(encoding="utf-8"))
    assert set(artifact) == {"evaluation", "predictions", "annotations"}
    assert artifact["evaluation"]["quality_claim_allowed"] is False
    assert artifact["annotations"] == data
    assert artifact["evaluation"]["program_evidence"]["offset_valid"]["value"] == 1


def test_missing_reference_category_is_not_a_false_classification_error():
    from app.job_analysis.governance.evaluation import evaluate
    data = benchmark(); prediction = copy.deepcopy(data["samples"][0]["annotations"])
    del data["samples"][0]["annotations"]["skills"][0]["category"]
    with pytest.raises(ValueError):
        evaluate(data, {"one": prediction})


def test_explicit_unreviewed_category_is_excluded_from_classification_denominators():
    from app.job_analysis.governance.evaluation import evaluate
    data = benchmark(); prediction = copy.deepcopy(data["samples"][0]["annotations"])
    data["samples"][0]["annotations"]["skills"][0]["category"] = None
    result = evaluate(data, {"one": prediction})
    technical = result["skill_categories"]["per_class"]["technical_skill"]
    assert technical["tp"] == technical["predicted"] == technical["expected"] == 1
    assert result["skill_categories"]["pending_reference_review"] == 1
