# 系统整合实施计划（2026-08-13）

- **状态**: 未决项已裁决（D26–D36），本计划生效，分阶段执行
- **依据**: `specs/2026-08-03-team-plan-design.md`（数据契约 §6 / 图谱 §7 / 接口 §9 / 反幻觉 §10）+ `specs/2026-08-11-repository-organization-design.md`（目录边界与迁移顺序）+ `plans/2026-08-08-plan0~M5` + `决策跟踪.md` D26–D36
- **范围**: 把根目录四个交付模块（`jd-filter-package/` M2、`图谱模块/` M3、`岗位能力图谱-前端源码/` M5、`人岗匹配/` M4）迁入正式目录，统一契约与接口，清理重复，形成可整体运行的系统（M1→M2→M3→M4→M5 + A 集成 API）
- **门禁**: 每阶段完成 → 测试/验证通过 → 进入下一阶段；任何阶段失败先回滚该阶段改动，记录陷阱

## 阶段 0：决策与文档落地（已完成）
- [x] 决策跟踪 D26–D36 记录
- [x] 删除 `jd-filter-package/data/seed_jd_pool.sql`（421MB，D27；gz 备份保留）
- [x] 资产与状态.md / CLAUDE.md / README.md 同步
- [x] 补齐 `jd-filter-package/requirements.txt`（httpx==0.27.2 / pydantic==2.12.0 / pytest==8.3.3，与 backend 对齐）
- [x] `run.bat` 改为纯 ASCII（0 非 ASCII 字节）
- [x] `.gitignore` 更新：图谱模块 `.idea/`、`lib/`、`job.db`、`output/`；jd-filter `.pytest_cache/`、`data/`、`result/`（防误 add）
- [ ] **通知全队**（由用户执行）：D31 change_type 扩展枚举、D33 experience 扩容为后续项（执行前再次提醒）

## 阶段 1：契约与基础对齐
1. [x] **skill_dict 种子（D31）**：`backend/app/skills/skill_dict_seed.json` 已生成（**285 canonical / 297 aliases**，10 分类）；`tests/test_skill_seed.py` 4 项通过（canonical 唯一、alias 无冲突、数量 ≥200）。
2. [x] **DDL 契约更新（D32）**：`job_change_log.change_type` 注释已补充扩展取值（duties_changed/scenarios_added/scenarios_removed/evolution_changed）；未改字段结构。通知全队由用户执行。
3. [x] **统一响应 code=0（D29）**：图谱 `Response.success` 已改 0；前端 `request.ts` 已启用 `code !== 0` 校验；接口文档 16 处 code 已改 0。后端 M1 `ok()` 原本为 0。
4. **experience 扩容（D33，暂缓）**：只登记提醒项；**不执行** DDL/代码修改。

## 阶段 2：M2 迁入 `backend/app/job_analysis/`（已完成）
1. [x] 源码 14 个 py → `backend/app/job_analysis/`，import 统一为 `app.job_analysis.*`；`config.py` 路径指向仓库根 `exchange/m2` 与 `backend/app/skills/skill_dict_seed.json`。
2. [x] 测试 → `backend/tests/test_job_analysis/`（58 项通过）；`test_db`/`test_integration` 改用小样例 `backend/tests/fixtures/job_analysis/seed_jd_pool.sql`（10 条，覆盖乱码/重复/空字段）。
3. [x] **skill_dict 约束接入（D31）**：`stage3_extract.py` 注入 canonical 列表 + 别名映射；未命中技能进 `unknown_skills`，不进正式技能；seed 小写归一（285 canonical / 122 aliases）。
4. [x] 输出目录 `exchange/m2`（小写）；预跑 7 个产出 JSON 已复制到仓库根 `exchange/m2/`；`main.py` 帮助文本更新。
5. [x] backend 全量回归通过（156+）。
6. [x] 交接验证：`exchange/m2/*.json` 为 UTF-8 JSON 数组、snake_case。

## 阶段 3：M3 迁入 `backend/app/graph/`（已完成）
1. [x] `图谱模块/graph.py` → `backend/app/graph/builder.py`（+ `__init__.py`）；测试 → `backend/tests/test_graph.py`（pytest 化，7 项通过）。
2. [x] 契约对齐：job 节点 id=job_name、skill 节点 id=canonical（小写唯一）；未归一技能跳过并警告（D31）；`metadata.exported_at` 动态时间；Response code=0（D29）。
3. [x] 数据源：默认 `exchange/m2/job_definition.json`，mock 回退（`exchange/m3/mock_job_data.json` 已复制）。
4. [x] 产物 `exchange/m3/graph.json`（mock 数据构建：53 节点 / 81 边）；`job.db`/`lib`/`.idea`/`output` 已加忽略（D28）。
5. [x] 测试通过；Neo4j 导入联调在阶段 6 执行。

