# Ubuntu 24.04 生产部署与运行

> 适用：腾讯云轻量应用服务器（Ubuntu 24.04 x86_64）首次部署 TalentMind。
> 当前范围：P1 部署基座（MySQL + FastAPI + Nginx + Basic Auth/TLS + 安装/运维脚本）与 P2 M1 Linux 采集（Edge/Xvfb/noVNC + Linux 进程组归属）。
> P2 已在本地 linux/amd64 容器完成烟测；**尚未在真实服务器执行，也未访问真实招聘站或执行真实采集**。

## 1. 前提

- Ubuntu 24.04 x86_64，4 核，3.6GiB 内存 + 1.9GiB swap，52GiB 可用磁盘。
- root 或 sudo。
- 云安全组/防火墙只开放 80/443（或自定义 HTTPS 端口）；不要开放 3306/7474/7687/6379，也不要开放 noVNC 的 6080（只通过 SSH 隧道访问）。
- 服务器能访问 apt 源和模型端点；Docker Hub 的 `registry-1.docker.io` 可能被 DNS 污染，脚本会用腾讯云镜像源。

## 2. 交付物

| 包 | 内容 | 是否公开 |
|---|---|---|
| `talentmind-code-<version>.tar.gz` | 代码、预构建镜像、`deploy/` 脚本、文档、空库初始化 | 可发布到公开 release |
| `talentmind-data-<version>.tar.gz` | MySQL dump、M2 运行数据、`deploy/model.env`、生产配置模板 | 只私下交付，不发布 |

两个包都解压到 `/opt/talentmind`，目录结构：

```
/opt/talentmind/
  app/                    # 代码包
  data/
    mysql/                # MySQL datadir
    backend/              # 容器 /app/data/local（M2 数据、采集运行态）
  app/deploy/
    .env                  # install.sh 生成（600）
    auth/htpasswd         # Basic Auth
    auth/.credentials     # 一次性凭据（600）
    tls/                  # 证书
    m2/                   # M2 模型配置与 Key（600，私有包提供）
    images/               # docker save 镜像
```

## 3. 首次安装

```bash
sudo mkdir -p /opt/talentmind
sudo tar -xzf talentmind-code-<version>.tar.gz -C /opt/talentmind
sudo tar -xzf talentmind-data-<version>.tar.gz -C /opt/talentmind
sudo bash /opt/talentmind/app/deploy/scripts/install.sh
```

`install.sh` 会：

1. 安装 Docker/Compose（优先腾讯云 Docker CE 源，回退 Ubuntu `docker.io` + `docker-compose-v2`）。
2. 在第一次 `docker pull` 前写入 `/etc/docker/daemon.json` 的 `registry-mirrors: ["https://mirror.ccs.tencentyun.com"]`，并重启 Docker。
3. 生成数据库口令、Basic Auth 凭据、代理秘钥和自签 TLS 证书。
4. 加载 `deploy/images/*.tar`；没有镜像归档时才依赖 Docker Hub。
5. 启动 MySQL；若存在 `deploy/data/mysql/talentmind.sql.gz` 或 `TALENTMIND_MYSQL_DUMP` 则导入；否则只导入 `ddl.sql` schema，日志会写 “schema only”。
6. 启动 backend/web，等待健康检查，打印访问地址与 Basic Auth 用户名/密码。

**已有数据保护**：`install.sh` 检测到 `data/` 下已有文件、已有容器或数据库内容时拒绝初始化，不会覆盖。恢复请用 `restore.sh`。

## 4. 访问与鉴权

- 默认地址：`https://<服务器公网 IP>/`（自签证书，浏览器会警告一次）。
- 先输入 Basic Auth 用户名/密码，再进入前端演示登录页；前端登录不是安全边界。
- 凭据保存在 `deploy/auth/.credentials`（600）；`deploy/auth/htpasswd` 需被 Nginx worker 读取（640 root:101 或 644）。
- 修改 Basic Auth：重新生成 `htpasswd` 后 `docker compose restart web`。

### TLS 模式

| `TALENTMIND_TLS_MODE` | 行为 |
|---|---|
| `selfsigned`（默认） | 安装时生成含服务器 IP/DNS 的 SAN 自签证书 |
| `files` | 使用 `deploy/tls/fullchain.pem` 与 `privkey.pem`；缺失时拒绝渲染 |
| `off` | 仅 HTTP，适合内网/临时调试，不建议公网 |

