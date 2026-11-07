"""Versioned, bounded task aspects shared by role checks and candidate research.

These are Agent-authored linguistic adaptations, not an occupational catalogue or
human labels. Unknown clauses remain visible. Technology names never establish a
task. Frames are built before seeing any target, preventing target-to-source fill.
"""
import re
import unicodedata

from .work_context import NEGATED, HISTORY, INSTRUCTION, _other_actor
from .work_evidence import CONDITION, AUXILIARY, STATEMENTS, PREDICATES, work_groups
from ..foundation.inputs import InputRecord
from ..semantics.models import Evidence

VERSION = "bounded-work-semantics-3"
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
OBJECT_JOIN = re.compile(r"、|以及|及")


def _object_phrase(work, begin, finish, obj, action):
    """Accept a noun head only when its complete complement has a known reading.

    Unknown heads/tails cannot disappear behind an internal vocabulary hit.
    Network modifiers need an explicit communications reading: the bare head
    alone cannot interpret arbitrary compounds such as neural/social networks.
    """
    if action.end() <= begin:
        start, end = action.end(), len(work)
    elif action.start() >= finish:
        start, end = 0, action.start()
    else:  # Intrinsic 编码 is both action and software object.
        start, end = begin, finish
    group = work[start:end].strip()
    # A shared predicate may govern several noun phrases; each keeps its own head.
    for split in OBJECT_JOIN.finditer(work, start, end):
        if split.end() <= begin:
            start = split.end()
        elif split.start() >= finish:
            end = split.start()
            break
    prefix, suffix = work[start:begin].strip(), work[finish:end].strip()
    # These describe the same object, rather than introduce a different noun head.
    suffix = re.sub(r"\([a-z0-9_ +./-]+\)", "", suffix)
    components = r"(?:核心)?模块|接口|服务" if obj in {"software", "business_intelligence"} else r"(?!)"
    if not re.fullmatch(r"(?:的|整体|工作|相关工作|日常工作|并发性能|性能|能力|产品|" + components + r")*", suffix):
        return None
    if obj == "network" and not re.fullmatch(
            r"(?:负责|承担|对|将|的|高效|稳定|安全|通信|信息通信|计算机|企业|公司|园区|办公|局域|广域|无线|有线|核心|骨干|5g|4g|ip|\s)*", prefix):
        return None
    return work[start:end].strip(), group


def _normalized_clause(text):
    normalized, positions = [], []
    for index, char in enumerate(text):
        part = unicodedata.normalize('NFKC', char).casefold()
        normalized.append(part)
        positions.extend([(index, index + 1)] * len(part))
    return ''.join(normalized), positions


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
    importance = "auxiliary" if value.get("importance") == "auxiliary" or value.get("core") is False or AUXILIARY.search(text) else "core" if value.get("core") is True else "unknown"
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
    inherited, heading_auxiliary = None, False
    for start, end, quote in parts:
        if re.fullmatch(r"[^:：\n]*[:：]\s*", quote):
            heading_auxiliary = bool(AUXILIARY.search(quote))
        local_importance = ("auxiliary" if heading_auxiliary or value.get("importance") == "auxiliary"
                            or value.get("core") is False or AUXILIARY.search(quote)
                            else "core" if value.get("core") is True else "unknown")
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
        normalized, positions = _normalized_clause(quote)
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
        local, rejected_object, object_groups = [], False, {}
        for begin, finish, obj in objects:
            # A noun's nearest predicate supplies its action. No cross-clause pairing.
            before = [a for a in actions if a.end() <= begin]
            after = [a for a in actions if a.start() >= finish]
            intrinsic = next((a for a in actions if obj == "software" and work[begin:finish] == "编码"
                              and a.start() == begin), None)
            action = intrinsic or (before[-1] if before else after[0] if after else None)
            if action is None or min(abs(begin-action.end()), abs(action.start()-finish)) > 24:
                continue
            object_match = _object_phrase(work, begin, finish, obj, action)
            if object_match is None:
                rejected_object = True
                continue
            object_phrase, object_group = object_match
            object_groups.setdefault(object_group, set()).add(object_phrase)
            related_actions = [action]
            if before and intrinsic is None:
                for earlier in reversed(before[:-1]):
                    if re.fullmatch(r"(?:\s|和|与|并|及|、|以及|并且)+", work[earlier.end():related_actions[-1].start()]):
                        related_actions.append(earlier)
                    else:
                        break
            elif after and intrinsic is None:
                for later in after[1:]:
                    if re.fullmatch(r"(?:\s|和|与|并|及|、|以及|并且)+", work[related_actions[-1].end():later.start()]):
                        related_actions.append(later)
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
                frame = dict(action=name, object=obj, object_detail=detail, object_phrase=object_phrase, scope=local_scope,
                             object_start=start + positions[begin][0], object_end=start + positions[finish - 1][1],
                             object_quote=quote[positions[begin][0]:positions[finish - 1][1]],
                             importance=local_importance, start=start, end=end, quote=quote)
                if frame not in local:
                    local.append(frame)
        frames.extend(local)
        for group, recognized in object_groups.items():
            members = [p.strip() for p in OBJECT_JOIN.split(group) if p.strip()]
            unknown = [member for member in members if member not in recognized]
            if len(members) > 1 and unknown and local_scope == 'affirmed':
                gaps.append(dict(start=start, end=end, quote=quote, importance=local_importance,
                                 reason='unrecognized_coordinated_object', object_phrases=unknown))
        if not local and local_scope == "affirmed" and re.search(r"[\u4e00-\u9fffA-Za-z]", quote):
            gaps.append(dict(start=start, end=end, quote=quote,
                             importance=local_importance,
                             reason="unrecognized_complete_object" if rejected_object else "unrecognized_work_aspect"))
    if any(f["scope"] == "affirmed" for f in frames):
        scope = "affirmed"
    return dict(version=VERSION, semantic_review="machine_unreviewed", scope=scope,
                importance=importance, frames=frames, gaps=gaps,
                limitation="有界中文/英文工作方面适配；未识别表述保留缺口，不证明整岗或正式职业等价。")


