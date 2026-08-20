"""CLI 入口：将 LinkedIn 公开数据集 CSV 导入 jd_pool。

用法:
  python -m app.collect.import_csv \
      --csv data/archive/postings.csv \
      --job-skills data/archive/jobs/job_skills.csv \
      --skills-map data/archive/mappings/skills.csv \
      --offset 0 --limit 100000 --batch-size 5000
"""
import argparse
import sys
import time
from app.collect.fetchers.dataset import iter_csv_postings, load_job_skills, load_skill_map
from app.collect.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="导入 LinkedIn CSV 数据集到 jd_pool")
    parser.add_argument("--csv", required=True, help="postings.csv 路径")
    parser.add_argument("--job-skills", help="job_skills.csv 路径（可选，用于技能补充）")
    parser.add_argument("--skills-map", help="skills.csv 路径（可选，用于技能名映射）")
    parser.add_argument("--limit", type=int, default=100000,
                        help="导入行数上限，0=全量（默认 100000）")
    parser.add_argument("--offset", type=int, default=0,
                        help="跳过前 N 条有效岗位，用于断点续导（默认 0）")
    parser.add_argument("--batch-size", type=int, default=5000,
                        help="每批清洗并提交的岗位数（默认 5000）")
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

    if args.offset < 0 or args.limit < 0 or args.batch_size < 1:
        raise SystemExit("offset/limit 不能为负数，batch-size 必须 >= 1")

    # 2. 流式加载 CSV，避免全量 postings.csv 一次性进入内存。
    print(
        f"Loading CSV from {args.csv} "
        f"(offset={args.offset}, limit={args.limit or 'all'}, batch_size={args.batch_size})..."
    )
    postings = iter_csv_postings(args.csv, offset=args.offset, limit=args.limit)

    # 3. 分批跑管道；每批独立提交，失败后可用 offset 续导。
    print("Running pipeline (clean → enrich → dedup → save)...")
    from app.db.mysql import get_db  # lazy import: argparse --help 无需 DB
    db = next(get_db())
    total_saved = 0
    total_groups = 0
    total_loaded = 0
    try:
        batch: list = []
        for raw in postings:
            batch.append(raw)
            if len(batch) < args.batch_size:
                continue
            stats = run_pipeline(
                db, batch,
                job_skill_map=job_skill_map if job_skill_map else None,
                skill_map=skill_map if skill_map else None,
            )
            total_loaded += len(batch)
            total_saved += stats["saved"]
            total_groups += stats["groups"]
            print(f"  processed={total_loaded}, saved={total_saved}", flush=True)
            batch = []

        if batch:
            stats = run_pipeline(
                db, batch,
                job_skill_map=job_skill_map if job_skill_map else None,
                skill_map=skill_map if skill_map else None,
            )
            total_loaded += len(batch)
            total_saved += stats["saved"]
            total_groups += stats["groups"]

        elapsed = time.time() - t0
        print(f"Done. {total_loaded} rows loaded, {total_saved} rows saved, "
              f"{total_groups} dup groups, {elapsed:.1f}s elapsed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
