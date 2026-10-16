"""Bounded occurrence/classification overlay. Never rewrite the source semantic document."""
import copy
import re

from ..foundation.inputs import digest
from ..semantics.rules import HEADINGS, RISK, SCOPE_RISK, evidence, occurrences

FIELDS = ("raw_text", "requirements", "duties", "experience", "job_title")
VERSION_TEXT = r"(?:v|[<>=~^]+)?\s*\d[^\s、,，。；;()（）]*(?:\s+[-~～至到]\s*\d[^\s、,，。；;()（）]*)?"
TERM = r"[A-Za-z][A-Za-z0-9_.+#/-]{1,63}(?:\s+" + VERSION_TEXT + r")?"
CAPABILITY = re.compile(r"(?:必须|需要|要求|需|须)?\s*(?:掌握|熟悉|精通|了解|熟练掌握)\s*(?P<term>" + TERM + r")\s*(?:基础)?")
HEADING = re.compile(r"(?:[【\[])?([^:：\]】]+)(?:[】\]])?[:：]\s*")
NON_RECRUITMENT_HEADINGS = {"公司介绍", "企业介绍", "福利待遇", "技术教程", "教程", "示例"}
QUALIFIER = re.compile(r"(?:不要求|无需|不需要)\s*|(?:如果|若)[^，,]+[，,]\s*(?:则)?\s*")
YEAR = r"(?:\d{1,2}|[一二三四五六七八九十两])"
YEARS = re.compile(r"(?<![0-9一二三四五六七八九十百千万零〇两.\-~～至到])(?P<years>" + YEAR + r")年以上\s*(?:(?P<skill>" + TERM + r")\s*开发经验|(?P<job>工作经验))")
EDUCATION = re.compile(r"(?:要求)?(?P<level>本科|硕士|博士|大专)(?:及以上)?学历")
CREDENTIAL = re.compile(r"(?:持有|取得|具备)\s*(?P<name>[A-Za-z][A-Za-z0-9+.-]{1,32}|[\u4e00-\u9fff]{2,12})\s*(?:证书|认证|资格证)")
COMPANY_TERM = re.compile(r"(?:corp|labs|inc|company|ltd)$", re.I)


def verify_evidence(value, record):
    if isinstance(value, dict):
        if {"quote", "start", "end", "field"} <= value.keys():
            if (value.get("namespace"), value.get("jd_id"), value.get("fingerprint")) != (
                    record.namespace, record.jd_id, record.fingerprint):
                raise ValueError("foreign governance evidence")
            text = record.payload.get(value["field"], "")
            a, b = value["start"], value["end"]
            if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(text) or text[a:b] != value["quote"]:
                raise ValueError("governance evidence offset mismatch")
        for child in value.values():
            verify_evidence(child, record)
    elif isinstance(value, list):
        for child in value:
            verify_evidence(child, record)


def overlaps(a, b):
    return a["field"] == b["field"] and a["start"] < b["end"] and a["end"] > b["start"]


def statement_ids(ev, original):
    return [s["id"] for s in original["statements"] if any(overlaps(ev, k["evidence"]) for k in s["skills"])]


