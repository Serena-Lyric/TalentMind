# Ubuntu 24.04 生产部署与运行

> 适用：腾讯云轻量应用服务器（Ubuntu 24.04 x86_64）首次部署 TalentMind。
> 当前范围：P1 部署基座（MySQL + FastAPI + Nginx + Basic Auth/TLS + 安装/运维脚本）。
> **M1 Linux 采集（Edge/Xvfb/noVNC）尚未在 P1 交付**，计划在 P2 单独完成；P1 不声称采集可用。

## 1. 前提

- Ubuntu 24.04 x86_64，4 核，3.6GiB 内存 + 1.9GiB swap，52GiB 可用磁盘。
- root 或 sudo。
- 云安全组/防火墙只开放 80/443（或自定义 HTTPS 端口）；不要开放 3306/7474/7687/6379。
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

## 7. 故障排查

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

## 8. 数据与安全边界

- 真实 JD、M2 原生报告、模型 Key、Basic Auth、TLS 私钥、浏览器 Cookie **不得进入公开代码包/release**。
- 部署后建议轮换模型 Key 和 Basic Auth 密码；私有包按敏感材料保管。
- 本机 `data/local/collection/frequency.sqlite3` 旧共享账本不迁移；服务器从每站新账本开始，模块频率硬下限仍生效。
- P1 不启动真实采集；M1 Linux Edge/Xvfb/noVNC 在 P2 交付，登录态不随包迁移，需在服务器重新人工登录。

## 9. 验证边界

P1 的自动化验证只覆盖：镜像构建、隔离 Compose 栈、Basic Auth、可信代理门禁、TLS 模式、启停/重启数据、安装导入、备份恢复。**尚未在真实腾讯云服务器执行**；Docker 安装/镜像加速/固网 DNS 以服务器实际执行为准。M1 真实采集和全链路业务验收不在 P1 声明完成。
