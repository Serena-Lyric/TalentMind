# P2 版本化知识、候选治理与岗位解释

本包把 P1 已保存的机器候选事实对齐到独立知识快照，不修改 P1 的
`claims/requirements/relations`、五态、程度、条件、组合、证据或
`machine_unreviewed`。默认入口是纯离线 CLI，不连接 MySQL/Neo4j、不调用模型，
也不发布正式技能或岗位目录。

## 当前交付

- `catalog/backend-foundations.v1/`：小范围外部知识快照。来源包含 Python 3.14.10
  中文文档、MDN 中文 JavaScript/TypeScript 页面和 Kubernetes 中文概述；两条 P0
  候选岗位参照保留原来源、字节摘要和许可未明限制。快照只保存短引用，不复制整页/整本资料。
  这里的“SHA-256”是知识开发时记录的来源下载字节摘要；`load_snapshot` 只校验仓库清单、
  来源字段、引用结构和短摘录非空，不会联网重新下载或独立证明外部页面/PDF 当前内容。

- `align_analysis`：只做 NFKC + 空白/大小写归一后的精确标准名或显式别名匹配。
  模糊名称、共同出现和同一模型重复输出都不会建立同义；一个原始 member 同时含多个已知概念时
  返回 `ambiguous`，不擅自拆分。
- `compare_roles`：按职责短语和显式边界比较，并识别局部否定。只有 P1 duties coverage
  完整、核心性明确且为正时才能给 `supported/not_supported`；partial 或 core 未确认时保持 `unresolved`。
  目录为空时返回 `no_role_candidates`，不阻止技能对齐加载。
- `CandidateRegistry`：只从有明确能力上下文的未知表达建立候选；每份观察显式保留来源身份。
  `candidate-evidence-policy-1` 只在至少两个已知且不同的来源身份提供语义一致证据时自动核验；
  未明来源、同源改写和跨来源近似转载分别保留 `source_independence_unverified / same_source_only /
  likely_republished`，不得进入 projection。不同用途上下文单独归档，但不自动宣称概念身份冲突。
  修订必须绑定新 P1 证据，版本只追加。普通新观察只追加证据，不解除 `disputed/withdrawn`，
  保留原争议/撤回原因、描述及竞争假设；当前未实现争议解决或自动恢复使用流程。
- `locate_impact`：旧对齐必须绑定旧静态知识与旧 candidate projection SHA；静态概念/别名/关系和
  candidate 新增、修订、撤回都可定位受影响对齐；角色、来源或无法证明范围时保守标记全部。
  projection 策略、revision、身份等非概念元数据变化时，保守重评所有提供的记录，
  即使同次还存在可精确定位的别名或概念变化；相同 projection 不额外触发重评。
- `build_profile`：只从已支持的角色比较与显式版本对齐重建候选画像，保留成员原始五态和组合，
  不把单个成员的 `required` 推广为全体岗位要求。

知识状态只允许 `test / candidate / formal`。当前发布快照没有正式条目；正式条目缺少逐项批准证据
会加载失败。候选合并、拆分、身份确认、正式准入和正式发布都返回
`requires_human_decision`，本段不开放自动正式准入。
自动核验只允许生成 `candidate` 投影，通过 `CandidateRegistry.project()` 持久化为独立 SHA；
消费时必须同时匹配 `target / category / context`。它既不是正式 knowledge，也不是人工确认，
来源独立性分类不是概率。画像必须绑定单一 candidate projection SHA，拒绝混版。


## 命令

以下命令从 `backend/` 执行。仓库内输出必须位于 `data/local/`；其他路径会拒绝。

```powershell
# 校验知识清单摘要、来源、许可字段和引用完整性
.\.venv\Scripts\python.exe -m app.job_analysis.knowledge validate `
  --snapshot app/job_analysis/knowledge/catalog/backend-foundations.v1

# 接受 P1 Analysis JSON 或含 manifest 的已保存 P1 run 目录
.\.venv\Scripts\python.exe -m app.job_analysis.knowledge align `
  --analysis ..\data\local\p1-run `
  --snapshot app/job_analysis/knowledge/catalog/backend-foundations.v1 `
  --output ..\data\local\p2-knowledge\alignment-001

# govern 成功后会生成 projections/<sha256>；可显式用于候选性质重解释
.\.venv\Scripts\python.exe -m app.job_analysis.knowledge align `
  --analysis ..\data\local\p1-run `
  --snapshot app/job_analysis/knowledge/catalog/backend-foundations.v1 `
  --candidate-projection ..\data\local\p2-knowledge\candidate-registry\projections\<sha256> `
  --output ..\data\local\p2-knowledge\alignment-candidate-001

.\.venv\Scripts\python.exe -m app.job_analysis.knowledge compare `
  --analysis ..\data\local\p1-run `
  --snapshot app/job_analysis/knowledge/catalog/backend-foundations.v1 `
  --output ..\data\local\p2-knowledge\comparison-001

