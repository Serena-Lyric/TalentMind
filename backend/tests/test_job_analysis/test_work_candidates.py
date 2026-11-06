"""Synthetic P3 lifecycle contracts; these fixtures are not human semantic truth."""
from copy import deepcopy

import pytest

from app.job_analysis.foundation.inputs import InputRecord, digest
from test_knowledge_alignment import analysis_with, evidence, shipped


def work(jd_id="one", text="开发订单接口，保障订单服务运行。", *, source="Synthetic", title="研发工程师"):
    value = analysis_with(["Python"], jd_id=jd_id)
    row = dict(id=jd_id, source=source, job_title=title, raw_text=text)
    record = InputRecord.from_row("synthetic", row)
    value.update(input_row=row, input_sha256=record.fingerprint)
    value["claims"] = [dict(id="d1", kind="duty", text=text, evidence=[evidence(record, text)],
                            core=True, requirement=None, reason="合成工作陈述")]
    return value


def ref(value, claim="d1"):
    return dict(analysis_sha256=digest(value), claim_id=claim)


def create(value, candidate_id="work-orders"):
    return dict(op="create", candidate_id=candidate_id, description="订单接口工作假设",
                research_question="跨语言实现是否承担相同订单服务责任？", core_work=[ref(value)])


def batch(store, batch_id, values=(), operations=(), **extra):
    return dict(schema_version="m2-work-batch-1", batch_id=batch_id,
                baseline=store.read()["binding"], operation_version="synthetic-operations-1",
                analysis_sha256s=sorted({digest(value) for value in values}), operations=list(operations), **extra)


def apply(store, request, values=(), knowledge=None):
    from app.job_analysis.work_candidates.service import apply_batch
    return apply_batch(store, request, {digest(value): value for value in values}, knowledge or shipped())


def test_two_batches_persist_identity_history_and_exact_retry(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    first, second = work(), work("two", "使用 Go 开发订单接口，保障订单服务运行。", title="平台程序员")
    path = tmp_path / "p3.sqlite3"
    with CandidateStore(path, create=True) as store:
        request = batch(store, "batch-one", [first], [create(first)])
        original = deepcopy(first)
        one = apply(store, request, [first])
        assert first == original
        assert one["binding"]["revision"] == 1
        assert len(one["candidates"]) == 1
    with CandidateStore(path) as store:
        two = apply(store, batch(store, "batch-two", [second]), [second])
        assert set(two["candidates"]) == {"work-orders"}
        assert two["candidates"]["work-orders"]["version"] == 2
        assert len(two["relations"]) == 2
        assert {r["state"] for r in two["relations"].values()} == {"pending_review"}
        assert store.read(1) == one
        assert apply(store, request, [first]) == one
        assert store.read() == two
        assert store.source("analysis", digest(first)) == first
        assert two["counts"]["independent_evidence"] is None
        assert two["counts"]["vacancies"] is None
        assert two["formal_roles"] == []


def test_stale_baseline_changed_retry_and_invalid_batch_roll_back(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        request = batch(store, "b1", [a], [create(a)])
        stale = batch(store, "stale", [a])
        one = apply(store, request, [a])
        with pytest.raises(ValueError, match="baseline"):
            apply(store, stale, [a])
        changed = deepcopy(request)
        changed["operation_version"] = "different"
        with pytest.raises(ValueError, match="batch ID"):
            apply(store, changed, [a])
        broken = batch(store, "broken", [a], [create(a, "new-candidate"), create(a)])
        with pytest.raises(ValueError, match="exists"):
            apply(store, broken, [a])
        assert store.read() == one
        assert store.history("work-orders")[0]["candidate"]["version"] == 1


@pytest.mark.parametrize("op", ["merge", "split", "publish", "formal", "assign_role"])
def test_formal_and_structural_operations_are_unavailable(tmp_path, op):
    from app.job_analysis.work_candidates.storage import CandidateStore
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        with pytest.raises(ValueError):
            apply(store, batch(store, "bad", operations=[dict(op=op)]))
        assert store.read()["binding"]["revision"] == 0


def test_new_candidate_requires_actual_duty_and_research_question(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = analysis_with(["Python"])
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        op = create(a)
        op["core_work"] = [ref(a, "r1")]
        with pytest.raises(ValueError, match="duty"):
            apply(store, batch(store, "skills-only", [a], [op]), [a])
        assert store.read()["candidates"] == {}
