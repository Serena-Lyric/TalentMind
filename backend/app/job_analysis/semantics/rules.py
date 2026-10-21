"""Exact, conservative clause grammar. Unrecognized text is an explicit coverage gap."""
import hashlib
from pathlib import Path
import re

from ...skills.normalizer import build_alias_map
from ..foundation.inputs import digest
from ..foundation.models import AnalyzerSpec
from ..foundation.runner import dictionary
from .models import resolve

RULESET = "bounded-skill-clauses-v4"
HEADINGS = {"任职要求": "requirements", "岗位要求": "requirements", "技能要求": "requirements",
    "加分项": "preferred", "优先条件": "preferred", "加分条件": "preferred",
    "技术栈": "stack", "工作职责": "duties", "岗位职责": "duties",
    "职位要求": "requirements", "任职条件": "requirements", "任职资格": "requirements",
    "兼职要求": "requirements", "工作内容": "duties", "岗位内容": "duties",
    "主要工作内容": "duties", "职责描述": "duties", "岗位描述": "duties",
    "职位描述": "duties", "职位内容": "duties",
    "能力要求": "requirements", "核心能力要求": "requirements",
    "技术要求": "requirements", "专业要求": "requirements"}
DEGREES = {"基础了解": "basic", "了解": "basic", "熟悉": "familiar",
    "熟练掌握": "proficient", "熟练": "proficient", "精通": "expert"}
VERB = r"(?:基础了解|了解|熟悉|熟练掌握|熟练使用|熟练|精通|掌握|具备)"
MODAL = r"(?:必须|需要|要求|需|须|应)"
# These affect the containing sentence/adjacent lines, not merely the matched skill token.
RISK = re.compile(r"如果|若|仅当|除非|针对|对于|前端岗位|后端岗位|公司|我司|本团队|例如|示例|教程|曾经|过去|并非|不是|不但|而且|非本岗位|据说|可能|待定|视情况|候选人以外|未知(?:扩展|工具|组件|技术|能力)?")
SCOPE_RISK = re.compile(r"如果|若|仅当|除非|当.+时|仅适用|适用于|仅限|限于|仅对|只对|针对|对于|前端岗位|后端岗位|不必满足|无须满足|无需满足|不需要满足|条件.{0,8}见")
GROUP_SCOPE_RISK = re.compile(r'[二三四五六七八九十\d]+选[一二三\d]+|满足.{0,8}(?:一项|其一)|(?:以上|上述|以下)(?:技能|要求|条件|能力|条款|满足)')
RECORD_SCOPE_RISK = re.compile(
    r"仅适用于|仅限|限于|仅对|只对|适用于|当.+时|"
    r"不必满足|无需满足|不需要满足|以下条件|上述条件|条件.{0,8}见"
)
TAIL_SCOPE_RISK = re.compile(
    r"以上[^。；;!?！？\n]{0,30}(?:一项|技能|要求|条件|加分|满足)|"
    r"上述[^。；;!?！？\n]{0,30}(?:一项|技能|要求|条件|加分|满足)|"
    r"均为加分|满足一项即可|[二三四五六七八九十\d]+选[一二三\d]"
)


def evidence(record, field, start, end):
    return dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
        field=field, start=start, end=end, quote=record.payload[field][start:end])


def occurrences(text, aliases):
    matches = []
    for alias, name in aliases.items():
        # ASCII boundaries allow 熟悉Python, but forbid Java in JavaScript / py in happy.
        left = r"(?<![A-Za-z0-9_])" if re.match(r"[A-Za-z0-9_]", alias) else ""
        right = r"(?![A-Za-z0-9_])" if re.search(r"[A-Za-z0-9_]$", alias) else ""
        for match in re.finditer(left + re.escape(alias) + right, text, re.IGNORECASE):
            matches.append((match.start(), match.end(), name))
    accepted = []
    for match in sorted(matches, key=lambda m: (-(m[1] - m[0]), m[0], m[2])):
        if not any(match[0] < b and match[1] > a for a, b, _ in accepted):
            accepted.append(match)
    return sorted(accepted)


