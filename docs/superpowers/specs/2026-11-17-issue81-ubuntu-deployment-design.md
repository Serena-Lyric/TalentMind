# Issue #81 Ubuntu 24.04 部署与阶段交付设计

> 状态：负责人已批准（2026-11-17）；按本设计进入实施。
> 已确认：服务器为全新机器；按标准目录规范存储；M2 模型沿用本机 DeepSeek 配置/Key；Neo4j/Redis 默认关闭，保留可选 profile。
> 日期：2026-11-17
> 关联：[Issue #81](https://github.com/Serena-Lyric/TalentMind/issues/81)、[PR #80](https://github.com/Serena-Lyric/TalentMind/pull/80)、[Issue #79](https://github.com/Serena-Lyric/TalentMind/issues/79)

## 1. 目标与完成定义

把 TalentMind 打包成可在 **Ubuntu 24.04 x86_64** 上直接部署的压缩包，由负责人在腾讯云轻量服务器部署；同一运行实例完成：

1. M1 三站采集入口可启动、停止、查看状态，真实采集结果进入 MySQL；单站受限不拖垮其余站。
2. M2 选择真实 JD，经当前 delivery 主链得到职责、技能/要求、证据与岗位解释。
3. M3 图谱消费当前来源与 M2 结果，查看真实岗位—技能/场景关系。
4. M4 简历解析、岗位匹配与学习路径可用，给出可解释的匹配与成长建议。
5. 前端七页可操作；启动、停止、日志、重启、备份/恢复有直接可执行的脚本；重启后核心数据仍在。

**交付物**：

- **公开代码包**：代码、预构建镜像、部署/运维脚本、空库初始化、文档；不含真实数据、API Key、Cookie。
- **私有数据包**：MySQL dump、M2 运行数据、生产配置；只交付给负责人，不发布到 GitHub。
- 负责人部署成功并反馈后，才把公开代码包发布为 GitHub release；不自动合并任何 PR。

## 2. 非目标与反目标

- 不做多用户/多租户权限平台、SSO、细粒度角色；只用 Nginx Basic Auth 作为真实入口鉴权。
- 不把真实 JD 原文、简历、运行报告、模型 Key、浏览器 Cookie 放进公开 release。
- 不重新研究 M2 语义、不追求 100% 准确率、不新增 Gate 0/1/2 或重复独立审核。
- 不把 Windows Edge 登录态搬到服务器；服务器上重新人工登录。
- 不默认运行 Neo4j/Redis；当前产品页面没有它们的运行时消费者。
- 不恢复旧图谱对比工程、旧 B1/B2/B3 执行链或旧看板。
- 不为被删旧代码新建兼容目录或第二套正式入口。

## 3. 已核实的事实与约束

| 事项 | 事实 |
|---|---|
| 仓库可见性 | `Serena-Lyric/TalentMind` 为 public；release 资产默认公开。 |
| 服务器 | Ubuntu 24.04 x86_64，由负责人部署；Agent 不持有 SSH 凭据。 |
| 服务器实测（2026-11-17） | Ubuntu 24.04.4 LTS / 内核 6.8.0-138；4 核；3.6GiB RAM + 1.9GiB swap；59GB 磁盘、52GB 可用；Docker/Compose 未安装；80/443 无服务且云防火墙已放行；`api.deepseek.com` 可达（401）；`registry-1.docker.io` 被 DNS 污染到 Facebook IPv6 段，Docker Hub 拉取失败。 |
| 现有启动 | 仅 Windows PowerShell + Docker Desktop + 本机 venv + Vite dev server；无 Dockerfile、无反向代理、无 Linux 进程托管。 |
| 现有数据 | MySQL 约 310MB；2026-11-17 只读查询：`jd_pool` 2455、`job_definition` 677、`job_change_log` 275、`job_skill` 873、`signal` 1540、`skill_dict` 285、`resume` 0、`talent_raw` 0。`data/local/m2-product` 约 678MB。Neo4j 约 783MB，节点 7845 / 关系 11412，与 `exchange/m3/graph.json` 口径一致，当前页面不查询 Neo4j。Windows Edge 档案约 849MB，含 Cookie，不迁移。 |
| M1 浏览器 | `backend/app/collect/browser.py` 的进程发现与启动只支持 Windows Edge；`worker_process.py` 使用 Windows Job Object；`scheduler.py` 的进程创建时间在非 Windows 返回 `None`。 |
| M2 原文门禁 | `backend/app/routers/m2.py` 与 `backend/app/routers/collection.py` 要求回环客户端 + `TALENTMIND_LOCAL_RAW=1`；经 Nginx 反代后客户端地址会变化，需要可信代理方案。 |
| 模型配置 | `OPENAI_API_KEY` / `OPENAI_BASE_URL` 为后端必填；M2 delivery 另需 `TALENTMIND_M2_CONFIG`（DeepSeek 配置 JSON）与 `TALENTMIND_M2_KEY_FILE`（私钥文件），缺任一项只能读历史、不能新建分析。 |
| 前端 | Vue + hash router + `base: "./"`；历史图谱由 Vite 构建时从 `exchange/m3/graph.json` 产出；M2 图谱走 `/api/m2/...`。 |
| 本机验证条件 | Docker Desktop 29.8.2、buildx 0.37.2；无 Ubuntu WSL 发行版，只有 docker-desktop 发行版。 |

## 4. 方案选择

### 4.1 部署形态（已选 A）

- **A（采用）Docker Compose + 预构建 `linux/amd64` 镜像 + Nginx**：部署包内含 `docker save` 镜像，服务器不构建；`restart: unless-stopped`；一键脚本管理生命周期。可复现、少依赖服务器网络。
- B 服务器现场构建：包小，但依赖 Docker Hub/构建网络，首次部署更慢、更易失败。
- C 原生 systemd，不用 Docker：与现有 compose 开发方式分叉，运维脚本更多，不选。

### 4.2 M1 浏览器（已选 A）

- **A（采用）Ubuntu 上 Microsoft Edge + Xvfb + noVNC，复用现有 CDP 引擎**：一套采集架构；人工登录通过 SSH 隧道打开 `127.0.0.1:6080`；不新增第二套浏览器引擎。
- B 采集留在 Windows 工作站：服务器只是产品端，依赖工作站常开，不符合“同一正在运行的产品”验收。
- C 换 Playwright/Chromium：需要新引擎和新的登录/门禁验证，与 #79 的既有决定冲突；无必要。

### 4.3 运行进程（已选 A）

- **A（采用）MySQL + backend + Nginx**：满足当前七页与 M2/M4；资源占用可控。
- B 完整 MySQL + Neo4j + Redis：Neo4j 只被导入工具使用，Redis 无运行时调用；当前代码没有这两者的运行时消费者。负责人已给出两者资源配额，默认仍关闭，保留 `graph-db` / `cache` 可选 profile；若要求默认启动，按 §5.1 限额加入。
- 保留 `neo4j`/`redis` 可选 compose profile，供以后需要时显式启用；不进入默认启动路径。

### 4.4 发布内容（已选 A，负责人已确认）

- **A（采用）公开 release 放无数据/无密钥的代码包；私有数据包单独交付**。
- B 公开 release 放完整数据：违反仓库私有边界，泄露真实 JD、报告与凭据，不采用。
- C 完整包放私有仓库：负责人暂未要求；如以后需要，可把同一归档发到私有仓库。

### 4.5 阶段与 PR（已选 A）

- **A（采用）按可交付阶段拆分，stacked 分支，每个阶段一个 PR，均不自动合并**。
- B 先清理再部署：上线被推迟，且清理会改动待部署代码，不选。
- C 单一大 PR：不可审阅，不选。

## 5. 部署设计

### 5.1 目录布局与资源限额

服务器实测：4 核 / 3.6GiB RAM / 1.9GiB swap / 59GB 磁盘（52GB 可用）。按实测配置限额，不再按 2GB 或 20GB 假设。M2 数据逻辑体积约 1.4GB，MySQL 索引 + 镜像 + 构建缓存预计 8–10GB，磁盘不构成约束。

| 组件 | 限额 |
|---|---|
| MySQL | `innodb_buffer_pool_size=512M`、`performance_schema=OFF`，`mem_limit: 1g` |
| backend | `uvicorn --workers 1`，`mem_limit: 1.5g`（含 Edge/Xvfb；M2 模型调用为网络等待） |
| Nginx | `mem_limit: 128m` |
| Neo4j（可选） | heap `512M`（initial=max）、pagecache `256M`，`mem_limit: 1g` |
| Redis（可选） | `maxmemory 128mb`、`maxmemory-policy allkeys-lru`，`mem_limit: 256m` |
| 宿主机 | `vm.swappiness=10`；保留 1.9GiB swap 兜底 |

默认不启动 Neo4j/Redis 时峰值约 2.6GiB；两者都启动时约 3.9GiB 上限、实际约 2.2–2.6GiB，依赖 swap 兜底。3.6GiB 下同时全开偏紧，默认关闭它们是为当前无运行时消费者的组件留余量。

```
/opt/talentmind/
  app/                         # 解压的代码包（含 deploy/、docs/、镜像 tar）
  data/
    mysql/                     # MySQL datadir（bind mount）
    backend/                   # 容器内 /app/data/local
      m2-product/
      m2-p5-p6-20261107/
      m2-delivery/
      collection/
        runtime/{platform}/    # 每站 SQLite 状态与频率账本
        browser_profiles/{platform}/
    logs/
  deploy/
    .env                       # 安装脚本生成的生产配置（600）
    model.env                  # 私有模型 Key（600，安装时合并进 .env）
    auth/htpasswd              # Basic Auth（600）
    auth/.credentials          # 首次生成的用户名/密码（600，交付后由负责人保管）
    tls/{fullchain.pem,privkey.pem}
    m2/{config.json,api-key.txt}  # M2 处理器配置与私钥（600）
    compose.override.yml       # 可选：TLS/端口/noVNC 绑定
```

### 5.2 服务

| 服务 | 镜像 | 对外 | 说明 |
|---|---|---|---|
| `mysql` | `mysql:8.0` | 不发布端口 | bind `data/mysql`；挂载 `deploy/mysql/my.cnf`（buffer pool 512M、performance_schema OFF）；healthcheck；仅内部网络。 |
| `backend` | 预构建 `talentmind-backend:<version>` | 不发布端口 | FastAPI + M1 运行时 + Edge/Xvfb/noVNC；挂载 `data/backend` 到 `/app/data/local`；`uvicorn --workers 1`；注入 `TALENTMIND_LOCAL_RAW=1`、`TALENTMIND_TRUSTED_PROXY_SECRET`、`TALENTMIND_M2_CONFIG`、`TALENTMIND_M2_KEY_FILE`；healthcheck `/health`。 |
| `web` | 预构建 `talentmind-web:<version>` | `80`、`443` | Nginx：静态前端 + `/api` 反代 + Basic Auth + TLS；仅它暴露公网。 |
| `neo4j` | `neo4j:5-community` | 不发布端口 | 可选 profile `graph-db`，默认不启动；heap 512M、pagecache 256M。 |
| `redis` | `redis:7-alpine` | 不发布端口 | 可选 profile `cache`，默认不启动；maxmemory 128mb、allkeys-lru。 |

- 不发布 3306/7687/6379 等数据库端口；即使临时排查也只绑定 `127.0.0.1`，避免 Docker iptables 绕过 ufw/云防火墙。对外只留 `web` 的 80/443。
- 镜像构建使用 `.dockerignore` 排除 `data/`、`input/`、`output/`、`backend/.env`、`docs/originalfile/`、`docs/submit/`、`笔记.md`、浏览器档案等；镜像只含代码与公开的 `exchange/m3` 快照。
- `restart: unless-stopped`；日志 `json-file` 限制大小与数量。
- noVNC 只绑定 `127.0.0.1:6080`，负责人用 `ssh -L 6080:127.0.0.1:6080 <user>@<server>` 后在本机打开 `http://127.0.0.1:6080`；不直接暴露公网。安全组只需开放 80/443（或自定义 HTTPS 端口），不开放 6080。
- 后端容器内以非 root 用户运行；Edge 在容器内需要 `--no-sandbox` 与 `--disable-dev-shm-usage`，并给 backend 设置 `shm_size: 1gb`；在文档中标注该取舍。
- 容器统一 `TZ=Asia/Shanghai`、`LANG=C.UTF-8`、`PYTHONUTF8=1`；MySQL 使用 `utf8mb4`。
- MySQL 使用独立应用账号（非 root）连接；root 只用于首次导入/恢复。数据库口令由安装脚本随机生成，不沿用开发口令。

### 5.3 鉴权与 HTTPS

- Nginx `auth_basic` 保护 `/` 与 `/api/`；`htpasswd` 由安装脚本生成，密码只打印一次。`htpasswd` 需被 Nginx worker 读取：设为 `640 root:101`（官方 nginx 镜像 GID 101）或 `644`；`.credentials` 为 `600`。
- TLS 默认自签证书（含服务器 IP SAN）；支持 `TLS_MODE=files` 使用负责人证书；有域名时可运行可选 Let's Encrypt 脚本。
- 80 端口在启用 TLS 时重定向到 443。
- 前端演示登录保留，但不再作为安全边界；真实入口由 Basic Auth 保护。
- M2/原文门禁：新增 `TALENTMIND_TRUSTED_PROXY_SECRET`。Nginx 覆盖写入 `X-TalentMind-Proxy-Secret`；后端只加入仅含 `web` 与 `backend` 的 `edge` 内部网络，不加入默认网络，后端端口不发布。`TALENTMIND_LOCAL_RAW=1` 仍为前置条件；秘钥匹配时跳过回环/Host/Origin 检查，但仍拒绝 `Sec-Fetch-Site: cross-site`。开发环境仍走原回环 + `TALENTMIND_LOCAL_RAW=1` 路径；客户端自带的同名头在 Nginx 处覆盖，不信任外部输入。边界是“未发布的后端 + Basic Auth 的 Nginx + 秘钥头”，不是容器 IP 白名单。
- 后端端口不发布，只有 Nginx 能访问；该秘钥不进入前端。
- Nginx 调整 `client_max_body_size`（≥20m，覆盖 10MB 简历上传）与 `proxy_read_timeout`/`proxy_send_timeout`（≥120s，覆盖 M2 启动等待；模型后台调用最长 600s，不占用反代连接）。

### 5.4 数据迁移

- **MySQL**：本机 `mysqldump --single-transaction --routines --triggers --events --no-tablespaces`，gzip 后放入私有数据包。首次安装检测目标库为空才导入；非空库不自动覆盖，恢复走显式 `restore.sh`。
- **M2**：对 `m2-product/analysis.sqlite3`、`workflow.sqlite3` 使用 SQLite 在线备份（Python `sqlite3.Connection.backup`）避免 WAL 半写；复制 `runs/`、`graphs/`、`native-reports/`；排除 `*.lock`、`*-shm`、`*-wal`。
- **M2 历史读取**：复制 `m2-p5-p6-20261107/{sequence-head-final,dev-head-final}/state`；保留原目录结构，供 delivery 历史比较读取。
- **M2 delivery**：`m2-delivery/` 当前本机不存在，部署时创建空目录；不伪造运行记录。
- **采集**：本机当前没有每站 `runtime/{platform}/frequency.sqlite3` 或检查点；只有旧共享账本 `data/local/collection/frequency.sqlite3`（20KB，含智联频率记录和一个未完成动作 flight）。该账本不复制到服务器：复制后 `scheduler.start()` 会 `collection_legacy_migration_required` fail closed，未完成 flight 还需 token 恢复。服务器以全新的每站账本开始，模块的页面动作 15–30 秒、组合 360–720 秒硬下限仍生效；本机旧账本不删除。若负责人要求迁移旧账本，须显式授权并单独处理未完成动作，不在本次默认流程内。旧日志、bridge、gate0 证据也不进入部署包。
- **Neo4j**：默认不迁移。当前 7845/11412 与 `exchange/m3/graph.json` 一致，历史图谱页直接读构建产物；如以后需要图数据库，再单独导出/导入。
- **Edge 档案**：不迁移；服务器上通过 noVNC 重新登录三站。
- **M2 处理器**：私有数据包包含本机在用的 `deepseek-flash-20261102.json` 与 `api-key.txt`（复制为 `deploy/m2/config.json`、`deploy/m2/api-key.txt`），并设置 `TALENTMIND_M2_CONFIG` / `TALENTMIND_M2_KEY_FILE`；不放进公开代码包。**待负责人确认**是否沿用这套 DeepSeek 配置/Key，或在服务器上另配。
- **`.env`**：私有数据包包含 `deploy/model.env`（本机 `OPENAI_API_KEY`、`LLM_API_KEY` 等模型密钥）；安装脚本生成 `deploy/.env`，数据库口令与 Basic Auth 随机生成，模型密钥从 `model.env` 合并；不沿用开发数据库口令。公开代码包只含 `.env.example`。
- **数据核对**：打包前后核对 MySQL 表行数（以打包时实际值为准，不套用历史文档的 2988/717 口径）、M2 SQLite `PRAGMA integrity_check`、文件数量与 SHA256。

### 5.5 打包与运维脚本

- `scripts/package-deploy.ps1`（Windows）：构建/保存镜像，生成两个归档与 `SHA256SUMS`：
  - `talentmind-code-<version>.tar.gz`
  - `talentmind-data-<version>.tar.gz`
  - 默认把 `mysql:8.0`、`neo4j:5-community`、`redis:7-alpine` 与 backend/web 镜像一并 `docker save`，避免服务器依赖 Docker Hub；若单包超过 2GB，再拆出镜像资产。镜像加速仍配置，供后续拉取/升级。
- `deploy/install.sh`：检查 Ubuntu 24.04/x86_64；**Docker/Compose 未安装时先安装**（优先腾讯云 Docker CE 镜像源，回退 Ubuntu 24.04 `docker.io` + `docker-compose-v2`）；在第一次 pull 前写入 `/etc/docker/daemon.json` 的 `registry-mirrors: ["https://mirror.ccs.tencentyun.com"]`（可用 `TALENTMIND_REGISTRY_MIRROR` 覆盖），重启 Docker；执行 `docker pull mysql:8.0` 烟测——失败但部署包内镜像齐全时记录警告继续，缺镜像才终止。加载镜像；创建目录与权限；生成 Basic Auth、TLS 与数据库口令；合并 `deploy/model.env` 生成 `deploy/.env`；首次导入数据；`compose up -d`；等待健康；打印访问地址与一次性凭据。
  - 部署包含 `deploy/docker/daemon.json.example`（腾讯云 registry mirror + 日志轮转）；安装脚本按实际镜像源写入 `/etc/docker/daemon.json`。
  - 缺少 Docker/Compose 且安装失败时只打印诊断并退出，不擅自改系统；不自动修改防火墙/安全组。
  - 检测到 `/opt/talentmind/data` 已有内容、已有 `talentmind` compose 容器或 MySQL 数据卷时，**拒绝初始化并退出**，提示先备份/接管；不自动覆盖已有业务数据。
- `deploy/start.sh`、`stop.sh`、`status.sh`、`logs.sh`、`backup.sh`、`restore.sh`、`upgrade.sh`。
- `backup.sh` 只保留一套备份机制：MySQL dump + `data/backend` 的 tar + `deploy/`（`.env`、auth、TLS、M2 配置/私钥）；`restore.sh` 停后端后恢复，默认拒绝覆盖非空库，需显式确认。备份包含密钥与 Cookie，文档要求私有保存。
- 打包产物默认放本机 `data/local/deploy/`，由负责人自行取走；该目录不提交 Git。代码包与数据包均附 `SHA256SUMS`。
- `upgrade.sh` 先备份，再加载新镜像并 `compose up -d`；数据迁移不在升级脚本中自动执行。
- 不在部署脚本中自动触发真实采集；M1 仍需页面显式启动。

### 5.6 重启与可观察性

- Docker `restart: unless-stopped` 覆盖进程崩溃与宿主机重启；MySQL/backend healthcheck 决定依赖顺序。
- M1 状态持久化在 `data/backend/collection`；重启后页面显示原状态，受限站保持 `blocked/needs_login`，不自动重试。
- `logs.sh` 聚合 `docker compose logs`；采集事件与报告仍在 `data/backend/collection`。
- `status.sh` 输出容器状态、健康检查、磁盘占用、端口监听与最近错误。

## 6. M1 Linux 适配

1. **Edge 发现**：Linux 路径 `/usr/bin/microsoft-edge`、`/opt/microsoft/msedge/msedge`、`PATH`；沿用独立 profile 校验，并拒绝 Linux 日常目录 `~/.config/microsoft-edge`、`~/.config/google-chrome`。
2. **进程证据**：用 `/proc` + `ps` 替代 PowerShell；只接受回环监听；动态端口与 `DevToolsActivePort` 逻辑保留。
3. **启动参数**：Linux 增加 `--no-sandbox`、`--disable-dev-shm-usage`；安装 `fonts-noto-cjk`、时区 `Asia/Shanghai`。
4. **进程树归属**：Linux 使用 `start_new_session=True` + 进程组；lease 保存 pgid；停止时向进程组发信号并等待退出；`scheduler` 用 `/proc/<pid>/stat` 的 starttime 替代 Windows 创建时间。无法核实整棵树时仍 fail closed。
5. **Xvfb/noVNC**：backend entrypoint 启动 `Xvfb :99`、`x11vnc`、`websockify`；`DISPLAY=:99`；noVNC 仅回环。页面“准备浏览器”后，用户通过 SSH 隧道登录三站。
6. **频率账本**：服务器为每站新建独立账本；不迁移旧共享账本，模块硬下限仍生效；不因换平台或首次部署绕过冷却检查。
7. **测试**：纯函数覆盖 Linux 路径/进程解析；容器内用本地 `about:blank` 或本地 HTTP 页验证 Edge 启动与 CDP 响应；不访问真实招聘站。

## 7. 旧入口清理边界

清理按实际调用图执行，不以文件名为准；每项删除前确认无正式消费者。

| 模块 | 保留 | 删除/退役 |
|---|---|---|
| M1 | `runtime/`、`fetch_boss_jobs.py`、`fetch_cn_jobs.py`、`pipeline.py`、`repository.py`、`identity.py`、`frequency.py`、`browser.py` 低层能力 | 旧单轮 `control.py` 中非 runtime 路径、`batch.py`、`bridge.py`、`collection_bridge` 路由、`boss_collect_loop.py`、`cn_collect_loop.py`、`collect_loop.py`、`fetch_all.py`、HN/信号旧入口、对应前端批次/桥接组件与扩展（若无消费者） |
| M2 | `delivery/`、`product/` 只读历史、`foundation/` 现行依赖、`understanding/`、`knowledge/`、`work_candidates/` | 未消费的 B1/B2/B3 旧执行器、旧运行管线、重复模型路由、无调用者的 CLI/兼容层；历史结果保留只读适配 |
| M3/M5 | `delivery_bundle.py`、`product_bundle.py` 只读历史、`exchange/m3` 静态图、现行 `/graph` | 历史图对比、旧模拟/候选图作为正式默认结果的分叉、重复构建/展示路径、已退役前端页面/切换与后端消费者 |
| M4 | `resume_parser`、`file_parser`、`canonical`、`matcher.quick_match_weighted`、`requirements`、学习路径现行模块 | 旧 `resume_matcher_app.py`、`matching/main.py`、`generate_test_data.py`、旧匹配/重复路径生成/失效占位逻辑 |

- M3 正式入口：`/graph` 不再把 2026-09-05 历史交接图当作默认真实数据；历史图保留为明确标注的只读历史层，正式入口从当前 M2 运行进入（运行选择/最近可用运行），没有当前运行时给出明确空态，不回落旧图。此调整属于 P5 清理范围，不新建第二套图谱构建器。

- 同步删除不再使用的 imports、测试夹具、路由注册、配置项与依赖。
- 已核实无消费者、可随清理删除的候选：`backend/app/llm/`（仅自身 import `openai`）、`backend/app/db/redis.py`（无调用者）、`openai`/`redis` 依赖及对应配置项；删除后重新核对 `config.py` 必填项与部署 `.env`。
- 私有业务数据、持久卷、`data/local` 资产不随旧代码删除。
- 清理不新建兼容目录；历史读取用精简只读格式适配。

## 8. 阶段与 PR

| 阶段 | 分支 | 内容 | 验收 |
|---|---|---|---|
| P1 部署基座 | `codex/issue81-p1-deploy` | Dockerfile、生产 compose、Nginx、Basic Auth/TLS、安装/运维脚本、可信代理门禁、Ubuntu 文档 | Linux/amd64 镜像构建；隔离 compose 启动；七页静态与 API 可访问；Basic Auth 生效；重启后数据仍在；DB 端口未公开；不访问真实招聘站 |
| P2 M1 Linux 采集 | `codex/issue81-p2-m1-linux` | Edge/Xvfb/noVNC、Linux 进程树、频率账本迁移、运行态复位 | Linux 路径/进程单元测试；容器内 Edge+CDP 烟测；noVNC 回环可达；不访问真实站点 |
| P3 M1 清理 | `codex/issue81-p3-m1-cleanup` | 收敛为 runtime 单一入口，删旧单轮/批次/桥接/循环/前端入口 | 调用图检查；相关测试更新；七页与 runtime 状态正常 |
| P4 M2 清理 | `codex/issue81-p4-m2-cleanup` | 保留 delivery + 只读历史，删旧执行器/模型路由/兼容层 | 后端与前端测试；历史读取仍可用 |
| P5 M3/M4 清理 | `codex/issue81-p5-m3-m4-cleanup` | 清理旧图谱分叉与旧匹配/路径生成 | 图谱页、简历/学习页回归；无旧入口路由 |
| P6 打包交付 | `codex/issue81-p6-package` | 生成公开代码包与私有数据包；Ubuntu 安装烟测；部署文档与资产页更新 | 两包校验和；隔离安装成功；数据量核对；不把私有数据放入代码包 |

- 每个 PR 面向 `master`，基分支为上一阶段分支（stacked）；不自动合并。
- 阶段内不重复索要授权；高风险操作（真实采集、迁移真实数据、删除真实数据）仍单独确认。
- 负责人部署成功并反馈后：发布公开代码包 release；真实运行问题按 Issue #81 的“仅报地址/现象/已解决/阻塞/下一步”格式继续提修复 PR。

## 9. 验证策略

- 后端：`pytest -m "not integration"`，新增/修改范围专项测试；不连接正式库。
- 前端：`pnpm test`、`pnpm run typecheck`、`pnpm run build`。
- 容器：Windows Docker Desktop 构建 `linux/amd64` 镜像；隔离 compose 启动，健康检查、静态页、API、Basic Auth、重启持久化。
- Docker 安装与镜像加速：在服务器实际执行前只做脚本幂等性/路径检查；`ubuntu:24.04` 容器烟测无法证明真实服务器的 Docker 安装与 DNS 绕过，最终以负责人服务器执行为准；`docker pull mysql:8.0` 失败即终止，不进入 compose。
- 打包：在 `ubuntu:24.04` 容器（挂载宿主 Docker socket）执行安装脚本烟测；明确记录“不是全新云主机”的限制；最终以负责人服务器部署为真实验证。
- 数据：打包前后核对 MySQL 表行数、M2 SQLite `integrity_check`、文件数量与 SHA256；不把测试夹具写入生产数据。
- 不声称真实三站采集通过，直到负责人部署后提供实际运行证据。

## 10. 风险与未决

| 风险 | 处理 |
|---|---|
| 云服务器 IP 触发站点验证/登录 | 单站暂停，保留其余站；记录真实现象，不写成已运行；不绕过验证。 |
| 自签证书浏览器警告 | 文档说明；有域名时用 Let's Encrypt 或负责人证书。 |
| GitHub release 资产体积 | 若单包超过 2GB，拆分镜像资产；代码包与数据包分开。 |
| 私有数据包分发 | 在本机 `data/local/deploy/` 生成，负责人自行取走；不提交 Git。 |
| 模型 Key 泄露 | `deploy/m2/api-key.txt` 与 `.env` 只进私有包；公开包只有 `.env.example`；文档建议部署后轮换。 |
| MySQL dump 一致性 | 导出前确认无写入；使用 `--single-transaction`；恢复前校验行数。 |
| M1 容器内浏览器沙箱 | 使用 `--no-sandbox` 的取舍写入文档；不将其描述为安全隔离。 |
| 无 SSH 凭据 | 部署与真实验证由负责人完成；Agent 依赖反馈与日志继续修复。 |
| Neo4j 默认不部署 | 当前页面不依赖；如需图数据库，后续单独导出/导入，不影响上线。 |
| 服务器是否全新 | **已确认全新**。安装脚本仍检测已有数据/容器/卷并拒绝初始化，防止误覆盖。 |
| 服务器实际资源与网络 | **已实测**：4 核 / 3.6GiB + 1.9GiB swap / 52GiB 可用；Docker 未安装；DeepSeek 可达；80/443 空闲。按 §5.1 限额部署。 |
| Docker Hub DNS 污染 | `registry-1.docker.io` 解析到 Facebook IPv6，直接拉取失败。安装脚本先写腾讯云 `registry-mirrors` 并重启 Docker，再执行 `docker pull mysql:8.0` 烟测；同时把运行时镜像全部打进部署包，避免依赖 Hub。镜像失败即终止，不进入 compose。 |
| Docker 未安装 | 安装脚本优先腾讯云 Docker CE 源，回退 Ubuntu `docker.io` + `docker-compose-v2`；失败则打印诊断退出，不假设已安装。 |
| Neo4j/Redis 是否默认启动 | **已确认默认关闭**。保留 `graph-db` / `cache` profile，按 §5.1 限额显式启动。 |
| M2 生产模型配置 | **已确认沿用**本机 `deepseek-flash-20261102.json` + `api-key.txt`，放入私有数据包。 |

## 11. 留给实施者的细节

- Dockerfile 基础镜像与 Edge 版本、Nginx 配置细节、脚本拆分与幂等性。
- 清理阶段的精确文件清单，以实际 import/路由/前端消费者检查为准。
- 打包脚本的具体压缩参数、数据核对清单、安装烟测用夹具。
- release 标签命名与发布说明模板。