## 阶段 4：M5 迁入 `frontend/`（已完成）
1. [x] `岗位能力图谱-前端源码/` → `frontend/`（24 个 src 文件 + public/配置/文档）；`README.md` 更新为项目说明。
2. [x] `request.ts` 已启用 `code !== 0` 校验（D29）；`USE_MOCK=true`、`VITE_API_BASE_URL` 逻辑保留。
3. [x] 保留 6 页（D26），路由/导航不变。
4. [x] 构建验证：`pnpm install`（修复 package.json BOM + `pnpm approve-builds --all` 放行 core-js/esbuild/vue-demi 构建脚本）+ `pnpm run build` 通过（11.4s）。注：chunk >500kB 为体积警告，非阻塞。

## 阶段 5：M4 迁入 `backend/app/matching/`（已完成代码迁移与契约对齐）
1. [x] 源码 8 个 py → `backend/app/matching/`（import 统一 `app.matching.*`）；`canonical.py` 归一模块；测试 → `backend/tests/test_matching.py`（5 项通过）；fixtures → `backend/tests/fixtures/matching/`（生成 JSON + 文本样例）；UI 原型 → `docs/prototypes/matching/`（index.html + SPEC.md）。
2. [x] 真实简历（`岗位测试用例/*.pdf/*.docx`）**未迁移、未提交**（D36）。
3. [x] 技能对齐：`matcher.py` 输出技能 canonical 化（D31）；输出含 `matched_skills/unmatched_job_skills/resume_extra_skills`，无 status。
4. [ ] `exchange/m4/` 运行说明与接口自述（/resume/analyze、/match）——阶段 6 与 API 一并补充。
5. [x] 文本解析/匹配测试通过；PDF/DOCX 解析依赖（pdfplumber/python-docx/mammoth）**未安装**（文本模式可运行，文件解析为可选功能，见资产清单）。

## 阶段 6：A 集成层（MVP 子集已完成）
1. [x] `import_exchange.py`：skill_dict（285）/ job_definition（8）/ job_skill（8）/ job_change_log（0）导入 MySQL，按 job_name 先删后插，幂等。
2. [x] `import_graph.py`：graph.json → Neo4j（Job/Skill MERGE + REQUIRES/RELATED_TO），幂等；当前 53 节点 / 81 边。
3. [x] `routers/mvp.py` **MVP 5 接口**：GET /api/jobs、GET /api/graph/data、GET /api/graph/jobs、GET /api/graph/years、POST /api/resume/upload、GET /api/resume/target-jobs、GET /api/resume/skill-dimensions（7 个端点）；统一 `{code:0,message,data}`、snake_case；main.py 挂载 `/api`。
4. [x] 测试：`tests/test_integration_mvp.py` 5 项通过（导入幂等 + API 冒烟）；全量 185 通过；HTTP 冒烟：/health、/api/jobs（total=8）、/api/graph/data（53/81）、/api/resume/upload（score=12, target=...）。
5. [ ] 剩余 14 个接口（jobs CRUD/import/export、dashboard 5、graph skill-radar、learning 等）→ MVP 联调后按需补全；前端 `USE_MOCK=false` 联调待后端 CORS/部署配置。

## 阶段 7：端到端验证与清理
1. 全量测试：backend 94+12 + 各迁移模块测试 + 新增集成检查。
2. 端到端冒烟：M1 数据 → M2 产出 → M3 graph.json → Neo4j 导入 → API → 前端页面（先 Mock 后真实）。
3. 清理（D24 门禁，全部验证通过后）：
   - 删除根目录 `jd-filter-package/`、`图谱模块/`、`岗位能力图谱-前端源码/`（Git 历史追溯）；
   - `人岗匹配/` 迁移验证通过后，删除源码/测试/UI 部分；**真实简历部分先与用户确认备份后处理（D36）**。
4. 更新资产与状态.md / README / CLAUDE / AGENTS / 决策跟踪。

## 风险与回滚
- **skill_dict 约束改变 M2 产出**：先建种子 + 样例验证（阶段 1 先行），再改 stage3；保留旧产出可回退。
- **421MB 输入已删**：管道输入改小样例/数据库导出；gz 备份可随时恢复原 SQL。
- **前端 20 接口实现量大**：按模块分批实现，先 6 个 MVP 接口（08-03 §9）打通，再补 CRUD/导入导出/看板。
- **人岗匹配真实简历**：全程只 add 明确文件，`git add -A` 禁止；删除前再次与用户确认。
- 未创建 Git commit（遵守"不主动提交"约定），完成关键里程碑后再统一提交。

## 验收标准（对应 08-11 完成标准）
- 每个模块只有一个正式源码位置（backend/app/ 或 frontend/）
- 交接文件可追溯到模块与契约版本；统一响应 code=0、snake_case
- 大型数据不被 Git 跟踪；旧重复目录验证后删除或有明确理由
- 全量测试通过；端到端可演示（M1→M2→M3→API→M5）