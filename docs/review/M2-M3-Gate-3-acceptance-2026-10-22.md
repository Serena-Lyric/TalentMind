# M2→M3 Gate 3 验收报告（2026-10-22）

> **结论：工程可用性条件通过；真实语义未验收。** 三个指定 v12 run 均从冻结 M2 报告独立生成候选图，完整性、版本、来源和证据位置对账通过；正式 Vue 页面、历史图往返及失败关闭实测通过。人工真值仍为 0，不计算真实 precision/recall，也不把候选陈述或大类候选写成正式需求/岗位。

## 1. 基线与环境

| 项 | 实际值 |
|---|---|
| 代码基线 | `master@0414a93329b1cbd1a4666783c8c44cc7af90a709` |
| 验收分支 | `codex/m2-m3-gate3-acceptance` |
| M2 版本 | `v12` |
| 冻结 v12 报告的 M2 实现摘要 | `676cda9db572422920c87b11a81695be1a15ad6b923eaad215bc06d1dd7f67f8` |
| Gate 3C 复审收口后当前 `versions('v12')` | `33782cb1c54e17c8a76cb82ae98da83bcf1b98fc23c1c133064c7085834de058`（只调整审核事件与有效视图，不改已有分析结果） |
| 图投影实现对象摘要 | `5c3ee13ee00a1f6db95071edfd0305b85266bd5a495ff9817b18ff5127c692ab` |
| Python / Node / npm | `3.14.5` / `24.15.0` / `11.12.1` |
| 图算法依赖 | `networkx 3.6.1`、`igraph 1.0.0`、`leidenalg 0.11.0` |
| 浏览器 | Microsoft Edge `155.0.4283.62` |
| 隔离页面 | 后端 `127.0.0.1:18101`，Vite `127.0.0.1:18181` |

执行前本地 `master` 与 `origin/master` 均在 `2de9c42`，任务指定提交尚未抓取。只执行了 `git fetch origin --prune` 和 `git merge --ff-only origin/master`，随后从指定基线创建验收分支。

## 2. Gate 3A：候选图工程验收

### 2.1 构建顺序与命令

严格按小样本 5 → 留出集 60 → 主集 120 顺序，使用现有 `product_bundle.build_bundle()` 从冻结 M2 报告投影。每个 run 位于独立 `data/local/m2-product/graphs/<run_id>/`，未复用 v9 图。

```powershell
cd D:\Application\ClaudeCode\repository\TalentMind\backend
.\.venv\Scripts\python.exe -c "from app.job_analysis.product.workflow import Workflow; from app.graph.product_bundle import graph_info; import json; w=Workflow('../data/local/m2-product'); r=graph_info(w,'276eb5469d704ead901c3ab8c63faf95',True); print(json.dumps(r,ensure_ascii=False,indent=2))"
.\.venv\Scripts\python.exe -c "from app.job_analysis.product.workflow import Workflow; from app.graph.product_bundle import graph_info; import json; w=Workflow('../data/local/m2-product'); r=graph_info(w,'0deea42f30ad4ef9bc91c61b3588b0ba',True); print(json.dumps(r,ensure_ascii=False,indent=2))"
.\.venv\Scripts\python.exe -c "from app.job_analysis.product.workflow import Workflow; from app.graph.product_bundle import graph_info; import json; w=Workflow('../data/local/m2-product'); r=graph_info(w,'5fab285c43414943a9ed239db04508ff',True); print(json.dumps(r,ensure_ascii=False,indent=2))"
```

完整逐边审计与隔离重生成：

```powershell
.\.venv\Scripts\python.exe ..\data\local\m2-m3-gate3-20261022\audit_bundles.py 0414a93329b1cbd1a4666783c8c44cc7af90a709 ..\data\local\m2-m3-gate3-20261022\gate3a-audit.json
```

### 2.2 run、输入与输出摘要

