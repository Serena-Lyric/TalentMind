"""Versioned, bounded task aspects shared by role checks and candidate research.

These are Agent-authored linguistic adaptations, not an occupational catalogue or
human labels. Unknown clauses remain visible. Technology names never establish a
task. Frames are built before seeing any target, preventing target-to-source fill.
"""
import re
import unicodedata

from .work_context import NEGATED, HISTORY, INSTRUCTION, _other_actor
from .work_evidence import CONDITION, AUXILIARY, work_groups

VERSION = "bounded-work-semantics-1"
ACTIONS = {
    "build": r"开发|研发|编写|实现|构建|创建|编码|封装|抽象为|develop|implement|build|create|program",
    "design": r"设计|规划|design",
    "maintain": r"维护|更新|管理|maintain|administer",
    "improve": r"优化|调优|修复|修改|修正|improve|optimi[sz]e|correct",
    "diagnose": r"排查|定位|排除|diagnos|troubleshoot",
    "analyze": r"分析|理解|梳理|analy[sz]e|understand",
    "document": r"撰写|编制|形成|输出|沉淀|document",
    "produce": r"制作|生成|produce|generate",
    "test": r"测试|评测|评估|验证|核验|检查|test|evaluat|verif",
    "clean": r"清洗|切分|标注|治理|clean|annotat",
    "review": r"评审|审阅|review",
    "teach": r"讲授|讲解|教学|授课|培训|teach|instruct",
}
# Longest matching noun phrases win over nested nouns (design document != code).
OBJECTS = {
    "specification": r"需求规格说明书|技术规范|开发规范|接口规范|评审标准|接口规格|设计文档|设计说明|设计方案|规格说明|评分口径|验收标准|specification|design document",
    "evaluation_material": r"标注测试集|评测集|测试集|测试用例|测试数据|evaluation dataset|test cases?",
    "knowledge_content": r"知识库|知识文档|文档清洗|知识内容|检索效果|knowledge base",
    "business_report": r"经营指标报告|业务数据报表|业务分析报告|商业智能报告|销售报告|业务报表|指标报表|仪表盘|报表|dashboard|business report",
    "business_intelligence": r"商业智能(?:平台|系统|工具|服务)?|(?<![a-z])(?:finebi|bi)(?![a-z])(?:\s*(?:平台|系统|工具|服务))?|business intelligence",
    "warehouse": r"数据仓库|数仓|etl(?:数据)?(?:管道|流程)?|data warehouse",
    "network": r"网络(?:运行|性能|配置|故障)?|路由器|交换机|network|router",
    "software": r"软件(?:模块|系统|服务|性能|错误)?|应用程序|程序(?:错误)?|代码|编码(?!规范|课程|教材)|爬虫系统|(?:订单|业务|算法|后端)服务(?:接口)?|后端接口|api(?:接口)?|接口|中间件|算法(?:实现)?|用户界面|测试框架|agent\s*化|skills?|software|application|source code",
    "requirements": r"用户需求|业务需求|软件需求|开发需求|需求分析|user requirements?",
    "data": r"数据清洗|数据抽取|数据管道|数据质量|业务数据|财务数据|data pipeline|data quality",
    "general_system": r"系统|平台|资源调度|服务|system|platform",
}
PATTERNS = {name: re.compile(pattern, re.I) for name, pattern in OBJECTS.items()}
ACTION_PATTERN = re.compile("|".join(f"(?P<{key}>{value})" for key, value in ACTIONS.items()), re.I)
PURPOSE = re.compile(r"以便|从而|旨在|让|使得|供(?!(?:应链|应商|需|给))|为.{0,16}(?:提供|准备)")


def _scope(text, explicit):
    if explicit and explicit != "affirmed":
        return explicit
    if CONDITION.search(text) or re.search(r"如有需要|按需|待.{0,12}(?:后|时)", text):
        return "conditional"
    if NEGATED.search(text):
        return "negated"
    if HISTORY.search(text):
        return "historical"
    if _other_actor(text) or re.search(r"为.{0,12}(?:人员|团队|同事|客户).{0,6}(?:整理|准备|提供)", text):
        return "other_actor"
    if INSTRUCTION.search(text):
        return "instructional"
    return "affirmed"


