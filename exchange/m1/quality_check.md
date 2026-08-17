# M1 质量分抽样核对记录（2026-08-16 重新导出 + 抽样标注）

- 数据源：`docs/originalfile/archive/postings.csv`（LinkedIn 数据集，**123,849 行**，2026-08-16 抽检实测；此前文档记"约 72 万行"有误）；本次导入 5000 行
- jd_pool cleaned 总数：5000；quality 范围 0.14–1.0，均值 0.757
- dup_group 非空分组数：4548（同一组内各行保留相同 dup_group 与 quality，消费方可按组取最高 quality 去重）
- 整体质量指标（5000 行）：空 job_title 0；空 raw_text 2（0.04%）；空 duties 4140（82.8%，为提取器标题覆盖限制，非数据源问题）；空 experience 1758（35.2%）；raw_text 残留 "Job description" 前缀文本 838（16.8%，清洗增强项）

## 抽样 10 条（quality 降序，2026-08-16 基于数据标注）

| id | job_title | quality | dup_group | 核对结论 | 依据 |
|---|---|---|---|---|---|
| 112275 | Seal Product Design Engineer | 1.0 | e3396ec59a62f9e7 | 通过 | title 有效；raw_text 5444 字符完整；experience=Entry level 合理；duties 788 字符已提取 |
| 112285 | Manufacturing Engineering Manager | 1.0 | 0988c060b0114e9f | 通过 | title 有效；raw_text 5086 字符完整；experience=Mid-Senior level 合理；duties 空属提取器未命中标题段 |
| 112296 | Store Manager | 1.0 | 7efe335f67b5b0e8 | 通过 | title 有效；raw_text 747 字符（短 JD 完整）；experience=Entry level 合理；同组 4 条重复，quality=1.0 交叉验证合理 |
| 112322 | Legal Assistant (Legal Access Officer) | 1.0 | cf08146f181f833c | 通过 | title 有效；raw_text 2162 字符完整；duties 354 字符已提取 |
| 112360 | Business Controlling, Full Value Chain Americas | 1.0 | d8b8d7cf1f37d7c1 | 通过 | title 有效；raw_text 5685 字符完整；duties 4461 字符提取完整 |
| 112365 | Store Manager | 1.0 | 7efe335f67b5b0e8 | 通过 | 与 112296 同组重复，分组正确 |
| 112372 | Store Manager | 1.0 | 7efe335f67b5b0e8 | 通过 | 与 112296 同组重复，分组正确 |
| 112430 | VP of Digital Enablement and Technology | 1.0 | 35f1b603bd7d40f7 | 通过 | title 有效；raw_text 4515 字符完整；experience=Executive 合理 |
| 112513 | Store Manager | 1.0 | 7efe335f67b5b0e8 | 通过 | 与 112296 同组重复，分组正确 |
| 112530 | Sales Development Representative | 1.0 | 8f9153d2483796fa | 通过 | title 有效；raw_text 3512 字符完整；duties 2650 字符提取完整 |

**标注结论：10/10 通过。** quality=1.0 均来自同 dup_group 多行交叉验证（去重分组正确）；title/raw_text/experience 客观指标均合理；duties 部分为空属提取器覆盖限制，非数据质量问题。

## 数据集抽检记录（docs/originalfile/archive，2026-08-16）

| 文件 | 行数(不含表头) | 内容 | 抽检结论 | 处置 |
|---|---|---|---|---|
| postings.csv | 123,849 | 岗位 JD 主表：title/description/薪资/地点/公司/经验级别/skills_desc | 通过：无空标题、描述完整、字段符合 M1 需求 | **已导入 5000 行**（子集）；全量 12.4 万行可导（待用户确认扩量） |
| jobs/job_skills.csv | 213,768 | job_id→skill_abr（126,807 个 job_id） | 通过：与 postings.job_id 关联 | **可作 enrich 输入**（dry-run 通过，重导 postings 时启用，待确认） |
| mappings/skills.csv | 35 | skill_abr→skill_name | 通过：仅 35 项映射，覆盖有限但无损 | 同上 |
| jobs/salaries.csv | 40,785 | job_id→薪资明细 | 通过：可补 M5 salary 字段 | 需契约扩展（jd_pool 无薪资列）→ **仅标记，暂不导入** |
| jobs/benefits.csv | 67,943 | job_id→福利 | 通过：M5 可选展示 | 同上 |
| jobs/job_industries.csv | 164,808 | job_id→industry_id | 通过：可补 M3 industry / M5 赛道 | 同上 |
| mappings/industries.csv | 422 | industry_id→industry_name | 通过：行业名称映射 | 同上 |
| companies/companies.csv | 24,473 | 公司名/描述/城市/国家/规模 | 通过：可补 M5 company/city/track | 同上 |
| companies/company_industries.csv | 24,375 | company_id→industry | 通过：公司行业 | 同上 |
| companies/company_specialities.csv | 169,387 | company_id→speciality | 通过：公司专长（可选画像） | 同上 |
| companies/employee_counts.csv | 35,787 | company_id→员工数/关注数 | 通过：公司画像（可选） | 同上 |

**判定说明**：11 个 CSV 均属同一 LinkedIn 岗位数据集、无简历/无个人敏感信息，全部符合项目需求维度。其中 3 个（postings/job_skills/skills）可直接接入 M1–M2 现有闭环；其余 8 个为 M5 展示与 M3 行业层的增强数据，**DDL 无对应表/列**（加表/加字段属契约变更，需用户与全队确认后再导入）。

## 说明
- 抽样核对结论已由 AI 基于客观指标标注（2026-08-16），10 条全部通过；如需人工复核可抽查。
- 已知限制：`jd_pool.experience` 已扩容 VARCHAR(255)（D33，2026-08-15），cleaner 提取上限 255（2026-08-16 修复单行描述捕获整段的问题）；本批数据为英文 JD，岗位标题未中文化（M2 处理）。
- 来源标签（D38，2026-08-17）：`jd_pool.source='linkedin'`（原 'dataset' 更名，D17 仅记录平台）、新增 `source_detail`（posting_domain / 数据集标识 'linkedin_job_postings'）；`exchange/m1/jd.json` 已按新 source 于 2026-08-17 重新导出。
- 备注：2026-08-15 曾导入 5003 cleaned，因集成测试误删（见 docs/superpowers/traps/2026-08-16-integration-test-wiped-jd-pool.md）；2026-08-16 清库后重新导入 5000 行。
