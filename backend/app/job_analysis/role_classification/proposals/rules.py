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
HEADINGS = re.compile(r"^(岗位职责|工作职责|职责|工作内容|岗位内容|主要工作内容|职责描述|公司介绍|企业介绍|历史项目|培训内容|示例|任职要求|技能要求|能力要求|核心能力要求|福利待遇)(?:[：:]|$)")
DUTY_HEADINGS = {"岗位职责", "工作职责", "职责", "工作内容", "岗位内容", "主要工作内容", "职责描述"}
PREFIX = re.compile(r"^(核心职责[：:]|主要职责[：:]|主要负责|负责|协助|辅助|配合)")
MULTIPLE = re.compile(r"招聘(?:两|多|[2-9])个(?:岗位|职位)|岗位[一二三1-9][：:]|职位[一二三1-9][：:]")
COMPOUND = re.compile(r"全栈|复合岗位|混合岗位")
RULESET = "closed-delivery-clauses-v2"
DUTY_RULESET = "closed-action-object-duties-v1"
UNSAFE_DUTY = re.compile(
    r"如果|若|仅当|除非|不负责|非本岗位|曾经|过去|公司介绍|企业介绍|历史项目|培训内容|示例|"
    r"如果需要|客户负责|客户销售|销售转化|销售软件|向客户演示|客户关系|"
    r"商务维护|普通客服"
)
DUTY_PATTERNS = {
    "software_engineering": (
        r"(?:设计|开发|研发|实现|编码|重构|维护|优化|迭代|调优)[^，,、。；;\n]{0,20}"
        r"(?:软件|系统|平台|模块|接口|应用|服务|后端|前端|中间件|代码)",
        r"(?:软件|系统|平台|模块|接口|应用|服务|后端|前端|中间件|代码)"
        r"[^，,、。；;\n]{0,20}(?:设计|开发|研发|实现|编码|重构|维护|优化|迭代|调优)",
    ),
    "test_quality_engineering": (
        r"(?:设计|编写|执行|维护|评审)[^，,、。；;\n]{0,16}"
        r"(?:测试用例|自动化测试|单元测试|接口测试|集成测试|回归测试|性能测试|测试报告)",
        r"(?:测试用例|自动化测试|单元测试|接口测试|集成测试|回归测试|性能测试)"
        r"[^，,、。；;\n]{0,16}(?:设计|编写|执行|维护|评审)",
    ),
    "data_ai": (
        r"(?:建设|搭建|开发|设计|维护|优化|实现|开展|参与)[^，,、。；;\n]{0,20}"
        r"(?:数据管道|数据仓库|ETL|数据清洗|数据标注|数据治理|数据处理|"
        r"数据分析模型|机器学习模型|算法模型)",
        r"(?:数据管道|数据仓库|ETL|数据清洗|数据标注|数据治理|数据处理|"
        r"数据分析模型|机器学习模型|算法模型)[^，,、。；;\n]{0,20}"
        r"(?:建设|搭建|开发|设计|维护|优化|实现|开展|参与)",
    ),
    "infrastructure_operations": (
        r"(?:部署|运维|维护|监控|保障|管理)[^，,、。；;\n]{0,20}"
        r"(?:服务器|云平台|集群|数据库|容器|生产系统|基础设施|应用)",
        r"(?:服务器|云平台|集群|数据库|容器|生产系统|基础设施|应用)"
        r"[^，,、。；;\n]{0,20}(?:部署|运维|维护|监控|保障|管理)",
    ),
    "network_information_security": (
        r"(?:排查|检测|修复|加固|评估|审计|防护|响应)[^，,、。；;\n]{0,20}"
        r"(?:安全漏洞|安全风险|网络攻击|安全事件|渗透测试|安全策略|安全体系)",
    ),
    "embedded_system_software": (
        r"(?:开发|设计|移植|调试|维护)[^，,、。；;\n]{0,20}"
        r"(?:嵌入式|固件|驱动|实时操作系统|RTOS|MCU|SoC)",
    ),
}
HARDWARE_DELIVERIES = {
    "hardware_integrated_circuits": (
        "设计硬件电路并交付电路原理图", "开发FPGA逻辑并交付验证结果", "设计数字IC并交付RTL"),
}
HARDWARE_TITLES = {"hardware_integrated_circuits": ("硬件工程师", "FPGA工程师", "数字IC工程师")}
ENGINEERING_DELIVERIES = {"hardware_integrated_circuits": (
    *HARDWARE_DELIVERIES["hardware_integrated_circuits"],
    "开发半导体工艺并交付验证报告", "优化封装工艺并交付工程方案", "改进制造良率并交付分析方案")}


