# P3 工作组合候选生命周期

独立离线入口，依赖已合并的 P1 `m2-semantic-0.2` 与 P2-1 知识快照，**不依赖 Draft PR #64**。授权及验收分账见 [Issue #65](https://github.com/Serena-Lyric/TalentMind/issues/65)，阶段状态仅在[总计划](../../../../docs/superpowers/plans/2026-10-28-m2-core-delivery-plan.md#3-分段地图与当前进度)维护。

## 运行

在 `backend/` 使用现有虚拟环境；不加载 `.env`、不访问模型、MySQL 或 Neo4j。所有 SQLite、输入和重定向的 JSON 输出放仓内 `data/local/` 或仓库外私有路径。**完整输出含原始分析/引文，不能上传公开仓库。**

```powershell
python -m app.job_analysis.work_candidates init --state ../data/local/m2-p3/state.db
python -m app.job_analysis.work_candidates apply --state ../data/local/m2-p3/state.db --batch ../data/local/m2-p3/batch-1.json --analysis ../data/local/m2-p3/p1-run --knowledge app/job_analysis/knowledge/catalog/backend-foundations.v1
python -m app.job_analysis.work_candidates show --state ../data/local/m2-p3/state.db
python -m app.job_analysis.work_candidates show --state ../data/local/m2-p3/state.db --revision 1
python -m app.job_analysis.work_candidates history --state ../data/local/m2-p3/state.db --candidate work-orders
python -m app.job_analysis.work_candidates jd --state ../data/local/m2-p3/state.db --namespace synthetic --jd-id one --revision 1
python -m app.job_analysis.work_candidates source --state ../data/local/m2-p3/state.db --kind analysis --sha256 <analysis-sha256>
```

`--analysis` 可重复给出，接受显式分析 JSON 或带 manifest 的 P1 run 目录；拒绝脱离 manifest 的 `run.json`。输入按原对象保存，不补写或改写默认字段。`--knowledge` 必须是 P2-1 manifest 校验通过的目录。空角色目录/部分分析可以保存，不自动创建候选；失败/未执行/职责缺口在 report 分别可见。

批次 JSON（占位符取实际输出，不是可直接执行的输入）：

```json
{
  "schema_version": "m2-work-batch-1",
  "batch_id": "batch-1",
  "baseline": {"registry_id": "<init/show 返回值>", "revision": 0, "sha256": "<init/show 返回值>"},
  "operation_version": "research-operations-1",
  "analysis_sha256s": ["<P1 分析对象 canonical JSON SHA256>"],
  "operations": [{
    "op": "create", "candidate_id": "work-orders",
    "description": "订单服务工作假设", "research_question": "不同实现栈是否承担相同工作责任？",
    "core_work": [{"analysis_sha256": "<同上>", "claim_id": "<实际 duty ID>"}]
  }]
}
```

SHA 由 `foundation.inputs.digest(value)` 计算，**分析对象 SHA 与输入 fingerprint、P1 run manifest SHA 不同**。后续每个新批次使用当前 `binding`。相同 batch ID、原请求和知识版本精确返回当时结果，即使当前已有后续批次；同 ID 改内容拒绝。过时/其他 registry 基线拒绝整批写入，需读取新基线后重新检查并使用新 batch ID。

## 候选、关联与证据性质

候选 ID 是显式稳定身份，与标题/描述内容无关。只有调用方明确提供具体工作证据和研究问题才执行 `create`；不会因分类失败、技能未知或多职位广告自动制造候选/vacancy。新建前记录已检查的基线候选及有字面线索的竞争候选。`core_work` 只引用不可变 P1 claim，至少有一项 duty；P1 五态、程度、条件、组合、证据及 `machine_unreviewed` 完整保留。

每批对基线候选的原核心证据执行**字面工作检索**（职责文本二元字符交集，至少两项交集；按最大交集排序，最多十个，显示截断和检查范围）。标题、要求技能、P2-2 结果和新描述不作为比较依据。工作目标、对象及作用域需进一步独立验证，字面交集不证明它们相同。相同技术的异责任可能被检索命中，等价改写也可能漏检；这不是同组算法或经校准语义分数。结果始终为 `pending_review`，包含 duty 对照、基线代表关系摘要和反对/撤回关系的引用，可继续检查其来源。无可用职责与检索无命中分别表达；没有关系不表示已排除该候选。

| 性质 | 表达与限制 |
|---|---|
| 机器提议 | `state=pending_review`、`semantic_validation=not_run`；显式 `link` 同样是提议 |
| 可定位事实 | `source_binding=validated_p1_quotes`；只证明 P1 引文/身份/偏移合法，不证明工作语义 |
| 合成独立参照 | `semantic_validation=synthetic_control_only`；支持时为 `controlled_support`，只允许 synthetic namespace，仍不是人审或真实效果 |
| 外部审核材料 | `external_record_unverified`；保存版本化材料及声称的 reviewer，**不认证署名/授权/独立性**，支持仍保持 pending |
| 人工确认 | 本接口不认证真人，始终 `human_confirmation=not_confirmed`；不能将上两项当成真人确认 |
| 正式职业 | 关系 `formal_identity=null`、状态 `formal_roles=[]`，不开放 merge/split/assign_role/publish 等操作 |

同一 JD 可关联多个候选，各关系独立；不选最高分职业、不沿成员关系传递相似身份。`members` 是当前待研究关系 ID 列表，包含有疑点的关系，**不是已确认同组 JD**。`disputed` 保留反证；`rejected_proposal`/`withdrawn` 不在当前 members 中，旧版仍可读取，原观察重跑不会复活它们。

