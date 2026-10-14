# 系统部署说明

> 版本：v0.1（2026-08-31）
> 说明：本系统采用 docker-compose 单点部署，后端 18000 / 前端 18080（本机 8000/5173 受 Windows 端口权限限制）。

## 1. 环境要求

- 操作系统：Windows 10/11（开发机实测）或 Linux
- Docker + Docker Compose
- Python 3.11+（后端）
- Node.js 18+ 与 pnpm（前端）

## 2. 快速启动

```bash
# 1) 启动基础设施（MySQL / Neo4j / Redis）
docker compose up -d

# 2) 准备后端环境
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows；Linux 用 source .venv/bin/activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env         # 按本机配置 .env（MySQL/Neo4j/Redis；LLM key 可选）

# 3) 启动后端
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18000

# 4) 启动前端（默认 /api 代理到 18000，可用 VITE_PROXY_TARGET 覆盖）
cd frontend
pnpm install
pnpm run dev                        # http://127.0.0.1:18080
```

## 3. 端口

| 服务 | 端口 | 说明 |
|---|---|---|
| 前端 | 18080 | Vue3 + Vite |
| 后端 API | 18000 | FastAPI，健康检查 GET /health |
| Neo4j Browser | 7474 | 图谱浏览器 |
| Neo4j Bolt | 7687 | 图谱驱动 |
| MySQL | 3306 | 主数据库 |
| Redis | 6379 | 缓存 |

## 4. 数据初始化

- Docker 命名卷持久化 MySQL/Neo4j/Redis 数据（重启不丢）；
- 首次启动由后端自动初始化 schema（`backend/app/contracts/ddl.sql` 冻结契约）；
- 完整 JD 池（128,625 条）如需导入：`docs/submit/seed_jd_pool.sql.gz`（或 `data/local/m2-data-pack/` 快照）；
- M2 岗位分析数据导入：`python -m app.integration.import_exchange`（全量重建语义）；
- 图谱导入 Neo4j：`python -m app.integration.import_graph`（MERGE 幂等，换数据先清空）。

## 5. 测试

```bash
cd backend
python -m pytest -q                # 全量（当前 224 通过 / 5 失败，M2 语义差异待回包）
python -m pytest -m integration    # 集成测试（需 Docker 已启动）
cd frontend
pnpm run build                     # 类型检查 + 构建
```

## 6. 配置说明

- `backend/.env`：数据库/图库/LLM 密钥，gitignore 保护，禁止外传/入库；
- `frontend/vite.config.ts`：dev 端口 18080，`/api` 代理默认指向 18000（`VITE_PROXY_TARGET` 可覆盖）；
- 采集循环：`python -m app.collect.fetch_all`（一键信号+hn+交叉验证）；`collect_loop --hours 6 --forever`（持续采集）。
