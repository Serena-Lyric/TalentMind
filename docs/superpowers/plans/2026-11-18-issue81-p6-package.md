# Issue #81 P6 打包与交付 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成可公开的代码包与只私下交付的数据包（含预构建镜像、MySQL dump、M2 数据与模型配置），并用隔离安装烟测核对 SHA256、数据行数与 SQLite 完整性。

**Architecture:** `scripts/package-deploy.sh` 在 Windows Git Bash/Linux 上执行：`git archive HEAD` 生成代码树，`docker save` 保存 backend/web/mysql/neo4j/redis 镜像，MySQL 容器内 `mysqldump` + SQLite 在线备份生成数据树，最后生成两个 `tar.gz` 与 `SHA256SUMS`。数据包只写 `data/local/deploy/`（Git 忽略）。

**Spec:** `docs/superpowers/specs/2026-11-17-issue81-ubuntu-deployment-design.md` §5.4、§5.5、§9；交接 `data/local/issue81-handoff-20261118.md` 阶段 2。

**Base:** `codex/issue81-p2-m1-linux` @ `0f200db`。分支 `codex/issue81-p6-package`；PR 基分支为 P2 分支（stacked），不合并 `master`。

## 交付物

```
data/local/deploy/
  talentmind-code-<version>.tar.gz
  talentmind-data-<version>.tar.gz
  SHA256SUMS
```

解压到同一根目录后布局：

```
<root>/app/                 # 代码包：仓库源码 + deploy/images/*.tar + package.env
<root>/data/                # 数据包：backend M2 数据、m2-p5-p6 state
<root>/app/deploy/data/mysql/talentmind.sql.gz
<root>/app/deploy/model.env
<root>/app/deploy/m2/config.json
<root>/app/deploy/m2/api-key.txt
```

## Global Constraints

- 代码包禁止包含：`data/`、`backend/.env`、`deploy/.env`、`deploy/model.env`、`deploy/m2/`、`deploy/auth/`、`deploy/tls/`、`deploy/data/`、Edge 档案/Cookie、采集频率账本、真实 JD/M2 报告。
- 数据包禁止包含：`*.lock`、`*-wal`、`*-shm`、浏览器档案、Cookie、旧共享频率账本；不迁移 Neo4j 与 Edge 档案。
- 不打印、不记录任何 Key/Cookie/口令；`manifest.json` 只含行数、大小、SHA256、完整性结果。
- 数据包只写 `data/local/deploy/`，不提交 Git、不发布 release。
- 打包为只读操作：不修改 MySQL、不删除/覆盖 M2 数据、不触发采集。
- M2 配置来源按设计 §5.4：`data/local/m2-p1-review3-20261102/deepseek-flash-20261102.json` + `data/local/m2-p1-20261029/api-key.txt`，复制为 `deploy/m2/config.json`/`api-key.txt`；文档标注“待负责人确认是否沿用”。
- 安装烟测记录“非全新云主机”的限制；最终以负责人服务器为准。
- Bash `set -euo pipefail`，单函数不超过 200 行。

## Task 0: 分支与计划

- [ ] 从 `0f200db` 切 `codex/issue81-p6-package`；提交本计划。

## Task 1: `scripts/package-deploy.sh`

**Files:**
- Create: `scripts/package-deploy.sh`
- Modify: `deploy/scripts/install.sh`（读取 `package.env`；对 `model.env`/M2 key 设 600）
- Test: 脚本 `--skip-images --skip-data` 试运行 + `bash -n`

**CLI：**
```
bash scripts/package-deploy.sh [--version V] [--output-dir DIR]
  [--skip-images] [--skip-data] [--mysql-container talentmind-mysql-1]
  [--m2-config PATH] [--m2-key PATH] [--model-env-source backend/.env]
```
- `--version` 默认 UTC `yyyyMMdd-HHmmss`；校验 `^[A-Za-z0-9._-]+$`。
- 默认输出 `data/local/deploy`；必须是绝对/相对仓库路径，不自动提交。

