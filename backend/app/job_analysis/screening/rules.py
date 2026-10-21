"""Conservative activity evidence for an explicitly configured offline scope."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...collect.cleaner import is_valid_jd
from ..foundation.inputs import canonical, parse_json
from ..foundation.models import VersionName

RULESET = "conservative-activity-v4"


class ScopeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scope_id: VersionName
    version: VersionName
    mode: Literal["offline_experiment"]
    description: str = Field(min_length=1)
    activities: list[Literal["software_development", "software_testing", "data", "it_operations"]] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_activities(self):
        if len(set(self.activities)) != len(self.activities):
            raise ValueError("duplicate scope activities")
        return self


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    field: Literal["job_title", "raw_text", "duties", "requirements"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)
    signal: str


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    validity: Literal["valid", "invalid", "undetermined"]
    scope_status: Literal["in_scope", "out_of_scope", "needs_review"] | None
    reason_codes: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    review_reasons: list[str]

    @model_validator(mode="after")
    def layers(self):
        if self.validity == "invalid" and self.scope_status is not None:
            raise ValueError("invalid JD has no scope decision")
        if self.validity == "undetermined" and self.scope_status != "needs_review":
            raise ValueError("undetermined validity requires review")
        if self.validity == "valid" and self.scope_status is None:
            raise ValueError("valid JD requires scope decision")
        if self.scope_status == "needs_review" and not self.review_reasons:
            raise ValueError("review reason required")
        return self


# Activity relations, rather than tool names or a job-title allowlist.
ACTIVITIES = {
    "software_development": r"(?:开发|设计|编写|实现|维护|优化|构建)(?!经验|流程|框架|效率|进度|工程师|工具|任务)[^，,、。；;!?！？\n]{0,24}(?:软件|程序|代码|接口|后端|前端|应用|微服务)|\b(?:build|develop|implement|maintain|write)\w*\s+(?:(?:software|backend|frontend|web)\s+)?(?:software|applications?|services?|apis?|code)\b",
    "software_testing": r"(?:执行|编写|设计|开展|负责|实施)[^。；;!?！？\n]{0,20}(?:软件测试|接口测试|自动化测试|测试用例)|\b(?:test(?:ing)?\s+software|(?:design|write|execute)\w*\s+(?:automated\s+)?tests?)\b",
    "data": r"(?:构建|开发|设计|分析|训练|维护)[^。；;!?！？\n]{0,20}(?:数据管道|数据模型|数据仓库|业务数据|机器学习模型|算法模型)|\b(?:build|develop|analyze|train)\w*\s+(?:data\s+(?:pipelines?|models?|warehouses?)|datasets?|machine\s+learning\s+models?)\b",
    "it_operations": r"(?:部署|维护|运维|管理|监控|保障)[^。；;!?！？\n]{0,20}(?:服务器|云平台|集群|网络系统|数据库|应用)|\b(?:deploy|maintain|monitor|administer)\w*\s+(?:servers?|infrastructure|databases?|applications?|clusters?)\b",
}
NONTECH = r"(?:负责|开展|处理|整理|承担|协助|维护)[^。；;!?！？\n]{0,16}(?:客户销售|客户签约|门店销售|行政报表|行政事务|前台接待|招聘面试|餐饮服务|仓库搬运)|\b(?:sell\s+products|handle\s+customer\s+sales|prepare\s+administrative\s+reports)\b"
TECH_TITLE = r"软件|开发|研发|程序员|测试|数据(?:工程|分析|科学)|运维|算法|后端|前端|\b(?:software|developer|programmer|devops|sre|data\s+(?:engineer|analyst|scientist)|qa|test\s+engineer)\b"
NONTECH_TITLE = r"销售|行政|前台|厨师|服务员|搬运|人事|\b(?:sales|receptionist|chef|waiter|administrative|recruiter)\b"
QUALIFICATION = r"(?:熟悉|熟练|掌握|具备)[^。；;!?！？\n]*[\w\u4e00-\u9fff]|\b(?:proficient|experience\s+with|required\s+skills)\b"
NON_RECRUITMENT = r"非招聘信息|无招聘意图|暂无招聘计划|仅供产品宣传|欢迎购买|培训招生|\b(?:not\s+(?:a\s+)?job\s+(?:posting|advertisement)|product\s+promotion)\b"
AMBIGUOUS = r"不(?:负责|参与|开发|编写|设计|实现|维护|优化|构建|执行|分析|训练|部署|管理|监控)|无需|不需要|不涉及|并非|不是|不会|不要|不用|未参与|不承担|不要求|例如|举例|曾经|过去|\b(?:not|never|no|without|previously|example)\b"
NON_JOB_CONTEXT = r"公司简介|公司介绍|关于我们|教程|本文介绍|(?:公司|我们|本公司|我司|本团队)[^。；;!?！？\n]{0,16}(?:开发|设计|构建)的|(?:向|给|为)客户(?:演示|介绍|展示)[^。；;!?！？\n]{0,24}(?:产品|软件|平台)|\b(?:about\s+us|our\s+company|tutorial)\b"


ACTIVITIES['software_development'] += (
    r'|(?:负责|参与|协助)[^，,、。；;!?！？\n]{0,12}'
    r'(?:应用程序|软件模块|后端业务系统|后端服务|前端应用)的'
    r'(?:设计|开发|维护|优化)(?:(?:与|和|及)(?:设计|开发|维护|优化))*(?=\s*(?:[，,、。；;!?！？\n]|$))'
)
ACTIVITIES['software_development'] += (
    r'|(?:系统|平台|模块|软件|程序|代码|接口|后端|前端|应用|服务|中间件)'
    r'(?:架构|业务|通信框架)?(?:的)?(?:设计|开发|研发|实现|编码|调试|重构|优化|维护|迭代)'
)
ACTIVITIES['software_testing'] += (
    r'|(?:测试用例|自动化测试|接口测试|集成测试|回归测试|性能测试)'
    r'(?:的)?(?:设计|编写|执行|维护|跟踪)'
)
ACTIVITIES['data'] += (
    r'|(?:数据仓库|数据管道|数据模型|业务数据|数据集|数据质量|ETL)'
    r'(?:流程)?(?:的)?(?:建模|设计|开发|建设|分析|清洗|校验|治理|维护)'
)
ACTIVITIES['it_operations'] += (
    r'|(?:服务器|云平台|集群|网络系统|数据库|应用|容器|系统)'
    r'(?:的)?(?:部署|维护|运维|监控|管理|保障)'
)


def _matches(field, text, pattern, signal):
    return [dict(field=field, start=m.start(), end=m.end(), quote=m.group(), signal=signal)
            for m in re.finditer(pattern, text, re.IGNORECASE)]


def _unique_evidence(items):
    unique = {}
    for item in items:
        unique[(item["field"], item["start"], item["end"], item["quote"], item["signal"])] = item
    return sorted(unique.values(), key=lambda item: (item["field"], item["start"], item["end"], item["signal"]))


def screen(record, scope):
    payload = record.payload
    titles = _matches("job_title", payload["job_title"], TECH_TITLE, "technical_title")
    other_titles = _matches("job_title", payload["job_title"], NONTECH_TITLE, "nontechnical_title")
    technical, other, qualification, ambiguous, non_job, context = [], [], [], [], [], []
    # Sentence-local checks keep explicit negation/examples from becoming positive evidence.
    for field in ("duties", "raw_text", "requirements"):
        text = payload.get(field, "")
        metadata = list(re.finditer(
            r"(?m)^[ \t]*(?:技能标签|公司|薪资|地点|学历|经验)[:：][^\n]*?"
            r"(?=(?:岗位职责|工作职责|工作内容|任职要求|岗位要求|职位要求|职位描述)[:：]|\n|$)", text))
        for clause in re.finditer(r"[^。；;!?！？\n]+", text):
            part = clause.group()
            found = []
            for activity in scope["activities"]:
                found += _matches(field, part, ACTIVITIES[activity], "technical_activity")
            found = [e for e in found if not any(m.start() <= clause.start() + e['start'] < m.end() for m in metadata)]
            negatives = _matches(field, part, NONTECH, "nontechnical_activity")
            qualifiers = _matches(field, part, QUALIFICATION, "qualification")
            adverts = _matches(field, part, NON_RECRUITMENT, "non_recruitment")
            uncertain = _matches(field, part, AMBIGUOUS, "ambiguous_context")
            background = _matches(field, part, NON_JOB_CONTEXT, "non_job_context")
            for evidence in found + negatives + qualifiers + adverts + uncertain + background:
                evidence["start"] += clause.start()
                evidence["end"] += clause.start()
            if (uncertain or background) and (found or negatives):
                ambiguous += found + negatives + uncertain
            else:
                technical += found
                other += negatives
            qualification += qualifiers
            non_job += adverts
            context += background
    evidence = _unique_evidence(
        titles + other_titles + technical + other + qualification + ambiguous + non_job + context
    )
    substantive = technical or other or qualification or ambiguous
    text = "\n".join(payload.get(f, "") for f in ("raw_text", "duties", "requirements"))
    validity = "valid" if substantive else "undetermined"
    if non_job and not substantive:
        validity, status, reason, explanation = "invalid", None, "non_recruitment", "明确非招聘内容，未发现岗位内容。"
    elif not substantive and not is_valid_jd({"job_title": payload["job_title"], "raw_text": text}):
        validity, status, reason, explanation = "invalid", None, "no_job_content", "仅有可识别占位或元信息，无实质岗位内容。"
    elif non_job or ambiguous or context:
        status, reason, explanation = "needs_review", "ambiguous_activity", "存在非招聘声明、否定、示例、历史或产品归属/演示语境，规则无法可靠裁决。"
        if non_job or context:
            validity = "undetermined"
    elif (technical and other_titles) or (other and titles) or (technical and other):
        status, reason, explanation = "needs_review", "title_activity_conflict", "标题与工作活动或多段职责证据冲突，保留复核。"
    elif technical:
        status, reason, explanation = "in_scope", "technical_activity", "存在目标范围内明确的技术工作活动。"
    elif other:
        status, reason, explanation = "out_of_scope", "nontechnical_activity", "存在明确非目标工作活动，未发现相反技术工作证据。"
    else:
        status, reason, explanation = "needs_review", "insufficient_evidence", "缺少可靠工作活动证据，标题或工具名称不足以确定范围。"
    if not evidence:
        evidence = [dict(field="raw_text", start=0, end=len(payload["raw_text"]),
                         quote=payload["raw_text"], signal="reviewed_content")]
    return Decision(validity=validity, scope_status=status, reason_codes=[reason], explanation=explanation,
                    evidence=evidence, review_reasons=[reason] if status == "needs_review" else []).model_dump()


def manifest(scope, rules_revision):
    scope = ScopeDefinition.model_validate(scope).model_dump()
    # Same syntax as A revision dependencies; reject arbitrary unbounded labels.
    from pydantic import TypeAdapter
    rules_revision = TypeAdapter(VersionName).validate_python(rules_revision, strict=True)
    return parse_json(canonical({"scope": scope, "rules": {"revision": rules_revision, "implementation": RULESET,
        "input_parser": "b1-json-v1", "fingerprint": "foundation-full-input-v1",
        "validity": "m1-valid-jd-v2-as-signal", "evidence": "original-field-offset-v1"}}))