NUMBER = r"(?:[（(]\d{1,2}[)）]|\d{1,2}[、.．](?!\d))"


def logical_lines(text):
    # Split structural markers by original offsets; never rewrite the evidence string.
    labels = '|'.join(re.escape(h) for h in sorted(HEADINGS, key=len, reverse=True))
    starts = r"(?:(?<!\S)|(?<=[。；;!?！？]))"
    marker = rf"{starts}(?:[【\[](?:{labels})[】\]]|(?:{labels})(?=[:：]|\s+{NUMBER}))|(?:(?<!\S)|(?<=[:：])){NUMBER}"
    for line in re.finditer(r"[^\n]+", text):
        cuts = sorted({line.start(), *(line.start() + m.start() for m in re.finditer(marker, line[0]))})
        for a, b in zip(cuts, cuts[1:] + [line.end()]):
            if text[a:b].strip():
                yield a, b


def units(text, default_section, aliases):
    """Yield original offsets without normalizing the source; headings persist by field."""
    section = default_section
    header_start = None
    lines = list(logical_lines(text))
    for index, line in enumerate(lines):
        start, end = line
        value = text[start:end]
        standalone = value.strip().strip("#【】[] ")
        if standalone in HEADINGS:
            section, header_start = HEADINGS[standalone], start
            continue
        heading = re.match(r"\s*(?:[【\[]([^\]】]+)[】\]][:：]?|([^:：\]】]+)[:：])", value)
        if not heading:
            labels = '|'.join(re.escape(h) for h in HEADINGS)
            heading = re.match(rf"\s*({labels})(?=\s+{NUMBER})", value)
        if heading:
            label = next(g for g in heading.groups() if g is not None).strip()
            section = HEADINGS.get(label, "unknown_section")
            header_start = start
            if label in HEADINGS:
                start += heading.end()
            # Unknown headings remain in the yielded text, including empty-body labels.
        numbering = re.match(rf"\s*{NUMBER}\s*", text[start:end])
        if numbering:
            start += numbering.end()
        for sentence in re.finditer(r"[^。；;]+", text[start:end]):
            a, b = start + sentence.start(), start + sentence.end()
            whole = text[a:b]
            if not whole.strip():
                continue
            context_start = header_start if header_start is not None else a
            context_end = b
            # Only this explicit contrast has an implemented cross-clause scope.
            split_contrast = re.fullmatch(r"\s*(?:不要求|无需|不需要).+[，,]\s*但(?:是)?(?:需|需要|必须).+", whole)
            comma_parts = list(re.finditer(r"[^，,]+", whole))
            def templated(part):
                candidate = part[0]
                for a, b, _ in reversed(occurrences(candidate, aliases)):
                    candidate = candidate[:a] + '\ufdd0' + candidate[b:]
                return re.sub(r'\s+', '', candidate)
            templates = [templated(part) for part in comma_parts]
            split_capabilities = (len(comma_parts) > 1 and not RISK.search(whole)
                and not re.search(r"不要求|无需|不需要", whole)
                and all(classify(t, section, False)[0] in ('required', 'preferred') for t in templates))
            parts = comma_parts if split_contrast or split_capabilities else [re.match(r"[\s\S]+", whole)]
            for part in parts:
                x, y = a + part.start(), a + part.end()
                while x < y and text[x].isspace():
                    x += 1
                while y > x and text[y - 1].isspace():
                    y -= 1
                if x < y:
                    yield x, y, section, context_start, context_end, whole


