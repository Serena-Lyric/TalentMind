# TalentMind

> 面向数字经济的人才能力大脑与岗位演化预测系统

TalentMind 将招聘岗位的原始需求整理为可追溯的能力事实，支持岗位分析、知识关系探索、简历适配与技能成长规划。它既是竞赛形成的工程作品，也是面向实际岗位需求持续演化的产品探索；当前的数据质量和模型效果必须依实际证据判断。

## 功能概览

| 产品页面 | 功能 |
|---|---|
| 数据采集控制台 | 分平台采集、任务控制、内容质量和岗位身份状态 |
| 岗位分析工作台 | 冻结 JD 输入，进行分层分析，查看证据、版本、复核和候选结果 |
| 岗位机会雷达 | 浏览岗位机会与岗位详情 |
| 能力动态更新 | 观察岗位需求和技能变化 |
| 岗位星云图谱 | 可视化岗位、技能及行业/场景关系，支持交互探索 |
| 简历星体分析 | 简历解析、岗位匹配与能力差距分析 |
| 技能成长轨道 | 根据目标岗位和能力差距生成学习建议 |

当前功能和工程可用性不等于真实市场预测准确率或已通过人工语义验收。最新证据与限制见 [资产与状态](docs/superpowers/资产与状态.md) 和 [近期验收](docs/README.md#近期阶段验收最多五份)。

## 技术与目录

- **前端：** Vue；正式入口 `frontend/`。
- **后端：** FastAPI；采集 `backend/app/collect/`、分析 `backend/app/job_analysis/`、图谱 `backend/app/graph/`、匹配 `backend/app/matching/`。
- **数据：** MySQL、Neo4j、Redis；数据库及跨模块约束以 [DDL/契约](backend/app/contracts/ddl.sql) 和实际代码为准。
- **交接：** `exchange/` 保存模块间可审核的交付内容，不用作运行时代码源。
- **私有资产：** `data/local/`、`input/`、`output/` 等只保存在获授权的本地环境，不上传真实 JD 原文、简历、凭据和数据库文件。

流程概览：`岗位来源 → M1 原始层 → M2 岗位事实与分析 → M3 图谱 → M4 人岗匹配 → 前端交互与成长规划`。不同分析阶段的写入与正式库发布受独立授权约束，不因某一模块可运行而自动更新下游。

## 本地启动（Windows）

前提：Python、Node.js/pnpm、Docker Desktop 和 PowerShell 7；请先核对本机端口及 `.env` 配置。

```powershell
# 仓库根目录：创建后端环境（首次）
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

按本机条件编辑 `backend/.env`，不要提交实际密钥。数据库与后端可分别启动：

```powershell
# 仓库根目录执行
docker compose up -d
docker compose ps

# 在 backend/ 下执行
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18000 --reload
```

新终端在 `frontend/` 下执行：

```powershell
pnpm install --frozen-lockfile
pnpm run dev
```

本地前端默认访问 `http://127.0.0.1:18080/`，后端健康检查为 `http://127.0.0.1:18000/health`。MySQL 宿主机端口为 `23306`（容器内 `3306`）；前端 API 默认代理到 `18000`。

日常 Windows 集成启动/停止可在仓库根目录运行：

```powershell
pwsh -File scripts/start-local.ps1
pwsh -File scripts/stop-local.ps1
```

以上命令不应自动触发新的真实岗位采集。详细环境、导入和恢复要求见 [部署与导入说明](docs/部署与导入说明.md)；竞赛旧版本有独立的 [V1 恢复手册](docs/V1恢复手册.md)。

## 测试

```powershell
# 在 backend/ 下运行不接触正式数据库的测试
.\.venv\Scripts\python.exe -m pytest -m "not integration"

# 在 frontend/ 下运行
pnpm test
pnpm run build
```

**安全边界：** 任何 integration、采集、数据库迁移、导入或清理操作，必须先确认目标是明确授权的隔离环境；历史曾发生默认导入误改正式分析表的问题，不可将测试通过等同于生产写入许可。详见 [AGENTS.md](AGENTS.md) 和 [测试事故陷阱](docs/superpowers/traps/2026-10-22-full-pytest-integration-default-import.md)。

## 文档与版本

- [文档导航与维护规则](docs/README.md)：从当前规范、模块说明和近期验收进入。
- [产品决策](docs/PRODUCT_DECISIONS.md)：当前生效的产品规则，区别于实现状态。
- [资产与状态](docs/superpowers/资产与状态.md)：当前模块、限制和资产位置。
- [Agent 阅读入口](AGENT_START_HERE.md) 与 [协作规则](AGENTS.md)。
- [竞赛 V1 Release](https://github.com/Serena-Lyric/TalentMind/releases/tag/competition-v1-2026-09-05)：2026-09-05 历史基线，固定标签 `4a473c2`。

正式竞赛交付文档、视频、演示包及其他提交成品集中存放于**仓库之外的私有交付目录**；完成后可转移出开发工作区，不为它们在公开 Git 仓库建立默认存放路径。

本 README 只维护项目当前入口，不记录逐日开发流水、PR 状态和历史测试数字；阶段性记录与历史提交通过 Git 追溯。