.\.venv\Scripts\python.exe -m app.job_analysis.knowledge govern `
  --analysis ..\data\local\p1-run `
  --alignment ..\data\local\p2-knowledge\alignment-001 `
  --registry ..\data\local\p2-knowledge\candidate-registry

.\.venv\Scripts\python.exe -m app.job_analysis.knowledge profile `
  --role-id p0-ref-programming `
  --comparisons ..\data\local\p2-knowledge\comparison-001 `
  --alignments ..\data\local\p2-knowledge\alignment-001 `
  --output ..\data\local\p2-knowledge\profile-001

.\.venv\Scripts\python.exe -m app.job_analysis.knowledge impact `
  --old app/job_analysis/knowledge/catalog/backend-foundations.v1 `
  --new ..\data\local\p2-knowledge\knowledge-v2 `
  --old-candidate-projection ..\data\local\p2-knowledge\old-projection `
  --new-candidate-projection ..\data\local\p2-knowledge\new-projection `
  --alignments ..\data\local\p2-knowledge\alignment-001 `
  --output ..\data\local\p2-knowledge\impact-001
```

所有成功命令只向 stdout 输出状态、计数和 SHA；失败返回 1 和安全原因码。
`value.json` 与 `manifest.json` 使用 write-once 目录，已有输出拒绝覆盖。

## 读取语义

- 对齐结果绑定 `input_sha256`、P1 完整分析摘要、知识 ID/revision/SHA。
- P1 的 `outcome` 和六维 coverage 原样进入对齐/岗位比较读取边界；`partial`、
  `not_run`、执行失败与知识未知不会合并成同一个空结果。
- `exact_synonym` 表示当前知识版本的精确名称/显式别名，不表示可替代性；
  关联概念的 `narrower_than`、`related_to` 等关系单独列出。
- `unknown` 只表示当前知识版本未命中，不是“不存在”或“不是技能”。
- `ambiguous` 保留全部候选概念 ID，不选一个答案。
- 自动核验候选只能通过独立 projection SHA 读取；`concept_source=candidate` 且正式准入仍为 false。
  同一表面词的不同上下文保留为 competing candidate IDs；不会累计为单一候选的独立验证强度。
- projection 保留 disputed 候选用于追溯，但不代表可确定使用。单个适用 disputed 候选返回
  `unknown`，不选择 concept，保留 candidate ID/版本 SHA 和未决原因；多个适用候选
  仍为 `ambiguous`。画像沿用未知/歧义和绑定的 projection，不把争议解释升级为确定概念。
- 无岗位目录时技能知识仍可加载/对齐；岗位比较返回 `no_role_candidates` 与空对比范围。
- 岗位摘要明确 `all_roles_in_bound_snapshot`；不能解释为排除快照外职业。
- 候选画像固定 `candidate_profile`、`linked_members_only`、`not_formal_role` 和
  `not_market_statistics`。

## 验证

```powershell
.\.venv\Scripts\python.exe -m compileall -q app/job_analysis/knowledge app/job_analysis/baseline
.\.venv\Scripts\python.exe -m pytest `
  tests/test_job_analysis/test_knowledge_catalog.py `
  tests/test_job_analysis/test_knowledge_alignment.py `
  tests/test_job_analysis/test_knowledge_roles.py `
  tests/test_job_analysis/test_knowledge_governance.py `
  tests/test_job_analysis/test_knowledge_versions.py `
  tests/test_job_analysis/test_knowledge_cli.py `
  tests/test_job_analysis/test_baseline_contract.py -q