def classify(template, section, risky):
    """Returns state/relation/reason. Full matches make unparsed modifiers visible."""
    def full(pattern):
        return re.fullmatch(pattern.replace("S", "\ufdd0"), template)

    if risky or section == "unknown_section":
        return "uncertain", None, "unsupported_context"
    if full(r"(?:不要求|无需|不需要)(?:" + VERB + r")?S(?:基础)?"):
        return "not_required", None, "explicit_negation"
    if full(r"S经验(?:优先|加分|为加分项)"):
        return "preferred", None, "explicit_experience_preference"
    if full(r"S(?:者)?(?:优先|加分|为加分项)"):
        return "preferred", None, "explicit_preference"
    if full(r"(?:" + MODAL + r")?S(?:或S)+(?:至少|需至少)?(?:掌握|熟悉|了解)一种") or full(
            r"(?:" + MODAL + r")?" + VERB + r"S(?:或S)+(?:中的)?(?:至少一种|任意一种|任选其一)"):
        return "preferred" if section == "preferred" else "required", "any_of", "explicit_any_of"
    if full(r"(?:" + MODAL + r")?(?:同时)?" + VERB + r"S(?:(?:和|及|与|、)S)+(?:全部|均)?"):
        # A bare skill list is not this grammar: an explicit capability verb is necessary.
        if section == "preferred" or re.match(MODAL, template) or section == "requirements":
            return "preferred" if section == "preferred" else "required", "all_of", "explicit_all_of"
    if full(r"(?:但(?:是)?)?" + MODAL + r"(?:" + VERB + r")?S(?:基础)?"):
        if section in ("duties", "stack", "title", "experience"):
            return "uncertain", None, "requirement_in_non_requirement_section"
        return "preferred" if section == "preferred" else "required", None, "explicit_requirement"
    if full(VERB + r"S(?:基础|语言|数据库)?") and section in ("requirements", "preferred"):
        return "preferred" if section == "preferred" else "required", None, "section_capability"
    if section in ("requirements", "preferred"):
        direct = re.match(r"(?:" + MODAL + r")?(?:" + VERB + r")\ufdd0", template)
        if direct:
            state = "preferred" if section == "preferred" else "required"
            tail = template[direct.end():]
            if re.search(r"不要求|无需|不需要|某些|部分|其中", tail):
                return "uncertain", None, "unsupported_clause"
            if ("\ufdd0" in tail
                    and not re.search(r"例如|如|等|可能", template)
                    and re.search(r"(?:至少|⾄少).{0,4}(?:一种|⼀种)", template)):
                return state, "any_of", "section_capability_extended_any_of"
            if "\ufdd0" in tail and not re.search(r"至少|任意|一种|项|例如|如|等|可能|待定", tail):
                if "或" in template[direct.start():]:
                    return state, "any_of", "section_capability_extended_any_of"
                if re.search(r"(?:和|及|与|、|/)\ufdd0", tail):
                    return state, "all_of", "section_capability_extended_all_of"
            if "\ufdd0" not in tail:
                return state, None, "section_capability_extended"
    if full(r"S(?:(?:和|及|与|、|/|或)S)*") or full(
            r"(?:负责)?(?:工作中)?(?:使用|运用)S(?:开发服务|开发软件|开发|工作)?"):
        return "mentioned", None, "list_or_work_use"
    return "uncertain", None, "unsupported_clause"