| 集合 | run | 输入 SHA-256 | 报告 SHA-256 | manifest SHA-256 | `data_version` |
|---|---|---|---|---|---|
| 小样本 5 | `276eb5469d704ead901c3ab8c63faf95` | `28ee686a364060792f414033216170a8c28ea327b1183c20fca8feb212637c1c` | `c7363726e768dc43356ad47533f1ade53dfba90d80b15ddc02d54d5bf797da64` | `043f228d972198227cd96fff87c80dd696961c10ef567030aca4feba8b283fa7` | `5996f55e8965932bd76117a357b22c1d799d1c91b745a9bf9a508705d6c70a3f` |
| 留出 60 | `0deea42f30ad4ef9bc91c61b3588b0ba` | `5752515313fa5df210c3b5552dd89c85014a2329330240f2bf8e1cb963132a34` | `440e48634a620a6c9a4d9bc5bdeb57c0faa42ae29cbdc261f1f9b8f696a5ee4f` | `9801b972f7ab7f133bd271273e7bc8a2c637dc5e265d83a6ebaec53f7ea88e08` | `b65454683f1f02157101eea99512eb1fe0aa7837144e66c03e1e1a0f747fa4a7` |
| 主集 120 | `5fab285c43414943a9ed239db04508ff` | `fe3aac13a0647076e244da1cba7dab569ecc180686e5fa5b946a7d9307b66d45` | `693ddd03752eb8e44ff2c23d0b02be24c9d1406498bce495ce1964a45c86760c` | `b62b5c64047a8de943132eb5b80feba8e4783021a6f9f32a70045878640db294` | `bd4340c86ca8d6ff43c9560ac645edefa3a02050db4243b512ea006704ae6bdd` |

四份 artifacts 的 SHA-256：

| 集合 | `facts.json` | `sources.json` | `derived.json` | `layout.json` |
|---|---|---|---|---|
| 小样本 5 | `4b016c0baa26f8be631b8583867be867433551983a27ea31b8fd4e1765e96667` | `62b30047d092ea1b717d2ccec3e066fa1e7cbf8ca6ac15c4e5c47f1b307b08ab` | `0fe9987cd5abc340c3fc05c527afd56e3b07e0f525ceb1f32e3080283629b153` | `5afd11425f65de8e5b7cc539808543bb77765cd2f73866ddfaee64d12b5efbc1` |
| 留出 60 | `f6c2fb6da00d21ef6cf8e67311b6337045b8e20f75ca0715083b3fefd4ddba3a` | `75488cb14cbce8d1c1becdd97165e8217726abc60af3a8a2d2ba9b515087e81d` | `0b842b6e5866e81e69a448866628f046296c35c84a29b03e9d77126586bdb918` | `c1c573cfe2e9945906c04f274ad475e19968fffa811f86dc62d3cba688b239ac` |
| 主集 120 | `807c9d6338a86944edc28f31531bed70db357dc649ae3b42c86e14e9e9898613` | `fcab862df2ff680643763e075ba2da23de2480cbe7d3d028de354c8c4b1e6885` | `a355bf4aea5e581f84b06e6632c870d677a2d85fe8af7df0cd67a0f5dda859d7` | `391f22be6e09d279817e3eebe2115ab63f52e91944bd756fc64e849f00b97e30` |

### 2.3 分层计数

| 集合 | 输入/进入分析/排除待审 | 事实节点（Job/Skill） | 事实关系 | 五态 | 派生相似 | 布局节点 | 装饰星尘 |
|---|---:|---:|---:|---|---:|---:|---:|
| 小样本 5 | 5 / 5 / 0 | 7（5 / 2） | 12 | uncertain 6、mentioned 6 | 0 | 7 | 214,200 |
| 留出 60 | 60 / 52 / 8 | 143（52 / 91） | 480 | uncertain 446、mentioned 33、required 1 | 0 | 143 | 214,200 |
| 主集 120 | 120 / 113 / 7 | 190（113 / 77） | 698 | uncertain 604、mentioned 71、required 23 | 1 | 190 | 214,200 |

主集 698 条事实关系的组合形状为：无显式组合 682、`all_of` 13、`any_of` 3；条件上下文 604，冲突 0。事实关系全部为 `HAS_SKILL_STATEMENT`，没有 `REQUIRES`。派生相似与装饰星尘不混入事实计数；装饰星尘来自前端固定预算，不属于 bundle 事实。

