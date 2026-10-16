"""Offline annotation/metric contract. Synthetic oracles exercise code, never certify semantics."""
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..foundation.inputs import InputRecord, check_public, digest, parse_json
from ..semantics.models import Degree, RequirementObject, State
from .catalog import Category, Strict

STATES = ("required", "preferred", "mentioned", "not_required", "uncertain")
CATEGORIES = ("technical_skill", "professional_skill", "engineering_practice", "soft_skill")


class Span(Strict):
    field: Literal["raw_text", "requirements", "duties", "experience", "job_title"]
    start: int
    end: int
    quote: str


class Fact(Strict):
    name: str = Field(min_length=1)
    evidence: Span
    state: State | None = None
    category: Category | None = None
    requirement_object: RequirementObject | None = None
    degree: Degree | None = None
    formal_admitted: bool = False


class Group(Strict):
    relation: Literal["any_of", "all_of"]
    state: State
    members: list[str] = Field(min_length=2)
    member_states: dict[str, State]
    evidence: Span


class Observations(Strict):
    skills: list[Fact]
    non_skills: list[Fact]
    candidates: list[Fact]
    groups: list[Group]


class Reference(Strict):
    method: Literal["synthetic_test_oracle", "human_annotation", "model_assisted_human_annotation"]
    review_status: Literal["pending_human_review", "human_reviewed"]
    reviewer: str | None
    legal_use: str | None
    version: str = Field(min_length=1)
    note: str = Field(min_length=1)


class Sample(Strict):
    id: str = Field(min_length=1)
    input_row: dict
    annotations: Observations


class Benchmark(Strict):
    schema_version: Literal["b22-benchmark-1"]
    dataset_id: str = Field(min_length=1)
    corpus_kind: Literal["synthetic", "real"]
    reference: Reference
    samples: list[Sample] = Field(min_length=1)


def ratio(numerator, denominator):
    return dict(numerator=numerator, denominator=denominator,
                value=numerator / denominator if denominator else None,
                status="observed" if denominator else "undefined_zero_denominator")


def pr(tp, predicted, expected):
    return dict(tp=tp, predicted=predicted, expected=expected,
                precision=ratio(tp, predicted), recall=ratio(tp, expected))


def span_key(fact):
    ev = fact["evidence"]
    return ev["field"], ev["start"], ev["end"]


def fact_key(fact):
    return (fact["name"], *span_key(fact))


def valid_span(fact, payload):
    ev = fact["evidence"]
    text = payload.get(ev["field"], "")
    return 0 <= ev["start"] < ev["end"] <= len(text) and text[ev["start"]:ev["end"]] == ev["quote"]


def validate_benchmark(data):
    check_public(data)
    parsed = Benchmark.model_validate(data)
    if any("category" not in skill.model_fields_set for sample in parsed.samples for skill in sample.annotations.skills):
        raise ValueError("reference skill category must be explicit; null means pending review")
    data = parsed.model_dump()
    reference = data["reference"]
    reviewed = reference["review_status"] == "human_reviewed"
    if reviewed and (not reference["reviewer"] or not reference["reviewer"].strip() or reference["method"] == "synthetic_test_oracle"):
        raise ValueError("human review requires attributed human annotation")
    if data["corpus_kind"] == "real" and (not reviewed or not reference["legal_use"] or not reference["legal_use"].strip()):
        raise ValueError("real corpus requires legal-use and human-review attestation")
    if not reviewed and reference["method"] != "synthetic_test_oracle":
        raise ValueError("unreviewed model/human drafts cannot be evaluation truth")
    identities = set()
    for sample in data["samples"]:
        if sample["id"] in identities:
            raise ValueError("duplicate sample identity")
        identities.add(sample["id"])
        record = InputRecord.from_row(data["dataset_id"], sample["input_row"])
        for kind in ("skills", "non_skills", "candidates", "groups"):
            keys = []
            for fact in sample["annotations"][kind]:
                if not valid_span(fact, record.payload):
                    raise ValueError("annotation evidence does not match source")
                keys.append(span_key(fact) if kind == "groups" else fact_key(fact))
                if kind == "groups" and set(fact["member_states"]) != set(fact["members"]):
                    raise ValueError("group members must have explicit member states")
                if kind == "skills" and fact["state"] is None:
                    raise ValueError("annotated skill state is required")
            if len(set(keys)) != len(keys):
                raise ValueError("duplicate annotation fact")
    return data


def load_benchmark(path):
    return validate_benchmark(parse_json(Path(path).read_text(encoding="utf-8-sig")))