def analyze(record, original, catalog):
    verify_evidence(original, record)
    skills, candidates, non_skills, unexplained, review_mentions = [], [], [], [], []
    policy_version = digest(catalog.manifest())
    domains = [r["canonical"] for r in catalog.seed if r.get("category") == "专业领域"]
    domain_pattern = re.compile("(?:" + "|".join(re.escape(d) for d in sorted(domains, key=len, reverse=True)) + r")(?:行业经验|领域知识)") if domains else None

    def non_skill(kind, value, field, match):
        non_skills.append(dict(id=f"n{len(non_skills) + 1}", kind=kind, value=value,
            evidence=evidence(record, field, *match.span()), skill_ids=[], status="bounded_rule_fact",
            context=evidence(record, field, 0, len(record.payload[field])), constraint_state="needs_review",
            interpretation="original_wording_only_no_global_requirement_inferred"))

    for field in FIELDS:
        text = record.payload.get(field, "")
        for hit in YEARS.finditer(text):
            raw = hit["years"]
            number = int(raw) if raw.isdigit() else {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
                "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}[raw]
            non_skill("work_years", dict(minimum=number, unit="year", scope="skill_specific" if hit["skill"] else "job_work_experience"), field, hit)
        for hit in EDUCATION.finditer(text):
            non_skill("education", dict(level=hit["level"]), field, hit)
        for hit in CREDENTIAL.finditer(text):
            non_skill("credential", dict(name=hit["name"].strip()), field, hit)
        if domain_pattern:
            for hit in domain_pattern.finditer(text):
                non_skill("domain_experience" if hit[0].endswith("行业经验") else "domain_knowledge", dict(text=hit[0]), field, hit)

    for field in FIELDS:
        text = record.payload.get(field, "")
        section, section_start = {"raw_text": "unspecified", "job_title": "title"}.get(field, field), None
        for unit in re.finditer(r"[^\n。；;]+", text):
            ca, cb = unit.span()
            while ca < cb and text[ca].isspace():
                ca += 1
            while cb > ca and text[cb - 1].isspace():
                cb -= 1
            if ca == cb:
                continue
            clause = text[ca:cb]
            body_start = ca
            heading = HEADING.match(clause)
            label = heading[1].strip() if heading else clause.strip("#【】[] ")
            if heading or label in HEADINGS or label == "技能" or label in NON_RECRUITMENT_HEADINGS:
                section, section_start = HEADINGS.get(label, "requirements" if label == "技能" else "unknown_section"), ca
                body_start = ca + heading.end() if heading else cb
            body = text[body_start:cb]
            context = evidence(record, field, section_start if section_start is not None else text.rfind("\n", 0, ca) + 1,
                (text.find("\n", cb) if "\n" in text[cb:] else len(text)))
            # All known terms are considered, but only old evidence or explicit new formats admit them.
            found = [(ca + a, ca + b) for a, b, _ in occurrences(clause, {k: k for k in catalog.index})]
            # Extend the raw occurrence BEFORE resolution; never lose concrete version text.
            for i, (a, b) in enumerate(found):
                suffix = re.match(r"\s+" + VERSION_TEXT, text[b:cb], re.I)
                if suffix:
                    found[i] = (a, b + suffix.end())
            explicit = []
            qualifier = QUALIFIER.match(body)
            capability_start = body_start + (qualifier.end() if qualifier else 0)
            eligible = section in ("unspecified", "requirements", "preferred", "stack")
            capability = CAPABILITY.fullmatch(text[capability_start:cb]) if eligible else None
            qualified = bool(qualifier or RISK.search(context["quote"]) or SCOPE_RISK.search(context["quote"]) or
                             re.search(r"不要求|无需|不需要", context["quote"]))
            if capability:
                explicit.append((capability_start + capability.start("term"), capability_start + capability.end("term"), "explicit_capability"))
            if section in ("requirements", "stack"):
                for part in re.finditer(r"[^、,，]+", body):
                    raw = part[0].strip()
                    if re.fullmatch(TERM, raw):
                        a = body_start + part.start() + len(part[0]) - len(part[0].lstrip())
                        explicit.append((a, a + len(raw), "explicit_skill_list"))
            for a, b, _ in explicit:
                # A complete explicit token supersedes a known prefix inside its version/name.
                found = [(x, y) for x, y in found if not (a <= x and b >= y)]
                if not any(a < y and b > x for x, y in found):
                    found.append((a, b))
            # Boundaries differ for compact versions (Vue3); explicit grammar supplies the whole term.
            accepted = []
            for a, b in sorted(found, key=lambda p: (-(p[1] - p[0]), p[0])):
                if not any(a < y and b > x for x, y in accepted):
                    accepted.append((a, b))
            for a, b in sorted(accepted):
                ev = evidence(record, field, a, b)
                if any(n["kind"] != "work_years" and overlaps(n["evidence"], ev) for n in non_skills):
                    continue
                normalized = catalog.resolve(text[a:b])
                links = statement_ids(ev, original)
                anchor = next((reason for x, y, reason in explicit if x == a and y == b), None)
                if not links and not anchor:
                    continue
                if normalized["canonical"]:
                    category, tags, basis = catalog.classification(normalized["canonical"])
                    if any(r.get("category") == "专业领域" for r in catalog.canonicals.get(normalized["canonical"], [])):
                        review_mentions.append(dict(**normalized, evidence=ev, context=context, category=None,
                            statement_ids=links, reason="domain_term_requires_contextual_review"))
                        continue
                    skills.append(dict(id=f"k{len(skills) + 1}", **normalized, category=category, tags=tags,
                        classification_status="classified" if category else "needs_review", classification_basis=basis,
                        evidence=ev, statement_ids=links, context=context))
                elif anchor and not COMPANY_TERM.search(text[a:b]):
                    reason = normalized["basis"] or ("unverified_or_ambiguous_alias" if normalized["baseline_matches"] else "outside_readonly_seed")
                    candidate = dict(id=digest(dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
                        field=field, start=a, end=b, version=policy_version)), version=policy_version, raw_name=text[a:b],
                        evidence=ev, context=context, statement_ids=links,
                        statement=dict(evidence=evidence(record, field, ca, cb), basis=anchor),
                        comparison=normalized, candidate_type="version_review" if reason == "unsupported_version_expression" else
                            "alias_review" if normalized["baseline_matches"] else "possible_skill",
                        tier="strong_context" if anchor == "explicit_capability" and not normalized["baseline_matches"] and not qualified else "disputed",
                        category=None, classification_status="needs_review", review_reasons=[reason, anchor] + (["unresolved_requirement_context"] if qualified else []),
                        governance_status="pending_review", review_basis=None, independent_validation="not_established", formal_admitted=False)
                    candidates.append(candidate)
            # Preserve all clauses, including arbitrary unknown prose which is not a candidate.
            unexplained.append(dict(reason="bounded_governance_does_not_claim_clause_completeness", evidence=evidence(record, field, ca, cb)))
    for fact in non_skills:
        if fact["kind"] == "work_years" and fact["value"]["scope"] == "skill_specific":
            fact["skill_ids"] = [s["id"] for s in skills if overlaps(s["evidence"], fact["evidence"])]
    result = dict(schema_version="b22-1", source_payload=record.payload, original_semantics=copy.deepcopy(original),
        skills=skills, non_skills=non_skills, candidates=candidates, review_mentions=review_mentions, unresolved_fragments=unexplained,
        analysis_complete=False, coverage_scope="bounded_name_classification_and_candidate_overlay",
        formal_statistics_eligible=False, evidence_validation="offsets_checked_not_semantic_truth")
    verify_evidence(result, record)
    return result
