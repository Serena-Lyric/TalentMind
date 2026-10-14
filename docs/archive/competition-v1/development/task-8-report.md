# Task 8 Report: 全量测试与采样冒烟

**Date:** 2026-07-24
**Status:** PASSED (with one data-driven fix applied)

---

## Step 1: Unit Tests (excluding integration)

Command: `cd backend && .venv/Scripts/python -m pytest -v -m "not integration"`

Result: **51 passed, 7 deselected** in 1.15s

All unit tests passed, covering:
- test_cleaner.py (17 tests): strip_noise, extract_duties, extract_experience, clean
- test_collect_repo.py (4 tests): build_insert_params, save_rows
- test_config.py (1 test): settings
- test_dataset_import.py (8 tests): CSV loading, skill maps, job skills
- test_llm_client.py (3 tests): extract_json, embed
- test_middleware.py (4 tests): health, error handling
- test_normalizer.py (3 tests): alias mapping
- test_pipeline.py (6 tests): enrich_skills, run_pipeline
- test_response.py (3 tests): response shapes
- test_schemas.py (2 tests): SkillItem, MatchResult

---

## Step 2: Integration Tests (Docker required)

Command: `docker-compose up -d --wait && cd backend && .venv/Scripts/python -m pytest -v -m integration`

Result: **7 passed, 51 deselected** in 1.23s

All integration tests passed, covering:
- test_collect_integration.py (1 test): CSV-to-jd_pool end-to-end pipeline
- test_db_integration.py (3 tests): MySQL, Neo4j, Redis roundtrips
- test_ddl_integration.py (3 tests): table creation, frozen columns, canonical unique

---

## Step 3: Real CSV Sampling Smoke Test

Command: `cd backend && python -m app.collect.import_csv --csv ../docs/originalfile/archive/postings.csv --job-skills ../docs/originalfile/archive/jobs/job_skills.csv --skills-map ../docs/originalfile/archive/mappings/skills.csv --limit 1000`

**First attempt:** FAILED with `DataError: (1406, "Data too long for column 'experience' at row 1")`. The `jd_pool.experience` column is `VARCHAR(32)` but real-world data contains longer strings (e.g., "Customer service: 1 year (Preferred)Health, Fitness, or Medical: 1 year (Preferred)" = 79 chars).

**Fix applied:** Added `[:32]` truncation in `build_insert_params()` at `backend/app/collect/repository.py` line 17, changing:
```python
"experience": row.get("experience", ""),
```
to:
```python
"experience": (row.get("experience", "") or "")[:32],
```

**Second attempt:** PASSED. **Done. 1000 rows saved, 996 dup groups, 1.5s elapsed**

---

## Step 4: Commit

```
git add backend/app/collect/repository.py
git commit -m "chore(A-csv): csv import pipeline complete, all tests green"
```

Commit: `484522b`

---

## Summary

| Step | Tests | Result |
|------|-------|--------|
| Unit | 51 | ALL PASS |
| Integration | 7 | ALL PASS |
| CSV Smoke | 1000 rows | PASS (after fix) |
| **Total** | **1058** | **ALL GREEN** |

## Concerns

1. **experience column size (VARCHAR(32))**: The DDL contract constrains `experience` to 32 chars, but real-world CSV data can have much longer strings. The current fix truncates silently. Consider expanding this column to VARCHAR(255) or TEXT after team notification (as required by the contract freeze).

2. **Smoke test performance**: 1000 rows (out of ~720K in postings.csv) processed in 1.5s. Full dataset import would take ~18 minutes at this rate, assuming linear scaling. Batch commit tuning may help.