```

专项测试均为合成或本地受控工程样例，不证明中文市场准确率，也不替代 P0 DEV 人工参照和
P6 独立效果评价。HOLD 未读取。

阶段依据：[Issue #61](https://github.com/Serena-Lyric/TalentMind/issues/61)、
[P2 分段目标](../../../../docs/superpowers/plans/2026-10-28-m2-core-delivery/P2-knowledge-role.md)、
[审核标准](../../../../docs/superpowers/specs/2026-10-28-m2-delivery-review-standard.md)。

## P2-2 岗位检索与四轴解释

`attribute_roles(analysis, knowledge, policy, candidate_projection=None)` 位于
`attribution.py`，输出独立 `m2-role-attribution-1`；当前解释器为 `bounded-work-attribution-2`，
`read_attribution(path)` 继续校验并原样读取解释版本 1/2 的历史结果。
原 `compare_roles` / `RoleComparisonSet` v1 和 `build_profile` 的语义保持不变。
P2-3 可读取 `axes`、`comparisons`、`unaccounted_work` 和 `alignment`，不能将候选值当正式岗位或统计资格。

从仓库 `backend/` 执行以下离线命令；路径中的 P1 run、projection 和新结果都须显式指定。
`--analysis` 也支持严格的 `m2-semantic-0.2` JSON，P1 run 目录必须通过原 manifest 校验。

```powershell
python -m app.job_analysis.knowledge attribute `
  --analysis ../data/local/<saved-p1-run> `
  --snapshot app/job_analysis/knowledge/catalog/role-references.v3 `
  --policy app/job_analysis/knowledge/policies/role-attribution.v2.json `
  --output ../data/local/<new-attribution-result>

python -m app.job_analysis.knowledge read-attribution --result ../data/local/<saved-attribution-result>

python -m app.job_analysis.knowledge reexplain `
  --previous ../data/local/<saved-attribution-result> `
  --snapshot app/job_analysis/knowledge/catalog/role-references.v3 `
  --policy app/job_analysis/knowledge/policies/role-attribution.v2.json `
  --output ../data/local/<another-new-result>
