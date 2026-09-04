# TalentMind 文档地图（docs/ 导航）

> 整理日期：2026-09-03（仓库文档整理）。权威与最新状态以本地图列出的“主文档”为准；历史与早期记录统一归档于 `docs/superpowers/历史时间线.md`，不作为当前依据（D21）。

## 主文档（必读入口）

| 文件 | 内容 / 用途 |
|---|---|
| 根目录 `README.md` | 项目总览、模块状态、启动/测试、目录边界 |
| 根目录 `AGENT_START_HERE.md` | 新对话必读路线（#0–#10） |
| 根目录 `AGENTS.md` | AI Agent 行为准则（细则权威） |
| 根目录 `CLAUDE.md` | AI 协作铁律与参考文档入口 |
| 根目录 `A_AGENT_HANDOVER.md` | A 角色（M1 + 集成）专属路线与交接 |
| `superpowers/决策跟踪.md` | 已决策 D1–D57 + 未决 P1–P6（裁决依据） |
| `superpowers/资产与状态.md` | 资产位置 / 整合状态 / 已知限制 / 工程经验 / 维护规则（工作前必读） |
| `superpowers/未决问题清单.md` | 全部未决/待办问题的集中跟踪清单 |
| `superpowers/历史时间线.md` | 历史核验/交接/采集日志归档（仅溯源） |

## 分类子目录

| 目录 | 内容 |
|---|---|
| `superpowers/specs/` | 设计文档（当前依据取最新；`specs/archive/` 仅溯源） |
| `superpowers/plans/` | 实施计划（按日期取最新；`plans/archive/` 仅溯源） |
| `superpowers/traps/` | AI 修复 bug 的陷阱记录（症状→根因→修复→教训） |
| `superpowers/archive/` | 已归档的工作报告与历史块（含 2026-09-04 全仓库文档核验与勘误报告，见 `archive/2026-09-04/`） |
| `prototypes/` | UI 原型（如 M4 matching 原型） |
| `submit/`、`originalfile/`、`前端卡通图片/` | 参赛/便利文件，**仅本地，不同步 GitHub（D57）** |

## 仓库边界速查（D57）

- **进 GitHub**：`backend/`、`frontend/`、`exchange/`、`scripts/`、根文档、`docs/` 正式文档（本地图所列）。
- **仅本地（不同步 GitHub）**：`input/`、`output/`、`docs/submit/`、`docs/originalfile/`、`docs/前端卡通图片/`、`笔记.md`、`data/local/`、`.superpowers/`。
- 修改资产/契约/目录后：更新 `资产与状态.md`；决策变更更新 `决策跟踪.md`；目录变更同步本地图。