有域名时可把证书放进 `deploy/tls/` 并设 `files`；Let's Encrypt/certbot 不在 P1 自动配置范围内。

## 5. 常用运维

```bash
cd /opt/talentmind/app
sudo bash deploy/scripts/start.sh       # 启动并等待健康
sudo bash deploy/scripts/stop.sh        # 停止容器，保留网络/数据
sudo bash deploy/scripts/status.sh      # 容器状态、健康、数据目录、端口
sudo bash deploy/scripts/logs.sh        # 跟踪日志
sudo bash deploy/scripts/logs.sh --no-follow
sudo bash deploy/scripts/backup.sh      # 备份
sudo bash deploy/scripts/restore.sh --yes <备份目录>
sudo bash deploy/scripts/upgrade.sh     # 先备份，再加载镜像并重启
```

- `status.sh` 健康时退出码 0，未健康/未运行退出码 1。
- `backup.sh` 会短暂停止 backend 以获得 M2 SQLite 一致快照，然后恢复；备份包含 `mysql.sql.gz`、`backend.tar.gz`、`deploy.tar.gz`、`SHA256SUMS`。
- `restore.sh` 默认拒绝执行；必须 `--yes`，且会覆盖数据库和 `deploy/` 密钥。恢复会重渲染 Nginx，并把 MySQL root/app 用户密码改为备份中的值；恢复后用备份的 `deploy/auth/.credentials` 登录。备份包含密钥/Cookie，必须私有保存。
- `upgrade.sh` 先备份，再 `docker load deploy/images/*.tar` 并 `compose up -d`；不做自动数据库迁移。

## 6. 资源与可选组件

- MySQL：`innodb_buffer_pool_size=512M`、`performance_schema=OFF`，容器 `mem_limit: 1g`。
- backend：`uvicorn --workers 1`，`mem_limit: 1.5g`。
- Nginx：`mem_limit: 128m`。
- 宿主机：`vm.swappiness=10`，保留 1.9GiB swap。
- Neo4j/Redis **默认不启动**：当前页面没有运行时消费者。需要时：
  ```bash
  docker compose --env-file deploy/.env -f deploy/compose.yml --profile graph-db --profile cache up -d
  ```
  限额：Neo4j heap 512M/pagecache 256M；Redis maxmemory 128mb/allkeys-lru。

## 7. M1 Linux 采集（Edge/Xvfb/noVNC）

backend 镜像内置 Microsoft Edge for Linux、Xvfb、x11vnc、noVNC（websockify）和 Noto CJK 字体。容器以默认命令启动 uvicorn 时，entrypoint 先启动 `Xvfb :99`，再启动仅监听容器内回环的 x11vnc（5900）和 websockify（容器内 6080 → 127.0.0.1:5900）；一次性命令（镜像检查、`docker exec` shell）直接 `exec`，不启动图形服务。

- **只回环**：`deploy/compose.yml` 仅为 backend 发布 `127.0.0.1:6080:6080`；18000 与数据库端口都不发布。不要改成 `0.0.0.0`，也不要在云安全组开放 6080。
- **SSH 隧道**：在操作电脑执行 `ssh -L 6080:127.0.0.1:6080 <user>@<server>`，保持会话，然后打开 `http://127.0.0.1:6080/vnc.html`。断开隧道即断开 VNC。
- **先准备浏览器，再人工登录**：在采集页点击“准备浏览器”。该动作只启动/发现受控 Edge 并打开目标页，**不会启动采集**；随后在 noVNC 桌面中人工登录 BOSS/智联/猎聘。遇到验证码/安全验证/访问限制时停止，不绕过。
- **登录态不迁移**：部署包和数据包都不含 Windows Edge 档案、Cookie 或会话；服务器上的登录必须重新人工完成。noVNC 本身不设密码，依赖回环绑定和 SSH 隧道隔离。
- **安全取舍**：Edge 在容器内以非 root 用户运行，但启动参数包含 `--no-sandbox` 与 `--disable-dev-shm-usage`（Docker 环境要求），不能当作安全隔离边界。
- **停止与清理**：调度器停止时先向 worker 进程组发 SIGTERM，超时再 SIGKILL；仍无法确认整棵进程树退出时状态保持失败并拒绝释放 lease（`collection_worker_termination_unknown`）。不要按 PID 手工猜测清理或复用。
- **日志位置**：容器内 `/tmp/talentmind-xvfb.log`、`/tmp/talentmind-x11vnc.log`、`/tmp/talentmind-websockify.log`；采集 worker 日志在宿主机 `data/backend/collection/runtime/<platform>/worker.log`。