**步骤：**
- [ ] 检查 `docker`、`docker compose`、`git`、`python`；`git status` 脏时警告“包来自 HEAD，不含未提交修改”。
- [ ] 代码 staging：`git archive HEAD` 解到 `stage-code/app`；`mkdir -p app/deploy/images`。
- [ ] 未 `--skip-images` 时构建 `talentmind-backend:$V`、`talentmind-web:$V`（linux/amd64），确保 `mysql:8.0`、`neo4j:5-community`、`redis:7-alpine` 存在（缺失则 `docker pull`），`docker save` 到 `app/deploy/images/{backend,web,mysql,neo4j,redis}.tar`。
- [ ] 写 `stage-code/app/deploy/package.env`：`TALENTMIND_VERSION=$V`（安装脚本据此选择镜像 tag）。
- [ ] `install.sh`：在生成 `.env` 前 source `deploy/package.env`（若存在）；source/复制 `model.env` 后 `chmod 600 "$model_env"`；安装时对 `deploy/m2/api-key.txt` `chmod 600`。
- [ ] 数据 staging（未 `--skip-data`）：
  - `mysql`：容器未运行则 `docker start`，等待 `mysqladmin ping`；`docker exec <c> sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --routines --triggers --events --no-tablespaces talentmind | gzip -9'` → `stage-data/app/deploy/data/mysql/talentmind.sql.gz`；`chmod 600`。
  - 行数：同一容器查询 `jd_pool/job_definition/job_change_log/job_skill/signal/skill_dict/resume/talent_raw`，写 `stage-data/MANIFEST.json`（不写口令）。
  - M2：用内联 Python `sqlite3.Connection.backup` 备份 `data/local/m2-product/{analysis,workflow}.sqlite3` 到 `stage-data/data/backend/m2-product/`；对目标执行 `PRAGMA integrity_check`，结果写入 manifest；复制 `runs/`、`graphs/`、`native-reports/`（`tar --exclude='*.lock' --exclude='*-wal' --exclude='*-shm'`）。
  - 历史：复制 `data/local/m2-p5-p6-20261107/{sequence-head-final,dev-head-final}/state` 保持目录结构到 `stage-data/data/backend/m2-p5-p6-20261107/`；创建空 `stage-data/data/backend/m2-delivery/`。
  - 模型配置：`deploy/model.env` 只写 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`LLM_API_KEY`、`LLM_BASE_URL`（从 `--model-env-source` 读取；缺失告警）；复制 `--m2-config`/`--m2-key` 到 `app/deploy/m2/config.json`/`api-key.txt`；Key 文件 `chmod 600`。
- [ ] 归档：`tar -czf talentmind-code-$V.tar.gz -C stage-code .`、数据包同理；先写 `.partial` 再 `mv`；`Get-FileHash` 等价 `sha256sum` 写 `SHA256SUMS`。
- [ ] 打印包路径、大小、SHA256、manifest 路径；不打印任何密钥。
- [ ] `bash -n scripts/package-deploy.sh`；`bash scripts/package-deploy.sh --version test-skip --skip-images --skip-data` 生成小代码包，检查 `tar -tzf` 含 `app/deploy/scripts/install.sh`、`app/deploy/package.env`，不含 `app/backend/.env`。

## Task 2: `deploy/tests/test-package.sh`

**Files:**
- Create: `deploy/tests/test-package.sh`

**行为：**
- 参数：`<code.tar.gz> <data.tar.gz>`；缺省在 `data/local/deploy` 选最新并匹配版本；找不到则打印 `SKIP` 退出 0（CI 无私有包）。
- `sha256sum -c SHA256SUMS`。
- 代码包内容检查：必需文件存在；禁止路径（见 Global Constraints）不出现；`deploy/images/*.tar` 非空。
- 数据包内容检查：dump、两个 SQLite、`runs/graphs/native-reports`、state、`model.env`、`config.json`、`api-key.txt` 存在；禁止 `*.lock/*-wal/*-shm`、`browser_profiles`、`Cookies`、`collection/frequency.sqlite3`。
- 解压到 `mktemp -d`（`root/app` + `root/data`），校验：
  - `MANIFEST.json` 行数与 SQLite `integrity_check`；
  - `deploy/package.env` 的版本与文件名一致。