## 操作与纠正

完整严格输入见 [models.py](models.py)，未知字段和操作拒绝：

- `link`：`candidate_id, analysis_sha256, work_ids, reason`。候选必须在批次基线，分析必须是本批输入，至少引用实际 duty；一个 JD 可以分别关联多个候选。已有关系只能 `correct`，不能通过重复 link 覆盖。
- `correct`：`relation_id, expected_sha256, decision, reason, verification`。decision 为 `corroborates/weakens/rejects/withdraw`。expected 是**旧关系完整对象**摘要；纠正需绑定基线旧关系，不会读取半批新状态。普通机器支持仍 pending；反证为 disputed，拒绝/撤回分别保留。可附 `counterevidence:[WorkRef]`，保留可回源的削弱依据。
- `correct.replacement`（可选）：`{analysis_sha256,work_ids}`，必须是本批同 namespace/JD 的新分析，至少有 duty。旧分析进入 superseded，新旧均可读。不能借替换更换 JD 身份。批内出现新分析但未明确替换时，旧关系保留，`pending_analysis_sha256s/needs_reassessment` 提醒重评，不自动选一个“更正确”版本。
- `describe`：`candidate_id, expected_version, description, research_question, unresolved, reason`。只修改机器解释及疑点，不修改 core_work、不使用描述扩大检索范围。完整共同职责重归纳属于后续 P4，此处没有偷做自动演化。

`verification=null` 是普通机器纠正。受控语义适配材料包含 `kind, subject_sha256, document, document_sha256, quote, reviewer, provider_version`；`kind` 为 `synthetic_control` 或 `external_review_record`。`document_sha256` 是 UTF-8 原文摘要，quote 必须在 document 内，且含 `service.review_subject(old_relation, baseline_candidate, decision, replacement, counterevidence)` 的完整摘要，以绑定确切候选/关系/比较范围。哈希通过只证明材料绑定；不存在将外部自述升级为认证人审的路径。未来可靠语义处理器可以提供带版本的新材料并用新批次重解释，旧材料不改写。

## P4/P5 最小读取契约与恢复

Python 入口为 `CandidateStore(path, create=False)` 上下文管理器及 `apply_batch(store, request, analyses_by_sha, loaded_knowledge)`。CLI 和 Python 使用同一事务实现；`init` 才能创建独立库。不能打开既有非 P3 SQLite，不迁移、不触碰旧分析库。只支持本地文件系统上的小规模离线研究，未做网络盘、断电或大规模性能验收。

| 输出版本 | 稳定字段/语义 |
|---|---|
| `m2-work-state-1` | `binding={registry_id,revision,sha256}` 指向整批不可变快照；`candidates`、`relations` 按 ID 查询；`analysis_sha256s` 为截至该版已观察的原分析摘要 |
| candidate | `id,version,status,maturity,core_work,description_nature,members,competing_candidate_ids,unresolved`；版本在有效成员/依据/解释变更时每批最多加一 |
| relation | `id,candidate_id,namespace,jd_id,analysis_sha256,work_ids,baseline,state,source_binding,semantic_validation,human_confirmation,formal_identity`；ID 绑定候选与来源 JD 身份；pending/superseded 分开 |
| state.report | 本批 `baseline,algorithm,operation_version,knowledge,inputs,alignments,observations,searches,reassessment_reasons,change_nature`；包括 P1 的输入/处理器/覆盖版本，P2-1 原始知识摘要与存储对象摘要分别保留 |
| `m2-work-history-1` | 候选每次实际变化的 `binding,candidate`；用其 revision 取整批关系截面 |
| `m2-work-jd-1` | 指定历史版内 JD 的全部观察分析摘要、当前关系及 binding；未分析/无关联仍可见，不是 vacancy 数 |
| source | `analysis/knowledge/alignment/review` 的冻结原对象；读取不执行当前模型或规则 |

SQLite `sources` 内容寻址、`batches` 只追加完整快照，UPDATE/DELETE/REPLACE 由触发器保护。`BEGIN IMMEDIATE` 和整批 binding 防止并发提交过时判断；同批自动线索和显式操作只读取同一基线。提交前退出由 SQLite 回滚，提交后输出丢失可按 batch ID 精确重试；不存在从半批状态继续的路径。读取时校验对象摘要；历史读取不重新运行算法。

同 JD 分析重跑不增加成员；不同来源的相同规范正文只列内容组，**内容不同也不证明来源独立**。`counts.linked_jd_identities`/`unique_content_groups` 只是当前关系的工程数量；`independent_evidence`、`vacancies` 始终 null，不计算需求率。知识变更显示重评原因，输入/分析版本分开保留；`change_nature=candidate_research_not_market_change` 禁止把重解释当成市场变化。

## 验证

```powershell
python -m pytest tests/test_job_analysis/test_work_candidates.py tests/test_job_analysis/test_work_candidates_cli.py -q
```

合成测试使用 pytest 临时目录与独立库，包含真实 CLI 子进程、两批读回、反证/撤回、同批快照、转载/重跑、多候选/链条、部分/目录空、过时基线/并发、来源保护、提交前/后强退。真实人审同组分母为零，不能由这些测试推导真实语义准确率；P2-2 的真实语义仍留待 #63。测试完成的数量、持久化演示与 CI 证据直接报告在 #65。
