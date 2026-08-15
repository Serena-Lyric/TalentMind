# 计划 M2 — 岗位分析 Implementation Plan

- **日期**: 2026-08-08
- **负责人**: M2（岗位分析）
- **依赖**: plan0（exchange 规范）；M1（jd.json ≥100 条）；现有 `app/llm/client.py`、`app/skills/normalizer.py`（复用）
- **依据**: 2026-08-03-team-plan-design.md + 决策跟踪.md（D8/D11–D14/D17）；旧 planC 已归档（D21，可参考任务思路）
- **格式说明**: 不锁定技术栈（D5）；LLM 经现有 client 或自选服务，只锁输出契约；接口自定（D19）；轻量惯例（D20）：snake_case、Mock 先行

**Goal:** 消费 jd.json，产出 `skill_dict.json` / `job_definition.json` / `job_skill.json` / `job_change_log.json`（含证据链与反幻觉），实现新岗位发现与演化 P0；构建 ≥100 条 JD 标注测试集。

## Global Constraints

- **岗位定义字段（D8/D17）**: job_name/core_duties/required_skills/bonus_skills/scenarios + source(仅平台)/quality/collected_at；**无 status**（D14）
- **证据链（反幻觉）**: 每条技能必须 skill_dict 归一 + evidence（JD 原文）+ confidence；无证据/低置信 → `review_queue.json`，不进正式产出
- **不编造数字（DR-2）**: evolution 无历史数据只做静态阶段分类
- 技能名强制对齐 `skill_dict.canonical`，否则 M3/M4 无法消费

## Task 1: skill_dict 种子

**Files:** `backend/app/extraction/skill_seed.py`（按自选实现）+ `exchange/M2/skill_dict.json`

**Consumes:** archive `mappings/skills.csv`、常见技能清单、jd.json 高频词
**Produces:** skill_dict（canonical/aliases/category），canonical 唯一

- [ ] 1. 构建种子：≥200 个 canonical，aliases 覆盖常见变体（python/Python3/Python语言 → python）
- [ ] 2. 导出 skill_dict.json 并验证 canonical 唯一
- [ ] 3. 提交：`feat(M2): skill_dict seed`

## Task 2: 约束抽取管道（jd → job_skill）

**Files:** `backend/app/extraction/extractor.py` + 测试 + `exchange/M2/job_skill.json`

**Consumes:** jd.json + skill_dict.json
**Produces:** 每 JD 的技能明细：`{skill_id, name, weight, confidence, evidence, is_required}`（is_required 区分必备/加分）

- [ ] 1. 写失败测试：抽取结果只含 skill_dict 内技能；含 evidence/confidence/is_required
- [ ] 2. 实现：LLM 约束抽取（候选限定 skill_dict；输出 JSON；Pydantic/等价校验；失败重试 ≤3 次）
- [ ] 3. 抽样人工核对 20 条，记录准确率（目标 ≥90%）
- [ ] 4. 导出 job_skill.json；低置信条目写入 `exchange/M2/review_queue.json`
- [ ] 5. 提交：`feat(M2): constrained extraction with evidence`

## Task 3: 岗位定义生成（job_definition）

**Files:** `backend/app/extraction/definition.py` + 测试 + `exchange/M2/job_definition.json`

**Consumes:** job_skill.json + skill_dict.json
**Produces:** 每岗位一条：五要素 + source(平台数组)/quality/collected_at/is_emerging/evolution(P0 静态分类)/first_seen/updated_at

- [ ] 1. 聚类/归并：job_skill → 岗位（岗位名归一，技能组合相似合并）
- [ ] 2. 生成定义：LLM 生成 core_duties/scenarios，required/bonus 来自 is_required；source 仅记平台，quality 用 M1 质量分
- [ ] 3. is_emerging 判定：与既有定义比对 + 技能组合新颖性 + 来源分散 → 候选新岗位（人工确认后可置 true）
- [ ] 4. evolution：P0 静态阶段分类（萌芽/增长/成熟/衰退），不输出无依据数字
- [ ] 5. 验证：每条含全部字段、无 status、snake_case；人工抽查 10 条定义质量
- [ ] 6. 提交：`feat(M2): job definitions with five elements`

## Task 4: 变更审计（job_change_log）

**Files:** `backend/app/extraction/changelog.py` + 测试 + `exchange/M2/job_change_log.json`

**Consumes:** 多批次/多来源 job_skill
**Produces:** 变更记录（change_type=added/removed/modified、skill_name、detail、source、reason、created_at）

- [ ] 1. 实现批次对比（同岗位不同 collected_at/来源的技能差异）
- [ ] 2. 验证：至少 1 个既有岗位存在变更记录；每条含 source 与 reason
- [ ] 3. 提交：`feat(M2): job change log`

## Task 5: ≥100 条 JD 标注测试集

**Files:** `exchange/M2/testset_jd.json`（标注：岗位名/必备技能/加分技能/职责，含输入输出示例）

- [ ] 1. 标注 ≥100 条 JD（与抽取结果可比对）
- [ ] 2. 计算 JD 解析 Precision/Recall/F1（目标 ≥90%），记录到 `exchange/M2/accuracy_report.md`
- [ ] 3. 提交：`test(M2): jd annotated testset + accuracy`

## Task 6: 接口自述

**Files:** `exchange/M2/接口自述.md`

- [ ] 1. 按模板填写（默认只产文件；若暴露抽取服务则写接口）
- [ ] 2. 提交

## 验收标准

- 四个 json 可被 M3/A 直接消费；字段与 ddl.sql 一致
- JD 解析准确率 ≥90%（测试集 + 报告）
- 反幻觉机制可演示（evidence 可溯源、review_queue 存在）

## 自审说明

- 字段与决策 D8/D11–D14/D17 一致；无 status；不编造数字；范围止于产出文件，不建图谱/不写前端
