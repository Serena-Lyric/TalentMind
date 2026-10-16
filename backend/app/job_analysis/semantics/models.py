"""B2 statements are separate from stage A's legacy/unreviewed fact labels."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

State = Literal["required", "preferred", "mentioned", "not_required", "uncertain"]
Degree = Literal["basic", "familiar", "proficient", "expert"]
RequirementObject = Literal["capability", "experience", "unresolved"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Evidence(StrictModel):
    namespace: str
    jd_id: str
    fingerprint: str
    field: Literal["job_title", "raw_text", "duties", "experience", "requirements"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)


class Skill(StrictModel):
    name: str
    evidence: Evidence


class Statement(StrictModel):
    id: str
    skills: list[Skill] = Field(min_length=1)
    state: State
    relation: Literal["any_of", "all_of"] | None
    requirement_object: RequirementObject
    degree: Degree | None
    degree_evidence: Evidence | None
    target: str
    condition: str | None
    section: str
    reason: str
    evidence: Evidence
    context: Evidence
    scope_evidence: list[Evidence]


class Effective(StrictModel):
    skill: str
    requirement_object: RequirementObject
    degree: Degree | None
    target: str
    condition: str | None
    state: State
    conflict: bool
    statement_ids: list[str]
    group_ids: list[str]
    reason: str


class Issue(StrictModel):
    reason: str
    evidence: Evidence


class Document(StrictModel):
    schema_version: Literal["b2-2"]
    coverage: Literal["complete", "incomplete"]
    coverage_scope: Literal["known_aliases_and_supported_clauses_only"]
    outcome: Literal["skills_identified", "no_recognized_skills"]
    semantic_validation: Literal["deterministic_rules_only"]
    statements: list[Statement]
    effective: list[Effective]
    issues: list[Issue]


def resolve(statements):
    """Compare only equal skill/degree/object/condition; never take max or last."""
    buckets = {}
    for statement in statements:
        for skill in statement["skills"]:
            key = (skill["name"], statement["requirement_object"], statement["degree"], statement["target"], statement["condition"])
            buckets.setdefault(key, []).append(statement)
    result = []
    for (skill, requirement_object, degree, target, condition), entries in buckets.items():
        singles = [s for s in entries if s["relation"] is None]
        groups = list(dict.fromkeys(s["id"] for s in entries if s["relation"] is not None))
        asserted = {s["state"] for s in singles} - {"mentioned"}
        definite = asserted - {"uncertain"}
        conflict = len(definite) > 1
        state = ("uncertain" if conflict or "uncertain" in asserted else
                 next(iter(definite)) if definite else "mentioned")
        result.append(dict(skill=skill, requirement_object=requirement_object, degree=degree, target=target, condition=condition,
            state=state, conflict=conflict, statement_ids=[s["id"] for s in singles], group_ids=groups,
            reason="conflicting_statements" if conflict else "group_membership_only" if not singles else "statement_resolution"))
    return result
