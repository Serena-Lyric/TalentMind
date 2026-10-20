# TalentMind 文档地图（docs/ 导航）

> 更新：2026-10-20。本文负责导航；产品方案、实际实现、历史记录和 Agent 规则分别维护，按下表及明确替代关系读取。历史材料仅供溯源，不自动授权执行。

## 主文档（按任务选择）

| 文件 | 内容 / 用途 |
|---|---|
| [统一产品集成验收](review/Product-integration-2026-10-21.md) | #40/#42/#37真实合并、单入口启动、控制台重构、双平台实际访问与数据库核验 |
| [M1历史控制链路](review/M1-historical-chain.md) | 历史入口与第三轮差异、原control/循环的离线子进程验收、配置/编码/统计修复；未恢复实采或日常运行 |
| [M1 Gate 1真实验收](review/M1-gate1-live.md) | 猎聘单页真实搜索因安全验证阻断；零候选/详情/写入，详情门禁修复与N/H准备；Gate 1未通过、不启动M2 |
| [M1 浏览器运行环境](review/M1-browser-runtime.md) | #40 控制台/CLI 共用独立 Edge 准备、三平台访问状态与前端字段同步、只浏览器烟测和限制；未运行写库采集 |
| [全站语义问题表与材料交付（2026-10-20）](review/TalentMind-semantics-and-evidence-2026-10-20.md) | 29项页面建议及成员责任；#38/#40双版本、零确认需求、M1因CDP未启动和最终讲稿；本轮仅改文档 |
| [2026-10-20 M1→M3 分阶段真实数据准入计划](superpowers/plans/2026-10-20-staged-m1-m3-real-validation.md) | Gate0核实目标与采前原像 → 有界M1可写现有jd_pool → M2新旧分别验证 → M3隔离小批 → 全量历史稳定性；#43取代必须新建隔离DB的旧前提，集成测试仍隔离 |
| [2026-10-20 全面实装总计划](superpowers/plans/2026-10-20-post-e2e-execution.md) | A 真实 JD 语义质量与重跑，B 共享空间星尘，C 产品语义与材料同步；三条新 Codex 对话与并行/验收边界 |
| [当前术语与能力证据](team/TALENTMIND_TERMINOLOGY_AND_CAPABILITY_2026-10-20.md) | 区分历史图、未审真实陈述、职业正式目录与竞赛可用表述；供前端与材料成员统一引用 |
| [PRODUCT_DECISIONS.md](PRODUCT_DECISIONS.md) | 当前已确认产品方案；M2-01～60、相关 M1 输入与新增 M3/M5 创新方向、Career Nebula 第一批设计；确认不等于已实现 |
| [Career Nebula 视觉设计基线](superpowers/specs/2026-10-17-career-nebula-visual-design.md) | 大型多色知识银河、《诗云》参考边界、图谱页面布局与交互/视觉规范，区分已确认与待议 |
| [Career Nebula P2.4 恒星与交互报告](review/M3-M5-P2-4.md) | 正式Vue四类恒星、默认无线与非关联可选、同条件截图、222原边、开销和回退；PR35追加候选，待产品评价 |
| [Career Nebula P2.5 视觉语义增量](superpowers/specs/2026-10-19-career-nebula-p25-visual-semantics.md) | 岗位／技能／旧场景三种主视觉、密度与银河融合、端点颜色渐变关系；已确认方向，不等于完成实现或最终美术验收 |
| [Career Nebula P2.3增量设计](superpowers/specs/2026-10-19-career-nebula-p23-design.md) | 用户本轮确认的三维正式集成、领域/历史语义边界与未来项；[实现与证据](review/M3-M5-P2-3.md)仍待独立审核/产品验收 |
| [Career Nebula P2.5 实施任务](superpowers/plans/2026-10-19-career-nebula-p25-implementation.md) | 新 Codex 对话；从 #36 文档 HEAD 叠加开发正式 /graph，主视觉三类、密度治理、连线渐变与可回退实机验收 |
| [Career Nebula Codex 第一批任务书](superpowers/plans/2026-10-17-career-nebula-first-phase.md) | P0 仅图谱页顶栏/高度，P1 独立《诗云》风格视觉样品，验收/回退与禁止事项 |
| [README.md](../README.md) | 项目总览、带日期的模块状态、启动/测试、目录边界 |
| [AGENT_START_HERE.md](../AGENT_START_HERE.md) | 少量核心阅读 + M1–M5 选读，不要求逐文件复述 |
| [AGENTS.md](../AGENTS.md) | 通用规则、安全边界、分阶段开发/审查/授权合并的唯一维护入口 |
| [CLAUDE.md](../CLAUDE.md) | Claude 补充约束，避免复制 AGENTS |
| 根目录 `A_AGENT_HANDOVER.md` | A 角色（M1 + 集成）专属路线与交接 |
| [决策跟踪](superpowers/决策跟踪.md) | 保留历史决策并追加至 D104（含 M2 与 M3/M5 新增确认）；当前产品规则查主文档 |
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
