# Task 7 Report: CSV -> jd_pool End-to-End Integration Test

## Status: Complete

## Commits

```
b1872e1 test(A-csv): csv to jd_pool end-to-end integration test
```

## Changes

- **Created**: `backend/tests/test_collect_integration.py` (62 lines)
  - Single test `test_csv_to_jd_pool_via_pipeline` marked `@pytest.mark.integration`
  - Creates 3 temporary CSV files (postings, skills, job_skills) in `tmp_path`
  - Loads 2 job postings with distinct paths through the pipeline:
    - Row 1 ("AI应用工程师"): has skills (ENG/PRJM) and a fused prefix ("Job description负责...")
    - Row 2 ("后端工程师"): no skills, clean text
  - Verifies end-to-end flow: CSV load -> clean -> enrich_skills -> dedup -> jd_pool insert
  - Cleans up test data: `DELETE FROM jd_pool WHERE source='dataset'`

## Full pytest Integration Output

```
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.3.3, pluggy-1.6.0
rootdir: D:\Application\ClaudeCode\repository\TalentMind\backend
configfile: pytest.ini
plugins: anyio-4.14.2
collected 1 item

tests/test_collect_integration.py::test_csv_to_jd_pool_via_pipeline PASSED [100%]

============================== 1 passed in 0.55s ==============================
```

## Self-Review

All assertions pass:

1. **2 raws loaded** -- both CSV rows have non-empty titles, both loaded
2. **stats["saved"] == 2** -- both rows pass through cleaner -> dedup -> save_rows
3. **2 rows in jd_pool** with `source='dataset'` and `status='cleaned'` -- confirmed via COUNT query
4. **Skill enrichment works** -- "Engineering" and "Project Management" present in raw_text for job_id=1
5. **Fused prefix fixed** -- "Job description" removed from raw_text (cleaner._fix_fused_prefix correctly strips the prefix because Chinese character "负" is alpha)
6. **Original content preserved** -- "负责 RAG" present in cleaned text
7. **Test isolation** -- cleanup DELETE runs before test; test uses tmp_path for CSV files

## Concerns

- None. The test is self-contained, uses temporary files, cleans up its DB entries. All modules consumed (load_csv_posting, load_skill_map, load_job_skills, run_pipeline, get_db) are real implementations -- no mocks.
