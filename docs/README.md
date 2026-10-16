# TalentMind 文档地图（docs/ 导航）

> 更新：2026-10-17。本文负责导航；产品方案、实际实现、历史记录和 Agent 规则分别维护，按下表及明确替代关系读取。历史材料仅供溯源，不自动授权执行。

## 主文档（按任务选择）

| 文件 | 内容 / 用途 |
|---|---|
| [PRODUCT_DECISIONS.md](PRODUCT_DECISIONS.md) | 当前已确认产品方案的主要依据；M2-01～60、相关 M1 输入原则与待决策；已确认不等于已实现 |
| [README.md](../README.md) | 项目总览、带日期的模块状态、启动/测试、目录边界 |
| [AGENT_START_HERE.md](../AGENT_START_HERE.md) | 少量核心阅读 + M1–M5 选读，不要求逐文件复述 |
| [AGENTS.md](../AGENTS.md) | 通用规则、安全边界、分阶段开发/审查/授权合并的唯一维护入口 |
| [CLAUDE.md](../CLAUDE.md) | Claude 补充约束，避免复制 AGENTS |
| 根目录 `A_AGENT_HANDOVER.md` | A 角色（M1 + 集成）专属路线与交接 |
| [决策跟踪](superpowers/决策跟踪.md) | 保留历史决策并追加至 D99（含阶段 A、B1、B2 两轮与 B3）；当前产品规则查主文档 |
| [DDL](../backend/app/contracts/ddl.sql)及同目录契约 | 当前源码契约，接口/存储/集成任务必读；产品更新不直接授权迁移 |
| [资产与状态](superpowers/资产与状态.md) | 按任务模块读资产/已知限制/证据日期；实现仍须核对代码与测试 |
| [未决问题清单](superpowers/未决问题清单.md) | 历史遗留/待办；新 M2 产品未决统一查 PRODUCT_DECISIONS 第 5 节 |
| `superpowers/历史时间线.md` | 历史核验/交接/采集日志归档（仅溯源） |
| [仓库冻结与资产保全报告-2026-10-14.md](仓库冻结与资产保全报告-2026-10-14.md) | V1 分支、资产清单、备份/恢复证据及离机副本缺口 |
| [V1恢复手册.md](V1恢复手册.md) | 新电脑恢复来源、步骤与覆盖风险 |
| [archive/competition-v1/README.md](archive/competition-v1/README.md) | 第二轮审查补全的设计、接口、开发/交接、演示与小型测试资料（历史归档） |
| [GitHub资产补全与备份精简报告-2026-10-14.md](GitHub资产补全与备份精简报告-2026-10-14.md) | 最新备份策略、公开新增资产、实际删除与空间核验 |

2026-10-15 入口核查：`笔记.md` 及 `output/` 仅本地存在，新检出不要求恢复这些私有目录；公开历史材料见 `archive/competition-v1/`；当前产品规则见 PRODUCT_DECISIONS，源码契约见 DDL，历史替代关系见决策跟踪。

