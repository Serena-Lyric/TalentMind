"""CLI 入口：将 LinkedIn 公开数据集 CSV 导入 jd_pool。

用法:
  python -m app.collect.import_csv \
      --csv data/archive/postings.csv \
      --job-skills data/archive/jobs/job_skills.csv \
      --skills-map data/archive/mappings/skills.csv \
      --limit 100000
"""
import argparse
import sys
import time
from app.collect.fetchers.dataset import load_csv_posting, load_job_skills, load_skill_map
from app.collect.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="导入 LinkedIn CSV 数据集到 jd_pool")
    parser.add_argument("--csv", required=True, help="postings.csv 路径")
    parser.add_argument("--job-skills", help="job_skills.csv 路径（可选，用于技能补充）")
    parser.add_argument("--skills-map", help="skills.csv 路径（可选，用于技能名映射）")
    parser.add_argument("--limit", type=int, default=100000,
                        help="导入行数上限，0=全量（默认 100000）")
    args = parser.parse_args()

    t0 = time.time()

    # 1. 加载技能映射（可选）
    job_skill_map = {}
    skill_map = {}
    if args.job_skills and args.skills_map:
        print(f"Loading skill mappings...")
        skill_map = load_skill_map(args.skills_map)
        job_skill_map = load_job_skills(args.job_skills)
        print(f"  {len(skill_map)} skill types, {len(job_skill_map)} jobs with skills")

    # 2. 加载 CSV
    print(f"Loading CSV from {args.csv} (limit={args.limit or 'all'})...")
    raws = load_csv_posting(args.csv, limit=args.limit)
    print(f"  {len(raws)} rows loaded")

    # 3. 跑管道
    print("Running pipeline (clean → enrich → dedup → save)...")
    from app.db.mysql import get_db  # lazy import: argparse --help 无需 DB
    db = next(get_db())
    try:
        stats = run_pipeline(
            db, raws,
            job_skill_map=job_skill_map if job_skill_map else None,
            skill_map=skill_map if skill_map else None,
        )
        elapsed = time.time() - t0
        print(f"Done. {stats['saved']} rows saved, {stats['groups']} dup groups, "
              f"{elapsed:.1f}s elapsed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