def project_predictions(report, benchmark):
    """Project saved outputs, never copy reference labels into predictions or repair old states."""
    data = Benchmark.model_validate(benchmark).model_dump()
    by_identity = {(m["namespace"], m["jd_id"]): m for m in report["members"]}
    result = {}

    def span(ev):
        return {key: ev[key] for key in ("field", "start", "end", "quote")}

    for sample in data["samples"]:
        record = InputRecord.from_row(data["dataset_id"], sample["input_row"])
        member = by_identity.get((record.namespace, record.jd_id))
        if member is None:
            continue
        if member["fingerprint"] != record.fingerprint:
            raise ValueError("prediction and annotation use different snapshots")
        body = member["body"]
        if body is None:
            result[sample["id"]] = dict(skills=[], non_skills=[], candidates=[], groups=[])
            continue
        original = body["original_semantics"]
        statements = {s["id"]: s for s in original["statements"]}
        predicted_skills = []
        for skill in body["skills"]:
            linked = [statements[s] for s in skill["statement_ids"]]
            statement = linked[0] if len(linked) == 1 else None
            predicted_skills.append(dict(name=skill["key"], evidence=span(skill["evidence"]),
                state=("mentioned" if statement["relation"] else statement["state"]) if statement else "uncertain",
                category=skill["category"], requirement_object=statement.get("requirement_object") if statement else None,
                degree=statement["degree"] if statement else None))
        groups = []
        for statement in original["statements"]:
            if not statement["relation"]:
                continue
            mapped = [s for s in body["skills"] if statement["id"] in s["statement_ids"]]
            names = list(dict.fromkeys(s["key"] for s in mapped))
            if len(names) < 2:
                continue
            # Only independently resolved facts of this same object/degree/subject/condition affect a member.
            states = {}
            for skill in mapped:
                originals = [k["name"] for k in statement["skills"] if span_key(k) == span_key(skill)]
                effective = [e["state"] for e in original["effective"] if e["skill"] in originals and
                    all(e.get(k) == statement.get(k) for k in ("requirement_object", "degree", "target", "condition"))]
                states[skill["key"]] = effective[0] if len(effective) == 1 else "uncertain"
            groups.append(dict(relation=statement["relation"], state=statement["state"], members=names,
                               member_states=states, evidence=span(statement["evidence"])))
        result[sample["id"]] = dict(skills=predicted_skills,
            non_skills=[dict(name=n["kind"], evidence=span(n["evidence"])) for n in body["non_skills"]],
            candidates=[dict(name=c["raw_name"], evidence=span(c["evidence"]), formal_admitted=c["formal_admitted"]) for c in body["candidates"]],
            groups=groups)
    return result


def pair_facts(expected, predicted):
    remaining = list(predicted)
    pairs = []
    for gold in expected:
        index = next((i for i, pred in enumerate(remaining) if fact_key(gold) == fact_key(pred)), None)
        pairs.append((gold, remaining.pop(index) if index is not None else None))
    return pairs + [(None, pred) for pred in remaining]


def classes(pairs, field, labels):
    pending = sum(g is not None and g.get(field) is None for g, _ in pairs) if field == "category" else 0
    if field == "category":
        pairs = [(g, p) for g, p in pairs if g is None or g.get(field) is not None]
    confusion = defaultdict(Counter)
    for gold, pred in pairs:
        a = gold.get(field) or "unclassified" if gold else "__spurious__"
        b = pred.get(field) or "unclassified" if pred else "__missing__"
        confusion[a][b] += 1
    return dict(pending_reference_review=pending, confusion={a: dict(counts) for a, counts in confusion.items()},
        per_class={label: pr(sum(g is not None and p is not None and g.get(field) == p.get(field) == label for g, p in pairs),
                            sum(p is not None and p.get(field) == label for _, p in pairs),
                            sum(g is not None and g.get(field) == label for g, _ in pairs)) for label in labels})