```

`attribute/reexplain` 可加 `--candidate-projection <saved-projection-directory>`。
重解释不会默认继承旧 projection；未指定代表本次没有使用该投影，结果明确绑定 null。
stdout 仅输出摘要和各轴状态，退出码 0 表示产物可读（包括未决），1 表示拒绝/输入输出错误。
结果仍使用只追加目录、`value.json` + SHA manifest；已有目录和仓内公开输出路径拒绝。

### 读取契约与判定边界

- **检索**：全量比较绑定快照中的每个角色，保留 available/checked/recalled IDs、
  `unranked_exhaustive` 及范围局限。旧 anchors 仅为 `retrieval_clues`，没有线索的角色也实际比较。
  当前目录内没有 top-k 截断；目录外职业、未配置中文表达和未命中来源任务仍可能遗漏。
- **逐候选解释**：`definition` 与原知识 JSON/摘要绑定，保留 maturity、来源、版本、未决边界。
  `supports/context_supports` 分别引用 P1 职责/目标对象和参考责任；每项保存动作、对象、
  core/auxiliary/unknown、精确局部引文及参考摘录。`bounded_pattern_support` 是有界规则支持，
  不代表语义已人审。`deliveries` 只使用与该参考工作处于同一工作片段的明确交付，不借用其他职责或无关联目标。
  未覆盖 duty、未对齐来源目标/对象、未覆盖参考责任与 `unaccounted_work` 分别保留。
- **质量**：P1 claims、五态、程度、组合、条件、对象、关系与原始证据嵌入保存，不改写。
  partial duties、重要性未知、缺交付等阻止强主岗；目标/对象各自的 partial/not_run 单独报告。
  否定、条件、他人责任、历史经验及教学/介绍的作用域做保守检查，无法覆盖的表达保持缺口。
  真正的 `conflict` 必须来自配置的明确参考边界及实际正向职责，不把有限目录未命中当排除。
- **四轴**：`family/canonical_job/technology_tracks/seniority` 各有 status、values、candidates、
  证据与理由。single/multiple 仅表示当前受限机器候选集合。核心工作并列时主岗为 null；
  辅助关联单列，未解释核心片段不能靠职责条目数消除。`canonical_job` 的值直接引用来源角色 ID，
  不自由生成正式名称。没有已配置级别标准时 seniority 未决，年限/熟练度不换算级别。
  技术方向由 `tracks.py` 单独读取有出处的实际技术工作（duty/goal），**不以岗位参照命中为前提**。
  目录为空、标准岗位未决或 core 不明确时，有明确手段—技术—工作证据仍可提出局部方向候选。
  技术名来自配置、原技术能力成员或实际工作中逐字出现的拉丁字母技术名称；未知名称保持原文候选，
  不发布规范名/同义关系。P1 摘要可省略工具，原引文必须明示使用且实际工作方面仍与该 claim 对账。
  单独熟悉要求、经验/技术列表、条件/否定、他人责任和培训内容不确认方向；跨任务不继承手段。
  仅有技能共现也不确认方向，不更改原要求五态或把实际使用变成必备/熟练度。
- **工作形态**：保留 single/parallel/mixed/composite hypothesis 与明确 multi-position advertisement；
  composite 必须由版本化参考规则显式声明，标题“全栈”或多技能不建立成熟职业。
  单候选缺交付/重要性证据复用 `unresolved`；`mixed_hypothesis` 需要不同方向及独立工作片段，
  并记录 `shape_evidence`，多个参照解释同一工作不构成混合。主岗+辅助可为受限混合假设；
  两项核心主次不明仍为 `parallel_core_hypothesis`，不因此建立 P3 身份或计数事实。
  明确多职位广告保留职责候选、清空单岗位选择；不拆分职位数。
  `identity_action=none`、`formal_statistics_eligible=false` 始终保留。
- **版本**：绑定原始 input、完整 P1 analysis SHA、知识原始 JSON SHA、候选 projection SHA、
  policy revision/规范化内容 SHA、检索/解释版本及载入时源码摘要。源码摘要将 CRLF 规范为 LF；
  知识摘要校验原始字节，Git attributes 固定其 LF，不改变旧 manifest。
  旧结果内含当时事实、规则、知识 JSON 与定义，读取不执行当前分类算法。
  `reexplain` 使用旧 P1 事实并追加 `reinterprets_sha256`，标为 `interpretation_only`，不表示市场变化。

### 参考来源与适用范围

`catalog/role-references.v2` 保留两个 P0 国内粗粒度参照，新增三个有来源的候选摘要：
软件开发、数据仓储、商业智能分析。`policies/role-attribution.v1.json` 是 Agent 编写的中文
动作/对象/交付适配规则，与外部原定义分开版本化；family 映射也是候选解释。
`canonical_candidate=true` 仅允许提出岗位候选，不代表正式职业获批。
新快照不包含 P2-1 的 synthetic test role；旧快照保持原字节和原摘要。

推荐的 `catalog/role-references.v3` / `policies/role-attribution.v2.json` 保留五个参照，
独立补入 O*NET Task 16139 的 BI 工具/系统维护工作方面；原任务原文和下载摘要可核对。
新策略对已有程序任务补“代码实现/编码”和设计文档输出，对 Task 21667 补原文已有的设计动作。
共享对象的并列谓词只在无第二对象的有界语法内联结，不能跨新对象/否定条件/其他任务借用。
`default_policy_path()` 仍返回 v1 以保持既有调用兼容；使用新版必须显式传入匹配的新策略和快照。
解释 v1 曾将单一弱候选标为 mixed，读取旧结果仍原样保留这一历史解释；需要纠正时显式 reexplain。

新增参考取自 [O*NET® 31.0 Database](https://www.onetcenter.org/database.html) 的
[Occupation Data](https://www.onetcenter.org/dl_files/database/db_31_0_json/occupation_data.json) 和
[Task Statements](https://www.onetcenter.org/dl_files/database/db_31_0_json/task_statements.json)，
原始来源为 USDOL/ETA，按 [CC BY 4.0 许可](https://www.onetcenter.org/license_db.html)使用。
TalentMind 翻译、摘编并添加中文匹配词表；USDOL/ETA 未批准、背书或测试这些修改。
Task ID、原文短引、来源下载摘要和具体更新时间随快照保留；完整下载仅在本地留存。
国外职业参考不等于中国市场正式标准，未摘录任务/未定义边界不能成为排除证据。

本实现不使用收费模型或在线检索，尚不能处理任意中文改写、隐含主次或目录外职业。
专项合成反例与真实 DEV 的结果分账，不用测试通过数或全部未决宣称市场准确率。
P2-2 方案、实际命令、首轮失败、DEV 分母、CI 和提审证据集中在
[Issue #63](https://github.com/Serena-Lyric/TalentMind/issues/63)，不新建重复阶段报告。

### 上下文解释与本地语义候选（显式启用）

前述 `bounded` 路径和 `m2-role-attribution-1` 继续保留。新增 `--method context`
返回 `m2-role-attribution-2` / `context-work-attribution-4`；不传该参数仍使用旧路径。
两种结果都由 `read-attribution` 读取，旧解释不补入新字段。`reexplain --method context`
以旧 P1 追加新结果和 lineage，不覆盖旧目录。

```powershell
python -m app.job_analysis.knowledge attribute `
  --analysis ../data/local/<saved-p1-run> `
  --snapshot app/job_analysis/knowledge/catalog/role-references.v3 `
  --policy app/job_analysis/knowledge/policies/role-attribution.v2.json `
  --method context --output ../data/local/<new-context-result>

