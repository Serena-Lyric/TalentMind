"""Local action/object evidence, with conservative scope and exact source offsets.

These bounded rules are not a general Chinese entailment model. Unsupported
paraphrases remain gaps; matching a rule never makes a machine claim reviewed.
"""
import re

from .role_policy import Frame

CLAUSES = re.compile(r"[^，,；;。.!！?？\n]+")
STATEMENTS = re.compile(r"[^；;。.!！?？\n]+")
CONDITION = re.compile(r"如果|若|除非|仅当|可能|视情况|必要时|能力允许|条件允许|在.{0,12}情况下")
UNSAFE = re.compile(
    r"不(?!同|断|少|仅|变|可或缺)|未(?!来)|无需|无须|禁止|避免|如果|若|除非|仅当|可能|视情况|必要时|能力允许|条件允许|情况下|"
    r"曾经|过去|经验|经历|熟悉|掌握|精通|了解|示例|例如|"
    r"客户负责|客户承担|他人负责|团队负责|其他.{0,6}负责|供应商负责|公司负责"
)
AUXILIARY = re.compile(r"协助|辅助|偶尔|配合|支持其他")
DELIVERY = re.compile(r"(?:交付|产出|输出|上线|完成验收|保障)[^，,；;。\n]{0,24}")
# A new predicate starts a separate local work unit; terms may not pair across it.
PREDICATES = r"开发|编写|修改|实现|设计|构建|建设|搭建|分析|整理|监测|监控|管理|维护|配置|排查|优化|讲解|教学|授课|验证|核验|清洗|处理|标注|采集|抽取|建模|训练|评测|评估|封装|生成|交付|产出|输出|保障"
WORK_PREFIX = r"(?:负责|承担|协助|辅助)?"
MEANS = r"使用|利用|基于|采用|借助|通过"
COORDINATE = re.compile(r"(?:并且|并|以及|同时|及)(?=" + WORK_PREFIX + r"(?:" + PREDICATES + r")|(?:" + MEANS + r"))")


def units(text):
    for clause in CLAUSES.finditer(text):
        parent = next(s for s in STATEMENTS.finditer(text) if s.start() <= clause.start() < s.end())
        # Modality/experience scopes over coordinated work in the same clause.
        if CONDITION.search(parent.group()):
            continue
        if UNSAFE.search(clause.group()):
            yield clause.start(), clause.end(), clause.group()
            continue
        start = clause.start()
        for split in COORDINATE.finditer(clause.group()):
            end = clause.start() + split.start()
            yield start, end, text[start:end]
            start = clause.start() + split.end()
        yield start, clause.end(), text[start:clause.end()]


GROUP_SPLIT = re.compile(
    r"[；;。.!！?？\n]+|(?:同时|另外|此外)|"
    r"(?:[，,]|并且|并|以及|及)(?=\s*" + WORK_PREFIX + r"(?:"
    + PREDICATES.replace("|交付|产出|输出|保障", "") + r")|(?:" + MEANS + r"))"
)


def work_groups(text):
    start = 0
    for split in GROUP_SPLIT.finditer(text):
        if start < split.start():
            yield start, split.start(), text[start:split.start()]
        start = split.end()
    if start < len(text):
        yield start, len(text), text[start:]


def same_work_group(first, second, row):
    if first.field != second.field:
        return False
    return any(start <= min(first.start, second.start) and max(first.end, second.end) <= end
               for start, end, _ in work_groups(row.payload.get(first.field, "")))


def source_conditioned(evidence, row):
    return any(s.start() <= evidence.start < s.end() and CONDITION.search(s.group())
               for s in STATEMENTS.finditer(row.payload.get(evidence.field, "")))


def occurrences(text, term):
    pattern = re.escape(term)
    if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9+#. -]*", term):
        pattern = r"(?<![a-zA-Z0-9_])" + pattern + r"(?![a-zA-Z0-9_])"
    return list(re.finditer(pattern, text, re.I))


def _shared_predicate_gap(unit, action_span, object_span, gap):
    if object_span.end() <= action_span.start() and re.search(PREDICATES, unit[:object_span.start()]):
        return False
    # Only grammatical particles and known coordinated predicates may intervene.
    # Any second noun/object blocks inheritance (e.g. service review + pipeline development).
    return (bool(re.search(PREDICATES, gap)) and bool(re.search(r"与|和|、|并|及", gap))
            and re.fullmatch(r"(?:\s|的|和|与|以及|及|并且|并|、|整体|日常|方案|" + PREDICATES + r")*", gap) is not None)


def frame_hits(text: str, frame: Frame):
    candidates = [(s, e, value, False) for s, e, value in units(text)]
    for clause in CLAUSES.finditer(text):
        parent = next(s for s in STATEMENTS.finditer(text) if s.start() <= clause.start() < s.end())
        if not CONDITION.search(parent.group()):
            candidates.append((clause.start(), clause.end(), clause.group(), True))
    for start, end, unit, shared in candidates:
        if UNSAFE.search(unit):
            continue
        for action in frame.actions:
            for action_span in occurrences(unit, action):
                for obj in frame.objects:
                    for object_span in occurrences(unit, obj):
                        if action_span.end() <= object_span.start():
                            gap = unit[action_span.end():object_span.start()]
                        elif object_span.end() <= action_span.start():
                            gap = unit[object_span.end():action_span.start()]
                        else:
                            continue
                        wrapper = re.search(r"介绍|讲解|讲授|培训|教学|授课|评审|演示|销售", unit[:min(action_span.start(), object_span.start())])
                        if wrapper and wrapper.group() not in frame.actions:
                            continue
                        if re.search(r"的(?:课程|教学|培训|介绍|讲解|演示)", unit):
                            continue
                        if re.match(r"(?:的)?(?:课程|教学|培训|介绍|讲解|演示)", unit[max(action_span.end(), object_span.end()):]):
                            continue
                        simple = not re.search(PREDICATES, gap) and not re.search(r"与|和|或|、|及|另", gap)
                        bound = (_shared_predicate_gap(unit, action_span, object_span, gap) if shared else simple)
                        if len(gap) <= 12 and bound:
                            local_end = max(action_span.end(), object_span.end()) if shared else len(unit)
                            yield start, start + local_end, action, obj, bool(AUXILIARY.search(unit[:local_end]))


def evidence_slice(evidence, start, end):
    return evidence.model_copy(update={
        "start": evidence.start + start,
        "end": evidence.start + end,
        "quote": evidence.quote[start:end],
    })


def claim_matches(claim, frame, row):
    # Both the P1 paraphrase and its actual cited source must support the frame.
    if not list(frame_hits(claim.text, frame)):
        return []
    matches = []
    seen = set()
    for evidence in claim.evidence:
        for start, end, action, obj, auxiliary in frame_hits(evidence.quote, frame):
            ev = evidence_slice(evidence, start, end)
            if source_conditioned(ev, row):
                continue
            key = (ev.field, ev.start, ev.end, action, obj)
            if key not in seen:
                matches.append((action, obj, auxiliary, ev))
                seen.add(key)
    return matches


def delivery_matches(claim, terms, row):
    result = []
    for evidence in claim.evidence:
        for start, end, unit in units(evidence.quote):
            if UNSAFE.search(unit) or AUXILIARY.search(unit):
                continue
            if any(any(occurrences(m.group(), term) for term in terms) for m in DELIVERY.finditer(unit)):
                ev = evidence_slice(evidence, start, end)
                if not source_conditioned(ev, row):
                    result.append(ev)
    return result