### 2.4 一致性与来源对账

以下检查对三套图逐条通过：

- manifest 恰好列出四份 artifacts，字典字节 SHA 与文件重算一致；
- M2 run ID、报告 SHA、输入 SHA、`v12` 版本和 M2 实现摘要一致；
- 冻结输入逐条等于报告 `items[].input`；
- Job 节点 ID 由 namespace、原始 JD ID 和指纹组成，节点标题/来源/来源记录索引与 `sources.json` 一致；
- Skill 节点名称是词项 canonical，目标边可定位到声明该陈述的 Skill；
- 每条事实边绑定原 JD `source_record`、statement ID、规范化 Skill、证据字段、`[start,end)` 和 quote；
- 事实五态、组合、条件、要求对象、目标上下文等于冻结陈述，所有边仍标记 `semantic_review=unreviewed`、`formal_statistics_eligible=false`；
- `sources` 重新执行 `project()` 得到与 `facts.json` 完全相同的对象；
- `derive()` 重算得到与 `derived.json`、`layout.json` 完全相同的对象；
- layout 节点 ID 与事实节点集合一一对应，派生端点均存在；
- 全部来源的 `identity_status=unknown`，导入/投影没有把身份冒充为已验证；
- 主集识别出 6 组重复正文：`248861/248917`、`248862/248916`、`248882/248918`、`248883/248926`、`248908/248934`、`248909/248937`；每组保留独立 JD 身份和独立来源边。

隔离副本重新生成的 manifest 与四份 artifacts 均与原 bundle 字节一致，说明同输入/同实现版本可复核复现。

### 2.5 缓存版本行为

`read_bundle()` 校验 manifest 内 M2 绑定和 artifact 哈希，但不强制旧 `implementation` 等于当前代码；旧 bundle 因而可继续只读保留。三套候选图保持冻结报告 M2 实现 `676cda…`，而 Gate 3C 复审收口后的当前代码摘要为 `33782c…`；页面显示旧的图 `data_version`、旧 M2 实现前缀和 `v12`，URL 又绑定完整 manifest SHA，因此没有把缓存结果改写成“新代码生成结果”。

这不是自动 stale 告警：如果代码版本变化，现有逻辑会继续返回旧版本，需要人员比较版本摘要。当前结论是“不会冒充”，但不是“自动判断过期”；后续如需批处理调度，可增加显式 current/stale 状态，不阻塞本轮工程验收。

## 3. Gate 3B：正式 Vue 页面验收

实际使用正式 Vue 图谱入口，显式 URL 包含 `graphDataset=real`、指定 `m2Run` 和 manifest SHA。主集页面可见：

- `190 个节点 / 698 条关联`；
- `输入 120 / 进入分析 113 / 拒绝或待审 7`；
- M2 run `5fab285c…`、分析版本 `v12`、候选图数据版本 `bd4340c86ca8…`、范围待复核 90；
- Job 蓝色、Skill 青绿、历史场景紫色图例及“原 JD 身份；非标准职业”说明；
- 装饰星尘实际 WebGL 统计 `214,200`，与事实节点分账。

选中 `MDC610` Job 后显示 18 条原文陈述关系和 11 个不同邻接节点；选择 `数据结构` Skill 后显示 9 条来源陈述。Job 详情可回源至 `248861`、`248917` 两个独立 JD 身份：

- `248861`：来源索引 126–143；
- `248917`：来源索引 293–310；
- `数据结构` 证据为 `duties [436,440)`，同步显示 freeze fingerprint、来源平台、采集观察时间和 `uncertain` 五态；
- 详情明确显示“原文技能陈述（未人工审核）”和“身份未知 · 不构成已确认独立岗位”。

含 `any_of` 的 `248924` 页面把 Java/Python/TypeScript 三条陈述显示为 `required · 组合 any_of`，没有拆成三个互不相关的确认需求；来源 JD、statement、五态和组合上下文一致。派生图层实测 1 条，独立显示“提交 1 / 总量 1”；缩放按钮改变相机距离，类型过滤可隐藏/恢复岗位层，重置与搜索可继续操作。

