# Issue #81 P4：M2 旧实现清理计划（2026-11-20）

## 目标与边界

按实际 import、路由注册、前端调用、测试与部署引用整理 M2，删除没有正式消费者的旧执行器、旧模型路由与配置，同时保留线上七页正在使用的 M2 能力：

- `/#/m2` 的输入分页、冻结输入、新建/开始/停止/恢复/放弃运行、逐条结果与证据读取；
- 历史 `data/local/m2-product` 只读运行、条目、报告、审核导出与历史图谱；
- 新旧 delivery 运行的版本比较；
- 工作候选与技能候选维护；
- M2 结果进入 M3 的 delivery 图谱快照。

不删除 `data/local/m2-product`、`data/local/m2-delivery`、`data/local/m2-p5-p6-20261107`、`exchange/m2`、数据库表或任何业务数据；不启动浏览器/模型，不触发真实分析；不改 M3/M4 页面与正式图谱入口；不新建兼容目录，不重命名保留模块。

## 实际消费者映射

以下按仓库内 import、FastAPI 路由、前端 API 调用、测试夹具和部署脚本核对，不按目录名推断。

### 后端运行时消费者

| 模块 | 实际消费者 | 处理 |
|---|---|---|
| `app.job_analysis.delivery.*`（`http_service`、`maintenance`、`comparison`、`runner`、`store`、`recorded`、`demo`、`evaluation`） | `routers/m2.py` 的 `/delivery/*`；`work_candidates/evaluation.py`；delivery/knowledge/work_candidates 测试；README 中的本机 CLI/评价命令 | 保留 |
| `app.job_analysis.product.source`、`product.workflow.History/adapted/Lease` | `routers/m2.py` 的 `/runs*` 历史读取；`delivery/http_service`、`delivery/store`；`test_m2_history.py`、`test_delivery_http.py` | 保留 |
| `app.job_analysis.foundation.inputs/store/runner/models/validation` | `routers/m2.py` 图谱 artifact 规范化；`graph/delivery_bundle.py`、`graph/product_bundle.py`、`graph/real_pipeline.py`、`graph/real_quality.py`；`scripts/run_m2_fixed_work_pairs.py`；delivery/understanding/knowledge/work_candidates 全链 | 保留 |
| `app.job_analysis.understanding.*` | `delivery/runner.py`（`understand`）、`delivery/http_service.py`（`CloudProcessor`）、`delivery/recorded.py`、`delivery/__main__.py`；P1 测试与 README CLI | 保留 |
| `app.job_analysis.knowledge.*` | `delivery/runner.py`、`maintenance.py`、`http_service.py`、`__main__.py`、`demo.py`、`evaluation.py`；`work_candidates/evolution.py`、`retrieval.py`、`models.py`、`evaluation.py`；`scripts/run_m2_fixed_work_pairs.py` | 保留 |
| `app.job_analysis.work_candidates.*` | `delivery/maintenance.py`、`runner.py`、`store.py`、`demo.py`、`evaluation.py`；候选维护与演化测试 | 保留 |
| `app.job_analysis.baseline.contract` | `delivery/runner.py`、`maintenance.py`、`recorded.py`、`evaluation.py`、`knowledge/alignment.py`、`attribution*.py`、`candidates.py`、`models.py`、`roles.py`、`understanding/*`、`work_candidates/*`、`graph/delivery_bundle.py` | 保留（现行语义契约） |
| `app.job_analysis.baseline.approved_assertions` | `delivery/evaluation.py` 的受控评价；P0 测试 | 保留 |
| `app.job_analysis.baseline.bundle/case_assertions/__main__`、`examples/`、`role-references.v1.json` | P0 基准 CLI 与测试；delivery 评价引用 `examples/analysis.json` | 保留（P0 评价工具，不在本轮旧执行器范围） |
| `app.job_analysis.semantics.models` | `baseline/contract.py`、`knowledge/*`、`understanding/*`、`work_candidates/*`、`role_classification/models.py` | 保留 |
| `app.job_analysis.semantics.rules/runner/store/validation` | `app/graph/real_pipeline.py` 的历史来源图离线构建；`governance/*`；对应测试 | 保留；M3 离线历史链，P5 判定 |
| `app.job_analysis.screening.*`、`governance.*` | 仅 `app/graph/real_pipeline.py`（离线历史来源图）与各自测试；无路由/前端/脚本消费者 | 保留；属 M3 离线链，P4 不改 M3 |
| `app.job_analysis.canonical_catalog.*` | 仅 `test_canonical_catalog.py`、`test_canonical_catalog_storage.py`；无 `app/`、`scripts/`、前端、工作流或部署引用 | 删除（B3 草案目录执行器，无正式消费者） |
| `app.job_analysis.role_classification.*` | 仅 `canonical_catalog` 与 9 个 `test_role_*` 测试；无正式消费者 | 删除（B3-0～B3-4 旧执行器） |
| `backend/app/llm/client.py` | 仅 `test_llm_client.py`；仅自身 import `openai`；无路由、job_analysis、脚本或前端调用 | 删除（重复模型路由） |
| `backend/app/db/redis.py` | 仅 `test_db_integration.py`；无正式调用者 | 删除 |
| `config.Settings.redis_url/openai_api_key/openai_base_url` | `db/redis.py`、`llm/client.py`、测试与部署 env；删除上述模块后无消费者 | 删除；保留 `mysql_url`、`neo4j_*`、`github_token` |
| `requirements.txt` 的 `openai`、`redis` | 仅上述两个被删模块 | 删除依赖 |
| `baseline` 的 `semantics.models.Evidence` 等 | 见上 | 保留 |

