# Issue #22 Career Nebula 实施计划

> For agentic workers: 按 executing-plans 逐任务执行，遵守 TDD；最终独立代码审查。用户已授权按 Issue #22 连续实现。

**Goal:** 修复关系定位与可见连线，保留默认 legacy 和原版外观。

**Architecture:** Canvas 保留。布局/边选择抽为纯逻辑；实验布局复用 G6 已依赖的 d3-force（3.0.0）固定 120 次计算，岗位与共享实体形成真实边骨架，共享实体按全部关联岗位质心定位，私有实体局部展开。输入先稳定排序且只复制，不修改业务图。实验版由 URL `nebula=experimental` 启用。

**Tech Stack:** Vue / TypeScript / Canvas / @antv/g6（锁定版本 5.1.1）/ Node 内置测试。

**Spec:** [Issue #22](https://github.com/Serena-Lyric/TalentMind/issues/22)

## Global Constraints

- 从 origin/master 425aef5 独立分支；保留原工作树未提交改动。
- legacy 默认；URL 位于 hash 前：`/?nebula=experimental#/graph`。
- 不改 CSS、导航、详情文案、M2、DDL、生产查询、导入或正式数据。
- 不生成业务边；布局骨架只使用输入真实边；PR #21 新身份不应用于现有图。
- 测试仅合成内存图；页面对照读取真实服务，无数据库写入。

## Review Focus

- 高度共享节点：所有关联岗位参与质心，聚焦关系完整且有限值。
- 空图、孤立节点与不存在端点：稳定回退、无 NaN、不绘制悬空边。
- 输入乱序及刷新：坐标与边集合确定；筛选/选择不重新布局。
- 超过默认预算的直连边：选择节点不截断，放大视口按需补全。
- 缩放/平移后命中与搜索：按实际屏幕半径命中，隐藏类型不被搜索选中。

### Task 1: 布局与回退

**Files:** 新建 frontend/src/graph/nebulaLayout.ts、frontend/src/graph/nebulaLegacy.ts、frontend/tests/nebulaLayout.test.ts；修改 GraphPanorama.vue、package.json。

**Interfaces:** buildLegacyLayout(nodes, edges): Map<string, Point>；buildRelationLayout(nodes, edges): Promise<Map<string, Point>>。消费者输入不变。

- [x] 保存真实页面四组基线、数据 hash 与尺寸。
- [x] 先写共享技能、输入乱序、高度共享、孤立节点测试；以 legacy 复现失败。
- [x] 抽出原算法，d3-force 骨架 + 全邻居质心 + 确定性局部分布；添加内部 URL 模式。
- [x] Node 测试与前端 build 通过，独立提交布局。

### Task 2: 边选择与交互

**Files:** 新建 frontend/src/graph/nebulaEdges.ts、nebulaViewport.ts 及定向测试；修改 GraphPanorama.vue。

**Interfaces:** selectEdges(edges, nodes, positions, options): GraphEdge[]；edgeStyle(edge, nodes) 返回虚线标志；视口转换/命中/聚焦纯函数。

- [x] 先写乱序、隐藏类型、坏端点、超过 900 条直连、真实三类关系、缩放/命中测试并观察失败。
- [x] 采用视口内真实边、节点覆盖优先、类型轮转的稳定预算；高倍缩放补全视口内关系；选择节点时返回所有可见直连，优先聚焦可用画布范围。
- [x] 只对岗位–岗位 related_to 画虚线；requires/applies_to 使用现有实线样式。
- [x] Node 全套与 build 通过，独立提交连线。

### Task 3: 验收与交付

**Files:** docs/review/M3-M5-issue-22.md、docs/review/issue-22/*、资产与状态、frontend/README、陷阱记录。

- [x] 同数据/尺寸保存四组实验版截图，并验证 legacy 回退；记录交互、总边/选中直连/实际绘制数及性能。
- [x] 独立代码审查、必要修复测试、最终 build、diff/hash/原工作树保护核验。
- [ ] 提交证据，普通推送独立分支，创建 PR 并附当前聊天；不合并或清理分支。

## 实测裁定

- G6 D3ForceLayout 包装器在后台页等待计时器，实测约 30.5s，且延迟 chunk 约 1.236MB。直接复用其底层已安装 d3-force，显式列为轻量直接依赖（无新增包/版本），固定 120 tick 后停止；新延迟 chunk 约 15.63kB。保留 G6 本身，未替换 Canvas。
- 实验版聚焦仅绘制选中节点和可见直连邻域，避免无关行业节点叠加遮线；命中候选与绘制集合保持一致。节点坐标不因聚焦或筛选重新计算。

- 独立审查两项Important：刷新旧选择/邻域及900px画布面板预留；已三项回归RED→GREEN，最终18项测试与build通过。相机现读取DOM实测边界。无Critical/Minor，其他美感/移动端/持续帧率由阶段报告列出边界。