小样本与留出集也由正式页面实际载入：小样本 `7/12`，留出集 `143/480`。从主集候选图切到历史 P2.5 图后实际载入 `7845/11412`；浏览器返回候选图后重新显示 `190/698`，搜索、选择、派生开关和相机状态均为初始值，未发生图数据或交互状态污染。

### 3.1 失败关闭实测

| 场景 | 页面结果 |
|---|---|
| URL manifest SHA 改为 64 个 `0` | 显示 `Real manifest hash mismatch or preview not enabled`，0 节点，无历史图静默替换 |
| 独立预览副本缺失 `facts.json` | 显示 `Real bundle unavailable: facts.json`，0 节点 |
| 独立预览副本篡改 `layout.json` | 显示 `Real artifact hash mismatch: layout.json`，0 节点 |
| 错误 run / 输入 / 来源绑定 | 自动化测试拒绝，错误不会进入图谱或覆盖报告 |

页面保留显式“旧 Canvas 回退”链接，但失败时不会自动跳转。

## 4. Gate 3C：人工语义审核准备

### 4.1 发现并修复的页面缺口

验收前 `product_reviews` 只有 JD 级“接受/拒绝/跟进”，无法分别保存 B1 范围、逐条 B2 五态和 B3 大类候选的人类真值。本轮先写失败测试，再增加可选 `human_annotations`：

- B1：人工范围状态与依据；
- B2：按 B2 statement 逐条保存人工状态与依据，附带规范化 Skill ID 列表；未进入 B2.2 的 statement 也可用空 `skill_ids` 审核，人工 `not_skill` 独立于机器五态；
- B3：按 `families-v3` 稳定 ID 记录接受、拒绝或跟进，并允许补记机器漏判候选；
- 机器阶段、`machine_sha256`、已发布报告和 `formal_statistics_eligible=false` 不变；
- 旧 JD 级审核事件保持兼容，无数据库表结构变更。

独立复审又发现：只读取每 JD 最后一次事件，会让后审 B2/B3 时丢失先前 B1，重新打开后也无法恢复有效标签。定向修复增加派生视图 `human_effective`：

- B1、每个 B2 statement、每个 B3 family 分别按事件顺序取最新有效值；
- 后续事件未包含某维度时不清空该维度；
- 每个有效标签携带 review ID、事件 SHA、审核人、时间、机器摘要和输入摘要；
- 同名对象改值时保留先前值和最新值两侧来源，并列入显式 `conflicts`；
- 旧 JD 级事件只计入 `legacy_review_count`，不会生成 B1/B2/B3 真值；
- item、run 列表缩略项和审核导出均包含同一个 `human_effective`；
- 页面只把历史有效值用于显示，不把它们自动预填为下一次提交，避免重复事件。

正式页面实际打开留出集 `248996`（GIS 产品经理）验证 B1 空表单、8 条逐项 B2 机器陈述/人工空状态和 B3 漏判补充入口。另打开 B2 statement 41 条、B2.2 Skill 38 个的 `248988`，页面实际渲染 41 行，41 个人工状态全部为“未填写”，证明未规范化陈述没有从审核分母消失。

另在隔离的合成 run `fdf4766893b241f1a7627727d5879b34` 上完成真实页面流程，不写入真实审核数据：

1. 第一次只提交 B1；
2. 第二次只提交两条 B2 statement 中的 `s1`；
3. 第三次只提交 B3；
4. 关闭并重新打开同一 JD，B1、B2 `s1` 和 B3 三项有效值及各自审核人/事件 SHA/时间/机器摘要全部仍在；
5. 第四次把同一个 B2 `s1` 从 `required` 改为 `preferred`，页面显示最新有效值，并明确列出先前值、新值及两个来源事件；四条 append-only 历史均保留；
6. 页面导出按钮实际请求导出 API，返回 4 个事件、1 个有效条目、3 个维度有效结果、1 个冲突和同一机器摘要绑定。