def compare_work(left, right):
    """Compare explicit task aspects; unknown clauses prevent a whole-claim match."""
    left, right = [value['source_explanation'] if isinstance(value, dict) and 'source_explanation' in value
                   else explain_work(value) for value in (left, right)]
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


def _section_label(text):
    label = unicodedata.normalize('NFKC', text).strip().rstrip(':').strip()
    label = re.sub(r'^(?:(?:\d+|[一二三四五六七八九十]+)[、.)]|\((?:\d+|[一二三四五六七八九十]+)\))\s*', '', label)
    for left, right in (('【', '】'), ('[', ']'), ('(', ')')):
        if label.startswith(left) and label.endswith(right):
            label = label[len(left):-len(right)].strip().rstrip(':').strip()
            break
    # A sentence mentioning assistance is not a structural responsibility label.
    return bool(re.fullmatch(r'(?:(?:协助|辅助|配合|主要|核心|次要|其他|日常|岗位|工作)(?:工作)?)?'
                             r'(?:职责|责任|任务|工作(?:内容|范围)?|要求)|(?:任职|技能|能力)要求', label))


def _preceding_heading(prefix, recover_plain_headings):
    headings = {match.start(): (match, False) for match in re.finditer(r'(?m)^[^\n]*[:：]\s*$', prefix)}
    if recover_plain_headings:
        for line in re.finditer(r'(?m)^[^\r\n]+', prefix):
            condition_only = CONDITION.search(line.group()) and not re.search(PREDICATES, line.group())
            if line.start() not in headings and (_section_label(line.group()) or condition_only):
                headings[line.start()] = (line, True)
    return headings[max(headings)] if headings else None


