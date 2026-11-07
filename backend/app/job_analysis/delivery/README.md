# M2 统一交付入口与恢复契约

`delivery` 将已审的 P1 `understand`、P2-1 `align_analysis/compare_roles` 和 P3/P4 `apply_batch` 接在同一个实际入口。无需 MySQL、Neo4j、M3、前端或完整职业目录。授权/开发证据集中在 [#69](https://github.com/Serena-Lyric/TalentMind/issues/69)，阶段审核与合并状态只看[总表](../../../../docs/superpowers/plans/2026-10-28-m2-core-delivery-plan.md#3-分段地图与当前进度)。


## 网页入口与配置

`/#/m2`通过`/api/m2/delivery/inputs`分页读取JD，`POST /delivery/runs {jd_ids:[...]}`冻结输入，随后显式`/start`或`/resume`；`/stop`在已提交边界保留部分结果。`/abandon`显式结束未完成任务并保留结果，之后可冻结新任务；同一账本最多一项未完成可执行任务，避免候选基线漂移。完成/放弃后不可原地恢复。

后端必须开启现有`TALENTMIND_LOCAL_RAW=1`并通过localhost/Origin门禁，演示登录不替代此门禁。模型处理器使用显式`TALENTMIND_M2_CONFIG`配置路径与`TALENTMIND_M2_KEY_FILE`私有密钥文件路径；缺配置返回明确错误，读历史不要求模型。冻结不调用模型，只有点击开始执行。本轮开发验证未发真实文本到模型，实际新模型运行需相应授权。

网页状态落`data/local/m2-delivery`。已知P5/P6 `sequence-head-final/state`和`dev-head-final/state`以只读历史挂载，标明合成或受控DEV来源；不迁移原件、不改原run ID，冲突ID拒绝。旧`/api/m2/runs`只读`data/local/m2-product`，不再提供旧执行POST。

技能候选通过`CandidateRegistry.observe→CandidateRegistry.project→align_analysis`被本次统一结果实际消费；原分析与投影版本分别保存，历史不依赖当前有效head重建。网页来源研究种子仅为单来源职责假设，不表示中文同组已确认。

`GET /delivery/compare?before_run=...&after_run=...`比较确切运行：同来源的原文、事实分析、知识与技能投影分层，研究候选需同registry才可比。`GET /delivery/runs/{id}/graph`冻结本次已提交结果，返回内容摘要绑定URL；artifact请求必须带该`snapshot`。快照保存在私有`graphs/<run>/<sha>/`，运行继续或服务重启不改旧快照，缺失时失败而不回落另一数据集。

## 执行

在 `backend/` 使用现有虚拟环境。默认不加载 `.env`，不调用网络/收费模型。stdout 仅安全摘要；**SQLite、请求、完整导出含原文，必须放 `data/local/` 或仓库外私有路径，不上传**。CLI 是本机文件消费者；网页另有受控 localhost HTTP 门禁；导出遵守同一私有路径限制。需要共享时另做人工审查/脱敏，不直接分享完整结果。

```powershell
python -m app.job_analysis.delivery init --state ../data/local/m2-delivery/state
python -m app.job_analysis.delivery head --state ../data/local/m2-delivery/state
python -m app.job_analysis.delivery run --state ../data/local/m2-delivery/state --id batch-1 --request ../data/local/m2-delivery/request.json --knowledge app/job_analysis/knowledge/catalog/backend-foundations.v1 --output ../data/local/m2-delivery/results
python -m app.job_analysis.delivery read --state ../data/local/m2-delivery/state --id batch-1 --expected-request <摘要> --output ../data/local/m2-delivery/readback
python -m app.job_analysis.delivery resume --state ../data/local/m2-delivery/state --id batch-1 --output ../data/local/m2-delivery/results
```

请求 `m2-delivery-request-1`：

```json
{
  "schema_version": "m2-delivery-request-1",
  "baseline": {"registry_id": "<init/head 实际值>", "revision": 0, "sha256": "<实际值>"},
  "items": [{"p1_run": "../data/local/explicit-p1-run"}],
  "operations": []
}
```

`p1_run` 是 CLI 的 manifest-bound 目录导入语法，冻结为完整原始 P1 对象，拒绝脱离 manifest 的 `run.json`。也可显式给 `namespace/row/input_version/analysis`，或只给 `namespace/row/input_version` 交处理器。Python API 为 `await execute(store, run_id, request, load_snapshot(path), processor=processor)`；原始 JD 必须有实现现有 `Processor` 协议的显式依赖，不隐式联网。

CLI 原始 JD 可用 `--replay recorded.json`，文件为 `{"schema_version":"m2-recorded-processor-1","runs":["<primary目录>","<audit目录>"]}`。各目录先验证 P1 manifest；可给 primary/audit 子目录，也可给包含 primary_run/audit_attempt 的标准完整 P1 目录，记录器会递归读取。只有**完全相同请求摘要**才能取得回包。缺缓存返回 `not_run`，不调用网络，也不以相近请求替代。不同模型配置分开运行；缓存内容摘要纳入处理器版本，metadata 标记 `cached_recompile/network_requests=0`。这是真实执行当前 P1 编译与审计代码，不能称为 fresh 模型运行。Python 接入 CloudProcessor 只是已有能力，实际发送真实文本/产生费用仍须对应授权。

`operations` 沿用 [P3/P4 契约](../work_candidates/README.md)：create/link/correct/describe 均支持显式输入；请求的 `research_sources` 默认false，网页置true时还会为每个来源核心职责生成独立create研究种子（ID绑定原分析SHA与claim），只作来源假设，不自动同组，引用真实分析 SHA 与 claim ID。初次 raw JD 可先无操作完成理解，再从私有结果取确切分析创建有依据的研究假设。检索、知识解释和研究投影自动执行；没有独立中文同组判断器，不会自动把标题/技能相近认作同一工作组合。每日研究修订不要求人工逐条批准；关键结构/正式归属/发布仍没有可信确认写入路径。

## 消费契约 `m2-delivery-result-1`

| 字段 | 含义 |
|---|---|
| `run_id/request_sha256/dependencies` | 不可变原请求与实际已加载依赖；读取不使用当前 head 重新计算 |
| `knowledge.sha256` | 本次冻结知识原字节 SHA，原始知识同请求保存在账本 |
| `items[].analysis/analysis_sha256` | 原始 `m2-semantic-0.2`、实际 analyzer/model/prompt/configuration/input 版本及完整五态/程度/条件/组合/稀疏关系；导入或复用不改写原分析 |
| `items[].p1/input_mode/reuse/observation` | 原 P1 完整执行、实际输入模式和复用来源；当前观察时间与原分析时间分开 |
| `items[].skill_candidates/knowledge_projection` | 本次实际观察的技能候选与有效知识投影，含证据/争议/状态及版本；随后被alignment消费，历史不重读当前registry |
| `alignment/roles` | P2-1 候选知识成熟度、精确技能对齐、有限岗位比较、覆盖及具体原因；不等于正式岗位归属 |
| `role_assignment` | `unavailable/p2_2_not_validated`，明确 #63 缺口，不伪造完整解释 |
| `items[].status/counts` | complete、partial、unknown、failed、not_run 分账，分母是本次 items；完整指 P1 五个适用维度及集成执行，不是人工语义验收。classification 的 not_run 仍原样存在 |
| `stage_results` | 取消/中断前已提交的 primary/audit 诊断；不冒充整项/候选已完成，重试会只追加新阶段 |
| `work` | 确切 P3/P4 binding、候选、研究版本、来源引用、未决/反证及结构建议；null 表示候选阶段未完成，不能回落当前 head |
| `semantic_review/market_accuracy` | machine_unreviewed/null；独立来源与 vacancy 未知、正式目录为空的边界不变 |

`read --id` 始终返回该 run 已存结果，`--expected-request` 可校验调用方选中的请求；即使后续运行成功也不替换旧读数。只读连接可在其他 worker 持有写租约时读取已提交结果。网页已直接消费本契约；旧 B1/B2/B22/B3 仅提供原结果只读历史，新结果不强制投影进旧字段。

## 复用与恢复

| 变化/故障 | 实际策略 |
|---|---|
| 同身份、同有效输入/处理器/提示/P1 源码 | 只跨 run 复用有事实且 P1 五维 complete、execution=ok 的结果；classification=not_run 不误阻止适用五维完成。partial、未识别、失败不冒充完整缓存 |
| 仅 crawled_at 变化 | CLI/Python在input_version不变时可复用P1；网页对整行生成input_version，因此保守重算。当前observation单独保存，不改原分析、不增加独立需求 |
| 正文或其他有效字段/input_version 变化 | 保守重做 P1，保留旧输入和结果 |
| 知识/标准变化 | 复用充分 P1，实际重做 P2/P4；完整保存新解释，旧 run 不重算 |
| 模型/配置/提示/分析源码变化 | 新 run 保守重评；未结束旧 run 必须匹配原有效依赖才能恢复。长驻 worker 发现磁盘提示/代码漂移会拒绝继续，先重启再另建 run。已结束历史读取不检查当前依赖 |
| `--stop-file` 存在 | 在条目/候选提交边界停止，未做项明确 not_run；移除标记后 resume。Ctrl+C/进程退出由 OS 释放写租约 |
| 条目提交前/后退出 | 未提交项重新执行；已提交项直接读取。已存 primary/audit 可诊断，未完成条目可能重复处理器调用，不能保证外部请求 exactly-once |
| 候选提交前/后退出 | 原批次 ID、旧 baseline 与输入集合被冻结；精确重试返回原快照，不重复演化；账本结果提交后导出失败可直接重发原结果 |
| 同 ID 改请求/过时基线/并发写者 | 拒绝；单个账本写者由现有 OS Lease 互斥。其他运行抢先推进候选时不自动重基，保留已完成事实并报 candidate_failed；用新基线另建 run |
| P2 或候选失败 | 已完成 P1/阶段及安全原因留存；新 run 可复用充分 P1。候选更新失败不伪装完整 work |

完整结果 `completed` 是已完成编排，仍须读取 counts/coverage/未决原因；不是所有业务事实完整或人审通过。导出不可覆盖不同内容，同一个 run 的进度快照与最终结果应使用不同目录。规模、网络盘、断电与真实模型吞吐未验收。

## 复现与评价

```powershell
python -m app.job_analysis.delivery.demo --output ../data/local/m2-delivery/synthetic-sequence --knowledge app/job_analysis/knowledge/catalog/backend-foundations.v1
python -m app.job_analysis.delivery.evaluation --state ../data/local/m2-delivery/state --suite ../data/local/m2-delivery/dev-suite.json --output ../data/local/m2-delivery/evaluation
python -m pytest tests/test_job_analysis/test_delivery.py tests/test_job_analysis/test_delivery_cli.py tests/test_job_analysis/test_delivery_evaluation.py -q
```

demo 是七批真实 CLI：新增职责供后批消费、显式反证收窄、重复不虚增、知识更新、停止恢复、历史和精确重试。仅合成输入，非真实同组准确率。

评价 suite 显式给 `release/manifest/approval` 与 `cases:[{sample_id,annotation,run_id,assessment?}]`。先执行 P0 签审发布完整性检查，只接受 DEV 和绑定的 annotation 原字节；从 run 取确切输入/分析。无新 assessment 时仅报告 source span 提示与未判数量，不将字面重叠算语义正确。可提供绑定 analysis/annotation/case 摘要的 `agent_diagnostic`，分别列职责/要求 matched/partial/missed/wrong/unknown、未审额外预测、A/B/C/D 条件，不能伪装独立人审。固定技能词典仅提及基线使用同一原文，保留命中/五态一致性提示及不能表达职责、限定/任选的限制，不按格式合法率评分。

既有 DEV 已参与开发，缓存费用/用量属于原模型运行；本轮离线重放零新增外部调用，不能代表 fresh 费用或性能。独立 HOLD、真实归属/检索同组/演化方向真值与新模型许可不足时准确率为 null、对应能力未验收，缺口继续追踪 #63。长期状态与本轮数量见资产页和 #69。

## 旧任务的去向

[#41](https://github.com/Serena-Lyric/TalentMind/issues/41) 的运行/人工/正式状态分离、原文作用域和证据边界继续适用；本入口保留这些状态，P0 DEV 是另外的受控参照。原 32 项草稿没有因新入口实现而获得签审，原 120/60 结果、B/C 旧空间/竞赛排期不自动成为本轮新依赖，也不标为本次完成。独立原始草稿复核及市场代表性仍需单独材料。

[#47](https://github.com/Serena-Lyric/TalentMind/issues/47) 的“执行完成、复核优先级、正式批准分离”和外发默认关闭边界仍适用。新入口已经分开执行与知识状态；Jev 专属 adapter、优先审核队列和真实 API 效果/成本没有实现或验收。旧指定模型试点/直接 master 开发建议不作为新底座依赖；将来若仍需要辅助分流，单独核对必要性、输入范围、官方接口及费用授权，本轮不借它确认工作同组或正式发布。
