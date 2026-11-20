# Issue #81 P1 部署基座 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Ubuntu 24.04 x86_64 上以 Docker Compose 启动 TalentMind 的 MySQL、FastAPI 后端与 Nginx 前端，带 Basic Auth、TLS、可信代理原文门禁、资源限额和安装/运维脚本；不含 M1 Linux 采集（P2）。

**Architecture:** 预构建 `linux/amd64` 镜像 + 生产 Compose；`web` 是唯一公网入口（80/443），`backend` 与 `mysql` 只在内部网络；Neo4j/Redis 以可选 profile 保留但默认关闭。安装脚本负责 Docker/镜像加速、密钥、TLS、首次数据导入与健康检查。

**Tech Stack:** Ubuntu 24.04、Docker Engine / Compose v2、Nginx、MySQL 8.0、Python 3.12 + FastAPI、Vue/Vite 静态构建、Bash 运维脚本。

**Spec:** `docs/superpowers/specs/2026-11-17-issue81-ubuntu-deployment-design.md`

## Global Constraints

- 目标机：Ubuntu 24.04 x86_64；实际 4 核 / 3.6GiB RAM / 1.9GiB swap / 52GiB 可用；Docker 与 Compose 当前未安装。
- Docker Hub 的 `registry-1.docker.io` 被 DNS 污染；第一次 `docker pull` 前必须写入 `registry-mirrors: ["https://mirror.ccs.tencentyun.com"]`（可用 `TALENTMIND_REGISTRY_MIRROR` 覆盖）。
- 只允许 `web` 发布 80/443；MySQL/Neo4j/Redis 一律不发布端口。
- Neo4j/Redis 默认关闭，保留 `graph-db` / `cache` profile。
- 限额：MySQL `innodb_buffer_pool_size=512M`、`performance_schema=OFF`、`mem_limit: 1g`；backend `uvicorn --workers 1`、`mem_limit: 1.5g`；Nginx `mem_limit: 128m`；Neo4j heap 512M/pagecache 256M/`mem_limit: 1g`；Redis `maxmemory 128mb`/`allkeys-lru`/`mem_limit: 256m`；宿主机 `vm.swappiness=10`。
- 真实数据、模型 Key、Cookie 不进入公开代码包/镜像；`.dockerignore` 排除 `data/`、`input/`、`output/`、`backend/.env`、`docs/originalfile/`、`docs/submit/`、`笔记.md`。
- 原文/M2 门禁：`TALENTMIND_LOCAL_RAW=1` 为前置条件；`TALENTMIND_TRUSTED_PROXY_SECRET` + `X-TalentMind-Proxy-Secret` 匹配时跳过回环/Host/Origin 检查，但仍拒绝 `Sec-Fetch-Site: cross-site`。
- 不在脚本中自动触发真实采集；不自动合并 PR；P1 分支 `codex/issue81-p1-deploy`，面向 `master`，栈式后续阶段不在此计划展开。
- 单函数不超过 200 行；Bash 脚本 `set -euo pipefail`，共享逻辑放 `deploy/scripts/common.sh`。

## Review Focus

1. **目标机已有数据**：安装脚本发现 `/opt/talentmind/data` 非空、已有 `talentmind` 容器或 MySQL 卷时，必须拒绝初始化并保持原数据不变，而不是覆盖。
2. **Docker Hub 不可达**：Docker 未安装且 `registry-1.docker.io` 被污染时，脚本要么配置加速源成功，要么在镜像齐全时用本地 `docker load` 继续；缺镜像时必须给出可诊断的失败。
3. **原文门禁被削弱**：非回环请求只有携带正确代理秘钥才可通过；错误秘钥、无秘钥、cross-site 必须仍为 403，开发回环路径保持原行为。
4. **私有数据/密钥泄漏进镜像或公开包**：构建上下文、镜像层、`deploy/images` 与代码包不得包含 `data/local`、`.env`、M2 Key、Cookie。
5. **备份/恢复破坏数据**：`restore.sh` 默认拒绝覆盖非空库；`backup.sh` 的 MySQL dump 与 M2 SQLite 必须一致可读，恢复后行数/完整性可核对。

---

### Task 0: 分支与设计/计划文档

**Files:**
- Create: `docs/superpowers/specs/2026-11-17-issue81-ubuntu-deployment-design.md`（已写，未提交）
- Create: `docs/superpowers/plans/2026-11-17-issue81-p1-deployment.md`（本文件）

**Interfaces:**
- Consumes: `origin/master`（PR #80 合并后的最新主线）。
- Produces: 分支 `codex/issue81-p1-deploy`，包含设计与 P1 计划文档的第一个提交。

- [ ] **Step 1: 切分支**

```bash
git fetch origin --prune
git switch -c codex/issue81-p1-deploy origin/master
```

- [ ] **Step 2: 提交文档**

```bash
git add docs/superpowers/specs/2026-11-17-issue81-ubuntu-deployment-design.md docs/superpowers/plans/2026-11-17-issue81-p1-deployment.md
git commit -m "docs(deploy): add issue 81 design and P1 plan"
```

- [ ] **Step 3: 确认基线**

Run: `git status --short && git log --oneline -1`
Expected: 工作区干净，HEAD 为文档提交，父提交为 `origin/master`。

---

### Task 1: 可信代理原文门禁

**Files:**
- Modify: `backend/app/routers/collection.py`（`_require_local_raw`）
- Test: `backend/tests/test_collection_trusted_proxy.py`

