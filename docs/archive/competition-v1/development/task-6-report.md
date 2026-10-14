# Task 6 Report: CLI Entry Point (import_csv.py)

## Status
**Complete**

## Commits
- `cd21053` — `feat(A-csv): cli entry point for csv to jd_pool import`

## Verification

### `python -m app.collect.import_csv --help` — PASS

```
usage: python.exe -m app.collect.import_csv [-h] --csv CSV
                                            [--job-skills JOB_SKILLS]
                                            [--skills-map SKILLS_MAP]
                                            [--limit LIMIT]

导入 LinkedIn CSV 数据集到 jd_pool

options:
  -h, --help            show this help message and exit
  --csv CSV             postings.csv 路径
  --job-skills JOB_SKILLS
                        job_skills.csv 路径（可选，用于技能补充）
  --skills-map SKILLS_MAP
                        skills.csv 路径（可选，用于技能名映射）
  --limit LIMIT         导入行数上限，0=全量（默认 100000）
```

### Notes
- `get_db` import is lazy (inside `main()`) so `--help` works without a database connection.
- All four CLI arguments present: `--csv` (required), `--job-skills` (optional), `--skills-map` (optional), `--limit` (default 100000).
- Import chain verified against existing interfaces (`load_csv_posting`, `load_job_skills`, `load_skill_map`, `run_pipeline`, `get_db`).
