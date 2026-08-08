# CLAUDE.md — TalentMind 项目

## AI 编码铁律

1. **不臆测** — 明确陈述假设；不确定就问。存在多种解释时列出选项而非悄悄选一个。遇到不清楚的地方停下来指出困惑点。不确定平台/API 行为时先查证而非从其他语言类推。

2. **简洁优先** — 用最少代码解决问题。不添加未要求的功能，不为一次性用途创建抽象层，不为不可能发生的场景写错误处理。如果写了 200 行而其实 50 行就够——重写。优先使用平台原生 API（如 `Get-NetTCPConnection`）而非文本解析（如 `netstat`）。

3. **精准修改** — 不要"改进"相邻的代码、注释或格式。不要重构没坏的东西。匹配现有代码风格。每一行修改都应能追溯到用户的具体请求。你留下的孤儿代码（无用 import/变量/函数）由你负责清理。

4. **闭环追踪** — 用户提出跨多轮的全局需求时，确认所有子项处理完毕再切换方向。每次回复前检查是否有用户已确认但未执行的协议。

## 参考文档

- 现行设计: `docs/superpowers/specs/2026-08-03-team-plan-design.md`（唯一当前依据）
- 决策与未决: `docs/superpowers/决策跟踪.md`
- 历史版本: `docs/superpowers/specs/archive/`、`docs/superpowers/plans/archive/`（仅供参考溯源，不作为当前依据）
- 有效信息汇总: `docs/superpowers/旧文档有效信息汇总.md`
- 项目需求: `docs/superpowers/项目需求.txt`
- 详细 AI 行为准则: `AGENTS.md`（按需读取）
- 历史陷阱记录: `docs/superpowers/traps/`（AI 修复 bug 后在此记录）

## 项目决策要点（2026-08-03 汇总）

权威清单与最新状态见 `docs/superpowers/决策跟踪.md`；详细设计见 `docs/superpowers/specs/2026-08-03-team-plan-design.md`。

- 协作模式：5 人 5 机；主库与 API 在 A；**文件交接 + A 唯一集成**；技术栈自选、效果优先
- 模块：M1 采集 / M2 岗位分析 / M3 图谱 / M4 简历+匹配 / M5 前端；对接只走数据契约与 API
- 规划顺序：需求 → 模块 → 产出-消费矩阵 → 数据契约 → API（v2 API 清单作废）
- 数据契约：原始层 jd_pool/talent_raw/signal；分析层 skill_dict/job_definition/job_skill/job_change_log/resume（DDL 见 `backend/app/contracts/ddl.sql`）
- 岗位定义字段：岗位名称/核心职责/必备技能/加分技能/典型行业应用场景 + source(仅平台)/quality/collected_at；无 status
- 图谱：Neo4j；M3 只交 graph.json 由 A 导入
