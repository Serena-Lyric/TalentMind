# CLAUDE.md — TalentMind 项目

## AI 编码铁律

1. **不臆测** — 明确陈述假设；不确定就问。存在多种解释时列出选项而非悄悄选一个。遇到不清楚的地方停下来指出困惑点。不确定平台/API 行为时先查证而非从其他语言类推。

2. **简洁优先** — 用最少代码解决问题。不添加未要求的功能，不为一次性用途创建抽象层，不为不可能发生的场景写错误处理。如果写了 200 行而其实 50 行就够——重写。优先使用平台原生 API（如 `Get-NetTCPConnection`）而非文本解析（如 `netstat`）。

3. **精准修改** — 不要"改进"相邻的代码、注释或格式。不要重构没坏的东西。匹配现有代码风格。每一行修改都应能追溯到用户的具体请求。你留下的孤儿代码（无用 import/变量/函数）由你负责清理。

4. **闭环追踪** — 用户提出跨多轮的全局需求时，确认所有子项处理完毕再切换方向。每次回复前检查是否有用户已确认但未执行的协议。

5. **测试数据清理（D37）** — 测试写入数据库/文件的数据必须在测试后自动清理（finally/teardown，按测试夹具特征精确删除，禁止按 source 等宽泛条件 DELETE）；运行集成测试后必须查询数据库验证无测试残留且生产数据完好。详见 AGENTS.md「测试数据清理」与 `docs/superpowers/traps/2026-08-16-integration-test-wiped-jd-pool.md`。

## 参考文档

- 现行设计: `docs/superpowers/specs/2026-08-03-team-plan-design.md`（唯一当前依据）
- 仓库整理设计: `docs/superpowers/specs/2026-08-11-repository-organization-design.md`
- 实施计划: `docs/superpowers/plans/`（按日期取最新；旧版见 archive/）
- 决策与未决: `docs/superpowers/决策跟踪.md`
- 历史版本: `docs/superpowers/specs/archive/`、`docs/superpowers/plans/archive/`（仅供参考溯源，不作为当前依据）
- 有效信息汇总: `docs/superpowers/旧文档有效信息汇总.md`
- 项目需求: `docs/superpowers/项目需求.txt`
- 详细 AI 行为准则: `AGENTS.md`（按需读取）
- 历史陷阱记录: `docs/superpowers/traps/`（AI 修复 bug 后在此记录）
- **资产清单与已知限制: `docs/superpowers/资产与状态.md`（工作前必读，变更后必更新）**
- **Agent 新对话起始路线: `AGENT_START_HERE.md`（通用必读）；A 角色另读 `A_AGENT_HANDOVER.md`**

## 资产与当前状态（工作前必读）

权威清单与维护规则见 `docs/superpowers/资产与状态.md`。摘要：

- 已交付、整合中模块（D26 定稿）：原根目录交付目录 `jd-filter-package/`、`图谱模块/`、`岗位能力图谱-前端源码/`、`人岗匹配/` 已统一归档至 `input/`（gitignore 保护，阶段 7 清理待用户确认）；正式位置为 M2 → `backend/app/job_analysis/`（约束重跑 22 岗位）、M3 → `backend/app/graph/`、M5 → `frontend/`（保留 6 页、20 接口为基线）、M4 → `backend/app/matching/`（脱敏入库暂缓 D36）
- 关键裁决（2026-08-13/16，详见决策跟踪 D26–D37）：统一响应 code=0（D29）；M2 接入 skill_dict 约束（D31）；`experience` 已扩容 VARCHAR(255)、`change_type` 已扩容 VARCHAR(32)（D32/D33 已执行，通知随全队会议）；421MB seed SQL 已删除（D27）；中英文过渡（API title 中文 + name_en）已上线；测试数据自动清理与验证（D37，2026-08-16）
- 协作按 `docs/superpowers/plans/2026-08-14-module-roundtrip.md` 回发闭环执行（schema 校验 → diff 门禁 → 单测/集成 → 导入+冒烟）；旧实施计划（08-08 六份 + 08-13 整合计划）已归档 `docs/superpowers/plans/archive/`
- 未决事项见 `docs/superpowers/决策跟踪.md`（P1 测试集 / P2 里程碑 / P3 部署演示 / P5 关联）；禁止 `git add -A`（`input/人岗匹配/` 含真实简历，D36 暂缓）

## 项目决策要点（2026-08-03 汇总）

权威清单与最新状态见 `docs/superpowers/决策跟踪.md`；详细设计见 `docs/superpowers/specs/2026-08-03-team-plan-design.md`。

- 协作模式：5 人 5 机；主库与 API 在 A；**文件交接 + A 唯一集成**；技术栈自选、效果优先
- 模块：M1 采集 / M2 岗位分析 / M3 图谱 / M4 简历+匹配 / M5 前端；对接只走数据契约与 API
- 规划顺序：需求 → 模块 → 产出-消费矩阵 → 数据契约 → API（v2 API 清单作废）
- 数据契约：原始层 jd_pool/talent_raw/signal；分析层 skill_dict/job_definition/job_skill/job_change_log/resume（DDL 见 `backend/app/contracts/ddl.sql`）
- 岗位定义字段：岗位名称/核心职责/必备技能/加分技能/典型行业应用场景 + source(仅平台)/quality/collected_at；无 status
- 图谱：Neo4j；M3 只交 graph.json 由 A 导入
- 仓库双重角色：本仓库既是 A 的 M1 数据采集开发仓，也是 M1–M5 集成后的完整系统唯一主仓
- 目录边界：后端正式源码只放 `backend/app/`，前端只放 `frontend/`；交接文件和小型 Mock 放 `exchange/`；大型本地数据放 Git 忽略的 `data/local/`
- 旧代码策略：不整体删除现有 `backend`；M1 采集管道继续复用。重复目录必须在迁移、测试和集成验证通过后才清理，Git 历史负责追溯
- M4 原型迁移：`input/人岗匹配/` 当前暂缓迁移（原根目录交付目录已归档 `input/`），保持原状，待用户另行确认后处理