隔离证据保存在 `data/local/m2-m3-gate3-20261022/interaction-evidence.json`（SHA-256 `9ae46b8f44bfb505e6d629b863caa1aa8de93fc7c2770a602c8d830c579e4b15`）；完整导出保存在同目录 `interaction-export.json`（SHA-256 `3b5753ac58fc8aa309809efe79062a8801136cbf539af0cfd5ba1097d305f625`）。两者只证明页面/API 管线，`semantic_truth=false`。

完成上述代码修复后再次运行 Gate3A 审计，退出码为 0；三套 v12 manifest 仍分别为 `043f228d…`、`9801b972…`、`b62b5c64…`，与会话开始及首次验收值完全一致。没有重写候选图、冻结 M2 报告或正式数据。

### 4.2 有限高价值待审队列

私有队列 `data/local/m2-m3-gate3-20261022/review-queue.json` 共 33 条：

| 集合 | 条数 |
|---|---:|
| 小样本 | 5 |
| 留出集 | 10 |
| 主集 | 18 |

覆盖 4 条 B1 产品边界、9 条 B2 选择/组合、12 条 B3 大类竞争、12 条重复 JD、5 条机器正例和 6 条“可能漏判”探查项；同一记录可同时属于多类。机器预测中保留 426 个 B2 statement 审核单位，其中 56 个没有 B2.2 规范化 Skill；B3 共 22 个候选判断单位，含 1 个人工漏判探查项。队列中机器预测与 `human_truth` 分开，33 条人工字段全部为空，`reviewed=0`，SHA-256 为 `603ebb5db38472cab51073dafb5f6625462e209272693d842f32038f46334ffd`。

逐项规范见 [人工语义审核规范](M2-M3-Gate-3-human-review-protocol.md)。只有真实审核人可填写；Codex/Agent/大模型不代签。

B2 当前审核对象仅是机器已生成的 statement；没有独立“机器漏判 statement”记录，因此本轮不能声称完整抽取 recall。该范围已写入规范，不建设新的完整标注系统。

### 4.3 PR #51 最终收口：B3 人工漏判补充持久展示

从 `e12f363d8c72191083e889dde5098e8498581913` 继续，工作区初始干净，远端 HEAD 一致。本次仅修改前端 `b3ReviewRows`：合并机器候选、`human_effective.b3_categories` 与本轮补充选择，按 `family_id` 去重；保留机器职责证据。历史有效标签不回填草稿，后端契约与机器报告未改。根因见[持久展示陷阱](../superpowers/traps/2026-10-22-m2-b3-supplement-visibility.md)。

新增两项组件回归先在旧实现失败（保存后实际为空行、混合集合缺少 `data_ai`），再以最小修复转绿。覆盖无机器候选的保存/重开、备注及来源、机器同类去重、机器/历史/本轮选择并集、空草稿不重发旧标签，以及直接更正历史补充行的请求内容。日志位于私有 `data/local/m2-m3-gate3-20261022/b3-closeout/`。

本次真实 Vue 页面验证使用独立 FastAPI M2 路由（`18103`）与 Vite（`18181`），目录查询返回合成目录，不连接 MySQL。用户手动完成演示登录后，在合成 run `debfcf2d03184cb4bbfc24eaf267e75d` / JD `990051` 完成：

1. 机器 B3 候选为空，补充 `data_ai`，以 `synthetic-ui-test-not-human` 提交合成 `accepted` 和备注；事件 #1 SHA `948fc3fcb9e8066c5b32efa7afd821b6fc909496004c2084de3d3feb51ae0908`。
2. 关闭并重开，补充下拉框恢复空白，但表格仍有“数据与人工智能 / 人工补充”，有效状态、备注、事件 #1 来源均可见；新增/更正和依据草稿为空。
3. 不重新选择补充大类，直接把该行更正为合成 `rejected`；事件 #2 SHA `8ee0e77485306ef9db710eae7301b4d633d86fef4c06b0ad1d546b0df46e7c14`。页面显示最新有效值、两条历史及一个 `b3_category/data_ai` 冲突，旧 `accepted` 与两侧来源保留。
4. 再次重开，只提交 JD 级跟进备注；事件 #3 SHA `1d9f43e15f58f2b748ae64507fc34a4c06194fd27bedf80b2c16bfb6bb788429` 不含 `human_annotations`，有效 B3 仍来自事件 #2。页面计数为逐项事件 `2 / 3`、legacy `1`，没有自动重复提交旧值。
5. 实际点击“导出人工审核 JSON”，并只读核对同一导出 API 回包：3 个 append-only 事件、1 个有效 B3、1 个冲突与 item 一致；B1/B2 人工标签仍为空，机器阶段和摘要不变。浏览器下载事件监听未返回，不据此声称已核验浏览器落盘文件；完整回包独立保存为 `export.json`。

