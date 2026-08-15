# 计划 0 — 契约与集成（A）Implementation Plan

- **日期**: 2026-08-08
- **负责人**: A（同学 1，兼数据采集与集成）
- **依赖**: 现有 FastAPI 骨架、ddl.sql（8 表已冻结）、旧计划已归档（D21）
- **依据**: `docs/superpowers/specs/2026-08-03-team-plan-design.md` + `docs/superpowers/决策跟踪.md`（D1–D21）
- **格式说明**: 本计划不锁定技术栈（D5）；接口由模块自定并附接口自述，A 集成时统一（D19）；只锁数据契约与交接规范

**Goal:** 冻结交接文件格式与"接口自述"模板，明确三个轻量惯例；A 搭建 exchange 规范、导入脚本与 Mock API，解锁 M1~M5 并行开发；最终由 A 联调出 MVP。

## Global Constraints

- **数据契约**: `backend/app/contracts/ddl.sql` 8 张表冻结；exchange 文件字段与 ddl.sql 一致（加表/加字段自由，改/删字段全队通知）
- **三个轻量惯例（D20，全队必须遵守；各模块计划中已分别强调）**:
  1. 统一响应 `{code, message, data}`，`code=0` 成功（仅接口层）
  2. 字段命名一律 snake_case
  3. Mock 先行：下游数据未到位时使用 Mock，禁止互相等待
- **交接规范**: UTF-8、JSON 数组、目录 `exchange/<模块>/`、每个模块随产出物附一页接口自述（D19）
- 技术栈: A 自选；优先复用现有 FastAPI 骨架（复用 > 重写）

## 文件结构（本计划创建）

```
exchange/
  README.md                  # 交接规范（编码/命名/目录/更新规则）
  接口自述模板.md             # 一页式模板：路径/入参/出参/字段/示例
  mock/
    jd.json                  # M1 样例（可先用现有 3 行 jd_pool 导出）
    skill_dict.json          # M2 样例（M2 未交付前占位）
    job_definition.json      # M2 样例
    job_skill.json           # M2 样例
    graph.json               # M3 样例
backend/app/integration/
  import_exchange.py         # exchange 文件 → MySQL（A 实现）
  import_graph.py            # graph.json → Neo4j（A 实现）
backend/app/routers/
  mock_router.py             # Mock API（读 exchange/mock，统一响应）
```

## Task 1: exchange 交接规范与模板

**Files:** `exchange/README.md`、`exchange/接口自述模板.md`、`exchange/mock/*.json`

**Consumes:** ddl.sql 字段定义
**Produces:** 全队统一的文件交接规范、接口自述模板、Mock 样例

- [ ] 1. 写 `exchange/README.md`：编码 UTF-8、JSON 数组、snake_case、`exchange/<模块>/<产物>.json`、加字段自由/改删通知
- [ ] 2. 写 `exchange/接口自述模板.md`：接口名、路径、方法、入参/出参 JSON、字段含义、一个示例、更新日期
- [ ] 3. 生成 5 份 Mock 样例：jd.json（从现有 jd_pool 导出）、skill_dict/job_definition/job_skill/graph.json（手工占位样例，字段与 ddl.sql 对齐）
- [ ] 4. 验证：每份 Mock 文件通过 JSON 校验，字段名全部 snake_case
- [ ] 5. 提交：`chore: exchange 交接规范与 Mock 样例`

## Task 2: exchange → MySQL 导入脚本

**Files:** `backend/app/integration/import_exchange.py` + 测试

**Consumes:** exchange/*.json
**Produces:** `import_exchange(path, table)` —— 按文件类型写入 jd_pool/skill_dict/job_definition/job_skill/job_change_log

- [ ] 1. 写失败测试：读样例文件 → 期望字段映射正确（mock 数据库）
- [ ] 2. 实现导入脚本：字段白名单与 ddl.sql 对齐；重复导入需可重复执行（先清同 source/同批次再写或 upsert）
- [ ] 3. 集成验证：导入 mock 样例 → 查询各表行数与字段一致
- [ ] 4. 提交：`feat(integration): exchange 导入 MySQL`

## Task 3: graph.json → Neo4j 导入

**Files:** `backend/app/integration/import_graph.py` + 测试

**Consumes:** exchange/mock/graph.json
**Produces:** Neo4j 节点（Job/Skill）与关系（REQUIRES/RELATED_TO）

- [ ] 1. 定义节点/关系字段映射（与设计文档 §7 一致：Job 对齐 job_name，Skill 对齐 skill_dict.canonical）
- [ ] 2. 实现导入：读取 graph.json → Cypher MERGE；幂等（重复执行不产生重复节点）
- [ ] 3. 集成验证：导入后 Cypher 查询节点/边计数正确
- [ ] 4. 提交：`feat(integration): graph.json 导入 Neo4j`

## Task 4: Mock API 骨架

**Files:** `backend/app/routers/mock_router.py` + 契约测试

**Consumes:** exchange/mock/*
**Produces:** `/jobs`、`/graph/overview`、`/graph/job/{id}`、`/resume/analyze`、`/match` 的 Mock 实现（统一响应 `{code,message,data}`）

- [ ] 1. 写契约测试：五个端点均返回统一响应结构、snake_case 字段
- [ ] 2. 实现 Mock：从 exchange/mock 读取数据返回；简历/匹配返回占位结果
- [ ] 3. 验证：`pytest` 通过；`/health` 与 Mock 端点冒烟
- [ ] 4. 提交：`feat(integration): mock api`

## Task 5: 契约公告与 MVP 联调准备

- [ ] 1. 更新 `docs/superpowers/决策跟踪.md` 未决项（如 exchange 格式定稿）
- [ ] 2. 通知全队：exchange 规范 + 接口自述模板 + 三个轻量惯例
- [ ] 3. 确认 M1~M5 均可从 Mock 开工，无人阻塞

## 验收标准

- exchange 规范与 Mock 可被 M1~M5 直接使用
- 导入脚本对 Mock 样例可重复执行（幂等）
- Mock API 满足统一响应与 snake_case 约定

## 自审说明

- 无 TBD/占位；字段与 ddl.sql 一致；不锁定技术栈；范围聚焦交接与集成，不实现业务逻辑（M2/M3/M4 各自负责）
