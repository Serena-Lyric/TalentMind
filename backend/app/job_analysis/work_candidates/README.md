# P3/P4 工作组合候选与自动研究演化

独立离线入口，依赖 P1 `m2-semantic-0.2` 与 P2-1 知识快照；通过 delivery 接入页面。跨批研究按 [#69 恢复授权](https://github.com/Serena-Lyric/TalentMind/issues/69#issuecomment-6703712797)复用 [#63](https://github.com/Serena-Lyric/TalentMind/issues/63#issuecomment-6703699048) 的有界工作语义接口。PR #64 已合并但真实语义未验收；阶段状态仅在[总计划](../../../../docs/superpowers/plans/2026-10-28-m2-core-delivery-plan.md#3-分段地图与当前进度)维护。

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

每批对基线候选的**有效研究证据**执行逐成员有界职责比较。`knowledge.work_semantics.compare_work` 独立构造来源动作、具体功能对象与责任语境；同一条入批职责必须对每个有效成员都存在直接局部支持，才生成自动研究关联。条件、否定、他人职责、辅助与核心错位不通过；A→B、B→C 不能传递并组。未知表述仍可能漏检；完全相同且明确承担的文本可保留 `exact_local_text_repetition` 局部观察，不冒充语义解释。`lexical_matches` 保留旧二元字符交集对照，但不据此写关系；`candidate_checks` 保存全部逐成员比较和未决原因，最多返回十个自动研究候选。无共享方面仅表示本方法没有支持，不是确定的职业反证。

P4 使用冻结 `research.comparison_work`；旧快照从冻结有效关系回源，空范围不回落已撤回种子。标题、技能与摘要不代替职责证据。关系仍为 `pending_review`，`discovery.kind` 区分 `automatic_bounded_semantic/explicit_link/explicit_seed`，自动关系另保存基线、逐成员检查与合成/观察输入性质。自动机器研究生效不需要逐条人审，但 `whole_group_confirmed=false`，不确认整岗身份。

| 性质 | 表达与限制 |
|---|---|
| 机器提议 | `state=pending_review`；自动有界比较为 `semantic_validation=bounded_machine_comparison`，显式 `link` 保持 `not_run`；均未独立人审 |
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
- `describe`：`candidate_id, expected_version, description, research_question, unresolved, reason`。兼容 P3 的显式研究标签/问题/备注修改，不修改种子 core_work、不使用文字扩大检索范围。P4 当前自动解释独立位于 `research`；下游读取它，不能把旧标签当自动修订结果。

所有关系创建/显式操作完成后，统一核对该 JD 截至本版已观察的分析，其他未明确 superseded 的版本均列为 pending；create/link 不能清空已存在的版本疑点。`analysis_selection=unreviewed_representative` 表示用于定位的代表分析，不表示其优于 pending 版本。种子引用同 JD 多版本时只保留一个确定性代表及全部竞争版本，不按最后写入覆盖；不同候选上的替代判断互不传递。

`verification=null` 是普通机器纠正。受控语义适配材料包含 `kind, subject_sha256, document, document_sha256, quote, reviewer, provider_version`；`kind` 为 `synthetic_control` 或 `external_review_record`。`document_sha256` 是 UTF-8 原文摘要，quote 必须在 document 内，且含 `service.review_subject(old_relation, baseline_candidate, decision, replacement, counterevidence)` 的完整摘要，以绑定确切候选/关系/比较范围。哈希通过只证明材料绑定；不存在将外部自述升级为认证人审的路径。未来可靠语义处理器可以提供带版本的新材料并用新批次重解释，旧材料不改写。

## P4/P5 最小读取契约与恢复

Python 入口为 `CandidateStore(path, create=False, readonly=False)` 上下文管理器及 `apply_batch(store, request, analyses_by_sha, loaded_knowledge)`。`readonly=True` 使用 SQLite `mode=ro`，不申请写事务或初始化，适用于任务运行期间读取。CLI 和 Python 使用同一事务实现；`init` 才能创建独立库。不能打开既有非 P3 SQLite，不迁移、不触碰旧分析库。只支持本地文件系统上的小规模离线研究，未做网络盘、断电或大规模性能验收。

| 输出版本 | 稳定字段/语义 |
|---|---|
| `m2-work-state-1` | `binding={registry_id,revision,sha256}` 指向整批不可变快照；`candidates`、`relations` 按 ID 查询；`analysis_sha256s` 为截至该版已观察的原分析摘要 |
| candidate | `id,version,status,maturity,core_work,description_nature,members,competing_candidate_ids,unresolved`；P4 新增 `research` 有效机器解释（见下节）；版本在有效成员/依据/解释变更时每批最多加一 |
| relation | `id,candidate_id,namespace,jd_id,analysis_sha256,work_ids,baseline,state,source_binding,semantic_validation,human_confirmation,formal_identity`；ID 绑定候选与来源 JD 身份；pending/superseded 分开 |
| state.report | 本批 `baseline,algorithm,operation_version,knowledge,inputs,alignments,observations,searches,reassessment_reasons,change_nature`；包括 P1 的输入/处理器/覆盖版本，P2-1 原始知识摘要与存储对象摘要分别保留 |
| `m2-work-history-1` | 候选每次实际变化的 `binding,candidate`；用其 revision 取整批关系截面 |
| `m2-work-jd-1` | 指定历史版内 JD 的全部观察分析摘要、当前关系及 binding；未分析/无关联仍可见，不是 vacancy 数 |
| source | `analysis/knowledge/alignment/review/comparison` 的冻结原对象；读取不执行当前模型或规则 |

SQLite `sources` 内容寻址、`batches` 只追加完整快照，UPDATE/DELETE/REPLACE 由触发器保护。`BEGIN IMMEDIATE` 和整批 binding 防止并发提交过时判断；同批自动线索和显式操作只读取同一基线。提交前退出由 SQLite 回滚，提交后输出丢失可按 batch ID 精确重试；不存在从半批状态继续的路径。读取时校验对象摘要；历史读取不重新运行算法。

同 JD 分析重跑不增加成员；不同来源的相同规范正文只列内容组，**内容不同也不证明来源独立**。`counts.linked_jd_identities`/`unique_content_groups` 只是当前关系的工程数量；`independent_evidence`、`vacancies` 始终 null，不计算需求率。知识变更显示重评原因，输入/分析版本分开保留；`change_nature=candidate_research_not_market_change` 禁止把重解释当成市场变化。

## 验证

```powershell
python -m pytest tests/test_job_analysis/test_work_candidates.py tests/test_job_analysis/test_work_candidates_cli.py -q
```

合成测试使用 pytest 临时目录与独立库，包含真实 CLI 子进程、两批读回、反证/撤回、同批快照、转载/重跑、多候选/链条、部分/目录空、过时基线/并发、来源保护、提交前/后强退。真实人审同组分母为零，不能由这些测试推导真实语义准确率；P2-2 的真实语义仍留待 #63。测试完成的数量、持久化演示与 CI 证据直接报告在 #65。

## P4 自动有效研究解释

`apply` 无需新增开关/人工接受步骤：先完成冻结旧基线上的所有比较和关系操作，再自动回读当前及历史关系引用的 P1 原对象，构造 `m2-work-research-1`。本批新投影只用于后续批次；整个事务失败则不产生半版。

| 字段 | 消费语义 |
|---|---|
| `research.version/description/nature/status` | 当前有效、自动生效的 `machine_hypothesis`；按具体职责范围去重描述，详细映射仍逐成员保留。`version/effective_hypothesis_sha256` 标识有效解释；来源投影精确版本由整批 binding 和完整 research SHA 标识。`disputed/no_active_basis/observing` 与候选稳定身份分开；不代表人审或正式岗位 |
| `comparison_work` | 当前可用的局部职责引用。只将关系选定范围用于**待研究检索**；disputed、撤回/拒绝和未选择分析版本不参与。不沿检索命中传递同组真值 |
| `shared_statements` | 所有当前适用成员完整、且无未选职责时的逐字职责交集；相同规范正文的转载不构成多个内容组。仅记录不同内容组都有这句话，不称语义共同核心或独立支持。不同语言栈不改变职责文本比较；等价改写可能没有逐字交集 |
| `semantic_shared_statements` | 不同内容组的局部共同工作，逐成员且所选工作两两直接比较，不取相似链传递闭包；每条保留引用与具体判断，仍不是整岗或人工确认 |
| `member_explanations[].semantic_scope` | 原职责逐条有界检查、已选职责、辅助职责、成员差异、未覆盖核心职责；作用域与覆盖独立于关系数量 |
| `member_explanations` | 当前每个关系的完整目标/对象/职责原 claim（含引文）、选定/未选职责、P1 coverage/outcome、分析器/模型/提示配置、疑点、反证、知识对齐和岗位比较摘要。partial 的有效局部可参与检索，但不能冒充完整共同范围 |
| `historical_relations/historical_explanations` | 所有曾影响该候选的确切关系及原成员在当前知识下的比较；只供检查，不复活旧成员。原时点的解释仍从对应 `show --revision` 读取 |
| `controlled_support_relation_ids/semantic_validation/independent_support` | 受控支持逐关系单列；当前为 `bounded_machine_comparison`，开放工作语义未独立验收，独立支持始终 null，外部 reviewer 材料不认证人审。转载内容组不等于来源独立性 |
| `report.evolution` | 本批冻结基线、旧/实际生效研究 SHA、版本、增删职责引用及改变/不改变原因。`applied` 表示有效解释改变，`evidence_updated` 表示源投影改变。相同观察重放不增加版本；新身份转载保留新关系/来源审计（P3 candidate 版本可变），有效解释不重复演化 |
| `report.evidence_changes/reassessment_reasons` | 新观察、原文内容、分析器/模型/提示变化与知识变化分账；同 JD 多版本保留竞争，不自动选最新。知识变化即使没有新 JD 也重新比较原成员；`change_nature` 始终研究重解释，不能据此计算需求或市场演化 |

这里的自动变化包括有界研究范围、局部语义共同陈述、成员差异及未覆盖范围，开放中文同组仍未独立验证。比较使用原始引文，P1 转述不能擦去原文否定；`core=null` 保留重要性未知，不称已知核心。争议反证尚未解除时不自动扩充关联；撤回会收窄解释和有效引用，旧版不重算。暂不把一条复杂 claim 中相同的局部方面扩张为整条支持：尚未支持的方面不能跟随完整 `work_ids` 进入后批。由此仍可能遗漏有价值的局部任务，需保留待裁决案例，不能以全部 unknown 宣称语义完成。

`structural_suggestions`（`m2-work-suggestion-1`）提供 `review_split/review_overlap/review_role`，各自绑定候选完整 SHA/版本、全部关系摘要、源引用与竞争解释。无逐字交集只是检查范围的理由，不证明必须拆分；共享局部同源职责不证明应合并。候选/测试岗位比较的 supported 只触发建议，不作正式归属。缺目录不生成新职业身份；新职业确认/正式发布没有写入入口。

当前环境没有可信人工身份链；所有建议为 `unconfirmed`、`formal_effect=false`，不接受任何 reviewer 字符串授予确认。`suggestion` 仅只读检查当前整批与确切主体版本；过期拒绝，需重新读取新建议，不把旧决定套用新版本：

```powershell
# binding.json 仅包含 show 返回的 binding 对象（registry_id/revision/sha256）
python -m app.job_analysis.work_candidates suggestion --state ../data/local/m2-p4/state.db --id <建议ID> --baseline ../data/local/m2-p4/binding.json
python -m app.job_analysis.work_candidates source --state ../data/local/m2-p4/state.db --kind comparison --sha256 <member_explanations中的role_comparison_sha256>

# 全新私有输出目录；每个 apply/show/retry 均使用真实 CLI 子进程
python -m app.job_analysis.work_candidates.demo --output ../data/local/m2-p4/demo-new --knowledge app/job_analysis/knowledge/catalog/backend-foundations.v1
python -m pytest tests/test_job_analysis/test_work_evolution.py tests/test_job_analysis/test_work_evolution_cli.py -q
```

永久合成演示保留六批请求/输出、输入、SQLite、命令退出码、源摘要和文件 manifest；再次使用相同输出目录拒绝覆盖。它检验两条初始证据、新局部职责自动生效、下一批实际读取并拒绝传递自动关联、显式合成误关联的反证/撤回收窄、重复无修订、旧版读回和精确重试。演示输出为有意保留的复核资产，pytest 临时夹具仍按唯一目录 finally 清理；不接触生产库。当前只面向小规模离线研究，逐候选回读历史的成本未做规模化验收。

真实受控回放入口（显式 DEV run map，不遍历 HOLD）：

```powershell
python -m app.job_analysis.work_candidates.evaluation --source-runs <已授权的source-runs.json> --knowledge app/job_analysis/knowledge/catalog/backend-foundations.v1 --output ../data/local/m2-cross-batch/new-run --via-delivery
```

逐批经过真实 `delivery.execute`，保存源 run/analysis、源码依赖、P1覆盖、技能状态及未决原因、四轴研究、全部成员比较、显式观察种子、自动关联和维护后批消费。种子及撤回是受控评价操作，不是新机器发现或真实方向人审。`replay_cli_baseline(current_output, output, backend, knowledge_path)` 可用明确的旧 checkout 真实 CLI 回放相同输入/顺序/种子，绑定源码摘要并拒绝运行中源码变化；不能把新方法中的字面对照冒称完整旧版回放。真实同组/演化人审分母为 0 时准确率、召回率保持 null，单独保留 Agent 来源绑定诊断。完整输出私有。

P4 固定 base/head、实际命令/分母、私有持久化产物和真实 CI 直接报告 [#67](https://github.com/Serena-Lyric/TalentMind/issues/67) 与独立 PR；真实语义人审分母为 0、准确率未验证，不能以合成测试数替代。