# 可选：只有明确提供本地文件清单才运行模型；不下载模型或连接远端服务。
python -m app.job_analysis.knowledge reexplain `
  --previous ../data/local/<saved-attribution-result> `
  --snapshot app/job_analysis/knowledge/catalog/role-references.v3 `
  --policy app/job_analysis/knowledge/policies/role-attribution.v2.json `
  --method context --local-model ../data/local/<runtime-root>/local-model.json `
  --output ../data/local/<new-local-model-result>
```

新契约的消费边界：

- `work_units` 保留 P1 职责实际引用内的局部工作、精确位置、作用域、原有重要性和参考缺口，
  目录为空也不丢失。`source_pattern_support` 直接对账原引用，不要求 P1 转述复述相同词表；
  它仍是有界模式支持，不代表通用语义等价。P1 原文、转述、五态和核心性不改写。
- `core_candidate` 表示局部核心工作有依据，不再要求每项职责 core 已知或出现交付动词。
  无对应交付原文时 `deliveries` 仍为空；未解释的核心或重要性未知工作保留在
  `unaccounted_work`，阻止强行选择主岗。可以解释的 core=null 工作不会全局否决其他核心支持。
- `work_links` 只记录同源语句中带目标/用途连接且没有多项职责争用的 duty—goal/object 上下文。
  来源关系单独保存，不补写 P1 成果，不把共享句子自动当成熟职业或正式明确关系。
- `axis_assessments` 区分实际执行与无参考未执行。当前 seniority 为
  `not_evaluated/no_versioned_reference`；技术仍为有出处的原词工作方向，不是正式方向目录。
  解释 v4 中 family/canonical 分别要求有职责事实和适用参考，缺少时明确 not_evaluated；
  技术轴可使用独立的 duty/goal 工作事实，不受职业目录为空影响。
  `axes.*.candidates` 新增 `basis` 与 `semantic_match_key`，可区分模式、技术原词和模型候选。
  解释 v4 的原始模型提议只留在 `semantic` 研究记录，**不进入 axes 候选、召回集合、选中值或主岗，
  不改变工作片段的支持状态或消除 gap**。历史 v3 曾把弱提议放入 candidates，读取仍保持原样；
  这不证明旧弱候选已获语义支持，纠正需显式 reexplain。
- 可选 `semantic` 输出本地模型对工作与参考任务的 `possible_support/related/insufficient`，
  保存理由、双侧证据、模型/运行时/生成参数、固定输入 JSON、当时提示词和响应摘要。
  输入 v2 按 claim 保存实际原文上下文，工作片段引用 claim ID，避免只凭 P1 转述补省略对象；
  列表数字/标点不形成工作。历史输入 v1 仍按当时保存内容验证。
  `possible_support` 只是未核验的局部任务方面假设，不证明覆盖整个任务、完整职业、排除或正式身份。
  技术知识只经 P1 已有 duty—requirement 关系进入输入，保留 explicit/inferred、知识成熟度和投影版本；
  没有关系时不因同一 JD 共现而补关联。历史读取校验保存的输入，不生成当前版本提示词或重新推理。
- 模型必须选择实际存在的工作/角色/任务 ID，解码约束和保存时校验分别执行。
  假 ID、错误归属、重复项或非法输出使 `semantic.status=failed`，保留原局部解释，CLI 摘要为
  `status=partial`。无本地模型、无可用工作或无参照分别标明 not_run 原因，不能算模型比较成功。
  CLI 退出 0 表示结果已保存可读；语义成功须另外检查 `semantic_status`，不能只看进程退出码。

本地清单由操作者准备，字段为 `schema_version=m2-local-model-1`、`binding`、`model_file`、
`runtime_file`、`runtime_files`。文件路径相对清单目录，拒绝绝对路径、逃逸和摘要不符。
`runtime_files` 应记录所用分发目录的全部 EXE/DLL；`binding.runtime_sha256` 为该映射的
`foundation.inputs.digest()`。模型与所有列明运行时文件在加载及每次推理前校验。
`binding` 还需模型 ID/revision/source_url/license_id/model_sha256/runtime_version 以及
`generation={seed:0, temperature:0, max_tokens:2048, context_size:8192}`。