## 8. 故障排查

| 现象 | 处理 |
|---|---|
| `docker pull` 卡住/`registry-1.docker.io` 解析异常 | 检查 `/etc/docker/daemon.json` 的 `registry-mirrors`；`systemctl restart docker`；或直接 `docker load -i deploy/images/*.tar`。 |
| Docker 未安装且 apt 失败 | 安装脚本会打印诊断；可手动用腾讯云 Docker CE 源或 Ubuntu `docker.io` + `docker-compose-v2`。 |
| MySQL 不 healthy | `logs.sh` 查看；确认 `deploy/mysql/my.cnf` 不是 world-writable（`chmod 644`）；确认磁盘/内存。 |
| 页面 401 | Basic Auth 未输入或凭据错误；查看 `deploy/auth/.credentials`。 |
| 自签证书警告 | 浏览器继续访问；或改用 `TLS_MODE=files` 的正式证书。 |
| 502/接口不可用 | `status.sh` 看 backend 健康；`logs.sh` 看 backend 启动和数据库连接。 |
| 80/443 被占用 | 停掉占用进程；`status.sh` 打印端口。 |
| 内存不足/容器被杀 | 确认 Neo4j/Redis 未默认启动；检查 `docker stats`；必要时增加 swap 或升级服务器。 |
| `install.sh` 拒绝执行 | 目标 `data/` 已有文件；这是防止覆盖。备份后用 `restore.sh` 或人工接管。 |
| 6080 打不开/noVNC 页面 404 | 确认 SSH 隧道仍在；`docker compose port backend 6080` 应输出 `127.0.0.1:6080`；宿主机与云安全组都不应直接开放 6080。 |
| noVNC 黑屏/没有桌面 | 查看 `/tmp/talentmind-xvfb.log`、`/tmp/talentmind-x11vnc.log`、`/tmp/talentmind-websockify.log`；确认 backend 以默认 `uvicorn` 命令启动（entrypoint 才会拉起图形服务）。 |
| “准备浏览器”报未找到 Edge | `docker exec <backend容器> microsoft-edge-stable --version`；检查 profile 目录权限与 `worker.log`；不要改用日常浏览器目录。 |
| 停止后仍显示运行中/终止未知 | 进程组无法确认退出时按失败关闭处理；查看 worker 日志与 `ps -o pid,pgid,cmd`，不要按 PID 手工清理或复用。 |

## 9. 数据与安全边界

- 真实 JD、M2 原生报告、模型 Key、Basic Auth、TLS 私钥、浏览器 Cookie **不得进入公开代码包/release**。
- 部署后建议轮换模型 Key 和 Basic Auth 密码；私有包按敏感材料保管。
- 本机 `data/local/collection/frequency.sqlite3` 旧共享账本不迁移；服务器从每站新账本开始，模块频率硬下限仍生效。
- P2 已交付 M1 Linux Edge/Xvfb/noVNC 与 Linux 进程组归属，但仍不自动启动采集；登录态不随包迁移，需在服务器经 SSH 隧道 + noVNC 重新人工登录。

## 10. 验证边界

P1 的自动化验证只覆盖：镜像构建、隔离 Compose 栈、Basic Auth、可信代理门禁、TLS 模式、启停/重启数据、安装导入、备份恢复。**尚未在真实腾讯云服务器执行**；Docker 安装/镜像加速/固网 DNS 以服务器实际执行为准。

P2 新增验证只在本地 linux/amd64 容器执行：`deploy/tests/test-m1-linux.sh` 检查 Edge/Xvfb/x11vnc/websockify/noVNC/Noto CJK、`/health`、Xvfb socket、经回环映射端口读取 `/vnc.html`、容器内 `about:blank` Edge CDP 和 worker 进程组停止。**未访问 BOSS/智联/猎聘、未在真实服务器运行、未执行真实采集、未迁移登录态**；M1 真实三站与全链路业务验收仍以负责人服务器反馈为准。

