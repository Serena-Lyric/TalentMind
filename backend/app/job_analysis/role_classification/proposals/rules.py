"""Closed, tested Chinese action/object/deliverable clauses. No frequency scoring."""
import re

from .models import FamilyTaxonomy, validate_proposal

# These are experimental grammar productions, not canonical jobs or general semantic rules.
DELIVERIES = {
    "software_engineering": (
        "开发后端接口并交付服务", "开发软件服务并交付应用", "开发前端页面并交付应用"),
    "test_quality_engineering": ("设计测试用例并交付测试报告",),
    "data_ai": ("训练机器学习模型并交付预测模型", "建设数据管道并交付数据集"),
    "infrastructure_operations": ("维护云基础设施并保障系统可用性",),
    "network_information_security": ("排查网络安全漏洞并交付修复方案",),
    "embedded_system_software": ("开发嵌入式驱动并交付固件",),
    "technical_services_delivery": (
        "实施客户系统并交付集成方案", "诊断客户系统复杂故障并交付修复方案",
        "设计客户系统技术架构并交付技术方案", "部署客户生产系统并完成系统验收"),
}
TITLES = {
    "software_engineering": ("软件工程师", "前端工程师", "后端工程师"),
    "test_quality_engineering": ("测试工程师",),
    "data_ai": ("数据工程师", "算法工程师"),
    "infrastructure_operations": ("运维工程师", "云平台工程师"),
    "network_information_security": ("安全工程师",),
    "embedded_system_software": ("嵌入式工程师",),
    "technical_services_delivery": ("技术支持", "解决方案工程师", "实施工程师"),
}
HEADINGS = re.compile(r"^(岗位职责|工作职责|职责|公司介绍|企业介绍|历史项目|培训内容|示例|任职要求|技能要求|福利待遇)(?:[：:]|$)")
PREFIX = re.compile(r"^(核心职责[：:]|主要职责[：:]|主要负责|负责|协助|辅助|配合)")
MULTIPLE = re.compile(r"招聘(?:两|多|[2-9])个(?:岗位|职位)|岗位[一二三1-9][：:]|职位[一二三1-9][：:]")
COMPOUND = re.compile(r"全栈|复合岗位|混合岗位")
RULESET = "closed-delivery-clauses-v1"


def _evidence(record, field, start, end):
    return dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
        field=field, start=start, end=end, quote=record.payload[field][start:end])


def suggest(record, taxonomy):
    FamilyTaxonomy.model_validate(taxonomy)
    candidates, title_clues, context, reasons = {}, [], [], []

    def flag(reason):
        if reason not in reasons:
            reasons.append(reason)

    title = record.payload["job_title"]
    for family, titles in TITLES.items():
        for term in titles:
            start = title.find(term)
            if start >= 0:
                title_clues.append(dict(family_id=family, evidence=_evidence(record, "job_title", start, start + len(term))))
    for field in ("job_title", "duties", "raw_text"):
        text = record.payload.get(field, "")
        for pattern, reason in ((MULTIPLE, "possible_multiple_positions"), (COMPOUND, "compound_role_unresolved")):
            for match in pattern.finditer(text):
                flag(reason)
                context.append(dict(reason=reason, evidence=_evidence(record, field, match.start(), match.end())))

    for field in ("duties", "raw_text"):
        text = record.payload.get(field, "")
        if field == "raw_text" and text == record.payload.get("duties"):
            continue
        active = True  # Without headings only a whole supported clause can match.
        for match in re.finditer(r"[^。；;\n\r]+", text):
            fragment = match.group()
            start = match.start() + len(fragment) - len(fragment.lstrip())
            end = match.end() - (len(fragment) - len(fragment.rstrip()))
            clause = text[start:end]
            heading = HEADINGS.match(clause)
            if heading:
                active = heading[1] in ("岗位职责", "工作职责", "职责")
                start += heading.end()
                # Strip only heading whitespace, retaining offsets in the original field.
                while start < end and text[start].isspace():
                    start += 1
                clause = text[start:end]
                if not clause:
                    continue
            if not active:
                context.append(dict(reason="non_duty_section", evidence=_evidence(record, field, match.start(), match.end())))
                continue
            prefix = PREFIX.match(clause)
            matched = False
            if prefix:
                work = clause[prefix.end():].strip()
                for family, productions in DELIVERIES.items():
                    if work not in productions:
                        continue
                    kind = ("core" if prefix[1] in ("核心职责：", "核心职责:", "主要职责：", "主要职责:", "主要负责")
                            else "auxiliary" if prefix[1] in ("协助", "辅助", "配合") else "unspecified")
                    clue = dict(kind=kind, rule=RULESET + ":" + family, evidence=_evidence(record, field, start, end))
                    candidates.setdefault(family, []).append(clue)
                    matched = True
            if not matched:
                flag("unsupported_duty_context")
                context.append(dict(reason="unsupported_duty_context", evidence=_evidence(record, field, match.start(), match.end())))

    core = {family for family, clues in candidates.items() if any(c["kind"] == "core" for c in clues)}
    titles = {c["family_id"] for c in title_clues}
    if candidates and titles and not titles <= set(candidates):
        flag("title_duties_conflict")
    if len(core) > 1:
        flag("competing_core_responsibilities")
    if candidates and (len(core) != 1 or any(c["kind"] == "unspecified" for clues in candidates.values() for c in clues)):
        flag("insufficient_primary_auxiliary_evidence")
    hint = next(iter(core)) if len(core) == 1 and not reasons else None
    body = dict(schema_version="b31-proposal-1", namespace=record.namespace, jd_id=record.jd_id,
        fingerprint=record.fingerprint, source_payload=record.payload,
        candidates=[dict(family_id=f, clues=c) for f, c in candidates.items()],
        title_clues=title_clues, context_clues=context, primary_family_hint=hint,
        resolution="proposed" if hint else "unresolved" if candidates or reasons else "unknown",
        reasons=reasons, canonical_job=dict(state="unknown", value=None), technology_tracks=[],
        seniority=dict(state="unknown", value=None), review_status="pending_review",
        classification_complete=False, formal_statistics_eligible=False,
        semantic_validation="finite_deterministic_suggestions_only")
    return validate_proposal(record, body, taxonomy)

