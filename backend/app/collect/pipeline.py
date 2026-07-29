from app.collect.cleaner import clean
from app.collect.talent_cleaner import clean_talent
from app.collect.dedup import assign_dup_groups, quality_score
from app.collect.repository import save_rows, save_talent_rows
from app.collect.schema import RawJD, RawTalent


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


def _assign_quality(rows: list[dict]) -> int:
    """按 dup_group 统计分组大小并填充 quality 分数，返回分组数。两侧共用。"""
    group_sizes: dict[str, int] = {}
    for r in rows:
        group_sizes[r["dup_group"]] = group_sizes.get(r["dup_group"], 0) + 1
    for r in rows:
        r["quality"] = quality_score(r, group_sizes[r["dup_group"]])
    return len(group_sizes)


def run_pipeline(
    db,
    raws,
    job_skill_map: dict[str, list[str]] | None = None,
    skill_map: dict[str, str] | None = None,
) -> dict:
    """按元素类型分流：RawJD 走岗位链(jd_pool)，RawTalent 走人才链(talent_raw)。
    raws 可混合两种类型；Fetcher.fetch() 的返回类型本身即路由依据。"""
    jd_raws = [r for r in raws if isinstance(r, RawJD)]
    talent_raws = [r for r in raws if isinstance(r, RawTalent)]

    jd_saved = 0
    talent_saved = 0
    total_groups = 0

    if jd_raws:
        rows = []
        for r in jd_raws:
            row = clean(r)
            if r.job_id:
                row["_job_id"] = r.job_id  # 临时传递，enrich 后删除
            rows.append(row)

        if job_skill_map and skill_map:
            rows = enrich_skills(rows, job_skill_map, skill_map)

        rows = assign_dup_groups(rows)
        total_groups += _assign_quality(rows)
        jd_saved = save_rows(db, rows)

    if talent_raws:
        rows = [clean_talent(r) for r in talent_raws]
        rows = assign_dup_groups(rows)
        total_groups += _assign_quality(rows)
        talent_saved = save_talent_rows(db, rows)

    return {
        "saved": jd_saved + talent_saved,
        "jd_saved": jd_saved,
        "talent_saved": talent_saved,
        "groups": total_groups,
    }