**Interfaces:**
- Consumes: 现有 `_require_local_raw(request: Request) -> None`、`HTTPException(403, '仅允许已启用的本地原文访问')`。
- Produces: 环境变量 `TALENTMIND_TRUSTED_PROXY_SECRET`；请求头 `X-TalentMind-Proxy-Secret`；函数签名不变。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_collection_trusted_proxy.py` 用最小 FastAPI app 包住 `_require_local_raw`，覆盖：
- `test_trusted_secret_allows_non_loopback`：`TALENTMIND_LOCAL_RAW=1`、secret `s3cret`、`TestClient(app, client=("10.0.0.5", 123))` + 正确头 → 200。
- `test_wrong_secret_is_forbidden`：错误头 → 403。
- `test_missing_secret_is_forbidden`：无头 → 403。
- `test_cross_site_is_forbidden_even_with_secret`：正确头 + `Sec-Fetch-Site: cross-site` → 403。
- `test_local_raw_env_is_required`：删掉 `TALENTMIND_LOCAL_RAW`，正确头 → 403。
- `test_dev_loopback_without_secret_still_works`：`TALENTMIND_LOCAL_RAW=1`、无 secret、`client=("127.0.0.1", 50000)`、`Host: 127.0.0.1:18000`、`Origin: http://127.0.0.1:18080` → 200。

