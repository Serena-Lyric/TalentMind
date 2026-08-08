# 计划 M5 — 前端三页 Implementation Plan

- **日期**: 2026-08-08
- **负责人**: M5（前端）
- **依赖**: plan0（Mock API 与接口自述）；M3/M4 的接口自述（A 定稿后切换真接口）
- **依据**: 2026-08-03-team-plan-design.md §9 + 决策跟踪.md；旧 planB 已归档（D21，页面范围以 2026-08-03 设计为准）
- **格式说明**: 技术栈 M5 自选（优先考虑 Vue3 + Vite，见有效信息汇总第三节）；接口先 Mock 后真接口（D19/D20）

**Goal:** 完成三个页面：所有岗位、图谱、岗位匹配；开发期用 Mock 不阻塞，联调期切换 A 定稿接口；图谱交互流畅、差距分析展示清晰（用户体验 15 分）。

## Global Constraints

- **三个轻量惯例（D20）**：只消费统一响应 `{code,message,data}`；字段 snake_case；Mock 先行
- 页面范围固定为三页（所有岗位/图谱/岗位匹配），不扩展旧 planB 的六页设想
- 图谱可视化优先考虑 G6（可交互、按技术栈/级别切换）
- 无后端逻辑；数据一律来自 API（开发期 Mock）

## Task 1: 工程初始化

**Files:** `frontend/`（自选脚手架）

**Produces:** 可本地运行的三页应用骨架（路由 + 布局）

- [ ] 1. 初始化工程（优先考虑 Vue3 + Vite + TypeScript）
- [ ] 2. 搭三页路由与统一布局（导航：所有岗位 / 图谱 / 岗位匹配）
- [ ] 3. 验证：本地 `npm run dev`（或等价）可访问三页
- [ ] 4. 提交：`feat(M5): scaffold three pages`

## Task 2: 所有岗位页

**Files:** `frontend/src/pages/Jobs.vue`（或等价）

**Consumes:** `GET /jobs`（Mock）
**Produces:** 岗位列表 + 搜索/筛选/分页

- [ ] 1. 用 Mock 数据实现列表与筛选
- [ ] 2. 验证：搜索/筛选/分页交互正常；加载态/空态/错误态齐全
- [ ] 3. 提交：`feat(M5): jobs page`

## Task 3: 图谱页

**Files:** `frontend/src/pages/Graph.vue`（或等价）

**Consumes:** `GET /graph/overview`、`GET /graph/job/{id}`（Mock graph.json）
**Produces:** 全景图谱 + 岗位技能子图（按技术栈/级别切换视图）

- [ ] 1. 集成图谱可视化（优先考虑 G6）：节点渲染、关系连线
- [ ] 2. 实现视图切换（技术栈/级别）与点击岗位看技能子图
- [ ] 3. 验证：Mock graph.json 渲染流畅；节点不重叠/可缩放拖拽
- [ ] 4. 提交：`feat(M5): graph page`

## Task 4: 岗位匹配页

**Files:** `frontend/src/pages/Match.vue`（或等价）

**Consumes:** `POST /resume/analyze`、`POST /match`（Mock）
**Produces:** 简历上传 → 解析技能 → 匹配度/已有/缺失/路径建议展示

- [ ] 1. 实现上传交互（PDF/DOCX）
- [ ] 2. 实现结果展示：匹配度、已有技能、缺失技能（清晰区分）、路径建议
- [ ] 3. 验证：Mock 流程完整；错误提示友好（格式不支持等）
- [ ] 4. 提交：`feat(M5): match page`

## Task 5: 切换 A 定稿接口

**Files:** `frontend/src/api/`（统一 API 层）

**Consumes:** A 定稿接口（D19）
**Produces:** Mock → 真接口切换（环境配置），联调通过

- [ ] 1. API 层统一封装；环境变量切换 baseURL
- [ ] 2. 与 A 联调三个页面
- [ ] 3. 验证：真接口下功能完整、错误码处理正确（code != 0 时提示）
- [ ] 4. 提交：`feat(M5): switch to real api`

## Task 6: 用户体验打磨

- [ ] 1. 对照评分项自查：图谱交互流畅、差距分析展示清晰、操作流程便捷
- [ ] 2. 录制演示视频素材（10 分钟视频的一部分）
- [ ] 3. 提交：`chore(M5): ux polish`

## 验收标准

- 三页可演示；Mock → 真接口可切换；图谱交互流畅；差距展示清晰

## 自审说明

- 页面范围与 2026-08-03 设计一致；只消费统一响应；不实现后端逻辑；D20 惯例贯穿