def explain_work(value):
    """Return source-only frames with exact clause spans; never infer an output."""
    value = {"text": value} if isinstance(value, str) else value
    text = str(value.get("text", ""))
    scope = _scope(text, value.get("scope"))
    importance = "auxiliary" if value.get("core") is False or AUXILIARY.search(text) else "core" if value.get("core") is True else "unknown"
    frames, gaps = [], []
    # Explicit new responsibility after a comma can reset local negation.
    parts = []
    groups, pending = [], None
    for begin, finish, group in work_groups(text):
        if pending is not None:
            begin, group = pending, text[pending:finish]
            pending = None
        if re.fullmatch(r"(?:\s|负责|承担|和|与|并|及|、|" + "|".join(ACTIONS.values()) + r")+", group):
            pending = begin
            continue
        groups.append((begin, finish, group))
    if pending is not None:
        groups.append((pending, len(text), text[pending:]))
    expanded = []
    for begin, finish, group in groups:
        offset = 0
        for split in re.finditer(r"并且|并(?!发|行|联|集|购|列)|以及|同时|另外|此外|和|与|[，,]", group):
            left = unicodedata.normalize("NFKC", group[offset:split.start()])
            if ACTION_PATTERN.search(left) and any(pattern.search(left) for pattern in PATTERNS.values()):
                expanded.append((begin+offset, begin+split.start(), group[offset:split.start()]))
                offset = split.end()
        expanded.append((begin+offset, finish, group[offset:]))
    for begin, finish, group in expanded:
        offset = 0
        for split in re.finditer(r"[，,](?=\s*(?:仅|只|本人|本岗位))", group):
            parts.append((begin+offset, begin+split.start(), group[offset:split.start()]))
            offset = split.end()
        parts.append((begin+offset, finish, group[offset:]))
    inherited = None
    for start, end, quote in parts:
        local_scope = _scope(quote, value.get("scope"))
        explicit_self = re.match(r"\s*(?:仅|只|本人|本岗位)", quote)
        if local_scope != "affirmed":
            inherited = local_scope
        elif inherited and not explicit_self:
            local_scope = inherited
        elif explicit_self and inherited not in {"conditional", "historical"}:
            inherited = None
        elif inherited:
            local_scope = inherited
        normalized = unicodedata.normalize("NFKC", quote).casefold()
        purpose = PURPOSE.search(normalized)
        work = normalized[:purpose.start()] if purpose else normalized
        # NFKC is only used for matching; saved evidence is the unchanged clause.
        objects = [(m.start(), m.end(), name) for name, pattern in PATTERNS.items() for m in pattern.finditer(work)]
        objects = [o for o in objects if not any(other[0] <= o[0] and o[1] <= other[1]
                   and other[1]-other[0] > o[1]-o[0] for other in objects)]
        actions = list(ACTION_PATTERN.finditer(work))
        objects = [o for o in objects if not (o[2] in {"software", "general_system"} and any(
            other[2] in {"specification", "evaluation_material", "knowledge_content"}
            and o[1] <= other[0] and not any(o[1] <= a.start() < other[0] for a in actions)
            for other in objects))]
        local = []
        for begin, finish, obj in objects:
            # A noun's nearest predicate supplies its action. No cross-clause pairing.
            before = [a for a in actions if a.end() <= begin]
            after = [a for a in actions if a.start() >= finish]
            intrinsic = next((a for a in actions if obj == "software" and work[begin:finish] == "编码"
                              and a.start() == begin), None)
            action = intrinsic or (before[-1] if before else after[0] if after else None)
            if action is None or min(abs(begin-action.end()), abs(action.start()-finish)) > 24:
                continue
            related_actions = [action]
            if before and intrinsic is None:
                for earlier in reversed(before[:-1]):
                    if re.fullmatch(r"(?:\s|和|与|并|及|、|以及|并且)+", work[earlier.end():related_actions[-1].start()]):
                        related_actions.append(earlier)
                    else:
                        break
            detail = obj
            if obj == "software":
                noun = work[begin:finish]
                detail = next((kind for kind, pattern in [
                    ("skill_capability", r"skill|agent.*化"),
                    ("interface_service", r"api|接口|服务"), ("algorithm", r"算法"),
                    ("user_interface", r"界面"), ("test_framework", r"测试框架"),
                    ("crawler", r"爬虫"), ("middleware", r"中间件")]
                    if re.search(pattern, noun)), "software")
            for related in related_actions:
                name = related.lastgroup
                if obj in {"specification", "evaluation_material", "knowledge_content", "business_report"} and name in {"build", "produce", "document"}:
                    name = "produce"
                frame = dict(action=name, object=obj, object_detail=detail, scope=local_scope,
                             start=start, end=end, quote=quote)
                if frame not in local:
                    local.append(frame)
        frames.extend(local)
        if not local and local_scope == "affirmed" and re.search(r"[\u4e00-\u9fffA-Za-z]", quote):
            gaps.append(dict(start=start, end=end, quote=quote, reason="unrecognized_work_aspect"))
    if any(f["scope"] == "affirmed" for f in frames):
        scope = "affirmed"
    return dict(version=VERSION, semantic_review="machine_unreviewed", scope=scope,
                importance=importance, frames=frames, gaps=gaps,
                limitation="有界中文/英文工作方面适配；未识别表述保留缺口，不证明整岗或正式职业等价。")


def compare_work(left, right):
    """Compare explicit task aspects; unknown clauses prevent a whole-claim match."""
    left, right = explain_work(left), explain_work(right)
    left_keys = {(f["action"], f["object_detail"]) for f in left["frames"] if f["scope"] == "affirmed"}
    right_keys = {(f["action"], f["object_detail"]) for f in right["frames"] if f["scope"] == "affirmed"}
    shared = left_keys & right_keys
    state, reason = "unresolved", "work_aspect_not_established"
    if left["scope"] != "affirmed" or right["scope"] != "affirmed":
        reason = "non_asserted_or_instructional_work"
    elif (left["importance"] == "auxiliary") != (right["importance"] == "auxiliary"):
        reason = "responsibility_importance_differs"
    elif not left["frames"] or not right["frames"] or left["gaps"] or right["gaps"] or any(
            f["object"] == "general_system" for side in (left, right) for f in side["frames"]):
        reason = "unrecognized_work_remains"
    elif left_keys == right_keys:
        state, reason = "supported", "bounded_same_task_aspects"
    elif not shared:
        reason = "different_aspects_not_counterevidence"
    else:
        reason = "only_partial_task_overlap"
    return dict(version=VERSION, state=state, reason_codes=[reason], left=left, right=right,
                matched_aspects=[dict(action=a, object=o) for a, o in sorted(shared)],
                semantic_review="machine_unreviewed", whole_job_equivalence=False)
