from app.collect.cleaner import clean
from app.collect.dedup import assign_dup_groups, quality_score
from app.collect.repository import save_rows


def enrich_skills(
    rows: list[dict],
    job_skill_map: dict[str, list[str]],
    skill_map: dict[str, str],
    job_id_key: str = "_job_id",
) -> list[dict]:
    """通过 job_id join 技能缩写→技能名，追加到 raw_text 尾部。"""
    for row in rows:
        job_id = row.pop(job_id_key, None)
        if not job_id or job_id not in job_skill_map:
            continue
        abrs = job_skill_map[job_id]
        names = [skill_map[a] for a in abrs if a in skill_map]
        if names:
            skill_text = "\n\nSkills: " + ", ".join(names)
            row["raw_text"] = row.get("raw_text", "") + skill_text
    return rows


def run_pipeline(
    db,
    raws,
    job_skill_map: dict[str, list[str]] | None = None,
    skill_map: dict[str, str] | None = None,
) -> dict:
    rows = []
    for r in raws:
        row = clean(r)
        if r.job_id:
            row["_job_id"] = r.job_id  # 临时传递，enrich 后删除
        rows.append(row)

    if job_skill_map and skill_map:
        rows = enrich_skills(rows, job_skill_map, skill_map)

    rows = assign_dup_groups(rows)

    group_sizes: dict[str, int] = {}
    for r in rows:
        group_sizes[r["dup_group"]] = group_sizes.get(r["dup_group"], 0) + 1
    for r in rows:
        r["quality"] = quality_score(r, group_sizes[r["dup_group"]])

    saved = save_rows(db, rows)
    return {"saved": saved, "groups": len(group_sizes)}