- 安装烟测（仅当 `TALENTMIND_PACKAGE_INSTALL=1`，默认执行）：
  - `TALENTMIND_ROOT=$tmp/root`、`TALENTMIND_DEPLOY_DIR=$tmp/root/app/deploy`、`TALENTMIND_DATA_DIR=$(path_win "$tmp/root/data")`、临时 env/nginx/auth/tls、`TALENTMIND_PROJECT=pkg-test-$$`、端口 18080/18443、`TALENTMIND_SKIP_ROOT_CHECK=1`、`TALENTMIND_SKIP_DOCKER_INSTALL=1`。
  - 运行 `install.sh`（加载包内镜像）；等待健康。
  - MySQL 各表行数与 manifest 完全一致；M2 SQLite `integrity_check` 为 ok。
  - `curl -u` `/api/collection/platforms`、`/api/jobs?page=1&page_size=1`、`/api/m2/delivery/inputs?limit=1&offset=0` 均 200；`/healthz` 无认证 200；`/` 带认证 200。
  - `tm_compose down -v`；清理临时目录；不触碰现有 `talentmind` 项目/容器/卷。
- 记录限制：宿主机 Docker（非全新 Ubuntu 云主机），最终以服务器部署为准。

## Task 3: 生成真实交付包（主会话执行）

- [ ] 提交 Task 1–2 后运行：`bash scripts/package-deploy.sh --version <V>`。
- [ ] 核对输出：两个 `.tar.gz`、`SHA256SUMS`；代码包不含私有数据；数据包含 MySQL/M2/state/model 配置。
- [ ] 运行 `bash deploy/tests/test-package.sh <code> <data>`（完整安装烟测）。
- [ ] 记录包大小、行数、SQLite 完整性、测试结果；不把包/哈希内容写入 Git（摘要可写文档）。

## Task 4: 文档与状态

**Files:**
- Modify: `docs/部署与运行-Ubuntu.md`（打包命令、两包边界、校验/解压/安装、模型配置待确认、烟测与限制）
- Modify: `docs/superpowers/资产与状态.md`（P6 资产、包位置、验证证据、未服务器部署）
- Modify: `backend/app/collect/README.md` 不需要；若部署文档已有 P2 说明则不重复。

- [ ] 文档明确：代码包可公开 release；数据包只私下交付；`SHA256SUMS` 校验；数据包解压到同一根目录；`TALENTMIND_VERSION` 由 `package.env` 提供。
- [ ] 说明模型配置来源与“待负责人确认”，不在公开仓库写真实 Key。
- [ ] 提交 `docs(deploy): document packaging and delivery (P6)`。

## Task 5: 验证与 PR

- [ ] `bash -n scripts/package-deploy.sh deploy/tests/test-package.sh deploy/scripts/install.sh`
- [ ] `bash deploy/tests/test-install.sh`（P1 安装回归，确认 package.env/chmod 改动不退化）
- [ ] `bash deploy/tests/test-package.sh`（真实包完整烟测）
- [ ] `git status` 确认 `data/local/deploy/`、`.env`、密钥未入 Git。
- [ ] 推送 `codex/issue81-p6-package`，`gh pr create --base codex/issue81-p2-m1-linux --head codex/issue81-p6-package`，标题 `feat(deploy): package code and private data (P6)`；正文记录包大小、测试结果、未执行项（真实服务器、真实采集、release 发布）；不合并。

## 未执行/边界

- 不发布 GitHub release；负责人部署成功后另办。
- 不迁移 Neo4j、Edge 档案、旧共享频率账本。
- 不在打包过程中启动完整产品栈（安装烟测临时启动后清理）。