当前适配器使用本地 **Qwen3 GGUF 非思考模板 + llama-completion**，固定 CPU 4 线程、offline 模式、
单次 300 秒超时、无 shell，临时提示文件在结束后清理。它不接受云端 URL/API Key，也不自动启动常驻服务。
本轮公开模型为 [Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF)
revision `bc640142c66e1fdd12af0bd68f40445458f3869b` 的 Q4_K_M（Apache-2.0），
模型 SHA `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`；
运行时为 [llama.cpp b12128](https://github.com/ggml-org/llama.cpp/releases/tag/b12128)。
完整模型、清单和真实产物仅留在私有 `data/local/m2-p2-2-20261105-review2/`。

此路径仍是有限五参照和有界语法保护下的实验性岗位候选解释。复杂作用域、未见表达、模型误支持、
参考覆盖及级别知识仍须独立评价；没有独立岗位人审真值时不报告职业准确率或完整召回。
当前本地 Qwen 4B 的受控 DEV 诊断已观察到明确对象/动作误支持和遗漏，**不宜自动用于业务岗位判断**；
弱候选隔离和来源校验不能证明模型语义可靠，P2-2 业务验收仍未通过。
本地生成式推理的实测与失败、NLI 方案拒用理由及分母见 Issue #63；CI 的合成契约回归不等于模型效果。

### 任务对照：动作、对象与实际执行关系

`--method evidence` 返回 `m2-role-attribution-3/task-evidence-attribution-3`，保留 context 的
P1、知识、对齐、作用域与 gap，再增加独立的任务检索/比较结果。原始模型提议、分数和机器对照
均不写入正式身份，不选择主岗，不回写 P1 或清除基线 gap。

```powershell
# 仅使用显式提供的本地文件；optional 依赖不用于普通 CLI 或历史读取。
python -m pip install -r app/job_analysis/knowledge/requirements-local-semantics.txt
python -m app.job_analysis.knowledge attribute `
  --analysis ../data/local/<saved-p1-run> `
  --snapshot app/job_analysis/knowledge/catalog/role-references.v3 `
  --policy app/job_analysis/knowledge/policies/role-attribution.v2.json `
  --method evidence --local-model ../data/local/<runtime-root>/local-model-instruct.json `
  --task-retriever ../data/local/<retriever-root>/source.json `
  --pairs-per-role 2 --output ../data/local/<new-task-comparison>
```

- `task_selection.proposals` 保存合资格职责与全部参考任务的对照池、两种优先级分数、输入是否截断。
  本地 NLI 只排检查顺序，不作语义核验；另一优先级采用源职责/参考任务的字符词面覆盖。
  每角色先语义首位、再词面首位，剩余预算按语义顺序，预算允许 1～3 个 **pair**，不是 claim 数。
  分数、标题或技术相同均不能确认工作。`selected_pair_ids/checked_pair_ids/pending_selected_pair_ids`
  与实际检查绑定；`unchecked_pair_ids` 单列预算外未检查范围，不作为否定或完整召回。
- 每个 `task_assessments` 只给定一个职责 claim 和一个参考任务，不让模型自由生成岗位/任务 ID。
  `action_relation/object_relation/execution_relation` 分别解释；处于同一流程或供他人使用的输入
  不等于本岗直接承担目标任务；招聘职责不要求已经做完，具体子任务也可以支持一般任务。
  双方动作/对象短引必须逐字来自实际原文、参考定义或该任务绑定的原始引用，原始响应、
  提示词、输入、模型/运行时摘要、模板类型和逐对耗时保存。
- `machine_supported` 要求动作、对象均支持且实际执行，还须通过源 claim、作用域和共同工作范围
  检查；不得把两项独立工作的动作与对象拼接。它是**机器任务方面判断，非独立人审确认**。
  v3 的正向主判断还须单独检查对象类型：同一模型只看到双方对象及实际动作短引，不看整个
  流程理由，区分对象本体/运行组成与说明、计划、输入材料。`object_check` 单独留存输入、输出、
  耗时与绑定；没有执行、未知或失败都不产生支持。它是同模型的第二个问题，不是独立模型/人工真值。
  `different_work` 只表示该对工作不相符，不是排除职业或正式边界反证；`unresolved/failed`
  分别保存语义/关系缺口与调用、格式、引用失败，不能合并为正确未知。
- 只有 machine_supported 生成独立的 `work_candidates`，每项绑定 assessment、源职责、参考任务和成熟度。
  它们与 `axes` 中的基线模式候选、`semantic` 的原始研究提议分别消费，均不能冒充正式职业。
  CLI 的 `task_execution_status`、选中/已检查/待检查数须一并查看；`semantic_status` 仍是旧研究提议阶段状态。
- 任务输入 v2/v3 去除重复身份元数据，有知识对齐的能力上下文才进入模型，未知项仍留在 P1/alignment，
  并保存未发送数量；不是删除未知能力。v3 明确比较岗位责任而非已完成履历；v1/v2 保留原读取语义，
  旧产物不补写空 object_check，不升级为 v3 已检查。历史读取不调用模型。

本地优先级清单 `source.json` 包含 `repository/revision/license/files`，files 必须恰为
`config.json/tokenizer.json/model.onnx` 的 SHA；路径和字节经校验，ONNX 仅 CPU 推理，不联网。
目前适配 id2label 为 entailment/neutral/contradiction 的 XLM-R ONNX；分数仅是 priority。

生成模型清单可显式设 `prompt_format=qwen3-instruct`；旧清单默认 qwen3-no-thinking。
Instruct 模板不注入思考标签或 no_think 指令，禁用上下文滚动，超长/截断输出按失败保留。
本轮使用 [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) 的
[Unsloth GGUF](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF)
revision `a06e946bb6b655725eafa393f4a9745d460374c9`、Q4_K_M、Apache-2.0；字节 SHA 为
`3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`。
模型和数据产物留在私有目录；效果、失败、DEV 分母与真实 CI 写在 Issue #63，不能仅据新契约声称业务通过。

### 源绑定工作解释

`--method work` 当前使用 `m2-role-attribution-4/source-bound-work-comparison-5`，其余显式本地
模型、检索器和预算参数与 evidence 相同。原文、参考任务和目标领域由程序绑定，模型只解释源工作，
不负责重新生成引文。此路径用于检验 evidence 路径的引用生成失败及语义错配；旧路径与旧结果仍可读取。

- `source_evidence/reference_evidence` 保留真实出处；发送的 `work_texts` 排除已识别为他人、条件等
  非当前职责片段，必要时另存 `model_source_evidence`。教学仍作为实际工作比较，不能当作本人编程。
  输入 v2 同时提供完整 `source_context/scope_context`，独立条件、主体和历史控制头在同一职责内
  跨换行或分离引用仍约束后续工作，不能因裁剪限定语而升级。旧输入 v1 不被重新解释或补写字段。
  作用域规则是有限语法保护，依赖 P1 引用覆盖，不是通用篇章理解；跨职责或复杂转折仍须复核。
- 目标输入包含绑定定义的 goals、known_scope、未决边界及已有动作/对象示例。它们限定目标任务，
  不补成源岗位事实；通用系统不能因此被假定为 BI 系统。词面优先级可使用这些版本化示例，
  `definition-context-task-budget-1` 仍只控制检查顺序，不作支持依据。
- 第一问归纳源动作/对象并比较责任、动作和功能对象；归纳字段是机器解释，不是逐字原文。
  潜在正向结果才运行第二问，第二问重新看到同一真实来源和完整目标，不接收第一问解释。
  任一问需要源未说明的用途、组件或责任假设，都不生成工作候选。两问来自同一个模型，存在共同偏差。
- 原始提示、响应、摘要、模型绑定及耗时均保存。读取按已保存响应验证状态和候选，不调用模型。
  只有两问明确支持才生成 `machine_hypothesis/machine_unreviewed` 的独立工作候选；
  不清除基线 gap、不增加业务轴或主岗，不计正式统计。完整性校验不能证明语义正确。
- llama.cpp b12128 的未锚定 `\S` pattern 分支会跳过长度约束；运行器仅移除这一不兼容 pattern，
  保留 schema 顺序和长度限制，程序端继续校验非空及长度。格式失败不被当作不同工作。

### 当前研究解释与执行入口

`research_summary.build_delivery_research(analysis, knowledge, candidate_projection=...)` 是 delivery
实际执行的无网络入口：使用调用方冻结的知识字节、对应策略和 P1 原始引用，逐职责检查当前全部
参照任务，返回 `m2-role-research-1`。来源、知识、策略、实现和结果摘要均保存。
没有匹配知识摘要的策略时使用显式空适配策略，不借用其他目录的岗位或 family。
`axes` 的四轴独立给出研究候选或未决原因；`seniority` 没有版本化参照，保持未执行。
`local_supports` 是有界源工作方面支持，`uncovered_work` 保留无支持职责；不生成主岗或正式统计资格。

`work_semantics` 是 Agent 编写的有界语言适配，不是新职业目录、通用语义模型或人工真值。
它先独立解释源动作、功能对象、具体对象及作用域，再供岗位参照和跨批研究共同消费；不看目标补源。
不同技术栈可保留相同工作；普通系统、规范、评测材料不能自动补成软件开发、BI 或网络责任。
否定、条件、他责、教学、辅助以及未知片段单列，未知表述不能作为反证。
动作与对象仅在同一局部语句绑定，共用对象的并列动词保留；支持不要求原文明示额外产出。
规则有未覆盖词义和复杂语法，保留局部支持不等于完整岗位归属、候选同组或知识覆盖验收。

work v5 使用 `bounded-work-semantics-3`：按完整宾语限定局部名词命中，未识别完整对象保留
`unrecognized_complete_object`；仅模型两次肯定不能消除该缺口。没有词汇命中的普通未知表述仍由模型比较，
不把所有未知都当明确不相符。对象后的组件、英文括号别名与明确通信网络修饰采用有限组合规则。
共享动词后的并列名词逐项解释：已知代码仍可支持局部任务，未知合同等保留 gap；不凭末项消除前项缺口。
名词头的位置映射回未规范化原文，短引文不能借用同句另一处同名对象。
输入 v4/v5 的源帧、完整上下文证据和重要性分开保存；原始引文只提供它实际包含的动作/对象，
上下文只能限制，不能补入未引用事实。原文标题的否定、条件、他责和辅助性质进入源解释；
并列后项的辅助限定不反向污染前项。P1 core、引文和原记录保持不变。
v5 接收和读回都执行已识别的来源限制：没有被引文支持的源帧且存在 `uncited_action_or_object`
时，即使两问都肯定也只能 unresolved，不生成工作候选。普通未知措辞仍交由模型比较；完整引用
包含的代码工作仍可支持局部任务。无冒号及括号式辅助标题随合法短引文保留，主要职责标题可重置。
仍由同一模型作两问，不能当独立核验。已公开 work v3 由 `work_semantics_v1.py` 冻结解释；
work v4 保留 semantics-2、原冒号标题恢复和原接收规则，已知误支持也作为历史记录原样读取，
不冒称已修复。已发布 v1/v2/v3/v4 读回不变；旧模型研究摘要按其解释版本标记 method_version。
默认 `start_work_comparison`、`--method work` 和固定对照运行器均创建 v5；显式旧版本仅用于
历史复现。按新规则重解释须另建 v5 结果并记录来源，不能修改旧文件或只换版本标识。
`claim-diverse-task-budget-1` 在角色内先分散到不同职责，再用余量检查同一职责的其他参照；
work 路径的显式每角色预算允许 1–1000，evidence 历史路径仍为 1–3。
扩大预算不保证召回；全池、选中、已查、待查和预算外各自保存。

当前 `source_work` 默认采用 `bounded-work-semantics-3` 的源上下文：完整行的职责/任务/工作内容标签可不带冒号，也可带配对括号或编号；明确辅助标题随合法短引用恢复，后续主要/中性职责标题结束旧限定，普通叙述和后置标题不控制前文。被完整引用的结构标题只作控制证据，不额外算未知工作，避免长短引用对同一辅助职责产生不同关联。P1原文、core及原引用不修改。

既有条件词构成、且没有实际工作动作的独立控制行也可不带冒号，例如“能力允许的话可以延伸”。
普通带动作的条件职责句不升级为标题；来源仍按局部范围解释，不拿旧版整句否定覆盖“仅开发软件”等明确肯定方面。

当完整源语句已识别具体动作/对象，而所引片段仅含动词或局部对象时，新源解释保留 `uncited_action_or_object` 与引用限制；普通未识别措辞仍是独立的词义缺口，不从上下文补入未引用事实。历史 v4 读取使用 `source_work(..., recover_plain_headings=False)` 保留旧冒号规则和旧局部引用处理，返回版本标识固定为 `bounded-work-semantics-2`；这个兼容模式不是新分析的默认值。旧 v3 继续使用独立冻结实现。

固定对照运行器为 `backend/scripts/run_m2_fixed_work_pairs.py`，只读取操作者显式指定的 manifest
和本地模型，输出限定私有路径，逐 pair 保存两次 fresh 回包、耗时与源码快照。
开发中间实验以当时源码快照解释，不用最终实现重判后冒称原实验读回；最终实现对旧回包的
校验必须另列为 revalidation。DEV 是反复使用的研发集；缺独立人审分母时 precision/recall 为 null。