def _evidence(record, field, start, end):
    return dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
        field=field, start=start, end=end, quote=record.payload[field][start:end])


def suggest(record, taxonomy):
    config = FamilyTaxonomy.model_validate(taxonomy)
    deliveries, title_terms = DELIVERIES, TITLES
    if config.revision == "families-v2":
        deliveries, title_terms = DELIVERIES | HARDWARE_DELIVERIES, TITLES | HARDWARE_TITLES
    elif config.revision == "families-v3":
        deliveries, title_terms = DELIVERIES | ENGINEERING_DELIVERIES, TITLES | HARDWARE_TITLES
    candidates, title_clues, context, reasons = {}, [], [], []

    def flag(reason):
        if reason not in reasons:
            reasons.append(reason)

    title = record.payload["job_title"]
    for family, titles in title_terms.items():
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
        active = True
        for match in re.finditer(r"[^。；;\n\r]+", text):
            fragment = match.group()
            start = match.start() + len(fragment) - len(fragment.lstrip())
            end = match.end() - (len(fragment) - len(fragment.rstrip()))
            clause = text[start:end]
            heading = HEADINGS.match(clause)
            duty_section = field == "duties" or heading is not None
            if heading:
                active = heading[1] in DUTY_HEADINGS
                duty_section = active
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
            matched_families = set()
            if prefix:
                work = clause[prefix.end():].strip()
                for family, productions in deliveries.items():
                    if work not in productions:
                        continue
                    kind = ("core" if prefix[1] in ("核心职责：", "核心职责:", "主要职责：", "主要职责:", "主要负责")
                            else "auxiliary" if prefix[1] in ("协助", "辅助", "配合") else "unspecified")
                    rule = ("closed-engineering-delivery-v1" if config.revision == "families-v3" else
                            "closed-hardware-delivery-v1") if family in HARDWARE_DELIVERIES else RULESET
                    clue = dict(kind=kind, rule=rule + ":" + family, evidence=_evidence(record, field, start, end))
                    candidates.setdefault(family, []).append(clue)
                    matched = True
                    matched_families.add(family)
            if active and duty_section and not matched_families and not UNSAFE_DUTY.search(clause):
                work = clause[prefix.end():].strip() if prefix else clause
                infrastructure_match = any(
                    re.search(pattern, work, re.IGNORECASE)
                    for pattern in DUTY_PATTERNS["infrastructure_operations"]
                )
                strong_software = bool(
                    re.search(r"设计|开发|研发|实现|编码|重构", work)
                )
                for family, patterns in DUTY_PATTERNS.items():
                    if family in matched_families:
                        continue
                    if family == "software_engineering" and infrastructure_match and not strong_software:
                        continue
                    if not any(re.search(pattern, work, re.IGNORECASE) for pattern in patterns):
                        continue
                    kind = ("core" if prefix and prefix[1] in ("核心职责：", "核心职责:", "主要职责：", "主要职责:", "主要负责")
                            else "auxiliary" if prefix and prefix[1] in ("协助", "辅助", "配合")
                            else "unspecified")
                    clue = dict(
                        kind=kind,
                        rule=DUTY_RULESET + ":" + family,
                        evidence=_evidence(record, field, start, end),
                    )
                    candidates.setdefault(family, []).append(clue)
                    matched = True
                    matched_families.add(family)
            if not matched:
                flag("unsupported_duty_context")
                context.append(dict(reason="unsupported_duty_context", evidence=_evidence(record, field, match.start(), match.end())))

    # An extracted duty cannot shed a conflicting section/context in another source field.
    for family, clues in list(candidates.items()):
        kept = []
        for clue in clues:
            ref = clue["evidence"]
            conflicts = [c for c in context if c["evidence"]["field"] != ref["field"]
                         and ref["quote"] in c["evidence"]["quote"]]
            if conflicts:
                flag("cross_field_context_conflict")
            else:
                kept.append(clue)
        if kept:
            candidates[family] = kept
        else:
            del candidates[family]
    core = {family for family, clues in candidates.items() if any(c["kind"] == "core" for c in clues)}
    titles = {c["family_id"] for c in title_clues}
    if candidates and titles and not titles <= (core if len(core) == 1 else set(candidates)):
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