def evaluate(benchmark, predictions):
    data = validate_benchmark(benchmark)
    check_public(predictions)
    known = {s["id"] for s in data["samples"]}
    if set(predictions) - known:
        raise ValueError("prediction sample not in benchmark")
    predictions = {key: Observations.model_validate(value).model_dump() for key, value in predictions.items()}
    all_pairs = {kind: [] for kind in ("skills", "non_skills", "candidates")}
    evidence_checks, group_pairs, member_matches = [], [], []
    missed, spurious, leakage, admitted, promoted = [], [], 0, 0, 0
    group_totals = Counter()
    for sample in data["samples"]:
        expected = sample["annotations"]
        predicted = predictions.get(sample["id"], dict(skills=[], non_skills=[], candidates=[], groups=[]))
        payload = InputRecord.from_row(data["dataset_id"], sample["input_row"]).payload
        for kind in all_pairs:
            pairs = pair_facts(expected[kind], predicted[kind])
            all_pairs[kind].extend(pairs)
            for gold, pred in pairs:
                if kind == "skills":
                    if gold is not None and pred is None:
                        missed.append(dict(sample_id=sample["id"], **gold))
                    if gold is None:
                        spurious.append(dict(sample_id=sample["id"], **pred))
                if pred is not None:
                    evidence_checks.append(dict(sample_id=sample["id"], kind=kind, name=pred["name"], evidence=pred["evidence"],
                        offset_valid=valid_span(pred, payload), matches_reference_fact=gold is not None))
        for pred in predicted["skills"]:
            def intersects(gold):
                a, b = pred["evidence"], gold["evidence"]
                return a["field"] == b["field"] and a["start"] < b["end"] and a["end"] > b["start"]
            # A correctly annotated co-occurring skill does not count as condition leakage.
            correct_skill = any(fact_key(pred) == fact_key(g) for g in expected["skills"])
            leakage += not correct_skill and any(intersects(g) for g in expected["non_skills"])
            promoted += not correct_skill and any(intersects(g) for g in expected["candidates"])
        admitted += sum(c["formal_admitted"] for c in predicted["candidates"])
        remaining = list(predicted["groups"])
        for gold in expected["groups"]:
            i = next((i for i, p in enumerate(remaining) if span_key(p) == span_key(gold)), None)
            pred = remaining.pop(i) if i is not None else None
            group_pairs.append((gold, pred))
            for name, state in gold["member_states"].items():
                member_matches.append(pred is not None and pred["member_states"].get(name) == state)
        group_pairs.extend((None, pred) for pred in remaining)
        group_totals["expected"] += len(expected["groups"])
        group_totals["predicted"] += len(predicted["groups"])
        for group in predicted["groups"]:
            evidence_checks.append(dict(sample_id=sample["id"], kind="groups", name=group["relation"], evidence=group["evidence"],
                offset_valid=valid_span(group, payload), matches_reference_fact=any(span_key(g) == span_key(group) and
                    g["relation"] == group["relation"] and sorted(g["members"]) == sorted(group["members"]) for g in expected["groups"])))
    metrics = {kind: pr(sum(g is not None and p is not None for g, p in pairs), sum(p is not None for _, p in pairs),
                       sum(g is not None for g, _ in pairs)) for kind, pairs in all_pairs.items()}
    skills = all_pairs["skills"]
    required_predicted = sum(p is not None and p["state"] == "required" for _, p in skills)
    wrong_required = sum(p is not None and p["state"] == "required" and (g is None or g["state"] != "required") for g, p in skills)
    exact_groups = sum(g is not None and p is not None and g["relation"] == p["relation"] and g["state"] == p["state"] and
                       sorted(g["members"]) == sorted(p["members"]) for g, p in group_pairs)
    reviewed = data["reference"]["review_status"] == "human_reviewed"
    return dict(schema_version="b22-evaluation-1", dataset_id=data["dataset_id"], benchmark_sha256=digest(data),
        predictions_sha256=digest(predictions), reference=data["reference"],
        mode="human_reviewed_corpus_evaluation" if data["corpus_kind"] == "real" and reviewed else "synthetic_program_check",
        quality_claim_allowed=data["corpus_kind"] == "real" and reviewed, quality_threshold=None,
        coverage=dict(samples=len(data["samples"]), human_reviewed_samples=len(data["samples"]) if reviewed else 0,
            missing_prediction_samples=sorted(known - predictions.keys()),
            limitation="counts describe this sample only; no adequacy threshold established"),
        **metrics, states=classes(skills, "state", STATES), skill_categories=classes(skills, "category", CATEGORIES),
        required_false_positive=ratio(wrong_required, required_predicted),
        groups=pr(exact_groups, group_totals["predicted"], group_totals["expected"]),
        group_member_states=ratio(sum(member_matches), len(member_matches)),
        non_skill_as_skill=ratio(leakage, metrics["skills"]["predicted"]),
        candidate_admission_risk=ratio(admitted, metrics["candidates"]["predicted"]), unknown_promoted_to_skill=promoted,
        program_evidence=dict(offset_valid=ratio(sum(c["offset_valid"] for c in evidence_checks), len(evidence_checks)),
            fact_correspondence=ratio(sum(c["matches_reference_fact"] for c in evidence_checks), len(evidence_checks)), checks=evidence_checks),
        diagnostics=dict(missed_skills=missed, spurious_skills=spurious))
