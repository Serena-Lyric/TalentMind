# 计划 M4 — 简历解析与岗位匹配 Implementation Plan

- **日期**: 2026-08-08
- **负责人**: M4（简历解析 + 匹配）
- **依赖**: M2（skill_dict.json / job_definition.json / job_skill.json）；plan0（Mock 与接口自述模板）
- **依据**: 2026-08-03-team-plan-design.md §9/§10 + 决策跟踪.md；旧 planE 已归档（D21，可参考）
- **格式说明**: 不锁定技术栈（D5）；交付可运行模块（代码 + 运行说明 + 输入输出约定）；接口自定（D19）；轻量惯例（D20）：统一响应、snake_case、Mock 先行

**Goal:** 交付可运行模块：解析用户上传简历（PDF/DOCX）→ 技能抽取（对齐 skill_dict）→ 匹配库内岗位 → 输出匹配度/已有/缺失/路径建议；简历提取与匹配准确率 ≥90%；由 A 集成进 API。

## Global Constraints

- 简历技能必须归一到 `skill_dict.canonical`（与 M2 同一词典，否则匹配算错）
- 匹配输出：target_job/score/matched/missing/path；**不输出"预计X个月"等无依据数字（DR-2）**
- 不做细粒度能力等级匹配（DR-1）
- 文件解析：PDF 文本层优先，扫描/复杂排版走多模态兜底（可选）；不支持的格式明确提示

## Task 1: 简历解析器

**Files:** `backend/app/resume/parser.py`（或自选实现）+ 测试 + 样例简历 3-5 份

**Consumes:** 用户上传文件（PDF/DOCX）
**Produces:** 结构化文本/段落（供抽取）

- [ ] 1. 写失败测试：PDF/DOCX 各 1 份解析成功
- [ ] 2. 实现解析：PDF 文本层 + DOCX；空/乱码检测 → 多模态兜底或明确报错
- [ ] 3. 验证：3-5 份样例简历解析通过
- [ ] 4. 提交：`feat(M4): resume parser`

## Task 2: 简历技能抽取

**Files:** `backend/app/resume/extractor.py` + 测试

**Consumes:** 解析结果 + skill_dict.json
**Produces:** 归一技能列表（含来源证据片段，可选 confidence）

- [ ] 1. 写失败测试：抽取结果全部在 skill_dict 内
- [ ] 2. 实现：LLM 约束抽取（复用 M2 的约束思路；候选限定 skill_dict）
- [ ] 3. 验证：抽取结果可溯源
- [ ] 4. 提交：`feat(M4): resume skill extraction`

## Task 3: 匹配算法

**Files:** `backend/app/resume/matcher.py` + 测试

**Consumes:** 简历技能 + job_definition.json/job_skill.json
**Produces:** `{target_job, score, matched, missing}`（权重 + 可选 embedding）

- [ ] 1. 写失败测试：指定岗位匹配返回合理分值与缺失技能
- [ ] 2. 实现：必备技能缺失显著降分；score 可解释（输出构成）
- [ ] 3. 验证：样例简历对库内岗位给出合理结果
- [ ] 4. 提交：`feat(M4): matcher`

## Task 4: 差距分析与路径建议

**Files:** `backend/app/resume/pathfinder.py` + 测试

**Consumes:** matched/missing + job_definition
**Produces:** 针对性建议与岗位路径（不编造时间/数字）

- [ ] 1. 实现：missing → 建议（基于加分技能/场景文案），岗位间路径（当前岗位→目标岗位技能差距）
- [ ] 2. 验证：输出可解释、无无依据数字
- [ ] 3. 提交：`feat(M4): gap analysis and path`

## Task 5: 可运行模块交付

**Files:** 模块入口（如 `backend/app/resume/main.py` 或自选服务）+ `exchange/M4/运行说明.md` + `exchange/M4/接口自述.md` + `exchange/M4/match_result.json`（示例）

**Consumes:** 简历文件 + 岗位数据文件
**Produces:** A 可直接集成的可运行模块；输入输出 JSON 约定；接口自述（/resume/analyze、/match 建议）

- [ ] 1. 提供运行入口与说明（依赖安装、启动命令、输入输出示例）
- [ ] 2. 按 plan0 模板写接口自述
- [ ] 3. 与 A 联调：模块接入 API 骨架（Mock → 真逻辑）
- [ ] 4. 提交：`feat(M4): runnable module`

## Task 6: 测试集与准确率验证

**Files:** `exchange/M4/testset_resume.json` + `exchange/M4/accuracy_report.md`

- [ ] 1. 标注 ≥30 份简历（技能标签）
- [ ] 2. 简历提取准确率 ≥90%、匹配准确率 ≥90%（与人工标注比对），记录报告
- [ ] 3. 提交：`test(M4): resume testset + accuracy`

## 验收标准

- 模块可在 A 机器运行并接入 API；输入输出符合约定
- 简历提取/匹配准确率报告达标（≥90%）

## 自审说明

- 与 DR-1/DR-2 一致；技能对齐 skill_dict；交付形态（可运行模块）符合 D3/D4；不建图谱不写前端