### 路由与前端

| 路由/符号 | 实际消费者 | 处理 |
|---|---|---|
| `GET /m2/delivery/inputs` | `frontend/src/api/m2.ts` `getDeliveryInputs`；`M2.vue` | 保留 |
| `POST/GET /m2/delivery/runs`、`GET /runs/{id}`、`/items/{index}` | `createDeliveryRun/getDeliveryRuns/getDeliveryRun`；`M2.vue`、`JobEvolution.vue` | 保留 |
| `POST /runs/{id}/start|resume|stop|abandon` | `M2.vue` 运行控制 | 保留 |
| `GET /m2/delivery/compare` | `frontend/src/api/evolution.ts` `compareDeliveryRuns` | 保留 |
| `/m2/delivery/candidates/*`（work/pending/skills/actions） | `frontend/src/api/candidates.ts`；`M2.vue`、`RoleResearch.vue` | 保留 |
| `GET /m2/delivery/runs/{id}/graph`、`/graph/{name}` | `frontend/src/graph/deliverySnapshot.ts`；`GraphPanorama.vue` delivery 模式 | 保留 |
| `GET /m2/runs`、`/runs/{id}`、`/items/{ordinal}` | `getM2Runs/getM2Run/getM2Item`；`M2.vue` 历史只读 | 保留 |
| `GET /m2/runs/{id}/report`、`/reviews/export` | `test_m2_history.py` 与历史读取契约；当前无前端调用但属只读历史能力 | 保留 |
| `GET /m2/runs/{id}/graph`、`/graph/{name}` | `frontend/src/graph/realSnapshot.ts` 历史图谱 | 保留 |

### 测试、脚本与部署

| 引用 | 实际消费者 | 处理 |
|---|---|---|
| `test_canonical_catalog*.py`、`test_role_*.py`（`test_role_research_summary.py` 除外） | 仅被删的 canonical/role 模块 | 删除；`test_role_research_summary.py` 只依赖 knowledge，保留 |
| `test_llm_client.py` | 仅 `app.llm` | 删除 |
| `test_db_integration.py` 的 redis 用例 | 仅 `app.db.redis` | 删除该 import 与用例，保留 MySQL/Neo4j 集成用例 |
| `test_config.py` 的 REDIS/OPENAI 必填断言 | `config.py` 被删字段 | 更新为只校验保留字段 |
| `backend/.env.example`、`deploy/.env.example`、`deploy/compose.yml`、`deploy/scripts/install.sh`、`deploy/tests/*` | `REDIS_URL`、`OPENAI_*` 仅为已删配置提供输入 | 从示例、compose backend 环境与部署测试中移除；Redis 可选 `cache` profile 保留 |
| `.github/workflows/m2-delivery.yml` 的 REDIS/OPENAI env | 仅为已删必填配置提供占位 | 移除 |
| `scripts/package-deploy.sh` 的 OPENAI 键转发 | 已删配置，继续转发只会产生缺失警告 | 从模型 env 转发列表移除 OPENAI_*，保留 LLM_* |
| `.gitattributes` 的 canonical_catalog sources 规则 | 目录被删 | 移除对应行 |
| `backend/app/job_analysis/README.md` 的 canonical_catalog/role_classification 保留说明 | 目录被删 | 更新为退役说明 |

## 保留清单

- `job_analysis/delivery/`：统一新分析、恢复、比较、候选维护、图谱快照。
- `job_analysis/product/`：`data/local/m2-product` 只读历史与 delivery 共用租约。
- `job_analysis/foundation/`：输入、摘要、路径边界、只追加存储与发布。
- `job_analysis/understanding/`、`knowledge/`、`work_candidates/`：P1/P2/P3/P4 现行链。
- `job_analysis/baseline/`：P0 契约、签审输入与评价工具；`contract.py` 是现行语义契约。
- `job_analysis/semantics/`、`screening/`、`governance/`：保留 `semantics.models` 供现行链使用；三个离线运行器仍由 `graph/real_pipeline.py` 消费，属 M3 历史来源图链，本轮不改。
- M2 路由的输入分页、历史运行/条目/报告/审核导出、版本比较、候选/技能维护与两类图谱。
- 部署中 Redis `cache` profile 与 Neo4j `graph-db` profile（设计 §4.3/§5.1 要求保留可选 profile，不进入默认启动）。

