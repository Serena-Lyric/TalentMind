"""Technology use is evidenced by local work, independent of role retrieval."""
import re

from ..foundation.inputs import InputRecord
from .attribution_models import AxisCandidate
from .role_policy import Frame
from .work_evidence import (
    MEANS, PREDICATES, UNSAFE, evidence_slice, frame_hits, occurrences, source_conditioned,
)

TECHNICAL_WORK = (
    Frame(reference_id="technical-development", actions=["开发", "编写", "实现", "构建", "封装", "调试", "部署", "维护"],
          objects=["代码", "程序", "脚本", "软件", "服务", "接口", "系统", "模块", "工具", "Skills", "Registry"]),
    Frame(reference_id="technical-data", actions=["清洗", "处理", "分析", "标注", "采集", "抽取", "建模"],
          objects=["数据", "文本", "图像", "样本"]),
    Frame(reference_id="technical-model", actions=["训练", "评测", "评估", "验证", "优化"],
          objects=["模型", "算法", "检索"]),
)


def _use_in_work(unit, term, action):
    if UNSAFE.search(unit):
        return False
    for name in occurrences(unit, term):
        for means in re.finditer(MEANS, unit):
            # A literal technology must be the local means, not another task's
            # unrelated mention after the work predicate.
            if 0 <= name.start() - means.end() <= 48:
                middle = unit[means.end():name.start()]
                if re.search(MEANS + "|" + PREDICATES, middle):
                    continue
                for predicate in occurrences(unit, action):
                    if name.end() <= predicate.start():
                        bridge = unit[name.end():predicate.start()]
                    elif predicate.end() <= means.start():
                        bridge = unit[predicate.end():means.start()]
                    else:
                        continue
                    if (not re.search(MEANS + "|" + PREDICATES, bridge)
                            and not re.search(r"后|然后|再|另外|此外|而|(?:和|与|及|并)\s*$", bridge)):
                        return True
    return False


def technology_candidates(analysis, configured_terms):
    row = InputRecord.from_row(analysis.namespace, analysis.input_row)
    # Source surfaces may form unreviewed hypotheses without publishing a new
    # canonical technology or rewriting the requirement that supplied its name.
    terms = set(configured_terms)
    for claim in analysis.claims:
        req = claim.requirement
        if req and req.target == "capability" and req.category == "technical_skill":
            terms.update(req.members)
    work = [c for c in analysis.claims if c.kind in {"duty", "goal"}]
    for claim in work:
        for ev in claim.evidence:
            for frame in TECHNICAL_WORK:
                for start, end, action, _, _ in frame_hits(ev.quote, frame):
                    unit = ev.quote[start:end]
                    for means in re.finditer(MEANS, unit):
                        actions = [m.start() for f in TECHNICAL_WORK for a in f.actions
                                   for m in occurrences(unit, a) if m.start() >= means.end()]
                        if not actions:
                            continue
                        phrase = unit[means.end():min(actions)]
                        terms.update(m.group().strip() for m in re.finditer(
                            r"[A-Za-z][A-Za-z0-9+#._-]*(?:[ ]+[A-Za-z][A-Za-z0-9+#._-]*){0,2}", phrase))
    candidates = []
    for term in sorted(terms):
        evidence, ids, seen = [], [], set()
        for claim in work:
            for frame in TECHNICAL_WORK:
                claim_pairs = {(a, obj) for _, _, a, obj, _ in frame_hits(claim.text, frame)}
                if not claim_pairs:
                    continue
                for ev in claim.evidence:
                    for start, end, action, obj, _ in frame_hits(ev.quote, frame):
                        part = evidence_slice(ev, start, end)
                        if ((action, obj) not in claim_pairs or source_conditioned(part, row)
                                or not _use_in_work(part.quote, term, action)
                                or (part.field, part.start, part.end) in seen):
                            continue
                        seen.add((part.field, part.start, part.end))
                        evidence.append(part)
                        ids.append(claim.id)
        if evidence:
            candidates.append(AxisCandidate(
                value=term, strength="local_hypothesis", role_ids=[], claim_ids=sorted(set(ids)), evidence=evidence,
                reason="P1实际技术工作片段明示以该技术完成工作；不依赖职业参照，不断言必备、熟练度或正式方向准入。",
            ))
    return candidates
