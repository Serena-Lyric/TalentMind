# 计划 M3 — 图谱 Implementation Plan

- **日期**: 2026-08-08
- **负责人**: M3（图谱节点/关系解析）
- **依赖**: M2（job_definition.json / job_skill.json / skill_dict.json）；plan0（graph.json → Neo4j 导入脚本）
- **依据**: 2026-08-03-team-plan-design.md §7（图谱契约）+ 决策跟踪.md；旧 planD 已归档（D21，可参考）
- **格式说明**: 不锁定技术栈（D5）；产出物为 graph.json 文件；接口自定（D19）；轻量惯例（D20）：snake_case、Mock 先行

**Goal:** 消费 M2 的结构化数据，把岗位关系解析成点和线，产出 `exchange/M3/graph.json`（nodes/edges），交付 A 导入 Neo4j；附图谱查询接口自述供 A 定稿。

## Global Constraints

- 节点：Job（对齐 job_definition.job_name）、Skill（对齐 skill_dict.canonical，技能必须已归一）
- 关系：REQUIRES（weight，required/bonus 标记）、RELATED_TO（技能关联）
- 数据来源可溯源：每条 REQUIRES 可追溯到 job_skill 的 evidence（反幻觉）
- M3 不连 A 数据库；本地可用 Neo4j Desktop/脚本预览，交接只交 graph.json

## Task 1: 图谱数据模型确认

**Files:** `exchange/M3/graph_schema.md`

**Consumes:** 设计文档 §7、ddl.sql
**Produces:** 节点/关系字段定义（字段名、类型、取值、与 M2 产出的对齐规则）

- [ ] 1. 写 graph_schema.md：nodes（id/name/type）、edges（source/target/rel/weight/required）
- [ ] 2. 全队过目确认（与 A 的 Neo4j 导入脚本对齐）
- [ ] 3. 提交：`docs(M3): graph schema`

## Task 2: 图谱构建器

**Files:** `backend/app/graph/builder.py`（或自选实现）+ 测试 + `exchange/M3/graph.json`

**Consumes:** job_definition.json / job_skill.json / skill_dict.json
**Produces:** graph.json（nodes + edges，UTF-8、snake_case）

- [ ] 1. 写失败测试：输入 M2 样例 → 节点/边数量正确；技能未归一时报错
- [ ] 2. 实现构建：Job/Skill 节点去重（按 name）；REQUIRES 按 is_required 标记、weight 取技能权重；RELATED_TO 可后续增强（P1）
- [ ] 3. 验证：节点数=岗位数+技能数（去重后）；每条边字段完整
- [ ] 4. 提交：`feat(M3): graph builder -> graph.json`

## Task 3: 本地可视化验证（可选，不阻塞）

**Files:** 本地脚本/Neo4j Desktop

- [ ] 1. 导入 graph.json 到本地 Neo4j 或渲染工具
- [ ] 2. 截图保存（答辩素材）：岗位→技能子图、技能关联
- [ ] 3. 记录验证结果到 `exchange/M3/verification.md`

## Task 4: 联调导入验证

**Consumes:** plan0 的 import_graph.py（A）

- [ ] 1. 与 A 联调：graph.json 导入 A 机 Neo4j
- [ ] 2. 验证：Cypher 查询 REQUIRES 关系正确、节点不重复（幂等）
- [ ] 3. 提交：`chore(M3): integration verified`

## Task 5: 图谱查询接口自述

**Files:** `exchange/M3/接口自述.md`

**Consumes:** 前端三页需求（M5）
**Produces:** 建议接口（供 A 定稿）：`/graph/overview`、`/graph/job/{id}`、可选 `/graph/skill-path`

- [ ] 1. 按模板写接口自述（入参/出参、字段、示例）
- [ ] 2. 提交

## 验收标准

- graph.json 可被 A 导入 Neo4j；节点/关系与 M2 产出一致且可溯源
- 图谱可截图展示（答辩素材）

## 自审说明

- 节点/关系契约与设计文档 §7 一致；只产文件不连库；RELATED_TO 明确为 P1，不阻塞