所有合成输入 provenance 与证据均标记 `semantic_truth=false`；自述审核人明确为 synthetic，不构成实际人工签审或语义真值。验证后仅停止本次归属已核对的 `18103` / `18181` 服务，并在关闭 SQLite 连接后精确删除本次合成夹具目录；残留计数 0（`b3-closeout/cleanup.json`），截图、导出和证据保留。真实 run 与历史交互证据未清理。

| 私有证据 | SHA-256 |
|---|---|
| `b3-closeout/evidence.json` | `de011684e7439abb183bac36aa95c1a120c1c98d2471b6e2a65df4fa48aadbe2` |
| `b3-closeout/export.json` | `dc6a6e97efa567a4b7ed1798733d5d99522755495b3f819481a61f310f24c1d8` |
| `b3-closeout/b3-reopened.png` | `a5eec4ab644357c5eca6881bc91ce31d375563f2aac641fbca3634ddc8ded96b` |
| `b3-closeout/b3-corrected.png` | `2782a5b33000fd22b6f9f17d57324cf1b35ad1368f2ef7d55e25275b17a284e5` |

数据保全采用直接文件哈希及 SQLite `mode=ro` 查询，不实例化真实 Workflow 或重生成图。25 份受保护文件的前后 SHA 完全一致：真实 `workflow.sqlite3` / `analysis.sqlite3`、三套 v12 输入/报告/manifest/四份图 artifacts、历史 `exchange/m3/graph.json` 与人工待审队列。三套 manifest 分别仍为 `043f228d972198227cd96fff87c80dd696961c10ef567030aca4feba8b283fa7`、`9801b972f7ab7f133bd271273e7bc8a2c637dc5e265d83a6ebaec53f7ea88e08`、`b62b5c64047a8de943132eb5b80feba8e4783021a6f9f32a70045878640db294`；三套真实 run 审核事件计数均为 0。正式 MySQL/Neo4j 未执行写入或重建。

## 5. 验证结果

| 验证 | 结果 |
|---|---|
| Gate 3A 逐边审计与隔离重生成 | 通过，三套 bundle 重生成字节一致 |
| 后端 M2/M3 定向测试 | `13 passed` |
| 多事件有效视图与导出定向测试 | 既有后端 `3 passed`；本次 M2 页面组件 `14 passed`；M2/M2 API/候选图三文件 `42 passed` |
| 后端完整非集成测试 | 本次显式 `-m "not integration"`：`1561 passed / 24 deselected / 2 failed` |
| 前端完整测试 | 本次 `160 passed`，含新增两项 B3 持久展示回归 |
| `vue-tsc --noEmit` + Vite build | 通过；仅保留既有大 chunk 与动态/静态导入提示 |
| integration 测试 | 本次显式排除 `24 deselected`；先前裸跑默认保护为 `24 skipped` |

两项后端失败均为基线已有、非本轮引入的 B3 目录来源漂移：

1. `test_repository_draft_covers_eight_families_and_empty_release`：`PRODUCT_DECISIONS.md` 的固定 SHA/引文失配；
2. `test_shipped_source_hash_matches_a_fresh_LF_checkout`：同一固定来源基准失配。

本轮没有通过修测试、重签来源或修改候选目录来掩盖这两项。

## 6. 问题清单与准入判断

### 必须修复

- 上述两项 B3 目录来源 SHA/引文失配需要由目录维护方重新核对并形成独立版本变更；在修好或得到明确豁免前，仓库全量测试不能称为全绿。
- Gate 3C 尚无真实人工审核，因此真实语义正确性、漏判率和准确率不能验收。