def source_work(claim, analysis, *, recover_plain_headings=True):
    row = InputRecord.from_row(analysis['namespace'], analysis['input_row'])
    units = {}
    for value in claim['evidence']:
        evidence = Evidence.model_validate(value)
        source = row.payload[evidence.field]
        for statement in STATEMENTS.finditer(source):
            if statement.end() <= evidence.start or statement.start() >= evidence.end:
                continue
            if recover_plain_headings:
                line_start = source.rfind('\n', 0, statement.start()) + 1
                line_end = source.find('\n', statement.end())
                if _section_label(source[line_start:line_end if line_end >= 0 else len(source)]):
                    # A cited heading supplies governing evidence below, not an
                    # additional unknown task that depends on quote boundaries.
                    continue
            begin = statement.start()
            governing = []
            heading_importance = None
            # Recover a preceding controlling heading even when P1 only cites the task line.
            preceding = _preceding_heading(source[:begin], recover_plain_headings)
            if preceding:
                match, plain = preceding
                heading = explain_work(match.group())
                if heading['scope'] != 'affirmed' or heading['importance'] == 'auxiliary':
                    begin = match.start()
                    governing = [evidence.model_copy(update=dict(start=match.start(),
                        end=match.end(), quote=match.group())).model_dump()]
                    if plain:
                        heading_importance = heading['importance']
            context = source[begin:statement.end()]
            parsed = explain_work(dict(text=context, core=claim.get('core'), importance=heading_importance))
            spans = [*parsed['frames'], *[dict(gap, scope='affirmed') for gap in parsed['gaps']]]
            found = False
            for span in spans:
                start = max(evidence.start, statement.start(), begin + span['start'])
                end = min(evidence.end, begin + span['end'])
                if start >= end or not re.search(r'[\u4e00-\u9fffA-Za-z]', source[start:end]):
                    continue
                found = True
                unit = evidence.model_copy(update=dict(start=start, end=end, quote=source[start:end])).model_dump()
                context_unit = evidence.model_copy(update=dict(start=begin + span['start'], end=begin + span['end'],
                    quote=source[begin + span['start']:begin + span['end']])).model_dump()
                # Context can restrict a quotation, but cannot lend it uncited action/object facts.
                view = explain_work(dict(text=unit['quote'], scope=span['scope'], core=claim.get('core'),
                                         importance=span['importance']))
                restricts_quote = 'object' not in span and bool(view['frames']) and not view['gaps']
                if 'object' not in span:
                    view.update(frames=[], gaps=[dict(span)])
                else:
                    cited_head = start <= begin + span['object_start'] and begin + span['object_end'] <= end
                    restricts_quote = bool(view['frames']) and not cited_head
                    view['frames'] = [dict(f, object_phrase=span['object_phrase']) for f in view['frames']
                                      if cited_head and (f['action'], f['object_detail']) == (span['action'], span['object_detail'])]
                    if not view['frames'] and (recover_plain_headings or not view['gaps']):
                        if recover_plain_headings:
                            restricts_quote = True
                        view['gaps'].append(dict(start=0, end=len(unit['quote']), quote=unit['quote'],
                                                reason='uncited_action_or_object', importance=span['importance']))
                key = (evidence.field, start, end)
                if key in units:
                    units[key]['context_restricts_quote'] |= restricts_quote
                    units[key]['view']['frames'].extend(f for f in view['frames'] if f not in units[key]['view']['frames'])
                    if units[key]['view']['frames']:
                        units[key]['view']['gaps'] = [g for g in units[key]['view']['gaps'] if g['reason'] != 'uncited_action_or_object']
                    elif recover_plain_headings:
                        units[key]['view']['gaps'].extend(g for g in view['gaps'] if g['reason'] == 'uncited_action_or_object'
                                                        and g not in units[key]['view']['gaps'])
                else:
                    units[key] = dict(evidence=unit, context_evidence=context_unit, scope=span['scope'],
                                      context_restricts_quote=restricts_quote, governing_evidence=governing,
                                      importance=span['importance'], view=view)
            if not found:
                start, end = max(evidence.start, statement.start()), min(evidence.end, statement.end())
                if not re.search(r'[\u4e00-\u9fffA-Za-z]', source[start:end]):
                    continue
                # Later uncited affirmative work must not lend its scope to an earlier quote.
                scope = explain_work(source[begin:end])['scope']
                unit = evidence.model_copy(update=dict(start=start, end=end, quote=source[start:end])).model_dump()
                view = explain_work(dict(text=unit['quote'], scope=scope, core=claim.get('core'), importance=heading_importance))
                units[(evidence.field, start, end)] = dict(evidence=unit, context_evidence=unit,
                    context_restricts_quote=False, governing_evidence=governing,
                    scope=scope, importance=view['importance'], view=view)
    ordered = [units[key] for key in sorted(units)]
    for unit in ordered:
        if unit['view']['frames']:
            unit['context_restricts_quote'] = False
        if not recover_plain_headings:
            unit['view']['version'] = 'bounded-work-semantics-2'
    affirmed = [unit for unit in ordered if unit['scope'] == 'affirmed']
    scope = 'affirmed' if affirmed else next((unit['scope'] for unit in ordered), 'unresolved')
    selected = affirmed or ordered
    importance = ('auxiliary' if any(u['importance'] == 'auxiliary' for u in selected) else
                  'core' if claim.get('core') is True else 'unknown')
    explanation = dict(version=VERSION if recover_plain_headings else 'bounded-work-semantics-2', semantic_review='machine_unreviewed', scope=scope, importance=importance,
        context_restricts_quote=any(u['context_restricts_quote'] for u in selected),
        frames=[f for u in selected for f in u['view']['frames']], gaps=[g for u in selected for g in u['view']['gaps']],
        limitation='原文上下文只限定实际引文，不补入未引用的工作事实。')
    return dict(text='\n'.join(unit['evidence']['quote'] for unit in selected),
                core=claim.get('core'), scope=scope,
                importance=importance, source_explanation=explanation, matched_source_units=ordered)
