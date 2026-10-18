# Career Nebula M3 Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 真实 M3 接入与 P1-A.2 独立可回退待审候选。
**Architecture:** visual-lab 只读打包快照，纯适配器保留身份/关系/来源，批处理渲染；历史两版 Git replay 比较。
**Tech Stack:** 现有 Three.js、Vite、Node test runner。
**Spec:** ../specs/2026-10-18-nebula-m3-candidate-design.md

## Global Constraints

- 不写数据库、不覆盖 exchange、不合并、不替代产品验收。
- 固定 214200 装饰粒子，知识图计数独立；保护历史证据及其他工作树。
- 候选端口 18127；保留原 /graph 与 ?data=demo 回退。

## Review Focus

- 重复 ID、悬空边、未知类型显式失败，不回退合成成功页。
- 空筛选与隐藏选中节点不继续命中。
- 多边与 nullable 历史语义不去重/布尔化。
- 布局不伪称职业分类，失败不伪装真实数据。
- 11412 边不能产生逐边 draw call；回退必须实测。

### Task 1: 数据适配与消费

**Files:** visual-lab/src/m3-adapter.js、knowledge.js、main.js、index.html、style.css、vite.config.js、tests/m3-adapter.test.js。
**Interfaces:** adaptM3(graph) -> {nodes,edges,provenance}; filterGraph(graph,{kind,query,focus}) -> {nodeIds,edgeIndices}; createKnowledge(scene,graph)。

- [ ] 测试正式快照 7845/11412、raw/index/id 保留、重复/悬空/未知类型失败、诱导子图、邻接与 null 语义；观察 RED。
- [ ] 实现适配/只读打包/批处理关系、筛选搜索详情；npm test、npm run build GREEN；独立提交。

### Task 2: 视觉与证据

**Files:** visual-lab/src/config.js、generate.js、particles.js、diagnostics.js；docs/review/issue-26-p1-a2/；阶段报告。
**Interfaces:** 保持 createDust(scene)；诊断增加真实/可见数量与 draw call。

- [ ] 先测试旋臂密度保留、有限坐标与少量间隙星点 RED，再从 P1-A shader 做最小分布调整 GREEN。
- [ ] 五视图三版本同条件截图与每视图 300 帧性能，另测 M3 请求/选择/筛选/缩放/回退/失败。
- [ ] 记录源哈希、字段索引、旧 builder/离线修复/正式交接差异、回退操作；完整相关回归。
- [ ] 独立审阅修复实质问题，更新资产/决策/README，提交并创建 Draft PR，注明待视觉验收。

## 执行记录

- 独立 builder-check：nothing important left。
- 工程选择依据用户完整任务书执行，无新增产品裁决。
