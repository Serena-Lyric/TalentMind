# M1→M5 真实 JD 首轮贯通交付

日期：2026-10-20（Asia/Singapore）。状态：已实际运行、正式 Vue 隔离加载并验证原文回溯；交付 Draft PR，等待集中审查，不具备合并或生产切换授权。

实现提交 `1e69013a21cf3d9f8ffb8b3eeb24779ef185c90f` 已推送；[Draft PR #38](https://github.com/Serena-Lyric/TalentMind/pull/38) 已附本聊天，base=master，实查 OPEN / isDraft=true / mergedAt=null / autoMergeRequest=null，暂无远端CI结果。本任务定向差异为 `fb68d3b..1e69013`；新工作区保留，正式本机预览为 `http://127.0.0.1:18090/?graphDataset=real&nebulaDebug=1#/graph`。

## 1. 本轮完成了什么

已有真实 JD → M2 B1 筛选 → M2 B2 五态 → B2.2 名称/证据治理 → 独立 M3 原文陈述事实图 → 独立派生相似/社区/布局 → 正式 `GraphPanorama.vue` Career Nebula → 原始 JD 身份、来源和全文。

这是有限规则分析的真实链路，**不是开放域岗位分析已完成，也不是可信招聘需求图已验收**。真实样本未作人工审核，B3 正式目录仍为空。新图保留不确定陈述，使用独立 `HAS_SKILL_STATEMENT` 边，不能当作已确认的 REQUIRES 或供生产匹配使用。

## 2. 最新 GitHub 只读核查与依赖

核查 `git ls-remote`、fetch、PR 状态及实际源码。master 为 `1e5f4da8d8739152718e03841257b67122eb5926`。

| 环节 | 已有能力/真实契约 | 缺口与本轮处理 |
|---|---|---|
| M1 | `jd_pool` 原始 ID、source/source_detail、job_title/raw_text/duties/experience、quality、观察时间、状态及去重组 | 不启动采集。当前 MySQL 连接被拒绝，改读已保全 SQL 文件，不启动生产服务。 |
| M2 A / PR4 | 不可变快照、持久化、指纹、运行/尝试/事实与重放基础 | 复用 `AnalysisStore` 体系；不使用仅 Python 字面演示分析器充当真实提取。 |
| M2 B1 / PR5 | 有效性与范围分层、逐条 input_failed、原因和原文偏移 | 直接复用；失败成员保留，不让一条空正文阻断整批。 |
| M2 B2 / PR6 | 五态、程度/对象/条件、组合及有效状态冲突，完整/部分/失败分离 | 直接复用；真实样本全部 partial，如实保留。 |
| M2 B22 / PR7 | 只读规范化、歧义候选、非技能和未解析片段 | 直接复用；未写词典、审核事件或正式质量结论。 |
| M2 B3 / PR9–19 | 八类及 19 条待审职业草案，正式发布为空 | 不调用这些草案作为分类真值；canonical_job/family 保持 null。 |
| M3 / PR21 | 实体身份/冲突纯函数修复，生产重建命令禁用 | 不恢复旧命令；新入口只消费显式私有文件，事实、派生结果和布局分别保存。 |
| M3/P2.0–P2.1 | 完整 Jaccard 候选、Leiden 与候选布局 | 复用算法，显式传入保守需求投影，参数/源码/软件版本记录。 |
| M5 / PR37 | 正式 Vue P2.5、历史快照绑定、真实端点交互和旧版回退 | PR37 尚未合并，基线 `fb68d3b7bd9dffdd33ed43c78b8387d5a8d31362`。本分支从它建立，PR 对 master 明确注明堆叠依赖；不表示 P2.5 已最终验收。 |

原工作区 `codex/m1-stage-02` 的未提交端口修复完整保留。新增工作区及分支 `codex/real-jd-e2e` 独立承载本任务。

## 3. 真实输入与各阶段实际数量

数据来自私有备份 `mysql-current-20261014.sql`，SHA-256：

`9df1424cedadd96dbd6ce5b5b5196679b757988199cf46b346dc5770e0012be2`

只解析 `jd_pool` 的 schema 与 INSERT 字面值，**没有执行 SQL**。备份原始层为 2,988 条（BOSS 1,137／智联 1,088／猎聘 763）；不是本轮实时生产库查询。固定按每平台原 ID 升序前 40 条，得到 120 条，未按分析结果挑样、补样或修改原文。这不是随机/代表性样本，不用于估计质量或准确率。

输入 SHA-256：`b6c37b28932ea43820eafaf7c43903b5747514f64ba86a8e5790aa71d5536dff`

| 阶段 | 实际结果 |
|---|---|
| M1 输入 | 120 条，三平台各 40，完整保留原身份和字段 |
| B1 有效性 | valid 42、undetermined 71、not_evaluated 7、invalid 0 |
| B1 范围 | in_scope 22、needs_review 91、not_applicable 7、out_of_scope 0 |
| B1 原因计数 | technical_activity 22、insufficient_evidence 80、ambiguous_activity 11、input_record_invalid 7；原因可多项，不能当互斥人数相加 |
| 进入 B2 | 22 条（智联 19／猎聘 3／BOSS 0）；其余 98 保留失败/待审原因 |
| B2 | completed 0、partial 22、failed 0；已识别技能不等于完成整篇分析 |
| B22 | overlays 22、upstream_failed 0、候选 0；未解析片段 530 |
| M3 事实图 | 22 个原 JD 节点 + 49 个技能节点 = 71 节点，417 条归属于原文的规则陈述 |
| 陈述状态 | uncertain 416、mentioned 1；required/preferred/not_required 0；本样本冲突 0（冲突能力另有合成回归） |
| 相似/社区 | 只用无冲突、无条件且明确 required/preferred 的单项参与，得到相似边 0、非平凡社区 0，22 个孤立分区；未用 uncertain 或 any_of 展平成已确认需求 |
| 布局 | 全部 71 节点有独立候选坐标；展示空间/旋臂/装饰粒子不代表可信职业分类 |
| 正式 Vue | 实际加载 71／417；Python 节点 56 条原文陈述、14 个不同相邻 JD，与 56 条已提交关系对应 |

## 4. 独立版本与可追溯产物

最终数据版本：`ba1717fcb4e7718195607f2c6cfb241040c5eaf3e86b6cb2f8b87e6929d31e5c`。

最终私有目录：`data/local/real-e2e-20261020-v2/`。中间 v1 保留在本地用于诊断，已由加强来源校验的 v2 替代，不作为交付版本。

| 产物 | 用途 |
|---|---|
| `input.json` / `source-provenance.json` | 冻结原始输入字节；备份哈希、选样规则、原 ID 和来源索引 |
| `analysis.sqlite3` | 隔离本地 M2 持久化，不是生产数据库；B1/B2/B22 分层报告/快照，保留审计运行 |
| `m2/<run_id>.json` | 各阶段完整运行报告和逐成员原因 |
| `sources.json` | 全部 120 条输入、B1 决策、M2 治理、原文偏移和快照/尝试/结果引用 |
| `facts.json` | 仅原文规则陈述；保留五态、对象、条件、程度、组合、冲突及完整 statement |
| `derived.json` | 独立相似边与社区；无可信数据就允许为空 |
| `layout.json` | 独立候选布局，绑定事实图、派生结果和参数 |
| `manifest.json` | 数据版本、输入/产物哈希、实际代码摘要、软件版本、运行 ID、计数与回退方式 |

原文、完整图和 SQLite 全部 Git 忽略，不复制到正式 `exchange/m3/graph.json`，也不公开为全站静态资源。公开的[运行清单](real-jd-e2e/run-manifest.json)只含版本/计数/相对路径/哈希，不含 JD 全文；实际原文仅在本机回溯。

再次从冻结 `input.json` 完整执行 B1/B2/B22 和构建，输出到新的 `real-e2e-20261020-replay/`，数据版本及以下三份文件**字节相同**：

| 产物 | SHA-256 |
|---|---|
| facts.json | `b0c06eeabcaa0a0de3c93e233cbaa3d8a26d64ab84170f477e794015bc0fff0c` |
| derived.json | `5a50b01202ff6b621e303cfe319670fec918dbf2b9d4417bf0f149de43c8e26a` |
| layout.json | `00e997eb7c24e4ebc852ca72dfe3984a617d181719dfea0948e610cdf97b1a08` |

运行 ID、时间及 SQLite 中独立尝试编号是各轮审计身份，不要求跨轮相同。verify 会重新投影事实、核对 M1/B1/B22、重算相似/社区/布局，不只相信文件自报哈希。

## 5. 运行与重放命令

使用 Python 3.14.5 和后端 requirements，另装离线算法依赖 `backend/app/graph/requirements-offline.txt`（networkx 3.6.1、igraph 1.0.0、leidenalg 0.11.0），不修改生产 requirements。本机复用 P2.0 的现有独立研究环境。以下在仓库根执行；路径按本机私有备份调整。

```powershell
Set-Location backend
# 仅解析已有备份，不连接 MySQL 或执行 SQL
python -X utf8 -m app.integration.real_jd_export --sql D:\backup\TalentMind-2026-10-14\snapshots\mysql-current-20261014.sql --output ../data/local/replay-input-new --per-platform 40
python -X utf8 -m app.graph.real_pipeline run --input ../data/local/replay-input-new/input.json --dataset m1-preserved-20261014-first40 --provenance ../data/local/replay-input-new/provenance.json --output ../data/local/replay-bundle-new
python -X utf8 -m app.graph.real_pipeline verify --output ../data/local/replay-bundle-new
```

所有导出/构建目标必须是新目录，不会覆盖旧包；运行中断时保留原包/M2 状态供调查，整体编排重试使用新目录。各阶段 SQLite 报告保留原始审计，不自动恢复生产任务。`--env <显式环境文件>` 是另外提供的 READ ONLY 事务导出入口，本轮因连接拒绝没有完成 live 导出，不以备份数字声称实时数据库状态。

正式 Vue 隔离预览（另开终端，从仓库根）：

```powershell
Set-Location frontend
$env:M3_REAL_PREVIEW_DIR=(Resolve-Path ../data/local/real-e2e-20261020-v2).Path
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 18090 --strictPort
```

打开 `http://127.0.0.1:18090/?graphDataset=real&nebulaDebug=1#/graph`，使用页面提供的演示账号登录。真实数据版本必须显式选择；移除 graphDataset 参数即可回到历史 P2.5。原文端点仅 dev 模式、loopback、同源、白名单文件可读；外部 Origin 返回 403，SQLite 等非白名单返回 404。普通 build 不携带私有图/来源，实际 dist 仅有 historical.json/layout.json。

## 6. 实际浏览器证据与失败案例

以下为正式 Vue 页面实际操作截图，保留实际浏览器视口（多数为1280×720，错误页为1413×918）；不是原型或合成数据画面：

- [最终真实版本全景](real-jd-e2e/final-overview.jpg)：71／417、120→22／98、版本号与分析边界。
- [Python 节点](real-jd-e2e/final-python-selected.jpg)：56 原文陈述、14 个不同相邻 JD、五态 uncertain。
- [关系→原文](real-jd-e2e/final-relation-source.jpg)：猎聘 JD 248946，完整指纹、来源和 Python 原文证据。
- [空正文拒绝](real-jd-e2e/final-rejected-source.jpg)：JD 248913，input_record_invalid，保留来源、观察时间与原始空正文，不补造内容。
- [历史回退](real-jd-e2e/historical-fallback.jpg)：7,845 节点／11,412 边仍可加载。
- [损坏产物拒绝](real-jd-e2e/corrupt-bundle-rejected.jpg)：独立可丢弃副本修改 facts 后，摘要不匹配，显示 0／0 和错误，不悄悄改用历史图。

真实样本暴露的是上游已存空正文、B1 范围不确定以及现有 B2 对真实长 JD 的语法覆盖不足。未在本任务扩写开放域规则以制造成功率；B3 未发布问题也没有用合成审核绕过。

## 7. 验证与独立审查

- 新后端定向回归：7 passed。覆盖来源身份/字节、空正文分层失败、五态/组合/冲突、未知候选、输出拒绝覆盖、重算哈希的错误来源/派生文件。
- 后端完整阻网非集成回归：**1182 passed、2 failed、2 skipped、23 deselected、190 个既有依赖警告**，67.58 秒。88 个父/子 Python 进程加载审计钩子，服务/外网/DNS 尝试 0，仅标准库内部 socketpair 6 次；专属测试临时目录退出后不存在。
- 两项失败都在未修改 P2.5 基线上再次复现：`test_repository_draft_covers_eight_families_and_empty_release`、`test_shipped_source_hash_matches_a_fresh_LF_checkout`，均为 B3 草案 definition_basis 对产品文档的来源哈希/引文不匹配。未修改草案/审核/正式发布，仍需目录维护者处理；因此不宣称全仓测试全绿。
- 首次完整测试隔离器漏识别 Python 3.14 `_fallback_socketpair`，额外造成六项测试失败；修正临时阻网器后它们全部通过。首轮等待时进程有长时间挂起，耗时不作为性能结果；最终回归以上述 67.58 秒为准。
- 前端 95 passed；`vue-tsc --noEmit` 与 Vite build 通过，仍有既有大 chunk 警告。pnpm 对复用依赖目录尝试重装时因非交互拒绝，实际使用相同现有依赖直接运行 Node 构建入口，没有执行依赖 purge。
- requesting-code-review 技能启动独立只读审查，报告了跨技能冲突污染、跨 JD 来源绑定、Unicode 码点偏移和派生校验缺失；均先复现失败再修复并通过定向回归。审查代理随后因用量限制中断，**未给出最终准入结论**；本报告不是 ChatGPT 的交付后集中复审。
- 未运行生产集成测试；没有数据库夹具或生产清理。测试临时 SQLite/文件由专属临时目录自动删除，实际审计包属于交付资产保留。未实时查询生产表计数，不能声称做过数据库内容全量核验。

## 8. 回退、限制与后续验收

`exchange/m3/graph.json` 原始字节 SHA-256 仍为 `6565d56dbc5a267eb90144f078c54f3d0c761c9a98ca29a18b4dc9c6cdde38e2`。未恢复禁用重建、未写 MySQL/Neo4j、未运行采集、未覆盖正式交接或改变 P2.5 默认输入。

首轮贯通完成的范围是“真实来源与有限分析结果可重建、可见、可回溯”。正式可信需求图、开放域完整语义识别、真实人工基准与语义准确率仍未完成；本样本没有足以产生正向相似边的明确需求单项。PR37 和本 PR 均需集中审查，不能自动合并、部署或切换生产。