### 非阻塞观察

- 缓存保留正确版本，但缺少“当前/过期”自动徽标；页面已可辨识具体数据版本，不构成冒充，后续批量调度再补。
- 主集派生相似只有 1 条，这是当前保守投影结果，不为丰富图谱补造关系。

### 最终分类

1. **工程可用性：条件通过。** 指定三套 run 的构建、完整性、版本、来源、布局、页面交互、历史图往返和失败关闭均通过；条件是全量测试中的两项既有来源门禁仍为红。
2. **真实语义：未验证。** 人工真值 0，没有 precision/recall 或“需求已确认”结论。
3. **需要修复：** B3 固定来源基准；随后由真实审核人处理 33 条有限样本。
4. **下一阶段批量稳定性：** 工程上可提出有限、版本化、非正式的稳定性扩容建议，但应先关闭/明确豁免两项来源门禁；不得据此直接分析全部 2,988 条。全量分析仍需单独授权。

本阶段未执行正式 MySQL DDL/写入、M2 正式表重导、Neo4j 重建或写入、自动岗位批准、需求提升、真实采集或 2,988 条全量分析。

## 7. PR #51 合并后的 Windows 同步与实机验收准备

以下步骤**尚未执行**。必须先由 ChatGPT 独立复审、经用户授权实际合并 PR #51；当前开发分支不等于已验收的 `master`。本次不改动本地 `master`。

在 PowerShell 中逐步执行；有未提交修改、本地 `master` 领先/分叉、服务占用或命令失败即停止，保留现场：

```powershell
Set-Location -LiteralPath 'D:\Application\ClaudeCode\repository\TalentMind'
$ErrorActionPreference = 'Stop'
git status --short --branch
if ($LASTEXITCODE -ne 0) { throw 'Git 状态读取失败' }
if (@(git status --porcelain).Count) { throw '工作区有未提交修改，先人工处理' }
$pr = gh pr view 51 --json state,mergedAt | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $pr.state -ne 'MERGED' -or -not $pr.mergedAt) {
    throw '尚未确认 PR #51 实际合并，停止同步'
}
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 18000,18080,18103,18181 })
if ($listeners.Count) {
    $listeners | Select-Object LocalAddress,LocalPort,OwningProcess
    throw '先确认并结束对应旧服务；不要停止归属不明的进程'
}
git fetch origin
if ($LASTEXITCODE -ne 0) { throw 'fetch 失败' }
$ahead = git rev-list --count origin/master..master
if ($LASTEXITCODE -ne 0 -or [int]$ahead -gt 0) { throw '本地 master 有远端之外的提交，停止同步' }
git switch master
if ($LASTEXITCODE -ne 0) { throw '切换 master 失败' }
git merge --ff-only origin/master
if ($LASTEXITCODE -ne 0) { throw '无法快进，停止并保留现场' }
git log -1 --oneline
git status --short --branch
pwsh -File scripts/start-local.ps1
```

访问 `http://127.0.0.1:18080/#/m2`，登录由用户完成。统一启动入口会核对已有服务归属；遇冲突不使用 `reset --hard`、`clean`、强制推送或结束未知进程。

实机验收清单（本次只准备，合并后由用户执行）：

- M2 工作台正常打开，三套真实 v12 历史 run 可读取，B1/B2/B3 机器结果与人工有效标签分离。
- 审核写入只在明确标记 `semantic_truth=false` 的隔离合成 run：补充机器漏判 B3，提交、重开、更正、检查冲突与历史、导出；新草稿为空，不自动重发旧标签。不要在统一启动后的真实 run 中试填。
- 旧 JD 级审核保持兼容，不生成逐项真值；真实 JD 仅由实际审核人判断和签审。
- 三套 v12 候选图正常加载；主集为 190 节点 / 698 事实关系，历史图为 7,845 节点 / 11,412 关系，候选图与历史图往返正常。
- 只读取冻结图与报告，不触发正式 MySQL/Neo4j 写入、导入或图谱重建；不启动真实采集或全量 2,988 条分析。
