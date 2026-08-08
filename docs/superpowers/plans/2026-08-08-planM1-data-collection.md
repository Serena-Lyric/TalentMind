# 计划 M1 — 数据采集完善 Implementation Plan

- **日期**: 2026-08-08
- **负责人**: M1（A）
- **依赖**: 现有采集代码（RawJD/RawTalent、cleaner、dedup、pipeline、dataset/github fetcher、import_csv）；plan0（exchange 规范）
- **依据**: 2026-08-03-team-plan-design.md + 决策跟踪.md；旧计划 planA/csv-extension 已归档（D21，可参考）
- **格式说明**: 不锁定技术栈（D5）；只产文件、接口自定（D19）；三个轻量惯例见 plan0（D20）

**Goal:** jd_pool 达到 ≥100 条清洗后 JD，导出 `exchange/M1/jd.json` 供 M2 消费；交叉验证质量分有抽样核对记录；为 M2/M4 解锁数据。

## Global Constraints

- 复用已实现管道，不重写（ponytail：复用 > 重写）
- 产出字段与 ddl.sql 一致；文件字段 snake_case
- 无对外 API 时，接口自述注明"只产文件，无接口"（D19）
- signal（技术/社区热度）为 P1，不阻塞 P0

## Task 1: 数据落库 ≥100 条 JD

**Files:** 无新增（复用 `import_csv.py` / `run_pipeline`）

**Consumes:** 本地数据集（postings.csv 等，A 机本地；archive 小 CSV 已入库）
**Produces:** jd_pool 中 `status='cleaned'` 的记录 ≥100 条

- [ ] 1. 用现有 CSV/数据集管道导入并清洗（如不足 100 条，补充公开数据集或人工样例）
- [ ] 2. 验证：`SELECT COUNT(*) FROM jd_pool WHERE status='cleaned'` ≥ 100
- [ ] 3. 记录数据来源与导入批次（答辩证据）
- [ ] 4. 提交：`feat(M1): seed 100+ cleaned jds`

## Task 2: 交叉验证质量分抽样核对

**Files:** `exchange/M1/quality_check.md`

**Consumes:** jd_pool.quality / dup_group
**Produces:** 抽样核对记录（抽 10 条：质量分合理性、去重分组正确性、交叉验证机制说明）

- [ ] 1. 抽 10 条样本核对 quality 与 dup_group
- [ ] 2. 记录核对结果与异常说明（写入 quality_check.md）
- [ ] 3. 提交：`docs(M1): quality check sample`

## Task 3: 导出 jd.json

**Files:** `exchange/M1/jd.json`

**Consumes:** jd_pool
**Produces:** JSON 数组（字段：id/source/job_title/raw_text/duties/experience/quality/dup_group/crawled_at/status）

- [ ] 1. 导出 ≥100 条为 JSON（UTF-8、snake_case）
- [ ] 2. 验证：JSON 合法；字段与 ddl.sql 对齐；M2 可直接消费
- [ ] 3. 提交：`feat(M1): export jd.json`

## Task 4: 接口自述（或注明无接口）

**Files:** `exchange/M1/接口自述.md`

- [ ] 1. 按 plan0 模板填写；若只产文件，注明"无对外接口，仅交付文件"
- [ ] 2. 提交

## Task 5（P1，不阻塞）: signal 采集

**Files:** `backend/app/collect/fetchers/signal_*.py`（按源自选）

**Consumes:** 技术/社区来源
**Produces:** `signal` 表数据 + `exchange/M1/signal.json`

- [ ] 1. 实现至少 1 个技术/社区信号源（如 GitHub star 增量）
- [ ] 2. 集成验证并导出
- [ ] 3. 提交

## 验收标准

- jd_pool 清洗后 ≥100 条；jd.json 可被 M2 消费
- quality/dup_group 有抽样核对记录

## 自审说明

- 复用现有管道，无重复实现；字段与 ddl.sql 一致；P1 明确不阻塞
