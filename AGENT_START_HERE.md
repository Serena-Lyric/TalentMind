# Agent 起始入口

先查看当前任务、Git 分支、`git status` 和相关 diff，保护用户未提交修改。核心阅读控制在以下三项；只需简要说明任务边界、冲突与下一步，**不要求逐文件复述或每次通读历史资料**。

## 核心阅读

1. [AGENTS.md](AGENTS.md)：通用规则、私有边界、测试安全和 GitHub 协作流程；Claude 另看 [CLAUDE.md](CLAUDE.md) 的少量补充。
2. [当前产品决策](docs/PRODUCT_DECISIONS.md)：阅读适用章节，分清已确认目标与待决策；文字/链接的小修仅核对影响含义的章节。
3. [资产与状态](docs/superpowers/资产与状态.md)：查任务模块的资产、已知限制和证据日期；不能把历史数字或测试结果当作实时状态。

产品决策优先于已被替代的历史产品设计；实际实现仍以对应提交的代码、配置和测试为证。需要查历史替代关系时读 [决策跟踪](docs/superpowers/决策跟踪.md)，不要求所有任务通读 D1–D60。

## 按任务选读

| 任务 | 补充入口 |
|---|---|
| 纯文档/链接/产品归档 | 目标文件及直接引用来源；[文档地图](docs/README.md)。不因文档修改运行采集、导入或业务测试。 |
| M1 数据采集与清洗 | [M1 README](backend/app/collect/README.md)、[M1 交接](exchange/m1/README.md)；涉及 A 的采集/集成工作再读 [A 交接](A_AGENT_HANDOVER.md)相关章节；有效 JD/中断边界查对应陷阱。 |
| M2 岗位分析 | 产品主文档 M2 全节、[M2 README](backend/app/job_analysis/README.md)、[M2 交接](exchange/m2/README.md)；涉及技能规范化再读 `backend/app/skills/` 的实现和词典。 |
| M3 图谱 | [M3 README](backend/app/graph/README.md)、[M3 交接](exchange/m3/README.md)；旧 builder 不能直接复现当前含行业的交接图，不覆盖已核验 graph.json。 |
| M4 简历与匹配 | [M4 README](backend/app/matching/README.md)、[M4 交接](exchange/m4/README.md)；遵守软技能推断与真实简历保护边界，原型迁移仍暂缓。 |
| M5 前端 | [前端 README](frontend/README.md)、实际 API 与关联模块文档；演示展示分与平台回退数值不当作准确率/实时统计。 |
| 契约/API/跨模块集成 | [DDL](backend/app/contracts/ddl.sql)及同目录契约、[integration README](backend/app/integration/README.md)、[A 交接](A_AGENT_HANDOVER.md)相关章节；改/删冻结字段通知全队，执行迁移另需许可。 |
| 测试/导入/恢复 | [README 测试入口](README.md#测试)、[部署与导入说明](docs/部署与导入说明.md)；恢复另读 [V1 恢复手册](docs/V1恢复手册.md)。先核对隔离环境与破坏性行为。 |
| 历史设计与协作溯源 | [决策跟踪](docs/superpowers/决策跟踪.md)、[团队设计](docs/superpowers/specs/2026-08-03-team-plan-design.md)、[目录设计](docs/superpowers/specs/2026-08-11-repository-organization-design.md)；旧计划/回发包按任务选读，不自动执行。 |

`input/`、`output/`、`笔记.md` 等仅本地使用；正式竞赛提交成品在仓库外私有目录。文档分类与最新五份阶段报告见 [文档导航](docs/README.md)，可公开的旧 V1 背景见 [竞赛 V1 归档](docs/archive/competition-v1/README.md)。私有文件保护及文档更新规则遵守 AGENTS。