## 删除清单

1. `backend/app/job_analysis/canonical_catalog/`（9 个跟踪文件：models/runner/store/CLI、candidates v1/v2、release、source 文本）。
2. `backend/app/job_analysis/role_classification/`（28 个跟踪文件：B3-0 角色断言、proposals/boundaries/governance 运行器与 family 目录）。
3. `backend/tests/test_job_analysis/test_canonical_catalog.py`、`test_canonical_catalog_storage.py`。
4. `backend/tests/test_job_analysis/test_role_boundaries.py`、`test_role_boundary_claims.py`、`test_role_boundary_storage.py`、`test_role_classification.py`、`test_role_family_versions.py`、`test_role_governance.py`、`test_role_governance_storage.py`、`test_role_proposals.py`。
5. `backend/tests/fixtures/role_classification/`（仅上述测试使用）。
6. `backend/app/llm/`（`__init__.py`、`client.py`）。
7. `backend/app/db/redis.py`。
8. `backend/tests/test_llm_client.py`；`test_db_integration.py` 的 redis 部分；`test_config.py` 的 REDIS/OPENAI 字段。
9. `backend/requirements.txt` 的 `openai==1.51.0`、`redis==5.0.8`。
10. `backend/app/config.py` 的 `redis_url`、`openai_api_key`、`openai_base_url`。
11. 部署与 CI 中的 REDIS/OPENAI 配置（见上表）；不删除 Redis `cache` profile 服务定义。

## 明确不删除

- `data/local/m2-product`、`data/local/m2-delivery`、`data/local/m2-p5-p6-20261107`、`exchange/m2`、MySQL/SQLite、持久卷与任何真实运行记录。
- `backend/app/job_analysis/data/`（已忽略的本地中间产物）。
- `graph/delivery_bundle.py`、`graph/product_bundle.py`、`graph/real_pipeline.py`、`graph/real_quality.py` 与 M3/M4 代码；其保留依赖 `screening/semantics/governance` 同步保留。
- Git 历史；删除的实现只能从历史找回，不在工作区建立兼容目录。

## 实施步骤

1. 删除 canonical_catalog、role_classification 及其测试/夹具；确认没有保留模块 import 它们。
2. 删除 `app/llm`、`app/db/redis.py`、对应测试与配置字段；从 `requirements.txt` 移除 `openai`、`redis`。
3. 更新 `test_config.py`、`test_db_integration.py`；确认 config 必填项只剩 MySQL/Neo4j。
4. 更新 `backend/.env.example`、`deploy/.env.example`、`deploy/compose.yml` backend 环境、`deploy/scripts/install.sh`、部署 shell 测试、`m2-delivery.yml`、`scripts/package-deploy.sh`、`.gitattributes`。
5. 更新 `backend/app/job_analysis/README.md` 的退役清单；不重写历史报告与产品决策。
6. 全局 `git grep` 核对无残留 import/符号，运行后端与前端验证。

## 验证

- `cd backend && .venv/Scripts/python.exe -m pytest -m "not integration" -q`，输出重定向临时文件只读尾部；记录与本轮无关的已知偶发失败。
- `cd frontend && pnpm test && pnpm run typecheck && pnpm run build`；不可用则明确说明。
- `git grep -n "canonical_catalog\|role_classification\|app\.llm\|db\.redis\|OPENAI_API_KEY\|REDIS_URL"` 确认无残留代码/部署引用（历史文档、`data/local` 与 git 历史除外）。
- `git diff --stat` 只包含本计划与计划内文件。
- 不启动 Docker、不访问外部模型/招聘站、不触发真实 M2 分析；不修改 `data/local` 或数据库。

## 风险与说明

- 删除 canonical_catalog/role_classification 会移除 B3 草案目录的离线校验能力；这些对象从未进入正式职业目录，原实现与资产保留在 Git 历史。
- `graph/real_pipeline.py` 仍 import `screening/semantics/governance`，因此本轮不能删除这些离线运行器；若 P5 退役该 M3 离线链，再一并删除并补测试。
- Redis `cache` 与 Neo4j `graph-db` 仍可作为显式 profile 启动，但后端不再读取 Redis；默认 compose 不会启动它们。
- 本轮只做离线测试，不声称线上七页已人工复验；M2 新建分析与真实模型执行仍未验证。
- 根 README 对 Redis/Neo4j 的概述与产品文档同步留在 Release 文档事项，不在本清理中改写历史说明。
