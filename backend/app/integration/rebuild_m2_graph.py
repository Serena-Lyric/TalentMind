"""Project the full M2 catalog offline; production rebuilding is disabled."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[3]
_CANONICAL_NAMES = {
    item["canonical"].lower(): item["canonical"]
    for item in json.loads((REPO_ROOT / "backend/app/skills/skill_dict_seed.json").read_text(encoding="utf-8"))
}


def _list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _object(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
    return value or "unknown"


def _skill_id(name: str) -> str:
    name = name.strip()
    return f"skill:{quote(_CANONICAL_NAMES.get(name.lower(), name), safe='')}"


def build_graph_data(rows: list[dict[str, Any]], skill_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Project legacy fields without resolving unreviewed aliases or requirement conflicts.

    Identity is exact canonical spelling (case insensitive) or the trimmed original
    name. The versioned seed is read only; its alias table is deliberately unused.
    """
    skill_by_job: dict[int, list[tuple[int, int, dict[str, Any]]]] = defaultdict(list)
    for row_index, row in enumerate(skill_rows):
        for index, item in enumerate(_list(row.get("skills"))):
            if isinstance(item, dict):
                skill_by_job[int(row["jd_id"])].append((row_index, index, item))

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    job_skill_sets: dict[str, set[str]] = {}
    related_candidates: dict[tuple[str, str], int] = defaultdict(int)
    entity_nodes: dict[str, dict[str, Any]] = {}
    entity_jobs: dict[str, set[str]] = defaultdict(set)
    entity_names: dict[str, set[str]] = defaultdict(set)
    entity_mappings: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    seen_jobs: set[str] = set()
    audit: dict[str, Any] = {"identity_version": "exact-canonical-percent-v1", "requirement_semantics": "legacy_required_bonus",
                             "unverified_canonical_claims": [], "skill_details": [], "requirement_conflicts": []}

    def register(kind: str, name: str, job_id: str, legacy_name: str | None = None, record_mapping: bool = True) -> str:
        raw_name = name
        name = name.strip()
        identity = _CANONICAL_NAMES.get(name.lower(), name) if kind == "skill" else name
        entity_id = f"{kind}:{quote(identity, safe='')}"
        if entity_id not in entity_nodes:
            entity_nodes[entity_id] = {"id": entity_id, "type": kind, "kind": kind, "name": identity,
                                       "normalization_status": "canonical_exact" if kind == "skill" and name.lower() in _CANONICAL_NAMES else "unreviewed_name"}
            if kind == "industry":
                entity_nodes[entity_id]["color"] = "#c77dff"
        entity_jobs[entity_id].add(job_id)
        entity_names[entity_id].add(raw_name)
        if record_mapping:
            legacy_id = f"{kind}:{_slug(legacy_name if legacy_name is not None else name)}"
            entity_mappings[(kind, job_id, raw_name, legacy_id)] = {
                "kind": kind, "job_id": job_id, "source_name": raw_name, "identity": identity,
                "legacy_id": legacy_id, "new_id": entity_id,
                "normalization_status": entity_nodes[entity_id]["normalization_status"]}
        return entity_id

    for row in rows:
        internal_id = int(row["id"])
        m2_id = str(row.get("m2_job_id") or f"db-{internal_id}")
        job_id = f"job:{_slug(m2_id)}"
        if job_id in seen_jobs:
            raise ValueError(f"Duplicate job ID after legacy projection: {job_id}")
        seen_jobs.add(job_id)
        required_values = [(index, str(item)) for index, item in enumerate(_list(row.get("required_skills"))) if str(item).strip()]
        bonus_values = [(index, str(item)) for index, item in enumerate(_list(row.get("bonus_skills"))) if str(item).strip()]
        required = [name for _, name in required_values]
        bonus = [name for _, name in bonus_values]
        details = skill_by_job.get(internal_id, [])
        legacy_aliases: dict[str, str] = {}
        unverified_skill_ids: set[str] = set()
        for row_index, index, item in details:
            audit["skill_details"].append({"job_id": job_id, "source_row_index": row_index,
                                           "source_index": index, "detail": dict(item)})
            display = str(item.get("name") or "").strip()
            canonical = str(item.get("canonical_name") or "").strip()
            # Reproduce the old last-wins aliases only for compatibility audit.
            legacy_canonical = str(item.get("canonical_name") or item.get("name") or "").strip().lower()
            if display and legacy_canonical:
                legacy_aliases[display.lower()] = legacy_canonical
            if legacy_canonical:
                legacy_aliases[legacy_canonical] = legacy_canonical
            if display and canonical and _skill_id(display) != _skill_id(canonical):
                unverified_skill_ids.add(_skill_id(display))
                audit["unverified_canonical_claims"].append({"job_id": job_id, "source_name": display,
                                                             "claimed_canonical": canonical, "mapping_applied": False})
        required_ids = [register("skill", skill, job_id, legacy_aliases.get(skill.lower(), skill.lower())) for skill in required]
        bonus_ids = [register("skill", skill, job_id, legacy_aliases.get(skill.lower(), skill.lower())) for skill in bonus]
        all_skill_ids = set(required_ids + bonus_ids)
        job_skill_sets[job_id] = all_skill_ids
        source = _list(row.get("source"))
        scenarios = [str(item) for item in _list(row.get("scenarios")) if str(item).strip()]
        nodes.append({
            "id": job_id, "type": "job", "kind": "job", "name": str(row.get("name_en") or row.get("job_name") or ""),
            "name_zh": str(row.get("job_name_zh") or row.get("job_name") or ""), "name_en": str(row.get("name_en") or ""),
            "category": str(row.get("category") or ""), "is_emerging": bool(row.get("is_emerging")),
            "evolution": _object(row.get("evolution")),
            "source": source, "platform": "/".join(source), "core_duties": str(row.get("core_duties") or ""),
            "required_skills": required, "bonus_skills": bonus, "quality": float(row.get("quality") or 0),
            "jd_count": int(row.get("source_jd_count") or 0),
        })
        requirements: dict[str, list[tuple[str, str, str, int, int]]] = defaultdict(list)
        for values, ids, state, field in ((required_values, required_ids, "legacy_required", "required_skills"),
                                          (bonus_values, bonus_ids, "legacy_bonus", "bonus_skills")):
            for (index, name), sid in zip(values, ids):
                requirements[sid].append((name, state, field, -1, index))
        for row_index, index, item in details:
            name = str(item.get("name") or "")
            sid = _skill_id(name)
            if sid in requirements and isinstance(item.get("is_required"), bool):
                register("skill", name, job_id, record_mapping=False)
                state = "legacy_required" if item["is_required"] else "legacy_bonus"
                requirements[sid].append((name, state, "skill_details", row_index, index))
        for sid, occurrences in sorted(requirements.items()):
            occurrences.sort()
            states = {state for _, state, _, _, _ in occurrences}
            conflict = len(states) > 1
            is_required = None if conflict else "legacy_required" in states
            edges.append({"source": job_id, "target": sid, "type": "REQUIRES",
                          "weight": None if conflict else (1.0 if is_required else 0.6), "is_required": is_required,
                          "source_names": [name for name, _, _, _, _ in occurrences],
                          "source_states": [state for _, state, _, _, _ in occurrences],
                          "source_fields": [field for _, _, field, _, _ in occurrences],
                          "source_row_indices": [row_index for _, _, _, row_index, _ in occurrences],
                          "source_indices": [index for _, _, _, _, index in occurrences],
                          "has_duplicates": len(occurrences) > 1, "status_conflict": conflict,
                          "needs_review": conflict or sid in unverified_skill_ids})
            if conflict:
                audit["requirement_conflicts"].append({"source": job_id, "target": sid})
        applied_industries: set[str] = set()
        for scenario in scenarios[:8]:
            industry_id = register("industry", scenario, job_id)
            if industry_id not in applied_industries:
                applied_industries.add(industry_id)
                edges.append({"source": job_id, "target": industry_id, "type": "APPLIES_TO", "weight": 1.0})

    for entity_id, node in sorted(entity_nodes.items()):
        node["source_names"] = sorted(entity_names[entity_id])
        node["display_name"] = node["source_names"][0]
        node["job_count"] = len(entity_jobs[entity_id])
        nodes.append(node)
    skill_jobs: dict[str, list[str]] = defaultdict(list)
    for job_id, skill_ids in job_skill_sets.items():
        for skill_id in skill_ids:
            skill_jobs[skill_id].append(job_id)
    for values in skill_jobs.values():
        names = sorted(set(values))
        for index, left in enumerate(names):
            for right in names[index + 1:]:
                related_candidates[(left, right)] += 1
    for (left, right), shared in sorted(related_candidates.items()):
        union = job_skill_sets[left] | job_skill_sets[right]
        similarity = shared / len(union) if union else 0
        if similarity >= 0.35:
            edges.append({"source": left, "target": right, "type": "RELATED_TO", "similar": round(similarity, 4)})

    legacy_targets: dict[str, set[str]] = defaultdict(set)
    for mapping in entity_mappings.values():
        legacy_targets[mapping["legacy_id"]].add(mapping["new_id"])
    audit["entity_mappings"] = [entity_mappings[key] for key in sorted(entity_mappings)]
    audit["legacy_id_collisions"] = [{"legacy_id": key, "new_ids": sorted(values)}
                                     for key, values in sorted(legacy_targets.items()) if len(values) > 1]
    audit["candidate_pair_count"] = len(related_candidates)
    for key in ("skill_details", "unverified_canonical_claims", "requirement_conflicts"):
        audit[key].sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return {"nodes": sorted(nodes, key=lambda node: node["id"]),
            "edges": sorted(edges, key=lambda edge: (edge["source"], edge["target"], edge["type"])), "audit": audit}


def rebuild() -> dict[str, int]:
    """Fail closed until consumers and an approved production migration are ready."""
    raise RuntimeError("rebuild disabled: offline projection only; use app.graph.diagnose_snapshot")


if __name__ == "__main__":
    rebuild()