M1 第二阶段验收记录：[PR #1](https://github.com/Serena-Lyric/TalentMind/pull/1)（临时报告合并前移除；长期结论分别写入正式文档和陷阱记录）。

M2 B3-1（Issue #10）：[七类职业家族与职责证据提示](../backend/app/job_analysis/README.md)、[实施/审查归档](superpowers/archive/2026-10-16-M2-stage-B3-1-implementation.md)（[PR #11](https://github.com/Serena-Lyric/TalentMind/pull/11)）。候选仅为待审 family 提示，未完成 canonical_job/技术方向/级别或真实 JD 准确率评测。

M2 B3-0（Issue #8）：[四维岗位基础使用说明](../backend/app/job_analysis/README.md)、[工程计划](superpowers/plans/2026-10-16-m2-b3-0-role-foundation.md)、[归档实施与复审报告](superpowers/archive/2026-10-16-M2-stage-B3-0-implementation.md)（[PR #9](https://github.com/Serena-Lyric/TalentMind/pull/9)）。仅显式离线断言/证据/版本持久化，不代表正式目录、自动分类或真实准确率完成；本轮不追加未经确认的产品决策。

M2 第一轮只读评估：[历史评估与源码证据](superpowers/archive/2026-10-15-M2-architecture-gap-assessment.md)（[PR #3](https://github.com/Serena-Lyric/TalentMind/pull/3)）；包含真实调用证据、24 项目标差距、阶段依赖、最小改造建议与待裁决项。仅用于后续设计参考，新方案尚未实施。

M2 B2 第二轮：名称/类别/候选与评测基础见 [M2 README](../backend/app/job_analysis/README.md)，[归档实施与复审报告](superpowers/archive/2026-10-16-M2-stage-B2-2-implementation.md)（[PR #7](https://github.com/Serena-Lyric/TalentMind/pull/7)）；正式准入关闭，合成程序自检不等于人工真值或真实效果。

M2 B2 第一轮：技能要求语义离线实现及限制见 [M2 README](../backend/app/job_analysis/README.md)，[审查与验证归档](superpowers/archive/2026-10-16-M2-stage-B2-1-implementation.md)（[PR #6](https://github.com/Serena-Lyric/TalentMind/pull/6)）；独立复审通过，不代表真实 JD 语料效果已验证。

M2 阶段 B1：JD 分层筛选的运行方式及输入输出契约见 [M2 README](../backend/app/job_analysis/README.md)，[历史实施与复审报告](superpowers/archive/2026-10-15-M2-stage-B1-implementation.md)（[PR #5](https://github.com/Serena-Lyric/TalentMind/pull/5)）。轻规则与合成测试不能代替真实 JD 准确率验证。

M2 第一阶段 A：独立事实基础层的运行方式、范围和接入契约见 [M2 README](../backend/app/job_analysis/README.md)，本轮验证及未决见 [历史实施报告](superpowers/archive/2026-10-15-M2-stage-A-implementation.md)（[PR #4](https://github.com/Serena-Lyric/TalentMind/pull/4) 审查记录）。旧评估的“尚未实施”描述对应原评估时点。

M2 B3-2（Issue #12）：[候选治理使用说明](../backend/app/job_analysis/README.md)、[实施计划](superpowers/plans/2026-10-16-m2-b3-2-canonical-governance.md)、[归档实施与复审报告](superpowers/archive/2026-10-16-M2-stage-B3-2-implementation.md)（[PR #13](https://github.com/Serena-Lyric/TalentMind/pull/13)）。正式目录为空，显式主张、关系与审核分开保存；不自动准入、分类或拆分职位。

M2 B3-4（Issue #16）：[工程范围与结构化材料证据](../backend/app/job_analysis/README.md)、[实施计划](superpowers/plans/2026-10-17-m2-b3-4-boundary-evidence.md)、[归档实施与独立复审报告](superpowers/archive/2026-10-17-M2-stage-B3-4-implementation.md)（[PR #17](https://github.com/Serena-Lyric/TalentMind/pull/17)）。v3 范围独立，b34 显式证据及审查可重放；标准岗位正式准入、职位拆分发布与统计均关闭。

## 分类子目录

M2 B3-5（Issue #18）：[候选目录与离线准入使用说明](../backend/app/job_analysis/README.md)、[工程计划](superpowers/plans/2026-10-17-m2-b3-5-canonical-catalog.md)、[归档实施与独立复审报告](superpowers/archive/2026-10-17-M2-stage-B3-5-implementation.md)（[PR #19](https://github.com/Serena-Lyric/TalentMind/pull/19)）。八类 19 个草案全部未确认，正式目录零条；具名审核与独立 manifest 可追溯，非合成只输出待现实授权发布提案，synthetic_only 准入模拟不发布职业、不分类 JD。

M2 B3-3（Issue #14）：[八类版本与候选兼容](../backend/app/job_analysis/README.md)、[实施计划](superpowers/plans/2026-10-16-m2-b3-3-eight-families.md)、[归档实施与独立复审报告](superpowers/archive/2026-10-16-M2-stage-B3-3-implementation.md)（[PR #15](https://github.com/Serena-Lyric/TalentMind/pull/15)）。七类历史只读，显式八类目录追加结果版本；正式标准岗位名单未发布；复审已完成，实际合并状态以 PR 为准。

| 目录 | 内容 |
|---|---|
| `superpowers/specs/` | 设计文档（按已裁决状态选择；后续决策优先，`specs/archive/` 仅溯源） |
| `superpowers/plans/` | 实施计划（按已裁决状态与任务选择，`plans/archive/` 仅溯源） |
| `superpowers/traps/` | AI 修复 bug 的陷阱记录（症状→根因→修复→教训） |
| `superpowers/archive/` | 已归档的工作报告与历史块（含 2026-09-04 全仓库文档核验与勘误报告，见 `archive/2026-09-04/`） |
| `review/` | 临时阶段报告；开发/审查期间保留，合并前沉淀长期结论并移除，修正链接 |
| `prototypes/` | UI 原型（如 M4 matching 原型） |
| `submit/`、`originalfile/`、`前端卡通图片/` | 参赛/便利文件，**仅本地，不同步 GitHub（D57）** |

## 仓库边界速查（D57/D59）

- **进 GitHub**：`backend/`、`frontend/`、`exchange/`、`scripts/`、根文档、`docs/` 正式文档（本地图所列）。
- **仅本地（不同步 GitHub）**：`input/`、`output/`、`docs/submit/`、`docs/originalfile/`、`docs/前端卡通图片/`、`笔记.md`、`data/local/`、`.superpowers/`。
- D59 仅允许已审查导出件进入 `archive/competition-v1/`，原私有目录继续隔离。
- 资产/契约/目录变更更新资产与状态；产品决策分批更新主文档与历史索引；行为流程在 AGENTS 维护；导航变化同步本地图。
