# M3｜节点引导银河统一空间候选

> **2026-10-22 状态更新：** 用户已实际查看并认可 `node-field-v1`，现已作为普通 `/#/graph` 的默认空间；`?graphSpace=legacy#/graph` 保留 P2.5 回退。下方“显式候选、省略参数恢复旧空间”等原始交付记录保留为当时状态，不再描述当前默认模式。

2026-10-20，Asia/Singapore。源码增量已实现、定向验证；**正式Vue真实图集成、可比前台FPS与最终视觉验收仍未完成**。保持显式候选，不替换默认P2.5，不合并PR。

## 基线与范围

- 工作树 `C:/Users/Serena Lyric/.codex/worktrees/m3-m5-p25/TalentMind`；预期及实际分支 `codex/m3-m5-p25`，起始干净，HEAD `fb68d3b7bd9dffdd33ed43c78b8387d5a8d31362`。开始的进程清单没有Vite/esbuild；其他Node进程未停止。只启动本任务预览18161。
- 继续现有 [Draft #37](https://github.com/Serena-Lyric/TalentMind/pull/37)，base仍为P2.5文档分支，不新建工作树/PR。空间实现独立提交 **`82192b3`**，定向审查 `fb68d3b..82192b3`；P2.5原提交与既有证据保留。
- 本分支没有任务书，从 [#39@e20e6ff](https://github.com/Serena-Lyric/TalentMind/blob/e20e6ffb9dd524aefbf1aa568ec27ee89cda0c31/docs/superpowers/plans/2026-10-20-m3-node-guided-galaxy-field.md) 只读取得；其中新建分支/PR的历史说明由本轮用户要求覆盖。执行记录见[实施计划](../superpowers/plans/2026-10-20-node-field-implementation.md)。
- 未改B1/B2、数据库、正式图谱、M3计算布局、其他成员工作树和非图谱页面。#38/#40的私有layout只读，未复制私有图、原文、来源索引或SQLite到本分支/公开目录。

## 实际改动

`GalaxySpatialField.ts` 消费 `layoutVersion / snapshotHash / positions / seed / viewSize`。positions直接来自真实知识层的 `spatialPoint` 结果：二维位置缩放1/30，Y沿用 `display-depth-v1`。节点位置、身份、关系端点与业务事实完全不调整，不产生新职业分类或社区。

固定128×128网格双线性沉积节点质量与展示高度，经X/Z可分离高斯平滑，累计分布二分采样；高度采用同核的加权展示深度。候选核宽11世界单位，边界至少覆盖200宽的基础空间及所有节点外缘4σ。背景dust/mist/stars保留45%原采样、55%节点密度；core保留75%原分布、25%节点影响。远景球壳field维持旧算法。参数是工程候选，非用户批准的美术定值。

这会改变**既有预算内背景粒子的总体分布**；不是给节点周围加点。原214,200背景粒子不增加，原94,140历史过渡点不增加。`tint`、`FAMILIES`、config、蓝紫色主题及星体shader未改，颜色仍按最终采样位置进入原tint函数。

精确缓存键包含完整排序ID/XYZ、布局/快照/深度/场版本、seed、世界范围；只保留最近一项，不用可能碰撞的短hash裁决命中。成本为排序O(N log N)、沉积O(N)、固定网格可分离核平滑和每粒子O(log 16384)，无N×粒子循环。`viewSize=200`是世界范围，像素resize不改世界坐标；相机orbit/roll/zoom与帧循环均不重建场。相同场复用现有GPU属性，变化时释放旧几何属性再替换，材质保留。

数据就绪与背景就绪两条路径均调用同步入口。失败时清除候选场、知识节点、关系几何和标签画布；卸载清缓存并走原GPU/帧循环释放。单元/SFC测试不执行真实mounted/unmounted调度，初始化交错及长期GPU泄漏尚不能据此认定全部验收。

## 运行与回退

在frontend运行 `pnpm test`、`pnpm run build`；本次正式生产构建预览：

```text
node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 18161 --strictPort
http://127.0.0.1:18161/?graphSpace=node-field-v1&nebulaDebug=1&freezeVisual=1#/graph
```

页面演示账号登录。候选 `graphSpace=node-field-v1`；`graphSpace=legacy` 或省略参数立即恢复P2.5旧空间。`graphStars=p24`、`graphStars=p23`、固定投影与旧Canvas回退仍保留。固定投影不会启用新场；没有增加常态设置面板。候选提示和回退位于折叠技术区。

## 自动验证与审查

| 检查 | 本轮结果 |
|---|---|
| 前端真实测试 `pnpm test` | **99 passed / 0 failed**，约7.37s；原93项+新增6项 |
| `pnpm run build` | vue-tsc与Vite均exit 0；Vite约12.30s，原大chunk警告保留 |
| M3离线回归 | `test_m3_candidate_layout.py`、`test_m3_graph_integrity.py`、`test_graph.py`：**45 passed**，0.14s；未运行数据库集成测试 |
| 空间分布/缓存 | 移动71个合成节点使110000个dust整体质心随之移动；保留跨区基础旋臂、预算不变；原7845坐标全部有限；空集逐字节回退；输入反序复现；坏/重复坐标拒绝；所有空间输入均使缓存失效 |
| 实际几何 | field变更使真实BufferGeometry分布变化；同field/resize/update保留属性引用与材质；回legacy恢复原数组 |
| Vue数据路径 | 真实SFC buildLayout更新背景；真实知识层先画24个关系顶点，再触发加载失败，最终关系drawRange=0、知识/缓存清空 |
| 原实现兼容 | [compatibility.json](m3-node-field/compatibility.json)：五层×四属性共20组数组与fb68d3b旧生成器字节完全一致；7项受保护输入/视觉/相机文件与Git基线LF一致 |

RED记录：最初新模块缺失；真实dust尚无setField；改变seed但粒子数组仍相同；审查指出的失败残线24≠0，均在后续实现/修复后转绿。独立只读审查发现1项Important（空图保留关系/标签），已用真实资源测试修复；Minor为mounted/unmounted与GPU长期验证不足，保留本节限制，不冒充独立产品验收。

正式graph.json当前字节SHA-256仍为 `6565d56dbc5a267eb90144f078c54f3d0c761c9a98ca29a18b4dc9c6cdde38e2`；layout字节SHA仍为 `dd33f0b17b4960b7d414cd47ce5097f3bd637ed9661c616bfae84e65fdc2481e`。故障与教训见[陷阱记录](../superpowers/traps/2026-10-20-galaxy-spatial-field-and-empty-layer.md)。

## 真实输入空间统计

复现脚本 `frontend/scripts/measureGalaxyField.ts`，命令 `node --experimental-strip-types scripts/measureGalaxyField.ts [显式layout路径...]`。不读原文或数据库，不输出节点身份。完整结果与各版本粒子摘要见 [spatial-metrics.json](m3-node-field/spatial-metrics.json)。

方法：XZ平面[-120,120]的40²格，比较粒子计数与所有知识节点σ=11高斯密度的Pearson相关；空区定义为格中心离所有节点超过22世界单位。非背景球壳的212000点参与all统计，dust单列110000点。该二维分箱指标不衡量知识语义、Y轴匹配或用户美术感受，也不能独自证明视觉连续性。

| 输入 | dust相关性 旧→新 | all相关性 旧→新 | all空区比例 旧→新 | 场构建 / 粒子生成旧→新 |
|---|---|---|---|---|
| 历史7845 | 0.620→0.906 | 0.396→0.623 | 3.45%→1.72% | 39.9ms / 470→491ms |
| #38首轮真实71 | 0.601→0.874 | 0.572→0.717 | 5.70%→3.31% | 11.1ms / 456→473ms |
| #40第二轮真实52 | 0.652→0.900 | 0.633→0.770 | 7.37%→4.41% | 18.7ms / 782→773ms |

单次Node进程计时有JIT/系统负载差异，不是稳定性能基准。三个输入反序重放粒子字节一致，没有非有限输出；52档有1个点落在统计框外（约0.00047%），不等于被丢弃。原节点/边从未改写；“全知识节点纳入密度”不表示每个节点都有同数星尘或每个节点在全景LOD显示。

71节点来自#38工作树 `data/local/real-e2e-20261020-v2/layout.json`（SHA见JSON），52节点来自#40工作树 `data/local/quality-round2-v3/layout.json`。本分支历史加载器仍固定7845/11412及历史摘要；**没有冒用历史图入口加载真实事实图，71/52正式Vue全景、近景、侧视、拾取、来源回溯与切换均待后续集成验收**。

## 实际浏览器证据

Edge、正式Vue生产构建、相同历史输入/seed、冻结视觉时钟。每张JPG配同名JSON保存视口、DPR、相机、节点/边及场诊断。不是ImageGen概念图。原有P2.5证据未覆盖。

[paired-checks.json](m3-node-field/paired-checks.json) 已断言六组相机/输入/视口逐项一致（1699×948、DPR1.5），新场旋转重置与原全景相机也精确一致。这里只证明配对条件，不以相机JSON代替图像视觉判断。

| 视角 | P2.5旧空间 | node-field-v1 |
|---|---|---|
| 全景 | [旧](m3-node-field/legacy-overview.jpg) | [新](m3-node-field/guided-overview.jpg) |
| 中景 | [旧](m3-node-field/legacy-middle.jpg) | [新](m3-node-field/guided-middle.jpg) |
| 近景 | [旧](m3-node-field/legacy-near.jpg) | [新](m3-node-field/guided-near.jpg) |
| 倾斜侧视 | [旧](m3-node-field/legacy-side.jpg) | [新](m3-node-field/guided-side.jpg) |
| 旋转/尾部视角 | [旧](m3-node-field/legacy-tail-orbit.jpg) | [新](m3-node-field/guided-tail-orbit.jpg) |
| 旋转后重置返回 | [旧](m3-node-field/legacy-returned.jpg) | [新](m3-node-field/guided-returned.jpg) |

新全景比旧图的暗旋臂间区更有填充，外缘更贴近知识密度；代价是艺术旋臂对比变弱。侧视仍保持盘状厚度。密集知识星体可读性和主观视觉接受度仍需用户判断，不能由相关性增幅代替。

额外保留Python222关系、原索引0高亮、近距离观察/返回、实际Q滚转0.12的截图与状态。搜索选中未改变全景相机；关系端点仍走原共享positions。平滑返回的部分截图采在过渡中，不能将其当作精确终态相等证明；相机终态数值及222条原边端点有原自动回归覆盖。

实际鼠标点击选择岗位 `job:j-45a56f1e0a55f89a`，12条真实直连均提交，相机保持原全景；见 [拾取截图](m3-node-field/guided-pointer-selected.jpg)。最终会话控制台warn/error列表为空。同输入“刷新数据”后场builds=1、hits=1、粒子重建0ms；[刷新前](m3-node-field/guided-before-refresh.json)/[刷新后](m3-node-field/guided-after-refresh.json)保留完整资源采样。短次刷新不等于长期泄漏验收。

## 性能与验收限制

历史浏览器首次候选场约35–46ms、随后粒子重建约749–757ms；初始旧背景也会先生成一次，候选首次进入因此增加一次生成开销。之后旋转、缩放、Q滚转的场builds仍为1。总点数/Shader与默认绘制预算未增加；没有每帧场计算。

早期guided全景148样本帧间隔p50=33.4ms、p95=34.2ms（约30FPS）。后续浏览器后台/遮挡节流使新旧两者都出现约1000ms间隔，拖动样本又混有前台帧；**这些混合窗口不能构成可比前台FPS或“无性能退步”的结论**。所有原始采样保留，未删掉慢样本。长期GPU释放/稳定前台性能需后续实机复验，不据本轮短样本声称无内存泄漏。

本轮M3测试未连接MySQL/Neo4j，不存在数据库夹具或生产数据删除。旧builder测试向本任务忽略目录 `data/local/node-field-pytest/` 生成6个graph.json；自动审批两次拒绝清理（含逐文件安全版本），仅返回“blocked by policy”。6个测试JSON及8个目录仍保留、未提交；正式graph.json与layout摘要已核对不变。此项清理没有完成，不能记为D37闭环通过。

## 后续明确待验收

1. 把独立空间场增量与#38真实图消费者受控集成后，对71/52做正式Vue成对截图、切换、来源/拾取验证。
2. 相同可见前台条件重测新旧稳态/交互FPS、GPU资源及多次加载卸载，不用后台节流样本下结论。
3. 用户评判旋臂连续性、知识星体融合与密集可读性；当前只保持显式候选开关。
4. 获允许的文件清理方式后清除本次6个隔离测试产物；不清理任何真实数据。