def extract(record, aliases):
    statements, issues = [], []
    record_scope = []
    for field in ("raw_text", "requirements", "duties", "experience"):
        text = record.payload.get(field, "")
        for match in re.finditer(r"[^\n。；;]+", text):
            fragment = match.group()
            if RECORD_SCOPE_RISK.search(fragment) and not occurrences(fragment, aliases):
                record_scope.append(
                    evidence(record, field, match.start(), match.end())
                )
            for scope_match in TAIL_SCOPE_RISK.finditer(fragment):
                record_scope.append(
                    evidence(
                        record,
                        field,
                        match.start() + scope_match.start(),
                        match.start() + scope_match.end(),
                    )
                )
    clause_owners = {}
    for field, default in (("requirements", "requirements"), ("duties", "duties"),
                           ("raw_text", "unspecified"), ("experience", "experience"),
                           ("job_title", "title")):
        text = record.payload.get(field, "")
        for start, end, section, ca, cb, sentence in units(text, default, aliases):
            signature = re.sub(r"\s+", "", sentence)
            if signature in clause_owners and clause_owners[signature] != field:
                continue
            clause_owners.setdefault(signature, field)
            clause = text[start:end]
            found = occurrences(clause, aliases)
            if not found:
                # Title and years are metadata, not claims of full skill coverage.
                if field not in ("job_title", "experience"):
                    issues.append(dict(reason="unparsed_text_or_unknown_skill", evidence=evidence(record, field, start, end)))
                continue
            template, position = "", 0
            for a, b, _ in found:
                template += clause[position:a] + "\ufdd0"
                position = b
            template += clause[position:]
            template = re.sub(r"\s+", "", template)
            context = text[ca:cb]
            scope_items = list(record_scope)
            risky = bool(scope_items) or bool(RISK.search(sentence)) or "\ufdd0" in clause
            state, relation, reason = classify(template, section, risky)
            if field == "job_title":
                state, relation, reason = "mentioned", None, "title_reference_only"
            if relation and len({name for _, _, name in found}) < 2:
                state, relation, reason = "uncertain", None, "non_distinct_group_members"
            if section in ("duties", "stack", "title", "experience") and relation:
                state, relation, reason = "uncertain", None, "group_in_non_requirement_section"
            degree_hits = list(re.finditer("|".join(DEGREES), clause))
            degree_hit = degree_hits[0] if len(degree_hits) == 1 else None
            if len(degree_hits) > 1:
                state, relation, reason = "uncertain", None, "multiple_degrees_unparsed"
            if not relation and len(found) > 1:
                # An unparsed multi-skill clause does not establish which skill owns the degree.
                degree_hit = None
            if state == "uncertain":
                issues.append(dict(reason=reason, evidence=evidence(record, field, start, end)))
            condition = ("\n".join(e["quote"] for e in scope_items) or context) if state == "uncertain" else None
            # Unparsed clauses with multiple skills retain independent uncertain statements,
            # not a fabricated conjunction. Preserve the unresolved object/condition in full.
            selections = [found] if relation else [[match] for match in found]
            for selected in selections:
                statements.append(dict(id=f"s{len(statements) + 1}",
                    skills=[dict(name=name, evidence=evidence(record, field, start + a, start + b)) for a, b, name in selected],
                    state=state, relation=relation, degree=DEGREES[degree_hit[0]] if degree_hit else None,
                    requirement_object="unresolved" if state == "uncertain" else
                        "experience" if reason == "explicit_experience_preference" else "capability",
                    degree_evidence=evidence(record, field, start + degree_hit.start(), start + degree_hit.end()) if degree_hit else None,
                    target="unresolved:" + condition if condition else "candidate",
                    condition=condition, section=section, reason=reason,
                    evidence=evidence(record, field, start, end), context=evidence(record, field, ca, cb),
                    scope_evidence=scope_items))
    if not statements and not issues:
        # No result is observable without inventing an uncertain skill or negative assertion.
        issues.append(dict(reason="no_supported_skill_content", evidence=evidence(record, "raw_text", 0, len(record.payload["raw_text"]))))
    return dict(schema_version="b2-2", coverage="incomplete" if issues else "complete",
        coverage_scope="known_aliases_and_supported_clauses_only",
        outcome="skills_identified" if statements else "no_recognized_skills",
        semantic_validation="deterministic_rules_only", statements=statements,
        effective=resolve(statements), issues=issues)


class SkillSemanticAnalyzer:
    """Conforms to foundation.models.Analyzer; its response uses a B2-specific schema."""
    def __init__(self):
        self.seed = dictionary()
        self.aliases = build_alias_map(self.seed)
        self.spec = AnalyzerSpec(extractor=RULESET, prompt="none", model="offline-rules", configuration="b2-2")

    def analyze(self, record):
        return extract(record, self.aliases)

    def manifest(self, revision):
        from ..foundation.models import VersionName
        from pydantic import TypeAdapter
        TypeAdapter(VersionName).validate_python(revision)
        # Code, schema, validator and execution semantics are actual dependencies, not labels alone.
        implementations = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))}
        root = Path(__file__).resolve().parents[1]
        for relative in ("foundation/inputs.py", "foundation/models.py", "foundation/store.py", "foundation/runner.py", "../skills/normalizer.py"):
            implementations[relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        return dict(revision=revision, spec=self.spec.model_dump(), dictionary=digest(self.seed),
            aliases=digest(self.aliases), implementation=implementations, input="foundation-strict-json-v1")
