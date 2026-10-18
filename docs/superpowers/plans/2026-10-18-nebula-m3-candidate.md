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

- [x] 测试正式快照 7845/11412、raw/index/id 保留、重复/悬空/未知类型失败、诱导子图、邻接与 null 语义；观察 RED。
- [x] 实现适配/只读打包/批处理关系、筛选搜索详情；npm test、npm run build GREEN；独立提交。

### Task 2: 视觉与证据

**Files:** visual-lab/src/config.js、generate.js、particles.js、diagnostics.js；docs/review/issue-26-p1-a2/；阶段报告。
**Interfaces:** 保持 createDust(scene)；诊断增加真实/可见数量与 draw call。

- [x] 先测试有限坐标/全分辨率边界 RED，再从 P1-A shader 做最小分布调整 GREEN。间隙比例测试本身在A1亦通过，不能单独证明改进。
- [x] 五视图三版本同条件截图与每视图 300 帧性能，另测 M3 请求/选择/筛选/缩放/回退/失败。
- [x] 记录源哈希、字段索引、旧 builder/离线修复/正式交接差异、回退操作；完整相关回归。
- [ ] 独立审阅修复实质问题，更新资产/决策/README，提交并创建 Draft PR，注明待视觉验收。

## 执行记录

- 独立 builder-check：nothing important left。
- 工程选择依据用户完整任务书执行，无新增产品裁决。
- Task 1: complete (994edb6..afd37d3, Node14/14，独立构建通过)。
- Task 2: visual code 2df4ff9；全分辨率边界7批次→5批次RED→GREEN；Node现13/13、浏览器15+24、五组对照/性能和构建后消费通过。
- Final review: Critical0/Important1/Minor0；畸形数组type已测试Missing expected exception RED→GREEN。详见阶段报告§7；没有再次派审阅。
- Ruling: 后端两个既有M2冻结引用失败保持原状并如实交付Draft，不夹带C35修复——本分支与基线的有关输入字节相同；代价是不能宣称全仓绿，合并审查仍有已知阻塞。
- Ruling: 继续保留历史haze-pass模块作A1实现证据，新版本不加载——符合用户保留实验要求；代价为一个不打包的历史文件。