断言只检查 HTTP 状态码与 `detail` 文案，不依赖数据库。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_collection_trusted_proxy.py -q`
Expected: FAIL（可信秘钥路径尚未实现）。

- [ ] **Step 3: 实现秘钥分支**

在 `_require_local_raw` 中按顺序判断：
1. `os.environ.get('TALENTMIND_LOCAL_RAW') != '1'` → 403。
2. `request.headers.get('sec-fetch-site') == 'cross-site'` → 403。
3. 读取 `TALENTMIND_TRUSTED_PROXY_SECRET` 与 `X-TalentMind-Proxy-Secret`；两者非空且 `hmac.compare_digest` 相等 → 直接返回。
4. 否则执行现有回环 client/Host/Origin 检查。

新增 `import hmac`；不改变错误文案。

- [ ] **Step 4: 运行测试**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_collection_trusted_proxy.py -q`
Expected: PASS（6 项）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/collection.py backend/tests/test_collection_trusted_proxy.py
git commit -m "feat(deploy): allow authenticated proxy access to raw endpoints"
```

---

### Task 2: Docker 安装与镜像加速脚本

**Files:**
- Create: `deploy/docker/daemon.json.example`
- Create: `deploy/scripts/install-docker.sh`
- Test: `deploy/tests/test-install-docker.sh`

**Interfaces:**
- Consumes: 无；可在 Ubuntu 24.04 由 root/sudo 执行。
- Produces: `ensure_docker()`（安装/启动 Docker 并返回 0）、`write_daemon_config(config_dir)`（合并 registry mirror 与日志轮转）、`verify_docker_pull(image)`（返回 0/非 0）。脚本可被 `source`，主流程由 `if [[ "${BASH_SOURCE[0]}" == "$0" ]]` 保护。

- [ ] **Step 1: 写失败测试**

`deploy/tests/test-install-docker.sh` 用 `mktemp -d` 作为 `TALENTMIND_DOCKER_CONFIG_DIR`，source 脚本后断言：
- 空目录写入后文件包含 `"registry-mirrors": ["https://mirror.ccs.tencentyun.com"]`、`"max-size": "20m"`。
- 已存在 `{"log-driver":"json-file","live-restore":true}` 时合并后保留 `live-restore` 且新增 mirror。
- `TALENTMIND_REGISTRY_MIRROR` 覆盖默认值。
- `configure_swappiness` 写入 `${TALENTMIND_SYSCTL_DIR}/99-talentmind.conf` 且包含 `vm.swappiness=10`；用临时目录覆盖系统路径。
- `mkdir -p "$tmp/bin"; printf '#!/bin/sh\nexit 0\n' > "$tmp/bin/docker"; chmod +x ...; PATH="$tmp/bin:$PATH"` 时 `docker_available` 为真。
- `bash -n deploy/scripts/install-docker.sh` 通过。

- [ ] **Step 2: 运行确认失败**

Run: `bash deploy/tests/test-install-docker.sh`
Expected: FAIL（脚本不存在）。

- [ ] **Step 3: 实现脚本**

`install-docker.sh` 职责：
- `docker_available`：`command -v docker` 且 `docker compose version` 或 `docker-compose version`。
- `install_docker_packages`：优先腾讯云 Docker CE apt 源，失败回退 `apt-get install -y docker.io docker-compose-v2`；`systemctl enable --now docker`。
- `write_daemon_config`：用 `python3 -c` 读取/合并 JSON，写入 `${TALENTMIND_DOCKER_CONFIG_DIR:-/etc/docker}/daemon.json`，保留已有键；包含 `registry-mirrors`、`log-driver=json-file`、`log-opts.max-size=20m`、`log-opts.max-file=3`。
- `configure_swappiness`：写入 `${TALENTMIND_SYSCTL_DIR:-/etc/sysctl.d}/99-talentmind.conf`（`vm.swappiness=10`），`sysctl --system` 或 `sysctl -p` 应用。
- `verify_docker_pull`：`docker pull mysql:8.0`，失败只返回非 0，由调用方决定。
- 主流程：`ensure_docker` → `write_daemon_config` → `systemctl restart docker` → `verify_docker_pull mysql:8.0`；pull 失败打印 DNS/镜像源诊断并 exit 1（单独执行时）。

`daemon.json.example` 与脚本写入内容一致。

- [ ] **Step 4: 运行测试**

Run: `bash deploy/tests/test-install-docker.sh && bash -n deploy/scripts/install-docker.sh`
Expected: PASS；apt/pull 的真实安装不在本机测试，只在服务器执行。

- [ ] **Step 5: 提交**

```bash
git add deploy/docker/daemon.json.example deploy/scripts/install-docker.sh deploy/tests/test-install-docker.sh
git commit -m "feat(deploy): install Docker with Tencent registry mirror"
```

---

### Task 3: 后端生产镜像与构建上下文

**Files:**
- Create: `.dockerignore`
- Create: `deploy/backend/Dockerfile`
- Test: `deploy/tests/test-backend-image.sh`

**Interfaces:**
- Consumes: `backend/requirements.txt`、`backend/app/**`、公开的 `exchange/m3/**`（仅 web 构建需要）。
- Produces: 镜像 `talentmind-backend:<version>`，容器内 `/app/backend/app`、`/app/data/local`、`/app/deploy/m2`，`PYTHONPATH=/app/backend`，用户 `talentmind`（UID 1000），监听 `0.0.0.0:18000`。

- [ ] **Step 1: 写验证脚本**

`deploy/tests/test-backend-image.sh`：
- `docker build --platform linux/amd64 -f deploy/backend/Dockerfile -t talentmind-backend:test .` 成功。
- `docker run --rm -e MYSQL_URL=... -e NEO4J_URI=... -e NEO4J_USER=... -e NEO4J_PASSWORD=... -e REDIS_URL=... -e OPENAI_API_KEY=x -e OPENAI_BASE_URL=https://example.com/v1 talentmind-backend:test python -c "import app.main"` 退出 0。
- `docker run --rm talentmind-backend:test id -u` 输出 `1000`。
- `docker run --rm talentmind-backend:test test -d /app/backend/app && test -d /app/data/local` 退出 0。
- `docker run --rm talentmind-backend:test test ! -e /app/backend/.env && test ! -e /app/data/local/m2-product` 退出 0（私有数据未进镜像）。

- [ ] **Step 2: 运行确认失败**

Run: `bash deploy/tests/test-backend-image.sh`
Expected: FAIL（Dockerfile 不存在）。

- [ ] **Step 3: 实现**

`.dockerignore` 至少包含：`data/`、`input/`、`output/`、`backend/.env`、`backend/.venv/`、`docs/originalfile/`、`docs/submit/`、`docs/前端卡通图片/`、`笔记.md`、`frontend/node_modules/`、`frontend/dist/`、`**/__pycache__/`、`**/*.pyc`、`.git/`、`.superpowers/`、`deploy/images/`、`deploy/auth/`、`deploy/tls/`、`deploy/.env`、`deploy/model.env`。

`deploy/backend/Dockerfile`：`FROM ubuntu:24.04`；apt 安装 `python3.12 python3.12-venv python3.12-dev build-essential ca-certificates tzdata curl`；复制 `backend/requirements.txt` 与 `backend/app` 到 `/app/backend/`，创建 `/opt/venv`，以 `/app/backend` 为工作目录执行 `/opt/venv/bin/pip install -r requirements.txt`（确保 `-r app/graph/requirements-offline.txt` 可解析）；`ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/app/backend PYTHONUTF8=1 LANG=C.UTF-8 TZ=Asia/Shanghai`；`RUN useradd -u 1000 -m talentmind && mkdir -p /app/data/local /app/deploy/m2 && chown -R talentmind:talentmind /app`；`USER talentmind`；`WORKDIR /app`；`EXPOSE 18000`；`CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","18000","--workers","1"]`；`HEALTHCHECK` 用 `python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18000/health')"`。

- [ ] **Step 4: 运行测试**

Run: `bash deploy/tests/test-backend-image.sh`
Expected: PASS；镜像不含 `backend/.env`（脚本可加 `docker run --rm ... test ! -e /app/backend/.env`）。

- [ ] **Step 5: 提交**

```bash
git add .dockerignore deploy/backend/Dockerfile deploy/tests/test-backend-image.sh
git commit -m "feat(deploy): build minimal backend image"
```

---

### Task 4: 前端静态镜像

**Files:**
- Create: `deploy/web/Dockerfile`
- Create: `deploy/web/nginx-image.conf`（仅镜像内默认配置，供 `nginx -t`）
- Test: `deploy/tests/test-web-image.sh`

**Interfaces:**
- Consumes: `frontend/`、`exchange/m3/graph.json`、`exchange/m3/overlays/p2-1-layout.json`。
- Produces: 镜像 `talentmind-web:<version>`，`/usr/share/nginx/html/index.html`，`/graph-artifacts/historical.json`，默认 `nginx -g 'daemon off;'`。

- [ ] **Step 1: 写验证脚本**

`deploy/tests/test-web-image.sh`：
- 构建 `talentmind-web:test`。
- `docker run --rm --add-host backend:127.0.0.1 talentmind-web:test nginx -t` 退出 0。
- `docker run --rm talentmind-web:test test -f /usr/share/nginx/html/index.html` 退出 0。
- `docker run --rm talentmind-web:test test -f /usr/share/nginx/html/graph-artifacts/historical.json` 退出 0。

- [ ] **Step 2: 运行确认失败**

Run: `bash deploy/tests/test-web-image.sh`
Expected: FAIL（Dockerfile 不存在）。

- [ ] **Step 3: 实现**

多阶段：
- Stage 1 `node:24.15.0-bookworm-slim`（若镜像不存在，用 `node:24-slim`）：`corepack enable`、`corepack prepare pnpm@11.5.1 --activate`；复制 `frontend/package.json`、`frontend/pnpm-lock.yaml`、`frontend/pnpm-workspace.yaml`，`pnpm install --frozen-lockfile`；复制 `frontend/` 与 `exchange/`；`pnpm run build`。
- Stage 2 `nginx:1.27-alpine`：复制 `dist/` 到 `/usr/share/nginx/html`；复制 `deploy/web/nginx-image.conf` 到 `/etc/nginx/conf.d/default.conf`。
- `nginx-image.conf` 只服务静态文件，`location /api/` 返回 502 占位（生产由挂载配置覆盖），避免 `nginx -t` 因上游 DNS 失败。

- [ ] **Step 4: 运行测试**

Run: `bash deploy/tests/test-web-image.sh`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add deploy/web/Dockerfile deploy/web/nginx-image.conf deploy/tests/test-web-image.sh
git commit -m "feat(deploy): build static web image"
```

---

### Task 5: 生产 Compose、MySQL 限额与内部网络

**Files:**
- Create: `deploy/compose.yml`
- Create: `deploy/mysql/my.cnf`
- Create: `deploy/.env.example`
- Create: `deploy/.gitignore`
- Test: `deploy/tests/test-compose-stack.sh`

**Interfaces:**
- Consumes: 镜像 `talentmind-backend:test`、`talentmind-web:test`；`MYSQL_ROOT_PASSWORD`、`MYSQL_PASSWORD`、`TALENTMIND_TRUSTED_PROXY_SECRET`。
- Produces: 服务 `mysql`、`backend`、`web`；网络 `edge`（web+backend）、`data`（mysql+backend）；可选 `neo4j`（profile `graph-db`）、`redis`（profile `cache`）；数据路径 `${TALENTMIND_DATA_DIR}`。

- [ ] **Step 1: 写验证脚本**

`deploy/tests/test-compose-stack.sh`：
- 创建临时 `.env`（随机口令、占位 Neo4j/Redis/OpenAI、`TALENTMIND_VERSION=test`、`TALENTMIND_DATA_DIR=$tmp/data`、`TALENTMIND_HTTP_PORT=18080`、`TALENTMIND_HTTPS_PORT=18443`）。
- `docker compose -f deploy/compose.yml --env-file "$env" config` 成功。
- `docker compose ... up -d mysql backend`；等待 `docker compose ... exec -T backend python -c "urllib.request.urlopen('http://127.0.0.1:18000/health')"` 成功。
- `docker compose ... ps --format json` 中 mysql/backend 的 `Publishers` 为空；`docker compose ... port mysql 3306` 无输出。
- `docker compose ... config` 输出包含 `innodb_buffer_pool_size=512M`、`performance_schema=OFF`、`--workers 1`、`mem_limit` 值。
- 清理：`down -v`（仅临时目录）。

- [ ] **Step 2: 运行确认失败**

Run: `bash deploy/tests/test-compose-stack.sh`
Expected: FAIL（compose 文件不存在）。

- [ ] **Step 3: 实现**

`compose.yml`：
- `name: talentmind`；服务按上表；`env_file: .env`；`restart: unless-stopped`；日志 `max-size: 20m/max-file: 3`。
- `mysql`：`mysql:8.0`，`MYSQL_DATABASE=talentmind`、`MYSQL_USER=talentmind`，挂载 `${TALENTMIND_DATA_DIR}/mysql:/var/lib/mysql` 与 `./mysql/my.cnf:/etc/mysql/conf.d/talentmind.cnf:ro`，healthcheck `mysqladmin ping`，`mem_limit: 1g`，仅 `data` 网络。
- `backend`：`image: talentmind-backend:${TALENTMIND_VERSION}`，挂载 `${TALENTMIND_DATA_DIR}/backend:/app/data/local` 与 `./m2:/app/deploy/m2:ro`；环境注入 `MYSQL_URL=mysql+pymysql://talentmind:${MYSQL_PASSWORD}@mysql:3306/talentmind`、`NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD`、`REDIS_URL`、`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`TALENTMIND_LOCAL_RAW=1`、`TALENTMIND_TRUSTED_PROXY_SECRET`、`TALENTMIND_M2_CONFIG=/app/deploy/m2/config.json`、`TALENTMIND_M2_KEY_FILE=/app/deploy/m2/api-key.txt`；`depends_on: mysql: condition: service_healthy`；healthcheck；`mem_limit: 1500m`；网络 `data`、`edge`。
- `web`：`image: talentmind-web:${TALENTMIND_VERSION}`；`ports: ["${TALENTMIND_HTTP_PORT:-80}:80", "${TALENTMIND_HTTPS_PORT:-443}:443"]`；挂载 `./nginx:/etc/nginx/conf.d:ro`、`./auth:/etc/nginx/auth:ro`、`./tls:/etc/nginx/tls:ro`；网络 `edge`；`mem_limit: 128m`。
- `neo4j`：`profiles: ["graph-db"]`，`neo4j:5-community`，`NEO4J_AUTH`，heap/pagecache env，`mem_limit: 1g`，仅 `data` 网络。
- `redis`：`profiles: ["cache"]`，`redis:7-alpine`，`command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru`，`mem_limit: 256m`，仅 `data` 网络。
- `my.cnf`：`[mysqld]` 下 `innodb_buffer_pool_size=512M`、`performance_schema=OFF`、`character-set-server=utf8mb4`、`collation-server=utf8mb4_0900_ai_ci`。
- `.env.example`：列出上述变量，秘密留空；`TALENTMIND_TLS_MODE=selfsigned`、`TALENTMIND_SERVER_NAME=_`、`TALENTMIND_REGISTRY_MIRROR=https://mirror.ccs.tencentyun.com`。
- `deploy/.gitignore`：`.env`、`model.env`、`auth/`、`tls/`、`nginx/default.conf`、`images/`、`data/`、`backups/`、`tests/tmp/`。

- [ ] **Step 4: 运行测试**

Run: `bash deploy/tests/test-compose-stack.sh`
Expected: PASS；临时容器/卷清理。

- [ ] **Step 5: 提交**

```bash
git add deploy/compose.yml deploy/mysql/my.cnf deploy/.env.example deploy/.gitignore deploy/tests/test-compose-stack.sh
git commit -m "feat(deploy): add production compose with resource limits"
```

---

### Task 6: Basic Auth、反向代理与代理秘钥

**Files:**
- Create: `deploy/scripts/auth.sh`
- Create: `deploy/scripts/render-nginx.sh`
- Create: `deploy/web/nginx-http.conf.template`
- Test: `deploy/tests/test-nginx-auth.sh`

**Interfaces:**
- Consumes: `TALENTMIND_ADMIN_USER`、`TALENTMIND_ADMIN_PASSWORD`、`TALENTMIND_TRUSTED_PROXY_SECRET`、`TALENTMIND_SERVER_NAME`、`TALENTMIND_HTTP_PORT`。
- Produces: `deploy/auth/htpasswd`、`deploy/auth/.credentials`、`deploy/nginx/default.conf`；Nginx 在 `/api/` 上覆盖 `X-TalentMind-Proxy-Secret`。

- [ ] **Step 1: 写验证脚本**

`deploy/tests/test-nginx-auth.sh`：
- 生成临时 auth/nginx 配置，启动 `mysql backend web`（复用 Task 5 临时栈，`HTTP_PORT=18080`）。
- `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${HTTP_PORT}/` → `401`。
- `curl -s -u "$user:$pass" -o /dev/null -w '%{http_code}' http://127.0.0.1:${HTTP_PORT}/` → `200`。
- `curl -s -u "$user:$pass" http://127.0.0.1:${HTTP_PORT}/api/collection/platforms` → `200` 且 JSON `code=0`。
- 请求带错误 `X-TalentMind-Proxy-Secret: wrong`，经 Nginx 覆盖后访问 `/api/collection/raw/1`，不应返回 403（数据库无行时为 404/503，均可）。
- `curl -s -u "$user:$pass" -H 'Sec-Fetch-Site: cross-site' /api/collection/raw/1` → `403`。
- `deploy/auth/.credentials` 权限为 600；`htpasswd` 为 `640 root:101` 或 `644`（Nginx worker 可读）。

- [ ] **Step 2: 运行确认失败**

Run: `bash deploy/tests/test-nginx-auth.sh`
Expected: FAIL（auth/render 脚本不存在）。

- [ ] **Step 3: 实现**

- `auth.sh`：`generate_basic_auth(user, password)` 用 `openssl passwd -apr1` 写 `htpasswd`；未给密码时用 `openssl rand -base64 24` 生成；写 `.credentials`（600）；`htpasswd` 设 `640` 并 `chgrp 101`（失败则 `644`）。
- `render-nginx.sh`：读取 `nginx-http.conf.template`，替换 `__SERVER_NAME__`、`__PROXY_SECRET__`，写 `deploy/nginx/default.conf`（600）。
- 模板：`server { listen 80; server_name __SERVER_NAME__; auth_basic "TalentMind"; auth_basic_user_file /etc/nginx/auth/htpasswd; client_max_body_size 20m; location = /healthz { auth_basic off; return 200 "ok\n"; } location / { root /usr/share/nginx/html; try_files $uri $uri/ /index.html; } location /api/ { proxy_pass http://backend:18000/api/; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header X-TalentMind-Proxy-Secret "__PROXY_SECRET__"; proxy_read_timeout 120s; proxy_send_timeout 120s; } }`

- [ ] **Step 4: 运行测试**

Run: `bash deploy/tests/test-nginx-auth.sh`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add deploy/scripts/auth.sh deploy/scripts/render-nginx.sh deploy/web/nginx-http.conf.template deploy/tests/test-nginx-auth.sh
git commit -m "feat(deploy): add basic auth and trusted proxy reverse proxy"
```

---

### Task 7: TLS（自签/文件/关闭）与 HTTP 跳转

**Files:**
- Create: `deploy/scripts/tls.sh`
- Create: `deploy/web/nginx-https.conf.template`
- Modify: `deploy/scripts/render-nginx.sh`（按 `TALENTMIND_TLS_MODE` 选择模板）
- Test: `deploy/tests/test-nginx-tls.sh`

**Interfaces:**
- Consumes: `TALENTMIND_TLS_MODE=selfsigned|files|off`、`TALENTMIND_HTTPS_PORT`、`TALENTMIND_SERVER_NAME`。
- Produces: `deploy/tls/fullchain.pem`、`deploy/tls/privkey.pem`；HTTPS 配置；`off` 时仅 HTTP。

- [ ] **Step 1: 写验证脚本**

`deploy/tests/test-nginx-tls.sh`：
- `TLS_MODE=selfsigned` 生成证书；`openssl x509 -noout -text` 含 SAN IP 或 DNS。
- 启动栈（`HTTP_PORT=18080`、`HTTPS_PORT=18443`）；`curl -k -s -o /dev/null -w '%{http_code}' https://127.0.0.1:${HTTPS_PORT}/` → `401`；带 `-u` → `200`。
- `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${HTTP_PORT}/` → `301` 或 `308`。
- `TLS_MODE=off` 时不生成 TLS 配置，HTTP 200（带 auth）。
- `TLS_MODE=files` 且证书缺失时 `render-nginx.sh` 退出非 0。
- Let's Encrypt 不在 P1 范围：有域名时先使用 `TLS_MODE=files` 挂载证书；文档注明后续可加 certbot。

- [ ] **Step 2: 运行确认失败**

Run: `bash deploy/tests/test-nginx-tls.sh`
Expected: FAIL。

- [ ] **Step 3: 实现**

- `tls.sh`：`generate_self_signed()` 用 `openssl req -x509 -newkey rsa:2048 -nodes -days 825`，SAN 包含 `IP:<server>`（默认为 `hostname -I` 第一个地址）或 `DNS:<TALENTMIND_SERVER_NAME>`。
- `nginx-https.conf.template`：80 server 返回 301 到 `https://$host$request_uri`；443 server 复用 Task 6 的 auth/location 指令并加 `ssl_certificate /etc/nginx/tls/fullchain.pem; ssl_certificate_key /etc/nginx/tls/privkey.pem;`。
- `render-nginx.sh`：`off` 用 HTTP 模板；`selfsigned` 生成证书后使用 HTTPS 模板；`files` 校验证书存在后使用 HTTPS 模板。

- [ ] **Step 4: 运行测试**

Run: `bash deploy/tests/test-nginx-tls.sh`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add deploy/scripts/tls.sh deploy/scripts/render-nginx.sh deploy/web/nginx-https.conf.template deploy/tests/test-nginx-tls.sh
git commit -m "feat(deploy): add TLS modes for nginx"
```

---

### Task 8: 启停、状态与日志脚本

**Files:**
- Create: `deploy/scripts/common.sh`
- Create: `deploy/scripts/start.sh`
- Create: `deploy/scripts/stop.sh`
- Create: `deploy/scripts/status.sh`
- Create: `deploy/scripts/logs.sh`
- Test: `deploy/tests/test-lifecycle.sh`

**Interfaces:**
- Consumes: `TALENTMIND_ROOT`、`TALENTMIND_DATA_DIR`、`deploy/.env`。
- Produces: `tm_compose()`、`tm_wait_healthy()`、`tm_require_root()`；`start.sh`/`stop.sh` 幂等；`status.sh` 健康时 exit 0、未健康 exit 1；`logs.sh [--no-follow]`。

- [ ] **Step 1: 写验证脚本**

在临时 root 启动栈后：
- `start.sh` 重复执行两次均 exit 0。
- `status.sh` exit 0 且输出包含 `mysql`、`backend`、`web` 与 `healthy`。
- `stop.sh` 后 `status.sh` exit 1；数据目录仍在。
- `start.sh` 后健康恢复。
- `docker compose restart backend mysql`（或 `tm_compose restart`）后 `status.sh` exit 0，且 `job_definition` 行数不变。
- `logs.sh --no-follow` exit 0 且输出非空。

- [ ] **Step 2: 运行确认失败**

Run: `bash deploy/tests/test-lifecycle.sh`
Expected: FAIL。

- [ ] **Step 3: 实现**

`common.sh` 提供路径/日志/命令包装；`tm_compose` 优先 `docker compose`，回退 `docker-compose`；`tm_wait_healthy` 轮询 backend `/health` 与 web `/healthz`（最多 90 秒）。
`start.sh`：`tm_compose up -d` → `tm_wait_healthy`。
`stop.sh`：`tm_compose stop`（不 `down`，保留网络/卷）。
`status.sh`：`tm_compose ps` + `docker inspect` 健康 + 端口 + `df -h`；不打印密钥。
`logs.sh`：`tm_compose logs --tail=200 "$@"`，默认 follow。

- [ ] **Step 4: 运行测试**

Run: `bash deploy/tests/test-lifecycle.sh`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add deploy/scripts/common.sh deploy/scripts/start.sh deploy/scripts/stop.sh deploy/scripts/status.sh deploy/scripts/logs.sh deploy/tests/test-lifecycle.sh
git commit -m "feat(deploy): add lifecycle scripts"
```

---

### Task 9: 安装脚本、密钥与首次数据导入

**Files:**
- Create: `deploy/scripts/install.sh`
- Create: `deploy/scripts/import-data.sh`
- Create: `deploy/tests/fixtures/mini.sql`
- Create: `deploy/tests/test-install.sh`
- Modify: `deploy/.env.example`（如需补充变量）
- Test: `deploy/tests/test-install.sh`

**Interfaces:**
- Consumes: `deploy/images/*.tar`、`deploy/model.env`（可选）、`deploy/data/mysql/*.sql.gz`（可选，`TALENTMIND_MYSQL_DUMP` 可覆盖）、`backend/app/contracts/ddl.sql`（无 dump 时的 schema）。
- Produces: `deploy/.env`、`deploy/auth/*`、`deploy/tls/*`、`deploy/nginx/default.conf`；首次导入后 MySQL 非空；重复安装检测已有数据并拒绝。

- [ ] **Step 1: 写验证脚本**

`deploy/tests/test-install.sh`：
- 临时 root + `TALENTMIND_SKIP_DOCKER_INSTALL=1`；把 Task 3/4 镜像 tag 为 `talentmind-backend:test`/`talentmind-web:test`；`TALENTMIND_VERSION=test`；`TALENTMIND_HTTP_PORT=18080`、`TALENTMIND_HTTPS_PORT=18443`。
- 执行完整 `install.sh`；生成 `.env`，包含随机 `MYSQL_ROOT_PASSWORD`、`MYSQL_PASSWORD`、`TALENTMIND_TRUSTED_PROXY_SECRET`，权限 600；auth/htpasswd、tls 文件存在。
- 带 `mini.sql.gz` 启动：`job_definition` 行数等于 1；`/api/collection/platforms` 200。
- 在已有 `data/` 标记文件后再次 `install.sh`：exit 非 0，标记文件仍在，容器未重建。
- 不提供 dump 时：导入 `ddl.sql`，表存在但无业务数据；日志明确“schema only”。
- `import-data.sh` 对非空库再次导入：exit 非 0，行数不变。

- [ ] **Step 2: 运行确认失败**

Run: `bash deploy/tests/test-install.sh`
Expected: FAIL。

- [ ] **Step 3: 实现**

`install.sh` 顺序：
1. `tm_require_root`；检查 `TALENTMIND_ROOT` 与 `TALENTMIND_DATA_DIR`；`is_initialized` 为真 → exit 1。
2. `TALENTMIND_SKIP_DOCKER_INSTALL=1` 时跳过 Task 2，否则 `source install-docker.sh` 并 `ensure_docker`。
3. 生成 `.env`：密钥用 `openssl rand -hex 24`；从 `deploy/model.env` 读取模型 Key（`set -a; source`）；写 600。
4. `generate_basic_auth`、`generate_self_signed`/`TLS_MODE=files`、`render_nginx`。
5. `docker load` `deploy/images/*.tar`（若存在）。
6. `tm_compose up -d mysql`；等待 healthy；`import-data.sh` 导入 dump 或 `ddl.sql`；`tm_compose up -d backend web`；`tm_wait_healthy`。
7. 打印 URL、用户名、一次性密码（来自 `.credentials`），不打印模型 Key。

`import-data.sh`：`mysql_is_empty()` 用 `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='talentmind'`；非空且 `--force` 未给 → exit 1；`gunzip -c dump | tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot talentmind`；导入后核对 `jd_pool`/`job_definition` 行数（dump 内有表时）。口令用 `MYSQL_PWD` 传递，不出现在命令行/日志。

`mini.sql`：最小 `job_definition` 表（含 `id`、`job_name`）与一行 `test-job`；只用于测试。

权限：`data/mysql` `chown 999:999`（官方镜像 mysql UID）、`data/backend` 与 `deploy/m2` `chown 1000:1000`；TLS 私钥 600；`deploy/.env` 600。

- [ ] **Step 4: 运行测试**

Run: `bash deploy/tests/test-install.sh`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add deploy/scripts/install.sh deploy/scripts/import-data.sh deploy/tests/fixtures/mini.sql deploy/tests/test-install.sh deploy/.env.example
git commit -m "feat(deploy): add installer with first-run data import"
```

---

### Task 10: 备份、恢复与升级

**Files:**
- Create: `deploy/scripts/backup.sh`
- Create: `deploy/scripts/restore.sh`
- Create: `deploy/scripts/upgrade.sh`
- Test: `deploy/tests/test-backup-restore.sh`

**Interfaces:**
- Consumes: 运行中的栈、`deploy/.env`、`deploy/auth`、`deploy/tls`、`deploy/m2`。
- Produces: `backups/<UTC timestamp>/` 包含 `mysql.sql.gz`、`backend.tar.gz`、`deploy.tar.gz`、`SHA256SUMS`；`restore.sh --yes <dir>` 恢复；`upgrade.sh` 先备份再加载新镜像。

- [ ] **Step 1: 写验证脚本**

- 启动临时栈并确认 `job_definition` 有 1 行。
- `backup.sh` 生成目录与四个文件；`sha256sum -c SHA256SUMS` 通过。
- `stop.sh`；清空临时 MySQL 数据（仅临时卷）后 `restore.sh --yes <backup>`；行数恢复为 1。
- `restore.sh <backup>` 不带 `--yes` 且库非空 → exit 非 0。
- `upgrade.sh` 用同一组镜像执行：先产生新备份目录，再 `compose up -d`，健康。

- [ ] **Step 2: 运行确认失败**

Run: `bash deploy/tests/test-backup-restore.sh`
Expected: FAIL。

- [ ] **Step 3: 实现**

`backup.sh`：先 `tm_compose stop backend` 取得 M2 SQLite 一致快照（记录原状态，备份后 `start.sh`）；`mysqldump --single-transaction --routines --triggers --events --no-tablespaces`，口令用 `MYSQL_PWD` 环境变量传给 `tm_compose exec -T -e MYSQL_PWD=... mysql mysqldump -uroot talentmind | gzip`；`tar -czf backend.tar.gz -C "$TALENTMIND_DATA_DIR" backend`；`tar -czf deploy.tar.gz -C "$DEPLOY_DIR" .env auth tls m2`（缺少目录时跳过）；备份目录 700；`sha256sum`。
`restore.sh`：要求 `--yes`；`stop.sh`；恢复 MySQL（`gunzip -c | tm_compose exec -T -e MYSQL_PWD=... mysql mysql -uroot talentmind`）；解压 backend；恢复 deploy 密钥（提示会覆盖）；`start.sh`。
`upgrade.sh`：`backup.sh` → `docker load deploy/images/*.tar` → `tm_compose up -d` → `tm_wait_healthy`。

- [ ] **Step 4: 运行测试**

Run: `bash deploy/tests/test-backup-restore.sh`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add deploy/scripts/backup.sh deploy/scripts/restore.sh deploy/scripts/upgrade.sh deploy/tests/test-backup-restore.sh
git commit -m "feat(deploy): add backup restore and upgrade"
```

---

### Task 11: Ubuntu 部署文档与状态记录

**Files:**
- Create: `docs/部署与运行-Ubuntu.md`
- Modify: `docs/README.md`（导航）
- Modify: `docs/superpowers/资产与状态.md`（部署资产与限制）
- Modify: `README.md`（指向 Ubuntu 部署文档，保留 Windows 本地启动）

**Interfaces:**
- Consumes: 本计划实现的所有脚本与路径。
- Produces: 可执行的操作说明；不新增运行代码。

- [ ] **Step 1: 写文档**

覆盖：服务器前提（Ubuntu 24.04/x86_64、4 核/3.6GiB/52GiB、Docker 未装）；Docker 安装与腾讯云 mirror；首次安装（代码包/数据包解压、`install.sh`）；Basic Auth 与 TLS（自签/文件/关闭）；端口与云安全组（仅 80/443）；`start/stop/status/logs/backup/restore/upgrade`；数据路径与备份；故障排查（Docker Hub DNS、mirror、MySQL 未 healthy、认证 401、TLS 警告、内存不足）；M1 noVNC 在 P2 提供，P1 不声称采集可用；私有数据/密钥不入公开包。

- [ ] **Step 2: 更新导航与状态**

`docs/README.md` 增加部署文档入口；`资产与状态` 增加 `deploy/`、部署脚本、镜像/数据包边界与“仅工程验证、未服务器实机”的限制；`README.md` 增加 Ubuntu 部署链接。

- [ ] **Step 3: 检查**

Run: `git diff --check`；人工核对相对链接；不启动业务测试。
Expected: 无空白错误，链接存在。

- [ ] **Step 4: 提交**

```bash
git add docs/部署与运行-Ubuntu.md docs/README.md docs/superpowers/资产与状态.md README.md
git commit -m "docs(deploy): document Ubuntu production deployment"
```

---

### Task 12: 全量烟测与 PR

**Files:**
- Create: `deploy/tests/run-all.sh`
- No product code changes.

**Interfaces:**
- Consumes: 全部 P1 脚本/镜像。
- Produces: 一份可复现的 P1 证据与 PR。

- [ ] **Step 1: 写总烟测脚本**

`deploy/tests/run-all.sh` 依次运行：
- `bash -n deploy/scripts/*.sh`
- `bash deploy/tests/test-backend-image.sh`
- `bash deploy/tests/test-web-image.sh`
- `bash deploy/tests/test-compose-stack.sh`
- `bash deploy/tests/test-nginx-auth.sh`
- `bash deploy/tests/test-nginx-tls.sh`
- `bash deploy/tests/test-lifecycle.sh`
- `bash deploy/tests/test-install.sh`
- `bash deploy/tests/test-backup-restore.sh`
- 栈内 API 冒烟（`ddl.sql` schema）：`curl -u` `/`、`/api/collection/platforms`、`/api/jobs?page=1&page_size=1`、`/api/m2/delivery/inputs?limit=1&offset=0` 均为 200；`/healthz` 无认证 200。
- 后端：`cd backend && .venv/Scripts/python.exe -m pytest -m "not integration" -q`
- 前端：`cd frontend && pnpm test && pnpm run typecheck && pnpm run build`
每步输出 PASS/FAIL，最后汇总；任一 P1 新增/改动测试失败或非已知失败 exit 1。全量后端套件若仅出现已知无关失败 `test_delivery_graph.py::test_concurrent_publish_returns_one_complete_immutable_snapshot`，记录为已知问题并在 PR 中区分，不修改无关模块；其他失败按 P1 失败处理。

- [ ] **Step 2: 运行**

Run: `bash deploy/tests/run-all.sh`
Expected: 全部 PASS；记录镜像构建时间、测试数、未执行项（真实 Docker 安装/服务器部署）。

- [ ] **Step 3: 检查工作区**

Run: `git status --short`；确认没有 `deploy/.env`、`deploy/auth/`、`deploy/tls/`、`deploy/images/`、`data/` 被误加。
Expected: 只含计划内文件。

- [ ] **Step 4: 提交并推送**

```bash
git add deploy/tests/run-all.sh
git commit -m "test(deploy): add P1 smoke suite"
git push -u origin codex/issue81-p1-deploy
```

- [ ] **Step 5: 创建 PR**

```bash
gh pr create --base master --head codex/issue81-p1-deploy \
  --title "feat(deploy): Ubuntu 24.04 production deployment base (P1)" \
  --body "P1 部署基座：Compose/Nginx/MySQL/backend/web、Basic Auth/TLS、可信代理门禁、安装与运维脚本、Ubuntu 文档。未包含 M1 Linux 采集。验证命令与限制见 PR 描述；不自动合并。"
```

PR 描述补充：测试命令与结果、未执行项（真实 Docker 安装、服务器部署、真实采集）、与设计文档链接。

---

## 后续阶段（本计划不展开）

- P2 `codex/issue81-p2-m1-linux`：Edge/Xvfb/noVNC、Linux 进程树、频率账本、运行态复位。
- P3 `codex/issue81-p3-m1-cleanup`：M1 单一入口，删除旧单轮/批次/桥接/循环。
- P4 `codex/issue81-p4-m2-cleanup`：M2 旧执行器/模型路由/兼容层清理。
- P5 `codex/issue81-p5-m3-m4-cleanup`：M3 正式入口与旧图谱分叉、M4 旧匹配/路径清理。
- P6 `codex/issue81-p6-package`：代码包/数据包、Ubuntu 安装烟测、私有数据交付、部署后 release。

每个后续阶段在开始前单独写计划；均从上一阶段分支切出（stacked），不自动合并。
