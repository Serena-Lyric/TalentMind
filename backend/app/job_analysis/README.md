# job_analysis

## 阶段 B3-5：八类候选目录与逐项人工准入

依据 [Issue #18](https://github.com/Serena-Lyric/TalentMind/issues/18)、产品 M2-52～60，新包 `canonical_catalog/` 独立于 B3-2/B3-4 的 JD 候选治理。`candidates.v1.json` 是八类 **19 个 AI 草案**，所有规范名、精确定义及别名均 `unconfirmed`。定义依据是产品规则的精确引文与原字节摘要，表示起草依据，不证明用户已经认可具体定义；嵌入式、系统软件、交付、硬件等细节尤须逐项讨论。草案非等量，可扩展，无市场数量/级别/熟练度推断。`release.empty.v1.json` 正式目录始终为空。

| family | 草案稳定 ID（待审） |
|---|---|
| 软件研发 | backend-development、frontend-development |
| 测试与质量工程 | automation-test、sdet |
| 数据与人工智能 | data-analyst、bi-engineer、data-engineer、ml-engineer、algorithm-research |
| 基础设施与运维 | devops、sre |
| 网络与信息安全 | security-development、secops |
| 嵌入式与系统软件 | embedded-development、system-software |
| 技术服务与交付 | technical-implementation、technical-solution |
| 硬件与集成电路 | hardware-development、digital-ic |

每条含主要责任、技术交付、排除项、相邻候选与区分原则、定义来源、待审别名及状态。候选 ID 独立于名称，跨类同名允许各自职责定义；同类重名/别名冲突拒绝，不能静默建立映射。原 JD 标题保留在原阶段，不导入/改写本目录；同工具不合并职业，不按语言拆职业。未审核候选相互引用只帮助界定草案边界。

### 运行与审核

工作目录 backend；使用已安装 requirements 的 Python，显式指定本工作树根作来源根。CLI 不加载旧 .env，不读正式 JD，也不调用模型。所有输出和 SQLite 放仓库内 `data/local/` 或独立仓库外目录。

```powershell
python -m app.job_analysis.canonical_catalog run --catalog app/job_analysis/canonical_catalog/candidates.v1.json --source-root .. --state ../data/local/m2-b35/state.db --output ../data/local/m2-b35/snapshots
python -m app.job_analysis.canonical_catalog review --snapshot <snapshot_id> --event <review.json> --source-root <source_root> --state ../data/local/m2-b35/state.db
python -m app.job_analysis.canonical_catalog export --snapshot <snapshot_id> --state ../data/local/m2-b35/state.db --output ../data/local/m2-b35/reviews
python -m app.job_analysis.canonical_catalog export --snapshot <snapshot_id> --manifest <release-manifest.json> --source-root <source_root> --state ../data/local/m2-b35/state.db --output ../data/local/m2-b35/proposals
python -m app.job_analysis.canonical_catalog replay --artifact <artifact_id> --state ../data/local/m2-b35/state.db --output ../data/local/m2-b35/replay
```

`run` 返回 artifact_id，快照中 `candidate_versions` 给出每条完整定义摘要。`review` 的严格 `c35-review-1` 输入包括 snapshot_id、candidate_id、candidate_sha256、decision（reviewed_accepted/rejected/deferred）、reviewer、basis、source、confirmed_responsibilities/confirmed_boundaries/confirmed_family 三个布尔确认、mode（manual_pending/synthetic_only）及 supersedes。只有三个确认全真才能记录接受；首次 supersedes=null，后续必须明确引用该快照该候选的最新事件。事件不修改原候选状态，不自动发布。

`source` 为 `{path, sha256, quote}`，path 是显式 source_root 下 POSIX 相对路径，拒绝越界（含 symlink/junction 解析）、错误 hash/引文。review 的引文须含 candidate ID、完整 candidate_sha256 和 snapshot_id，不能用一般产品原则或旧版本记录代替。程序冻结来源原字节与输入 JSON，再按同一字节解析，重放不依赖原文件继续存在。**这只验证结构和字节，不验证署名身份、语义或授权真实性。**

候选依据的产品文档通过根 `.gitattributes` 固定 LF 检出，保证 Windows/Linux 使用同一原字节摘要。以后更新产品文档须显式维护新候选版本/来源，旧 SQLite 快照仍按原字节 replay；其他源码字节变化按依赖摘要保守生成新版本。

独立 `c35-release-manifest-1` 输入如下（占位符须来自实际快照与审核记录；本轮没有真实逐项批准，不提供已批准样例）：

```json
{
  "schema_version": "c35-release-manifest-1",
  "revision": "release-proposal-v1",
  "snapshot_id": "<snapshot_id>",
  "mode": "release_proposal",
  "previous_release_id": null,
  "approvals": [{
    "candidate_id": "<candidate_id>",
    "candidate_sha256": "<full_candidate_sha256>",
    "review_id": "<current_accepted_review_id>",
    "confirmation_source": {"path": "individual-confirmation.md", "sha256": "<source_sha256>", "quote": "<逐项用户确认记录中的 candidate_id、candidate_sha256 和 snapshot_id 及确认正文>"}
  }]
}
```

确认来源必须独立于候选定义、候选输入、审核依据、审核事件 JSON 及其副本、旧审核记录和 manifest 本身；按路径和原字节摘要排除，必须明确指向本快照、本完整定义。审核与 manifest 模式严格对应，不能将 synthetic 审核包装成真实发布提案。manifest 版本不可对应两个不同内容；有前版时显式 previous_release_id，新版须重新提供每项批准，不隐式继承/删除。定义、family、别名、边界、依赖/规则版本改变均绑定新快照；相同候选 revision 不得原地修改。

### 发布边界与恢复

候选 → reviewed_accepted/rejected/deferred → release_proposal 的状态可审计；非合成最终为 `awaiting_external_approval`、identity_verified=false、formal_jobs=[]，**工具不会认定用户已批准或写正式 release**。只有未来用户逐项真实确认、受控 PR 审核和显式目录变更才能形成正式发布。该政策已确认不等于本草案获批。synthetic_only 只在临时输出 `simulated_jobs`/admitted，仍 formal_jobs=[]，不能写入仓库正式 release。

真实 JD 样本不是初次收录强制前置；目录定义不自动生成任何 JD canonical_job，不改变四维独立性。未知/竞争/跨类一体化职责继续 unknown/unresolved/pending，不新增分类器、vacancy 或正式统计资格。旧 B3-2 reviewed_accepted、B3-4 pending_review、family 七/八类版本与旧报告均原样保全，不参与自动准入。

c35_artifacts 保存不可变快照/事件/导出及依赖图，c35_revisions 绑定命名目录/发布版本与摘要；AnalysisStore(recover=false) 只复用锁和基础 schema，不恢复上游 running。整轮事务提交前异常/硬退出回滚，提交后输出故障可以 `SELECT id,kind FROM c35_artifacts ORDER BY rowid` 找到 artifact_id 再 replay；不用重审当前输入。输出先校验与所有输入/来源/状态文件隔离，再用暂存、fsync 和原子发布；已有不同内容拒绝覆盖，遗留暂存只清理同 artifact。

验证：`python -m pytest tests/test_job_analysis/test_canonical_catalog.py tests/test_job_analysis/test_canonical_catalog_storage.py -q`。全部合成临时目录 finally 清理；包含真实子进程硬退出、输出故障、CLI 和旧混合历史共库。完整阻网回归与内部独立审查见 [临时实施报告](../../../docs/review/M2-stage-B3-5.md)，合成通过不能证明真实语义准确率。

## 阶段 B3-4：工程范围与独立材料证据层

依据 [Issue #16](https://github.com/Serena-Lyric/TalentMind/issues/16) 与产品 M2-48～51，新增八类 `proposals/families.v3.json`：ID/标签不变，硬件与集成电路范围明确包括工艺、封装、制造与良率工程技术；普通产线/重复设备操作不能凭产业背景入类，设备维护及生产技术支持仍按实际责任与 B1 范围复核。v1/v2 文件原字节保全，不回写旧报告。

v3 自动线索只增加三条封闭职责句式：「开发半导体工艺并交付验证报告」「优化封装工艺并交付工程方案」「改进制造良率并交付分析方案」，沿用 core/auxiliary/unspecified 前缀及上下文规则。其余工程范围可走显式证据路径；这三条句式不是正式标准岗位名，也不是开放域分类器。v2 不启用新增句式；v1/v2 新运行因共享源码更新保守追加版本，历史 replay 不重新解释范围。B1 范围筛选不因 v3 自动扩展。

新增隔离子包 `role_classification/boundaries/` 与严格 schema `b34-submission-1`，选择独立 b34 层以保全 B30/B31/B32 schema、报告和审核截面。**当前只接收显式 source=synthetic 的输入与 synthetic_only 提交**；不是生产人工审核服务，不收真实 JD，不调用模型，也不消费 B31 hint 作为人工断言。

工作目录 backend，以下四条材料全部为合成例子，提议人也是测试署名，不是已审人工真值；示例候选没有预置正式岗位名称：

```powershell
python -m app.job_analysis.role_classification.boundaries run --input tests/fixtures/role_classification/boundaries.input.json --dataset synthetic-b34 --submission tests/fixtures/role_classification/boundaries.submission.json --family-taxonomy app/job_analysis/role_classification/proposals/families.v3.json --state ../data/local/m2-b34/state.sqlite3 --output ../data/local/m2-b34/results
python -m app.job_analysis.role_classification.boundaries replay --run <run_id> --state ../data/local/m2-b34/state.sqlite3 --output ../data/local/m2-b34/replay
python -m app.job_analysis.role_classification.boundaries review --result <result_id> --event <explicit-review.json> --state ../data/local/m2-b34/state.sqlite3
python -m app.job_analysis.role_classification.boundaries export-reviews --run <original_run_id> --state ../data/local/m2-b34/state.sqlite3 --output ../data/local/m2-b34/reviews
python -m pytest tests/test_job_analysis/test_role_boundaries.py tests/test_job_analysis/test_role_boundary_claims.py tests/test_job_analysis/test_role_boundary_storage.py -q --tb=short
```

### 显式主张与门禁

每条 annotation 绑定 namespace/jd_id/完整 fingerprint、synthetic_assertion 来源与非空 proposer（family/方向/级别断言继承该署名）；`family_assertions`、`candidates`（沿用 B32 候选格式）、`technology_tracks`、`seniority`、`assessments`、`conflicts` 与 notes 分开。全部 ID 在提交内唯一。family 只接受显式 taxonomy 中的 ID；family 的单一 core 职责引文可给 `pending_claim`，缺职责/责任不明/多核心或显式冲突为 unresolved，不会给已确认分类。技术方向与级别断言保留各自值和证据，不因 canonical_job 未知而清空，不用技术栈制造职业。

| 待审主张 kind | 输出行为 |
|---|---|
| family_identifiable_job_unknown | 无具体职业证据则 canonical_job=unknown；有候选或冲突时另记门禁不足原因，不裁决职业。 |
| competing_canonical_candidates | 多个显式具体岗位候选保留 unresolved；技术栈候选不进入 canonical_job.candidates。单个岗位候选也不自动确认。 |
| integrated_composite_candidate | 须显式列至少两个不同 domain 的 core 责任组件、互不重复/重叠的职责引文，以及独立于组件引文的共同完整交付证据；程序只检查结构和出处。标题/技能罗列/辅助或冲突会保留为 composite_unproven；满足结构也只待审核。 |
| possible_multiple_positions | 至少两个可区分的独立目标，每目标须有同一原文字段内、可定位且互不重叠的完整 section，含精确标题、各自职责和要求，编号可选但如有须唯一且在该段内；标题同名时必须各有不同的明确编号区分。各证据角色不能重用同一 span；整组一致且无已声明冲突才输出 position_target_proposals。缺项/重叠/竞争分段则 proposals 为空、材料 unresolved，原主张仍完整保存。 |

多职位门禁只生成可审核的**分段主张**，不改写原 JD，不创建拆分实体；一体化复合候选也不生成两个职位。招聘人数没有默认值，不接收 headcount/vacancy_count/正式准入等额外字段，不根据目标数输出人数或需求率。真正自动拆分、发布契约与统计仍待确认。

`submitted_claim` 保留原始主张；`gate_reasons` 解释结构不足。报告完整保存 source_payload、候选上下文及所有证据的 Python 字符 `[start,end)`、来源身份/指纹。**可定位和结构完整不证明语义正确**：显式导入者可能把历史、否定、技能或无关句错标为职责/完整交付；本层保留原文与显式 conflicts，不能自动识别全部隐含冲突。该情形须由复核者检查完整上下文，不能把 gate 通过当作独立招聘目标或复合职业已证实。

### 持久化、审核与恢复

只追加 b34_versions/inputs/results/reports/reviews/exports 和缺失的共享不可变 snapshots。AnalysisStore(recover=false) 不恢复旧 A running，不写其他层 heads/事实/观察/报告。输入原字节、完整提交、taxonomy 全文/revision、规则 revision 及实际调用源码摘要进入 manifest/result_version；源文、提交、目录或实现变化追加，纯观察时间变化可复用结果并逐轮保存 observation。规则 manifest 显示实验来源、scope、semantic_validation=not_performed、formal_admission=disabled、position_publication=disabled、formal_statistics_eligible=false。

review 格式沿 B32：target_kind（candidate/family_assertion/technology_track/seniority/assessment/position_target）、target_id、原 result_version、decision、reviewer、basis、evidence_refs、supersedes、formal_admitted:false。事件只追加，撤回绑定同结果同目标的旧事件；程序验证署名非空而不验证身份。审核接受不改原 pending_review，也不发布候选；导出保存不可变事件截面，后续事件不改旧导出，可用 replay 重放 export_id。

全轮单事务，错误或提交前硬退出回滚；提交后输出失败可查询 `SELECT run_id FROM b34_reports` 后 replay，不重载当前目录/源文件或重判语义。输入/配置/提交须位于输出目录外，沿用状态锁、硬链接与原子发布保护。新表不改变 user_version=1，无正式数据库迁移；不承诺断电、损坏或多机网络盘恢复。

所有结果 classification_complete/formal_statistics_eligible/formal_admitted 恒 false，正式目录恒空。完整阻网回归、历史保全与独立内部审查证据见 [实施报告](../../../docs/superpowers/archive/2026-10-17-M2-stage-B3-4-implementation.md)，已完成 GitHub 独立静态复审，不代替本地全部回归重跑；不启动 B4/M3/M4、不使用生产数据或真实模型。

## 阶段 B3-3：八类目录版本与候选兼容

依据 [Issue #14](https://github.com/Serena-Lyric/TalentMind/issues/14) 和产品 M2-45～47，新增 `role_classification/proposals/families.v2.json`。保留原七类 `families.v1.json` 字节与历史报告，新版只追加稳定 ID `hardware_integrated_circuits` /「硬件与集成电路」，其余七个 ID/中文名不变。沿用 schema `b31-family-taxonomy-1`，按 revision 的注册表精确检查集合：families-v1 必须七类、families-v2 必须八类；缺项、重复、错误标签/ID、未知 revision 或把七类改标签成 v2 均拒绝。scope 文字可调整但全文参与版本摘要。

标准岗位按核心职责/技术交付/职业功能区分，技术栈为独立可多选方向；八类同步建设基础目录是产品原则，**具体正式名单仍待讨论**。两版配置的 canonical_job、technology_tracks、seniority 值集保持空，B3-2 formal_jobs 也为空；合成「合成硬件岗」等名称只是演示候选，不是目录条目或人工真值。

工作目录 backend，以下三个样例 JD、四个显式待审主张、一个方向关系可离线执行；namespace 必须为 synthetic-b33：

```powershell
python -m app.job_analysis.role_classification.proposals run --input tests/fixtures/role_classification/families-v2.input.json --dataset synthetic-b33 --taxonomy app/job_analysis/role_classification/proposals/families.v2.json --state ../data/local/m2-b33/state.sqlite3 --output ../data/local/m2-b33/proposals
python -m app.job_analysis.role_classification.governance run --input tests/fixtures/role_classification/families-v2.input.json --dataset synthetic-b33 --submission tests/fixtures/role_classification/families-v2.submission.json --catalog app/job_analysis/role_classification/governance/catalog.empty.v1.json --family-taxonomy app/job_analysis/role_classification/proposals/families.v2.json --state ../data/local/m2-b33/state.sqlite3 --output ../data/local/m2-b33/candidates
python -m app.job_analysis.role_classification.proposals replay --run <proposal_run_id> --state ../data/local/m2-b33/state.sqlite3 --output ../data/local/m2-b33/proposal-replay
python -m app.job_analysis.role_classification.governance replay --run <candidate_run_id> --state ../data/local/m2-b33/state.sqlite3 --output ../data/local/m2-b33/candidate-replay
python -m pytest tests/test_job_analysis/test_role_family_versions.py tests/test_job_analysis/test_role_proposals.py tests/test_job_analysis/test_role_governance.py tests/test_job_analysis/test_role_governance_storage.py tests/test_job_analysis/test_role_classification.py -q --tb=short
```

B3-2 新增可选 `--family-taxonomy`（Python `execute/validate_submission` 的 `taxonomy=`）；省略时明确加载原 v1，历史提交无需重写。新 ID 必须显式提供已验证 v2；v1 不接受第八类 ID。完整 family_taxonomy 与正式空 catalog 分开存入 manifest，绑定 submission revision/全文、源码和 result_version。配置文件不能位于输出目录内；输入错位/配置非法整轮拒绝。审核仍绑定具体结果版本，不能跨目录升级继承；接受只保存意见，formal_admitted 不变。

v2 的硬件提示仅支持三条完整动作/对象/成果句式：「设计硬件电路并交付电路原理图」「开发FPGA逻辑并交付验证结果」「设计数字IC并交付RTL」，沿用下文 core/auxiliary/unspecified 前缀和原始字符偏移。硬件/FPGA/数字IC标题只作对照线索，SoC、芯片或技术栈词面不直接赋类。与嵌入式职责同时核心、责任不明、标题冲突或未解析职责保留候选/unresolved；公司介绍、历史、培训、销售/产品演示不能凭硬件术语获得职责候选。规则不是开放自然语言算法，未覆盖表达保留原文与待审原因。B3-2 不执行自动语义识别，只核对显式主张及证据；technology_stack 排除在主岗位候选集合之外，不回写 B2 技能事实。

两版可在同一临时 SQLite 混合运行，继续使用原 B31/B32 表和不可变历史保护，无数据库迁移。共享验证/规则源码变化会使**后续新运行**的 B31/B32 manifest 摘要变化，即使使用 v1 也保守追加新结果；v1 职责输出保持兼容，不伪装成旧源码版本复用。旧版本条目、报告/审核/导出截面逐字段保留，replay 只读已保存报告与原输入字节，不加载新目录、不重新解释规则。历史夹具来自 master `bbe5309` 上升级前的合成实际执行，覆盖旧清单/结果/审核/导出重放。A/B1/B2/B22/B30 源码未改、既有表不写。

所有自动建议始终 pending_review、classification_complete=false、formal_statistics_eligible=false，候选与关系 formal_admitted=false；没有正式发布、vacancy 数、需求率、真实 JD/模型评测或 B4。验证和独立内部审查见 [B3-3 实施报告](../../../docs/superpowers/archive/2026-10-16-M2-stage-B3-3-implementation.md)；内部审查不替代交付后 ChatGPT 集中复审。

## 阶段 B3-2：标准岗位候选与关系治理（离线）

依据 [Issue #12](https://github.com/Serena-Lyric/TalentMind/issues/12)，新增独立 `role_classification/governance/`，只录入**显式候选主张**，不运行自然语言岗位提取器。`catalog.empty.v1.json` 的正式目录恒空，候选、待审关系、审核事件和正式发布分别表达；没有正式发布或自动准入接口。产品仅追加用户已确认的 M2-44 多核心未决原则，具体名单、粒度、复合边界、发布条件仍待决策。

工作目录 backend；示例为纯合成 JD 与待审核的 Codex 标注，不能当作正式目录或人工真值：

```powershell
python -m app.job_analysis.role_classification.governance run --input tests/fixtures/role_classification/governance.input.json --dataset synthetic-b32 --submission tests/fixtures/role_classification/governance.submission.json --catalog app/job_analysis/role_classification/governance/catalog.empty.v1.json --state ../data/local/m2-b32/state.sqlite3 --output ../data/local/m2-b32/results
python -m app.job_analysis.role_classification.governance replay --run <run_id> --state ../data/local/m2-b32/state.sqlite3 --output ../data/local/m2-b32/replay
python -m app.job_analysis.role_classification.governance review --result <result_id> --event <explicit-review.json> --state ../data/local/m2-b32/state.sqlite3
python -m app.job_analysis.role_classification.governance export-reviews --run <original_run_id> --state ../data/local/m2-b32/state.sqlite3 --output ../data/local/m2-b32/reviews
python -m pytest tests/test_job_analysis/test_role_governance.py tests/test_job_analysis/test_role_governance_storage.py -q --tb=short
```

无独立 venv 的工作树可使用已安装 requirements 的 Python 绝对路径。输入沿用 A 的显式 JSON/JSONL；submission/catalog/review 为严格 JSON（拒绝重复键、额外字段和凭据字段）。所有身份、完整指纹、字段及 Python 字符 `[start,end)` 逐字核验；原名必须有完全相同的原文引文，可能规范名只是主张。每条保存完整 source_payload、标题/职责引文及候选所引字段的完整上下文。否定、历史、公司介绍等语境不丢失，但**不作自动语义判断**；可定位的引文仍只是待审核主张，不升级为当前招聘事实。

候选有稳定 ID、raw_name/proposed_name、来源类型/提议人、synthetic_only、外部声明的 core/auxiliary/unspecified、零个或多个 family 候选及未决原因。ID 在本轮所有候选/关系中唯一，跨版本以 result_id/result_version 区分，旧版本不覆盖。family 只校验七类 ID，不决定单一归属。技术栈 `technology_stack` 不进入主岗位候选集合；复合职业只标 `mature_composite_candidate`，不认定成熟、不拆岗位。主岗位有候选时保守 unresolved，没有则 unknown；不从单个候选自动裁决。多个 core 全部保留，possible_multiple_positions 也须显式标注及证据，不生成 vacancy 数、需求率、岗位占比或匹配分。

关系只支持 synonym、related_to、specialization_of、technology_direction_of、possible_composite_of 的**待复核提案**，目标必须是同一来源/本轮候选，不能跨快照偷换名称。即使 synonym 也不建立生产映射；其余关系不作同义、传递或替代。名称比较仅用于审计，不修改原词：逐 JD 与整轮目录均保留同名/多目标，多个 synonym 目标单独审计，不用字典覆盖顺序裁决。跨 JD 关系尚未支持，不能用本轮关系结构当正式职业本体。

### 审核契约与准入门禁

显式 review JSON 包含：`target_kind`（candidate/relation）、`target_id`、`result_version`、`decision`（reviewed_accepted/reviewed_rejected/deferred/withdrawn）、`reviewer`、`basis`、`evidence_refs`（本条完整 Evidence 数组）、`supersedes`（先前事件 ID 或 null）、`formal_admitted:false`。result_id 与 result_version 从原报告 members 取得；后者绑定目录/规则/实际源码、完整提交与结果正文，候选内容或依赖变更后不能复用旧审核。撤回必须指向同结果/同目标/同版本的先前事件；其他变更也可显式关联 supersedes。非空归因和本 JD 证据必须通过检查；程序不能证明署名身份或依据的语义真实性。

审核事件只追加，不修改候选或原报告的 pending_review。接受是离线审查意见，formal_admitted 永远 false、正式目录仍空。`store.reviews(result_id)` 返回顺序事件，不把最后一条事件自动解释成最终准入。`export-reviews` 保存一个不可变的事件截面，含旧候选正文和历史；stdout 给 export_id，后续可用 `replay --run <export_id>` 原样恢复该截面，后来的审核不改变旧导出。发布失败可查询 b32_reports/b32_exports 找回 ID 再 replay。

### 存储与版本边界

复用 A 的 AnalysisStore（recover=false）、不可变 snapshots、锁、路径保护及原子发布；共库只追加 b32_versions/inputs/results/reports/reviews/exports，不恢复旧 A running，不写旧层的事实、观察、报告或 heads。独立子包不进入旧 B3-0/1 源码 glob，旧版本清单及 replay 保持。全轮原始输入字节、完整提交、目录/显式 revision/实际源码 SHA-256 及报告均保存；结果按 snapshot + 完整 submission 摘要 + 版本精确复用。提交任意变化保守使本轮结果失效，不做未经确认的细粒度裁剪。只改观察时间可复用结果，各轮 observation 独立保存。

整轮单事务：提交前错误/硬退出无本轮结果，重跑原命令；提交后发布失败可 replay，不重读当前目录或重新解释主张。历史 UPDATE/DELETE/REPLACE 拒绝。所有输入必须在输出目录外；状态可以与输出共目录，沿用硬链接保护。CLI 退出 0 只表示本轮保存/发布成功，不等于分类完成或真实准确率。仅验证本机临时 SQLite 的进程中断，不承诺断电/损坏/网络盘恢复。未读取或改写 B3-0/1 建议报告；如需用作候选来源，调用者须另行显式提交原文证据，不能提升 primary_family_hint。

验证证据、内部审查与边界见 [B3-2 实施报告](../../../docs/superpowers/archive/2026-10-16-M2-stage-B3-2-implementation.md)。未接生产服务/真实模型/真实 JD，未启动 B4/M3/M4，不替代用户与 ChatGPT 的产品裁决及集中复审。

## 阶段 B3-1：七类目录与有限职责建议

依据 [Issue #10](https://github.com/Serena-Lyric/TalentMind/issues/10) 与产品 M2-41～43，新增独立 `role_classification/proposals/`。只输出待审 family 候选、核心/辅助/未明确职责线索、标题对照与未决原因；不把程序建议写成 B3-0 的 known 断言。B1 范围、B2 技能和 B3 职业目录仍分层，入口不隐式运行其他阶段。

工作目录 backend，显式合成输入、目录、数据集、状态和输出：

```powershell
python -m app.job_analysis.role_classification.proposals run --input tests/fixtures/role_classification/proposals.input.json --dataset synthetic-b31 --taxonomy app/job_analysis/role_classification/proposals/families.v1.json --state ../data/local/m2-b31/state.sqlite3 --output ../data/local/m2-b31/results
python -m app.job_analysis.role_classification.proposals replay --run <run_id> --state ../data/local/m2-b31/state.sqlite3 --output ../data/local/m2-b31/replay
python -m pytest tests/test_job_analysis/test_role_proposals.py tests/test_job_analysis/test_role_classification.py -q
```

`families.v1.json` 为独立 `b31-family-taxonomy-1` schema、revision=families-v1。七个 ID 与中文名成对冻结，拒绝缺项/重复/未知值；scope 文字与修订纳入内容版本。canonical_job、technology_tracks、seniority 目录仍为空。B3-0 的 empty/synthetic_example 解析、报告与源码完全不改；新增子包不进入旧 manifest 的顶层 *.py glob。

| Stable ID | 显示名 | 首批试验动作/对象/成果（均非标准岗位名） |
|---|---|---|
| software_engineering | 软件研发 | 开发后端接口并交付服务；开发软件服务并交付应用；开发前端页面并交付应用 |
| test_quality_engineering | 测试与质量工程 | 设计测试用例并交付测试报告 |
| data_ai | 数据与人工智能 | 训练机器学习模型并交付预测模型；建设数据管道并交付数据集 |
| infrastructure_operations | 基础设施与运维 | 维护云基础设施并保障系统可用性 |
| network_information_security | 网络与信息安全 | 排查网络安全漏洞并交付修复方案 |
| embedded_system_software | 嵌入式与系统软件 | 开发嵌入式驱动并交付固件 |
| technical_services_delivery | 技术服务与交付 | 实施客户系统并交付集成方案；诊断客户系统复杂故障并交付修复方案；设计客户系统技术架构并交付技术方案；部署客户生产系统并完成系统验收 |

### 试验语法与审核提示

这是**封闭中文句式子集**，不作开放域匹配：整条分句须为上表动作/对象/成果之一，加“核心职责：/主要职责：/主要负责”（core）、“协助/辅助/配合”（auxiliary）或“负责”（unspecified）。中英文冒号均支持；句号、分号、换行分句，保留 Python 字符偏移与原字段，不搜索嵌套字符串或改写原文。单纯标题、技术词、“部署/演示/技术支持”不生成 family 候选。职责条数与词频不参与主辅判断。

只给 family 层的 `primary_family_hint`，**不是 canonical_job 主岗位裁决**。一项显式核心家族且其余已识别工作均明确辅助、没有冲突或未解析职责时可提出 proposed；没有核心/多个核心/未明确主辅/标题冲突/未解析职责时 unresolved，hint=null。所有 proposed 也只 pending_review，不能当作已确认分类。全栈/复合词和有限多职位标记只提示复核，不拆分、不造 canonical_job 或独立职位数。未知材料允许完全没有 family 候选。

公司介绍、历史项目、培训内容、示例、任职/技能要求、福利等已识别章节不用于当前职责候选；否定、条件、他人动作、产品演示及未覆盖句式保存未解析上下文，阻断主岗提示。duties 与 raw_text 均检查，正文相同则不重复处理；一个字段的候选分句若逐字出现在另一字段的排除/未解析语境内，撤销该分句候选并保留跨字段冲突，不能靠摘录丢掉来源语境。标题与唯一核心家族对照，不能因标题恰好对应辅助家族而消除冲突。原始 payload、标题线索、全部候选引文/身份/完整指纹与字段字符区间保存并逐字核验；未理解语境也保留原文。引文校验通过不能证明语义准确，复杂语境与未知章节仍有漏识别边界。

### 版本、保存与恢复

只追加 `b31_versions/inputs/results/reports` 及缺失的共享不可变 snapshots；不写 A/B1/B2/B3-0 运行、事实、heads、观察或四维断言。ProposalStore 打开时 recover=false，不恢复旧 A running 状态。明确输入的每条材料对应一个 member，保存 input_position、来源、观察与指纹；不隐式吸收历史未出现在本轮输入的 JD。

复用键为完整 snapshot + version。版本包含目录全文/修订、显式 --rules-version、本子包及所调用公共源码 SHA-256；内容/身份/目录/源码/规则变化追加，纯观察时间变化可复用提取，但每轮观察独立留存。UPDATE/DELETE/REPLACE 被拒绝；整轮单事务，无隐式 resume。提交前失败重跑；提交后发布失败可 SELECT run_id FROM b31_reports 找回，replay 不加载当前目录或重新解释规则，核对报告与输入字节摘要后原样发布。输入和目录不能位于输出目录内；路径/锁/硬链接/原子发布沿用 A 的保护，状态库可以与输出共目录。

分类始终 incomplete，正式统计资格恒 false；不输出岗位占比、需求率、匹配评分或 vacancy 数。只验证合成材料/临时 SQLite，真实 JD/模型效果未评测，生产迁移、B4/M3/M4 未执行；完整标准岗位目录、技术方向、级别、混合岗位细则与审核流程仍待确认。开发验证与遗留见 [B3-1 实施报告](../../../docs/superpowers/archive/2026-10-16-M2-stage-B3-1-implementation.md)。


## 阶段 B3-0：岗位四维证据与版本基础

Issue [#8](https://github.com/Serena-Lyric/TalentMind/issues/8) 的独立基础包 `role_classification/` 只读取显式 JD 和显式分类断言，不运行自然语言分类器。依据当前产品 M2-07～11，职业大类 `job_family`、主标准岗位 `canonical_job`、多项 `technology_tracks`、独立 `seniority` 分开保存；不约束成单父树，不从 B1 范围或 B2 技能推导分类。

工作目录 backend，可直接用仓库内的纯合成示例：

```powershell
python -m app.job_analysis.role_classification run --input tests/fixtures/role_classification/input.json --dataset synthetic-b30 --annotations tests/fixtures/role_classification/annotations.json --taxonomy tests/fixtures/role_classification/taxonomy.empty.json --state ../data/local/m2-b30/state.sqlite3 --output ../data/local/m2-b30/results
python -m app.job_analysis.role_classification replay --run <run_id> --state ../data/local/m2-b30/state.sqlite3 --output ../data/local/m2-b30/replay
python -m pytest tests/test_job_analysis/test_role_classification.py -q
```

无独立 venv 的工作树可使用已安装 requirements 的 Python 绝对路径。输入沿用 A 的严格 JSON 数组/JSONL；annotations 和 taxonomy 必须显式 UTF-8 JSON，拒绝重复键、额外字段、凭据字段和不合法结构。详见 [合成示例](../../tests/fixtures/role_classification/README.md)。所有输入原文件只读，输出沿用 A 的本地路径/锁/硬链接保护；输出不能包含 JD、标注或目录输入文件，状态可在输出目录中。

### 保存与验证的范围

- `Decision` 的 state 为 known / unknown / unresolved，value 与 candidates 的合法值限定于显式 taxonomy。known 只表示输入提供明确值，必须有本条 JD 原文证据；unknown 不造值，unresolved 可以保存有证据的候选。不是独立人工确认或模型识别结果。每项技术方向独立保存 evidence，多值不重复；方向集合也有独立的未知/未决状态。
- `origin` 仅 synthetic_assertion / manual_pending；author 必填，review_status 只允许 pending_review。程序核对 namespace/jd_id/fingerprint、原始字段和 Python 字符 `[start,end)` 的逐字引文；不能用归一名、翻译或模型自述代替。标注与不可变快照完整绑定，标题和独立 duties 原文证据另存，完整 raw_text 等字段保留于 source_payload。
- canonical_job 是主岗位，auxiliary_roles 保存主岗位引用、辅助岗位 Decision 和关系 evidence；不生成额外职位。无法明确主辅时保留 unresolved/候选/原文说明，不替产品定义主辅算法。material_kind 分别保存 undetermined / single_role / hybrid_role / possible_multiple_positions，具体解释需证据；疑似多职位仅待复核，不拆分、不输出职位数量。
- conflicts 保存维度、标题引文、职责/正文引文及原因；冲突维度必须 unresolved，不能保留强制确认值或标题优先裁决。语义矛盾由用户显式标注，程序不承诺自动发现所有冲突。
- 允许不完整待审断言共存：例如方向集合 unresolved 下保留部分 known 方向，或 possible_multiple_positions 材料同时附有待审主辅关联。这仅保留输入内容与歧义，不能据此认定多个真实职位或已确认混合岗位；消费方须同时读取集合/材料状态和审核状态。
- 严格畸形、跨 JD、伪造位置或目录外值使整轮拒绝，退出2，不当作零分类成功；没有提供标注的合法输入仍保存为 not_annotated/body=null。已标注的 unknown/unresolved 完整保留。进程码0只说明本轮保存/发布完成，不表示分类完整或准确；每条 requires_review=true、classification_complete=false、semantic_validation=not_performed，正式统计资格恒 false。

### 版本、事务与历史

只追加 `b30_versions/inputs/results/reports`，共用 A 不可变 snapshots；不写 A/B1/B2 的运行、事实、heads、观察、正式 DDL、词典、exchange 或旧 StateDB。A 存储新增默认 recover=true 的兼容开关；B3 显式 recover=false，共库打开不会恢复旧 A 未完成运行，旧调用保持原行为。

版本覆盖完整 taxonomy 内容/修订、显式 `--rules-version`、本包与所用公共源码 SHA-256。结果复用键为不可变 snapshot + 完整标注摘要 + version；输入、标注、目录或实现变化追加新结果。来源观察值独立存在每轮 member，只改观察时间可复用；不推断真实发布时间、独立职位或下架。本轮每个报告范围恰为显式输入，不隐式扩展到 A/B1/B2 或先前未出现的成员。

每轮以单一 SQLite 事务保存全部快照/结果/源文件字节与摘要/不可变报告，没有长期 running 或隐式 resume：提交前失败/中断无本轮数据，原命令重跑；提交后发布失败，SELECT run_id FROM b30_reports ORDER BY rowid 可找回 ID，使用 replay 重新发布，不重新解释标注。replay 不需要当前目录配置或输入文件，不调用新验证器；原报告与源文件摘要经核对后原样发布，不覆盖不同内容的既有产物。已有结果同版本复用时核对存储正文和摘要；UPDATE/DELETE/REPLACE 被历史保护拒绝。

完整输入源文件字节保存在 b30_inputs，标注与 taxonomy 保存的是经严格解析的完整结构，字段顺序/空白不作为分类依赖。报告保存原输入文件路径供发布保护，重放仍保护这些路径。单进程串行本地 SQLite 与原子文件发布沿用 A；本轮未验证断电/损坏/网络盘恢复能力。

职业大类目录、标准岗位目录、技术方向/级别映射、主辅判定算法、成熟复合职业边界、多职位拆分与统计计数仍待用户和产品团队确认。本轮不修改 PRODUCT_DECISIONS 的已确认规则，不启动 B4/M3/M4、真实标注/模型评测或正式需求率。执行证据与内部审查见 [归档实施及复审报告](../../../docs/superpowers/archive/2026-10-16-M2-stage-B3-0-implementation.md)，报告已完成归档；本阶段仅为离线保存与验证基础层，分类规则与七类目录在后续独立阶段落实。

## 阶段 B2 第二轮：离线名称、类别与候选治理

入口 `python -m app.job_analysis.governance`；新增 `governance/`，只消费已保存的 B2 run 和原始 snapshots，不隐式重跑 B1/B2，不连接服务/模型。产品依据 M2-37～40。285 条 seed 和共享 normalizer 完全只读；旧 B2 文档（包括 b2-1 历史）原样保存为 original_semantics，五态、对象、程度、组合、上下文与 effective 不重算/覆写。

```powershell
cd backend
# 先用下文 semantics 的显式输入命令生成 B2 run，再使用它的 run_id：
.\.venv\Scripts\python.exe -m app.job_analysis.governance run --b2-run <b2_run_id> --state ../data/local/m2-b2/state.sqlite3 --output ../data/local/m2-b22/results
# 保存失败时可只读查询 b22_reports 的 run_id，然后原样重放，无须当前规则：
.\.venv\Scripts\python.exe -m app.job_analysis.governance replay --run <governance_run_id> --state ../data/local/m2-b2/state.sqlite3 --output ../data/local/m2-b22/replay
# 基准的输入/namespace/完整快照必须与预测对应；此文件只供合成程序自检：
.\.venv\Scripts\python.exe -m app.job_analysis.governance evaluate --run <governance_run_id> --benchmark tests/fixtures/governance/synthetic-reference.v1.json --state ../data/local/m2-b2/state.sqlite3 --output ../data/local/m2-b22/evaluation
```

工作树可用已安装 requirements 的 Python 绝对路径。run 的 `--rules-version` 默认 v1；状态和输出沿用 A 的路径保护、单进程锁和本地限制。输入不能位于输出目录下，状态文件可以在输出目录中。运行成功也必须检查 upstream_failed 和每条 body；失败上游保留 upstream_failed/body=null，不冒充零技能成功。治理始终 analysis_complete=false、formal_statistics_eligible=false。配置/存储/发布错误退出 2；已提交报告可 replay 恢复发布，若 stdout 丢失可查询 b22_reports。没有自动 resume 重跑旧 B2 的隐式动作。

### 名称与关系

- Catalog 保存 seed 每个 canonical/alias 出现位置，多目标、重复项/重复 canonical、未审别名及数字别名全部可审计。当前六个多目标名为 sass、js、ts、k8s、oop、敏捷开发；审计不修改原始数据。
- `policy.v1.json` 是轻量审定关系/分类规则，不是正式词典或通用知识图谱。只有 synonym 边用于映射（例如 JS→javascript）；related_to、narrower_than、version_of 不产生互换、传递归一或替代关系。SQL/MySQL、Spring/Spring Boot、CSS/Sass 独立；未审的 cv/ci/angularjs/es6/optimization 等保留 baseline_matches 与复核原因。
- 精确 seed canonical 默认保留；只对明确同义的 js/ts/k8s 等覆盖层改名，不大规模重写 canonical。少量数字版本语法仅为 Vue/Python/OAuth/Java 开启，保存 raw_name、canonical、version、key，如 Vue→vue、Vue 3→vue@3、Vue 3.x→vue@3.x。rc/beta/+/>=及范围等未支持表达整体保留为version_review候选，不截断到已知前缀；不解释范围或推断兼容/可替代。
- skills 是逐次出现，不按名称抹掉重复位置。statement_ids 指向不变原陈述；位置/namespace/jd_id/fingerprint 经程序核对，canonical/版本不是原文证据替代品。

### 分类与非技能事实

明确技术类别或显式分类条目才给四类主类别，classification_basis 与辅助 tags 一起保存。旧 DevOps/运维粗类不整体投射technical_skill；Scrum/Agile/Kanban显式归engineering_practice，其余未审项待复核。未知类别为 null、classification_status=needs_review，不能因词典外而给 technical_skill。旧“专业领域”词在明确行业经验/领域知识语境中形成 non_skills，否则放 review_mentions，不擅自视作技能。

非技能仅有限规则：领域词+行业经验/领域知识，本科/硕士/博士/大专学历，明确“X年以上工作经验”或“X年以上 Java 开发经验”，以及“持有/取得/具备 X 证书/认证/资格证”。结构带证据与完整字段上下文；constraint_state=needs_review，词面提取并未可靠解析否定/条件作用域，不直接断言无条件招聘要求。“三年以上 Java 开发经验”可同时给 java 与 work_years，后者 scope=skill_specific 并用 skill_ids 关联；不变成整份 JD 工作年限、不转成熟练程度。原 B2 的 requirement_object=experience 也不会自行生成 work_years。

### 未知候选与审核接口

开放词候选只从完整匹配的能力动词短句或显式技能/技术栈列表提取；当前开放词形为有限 ASCII 技术名/数字版本，任意中文新名和复杂混合句不作通用 NLP。每个候选含原词/位置、来源快照、statement 与 context 证据、旧词典比对、candidate_type/tier/review_reasons、版本及 pending_review。strong_context 表示直接能力动词格式依据；技能列表或旧别名争议为 disputed，等级不代表校准概率或已确认是技能。已识别公司后缀、公司描述/福利/证书条件不能凭陌生词变成候选。其他原文保存在 unresolved_fragments/original_semantics，不静默消失。

任职要求/岗位要求/技能要求标题支持同行能力句、独立标题换行及纯词列表；正文索引直接对应原字段，context 包含章节标题。未知冒号标题、公司介绍/福利等已知独立标题与职责章节阻止新增开放词锚点，后续明确招聘标题可重新建立上下文，字段间不继承章节。有限“不要求/无需/不需要”或“如果/若…，则…”前缀可保留具体候选，但只记 disputed + unresolved_requirement_context，不推断确定要求状态；复杂句仍保留未解析。旧 B2 语义不重算，治理实际源码哈希变化使旧结果失效并追加新版本，历史仍可重放。

`candidates.review_event()` 要求审查人、依据、证据引用，decision 为 reviewed_accepted/reviewed_rejected/deferred；`GovernanceStore.record_review(result_id,event)` 追加不可改事件，`store.reviews(result_id)` 可导出完整审查历史。原报告不被新审查改写。reviewed_accepted 只表示离线审查决定，不是正式词典收录；`validate_admission(candidate,review=None)` 永远 allowed=false，报告自动准入关闭/验证策略未定/独立证据未建立。本包没有写 seed 或正式词典的接口。同文跨平台、dup_group、cross_source 都不作为独立验证。

### 持久化、版本与评测

只新增 b22_versions/results/reports/reviews，不改 A/B1/B2 表/事实/heads/观察；原有 user_version=1。version_id 覆盖实际词典、完整策略、显式 revision、本包与所用公共源码摘要；每 result 绑定 source_attempt/source_snapshot/source_sha256。相同依赖复用结果，策略变化追加；整个新报告事务提交后原子发布，中断未提交则无新结果，发布失败可从已保存报告 replay。旧语义的 partial 不因治理层成功而升格。

评测使用独立严格标注格式，见 [合成参考说明](../../tests/fixtures/governance/README.md)。`evaluation.evaluate(benchmark,predictions)` 不调用提取器；`project_predictions(report,benchmark)` 只投影保存的事实，不读取参考类别/状态来修补预测。输出 artifact 的 annotations、predictions、evaluation 分开，摘要可复核。投影对原组合保留组状态和独立有效成员状态；新名称的状态仍来自原陈述，不能把组 required 分发到成员。

提取 P/R 按名称（含具体版本）+字段/字符区间一一配对；遗漏和误提逐条列出。五态/四类输出分母与混淆，必备误判分母为所有 predicted required；组合对关系/组状态/成员比较，成员状态另计。非技能被误提为技能、候选 P/R、候选 formal_admitted 和未知项直接提升技能均单独审计。程序引文位置通过与参考事实对应各计一项；可定位不等于事实正确。零分母返回 value=null/status=undefined_zero_denominator，缺预测按遗漏算、缺标注拒绝、不忽略重复预测；技能参考category必须显式给出，null表示类别待复核并从分类分母排除，独立计pending_reference_review；未覆盖类与小分母可见，无正式充分性或质量阈值。

提交的 14 条合成参考由 Codex 手写、待人类复核，只可作为 synthetic_program_check，quality_claim_allowed=false；未经审核的模型输出不当真值。本轮只报告程序计数与差异，不报告真实语义准确率。真实语料评测模式要求合法使用及具名人类逐项审核声明，程序只能核验声明完整性，不能证明许可/审核真实性。正式阈值后定。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_governance.py tests/test_job_analysis/test_governance_evaluation.py -q --tb=short
```

实际回归、样例差异与遗留见 [本轮阶段报告](../../../docs/superpowers/archive/2026-10-16-M2-stage-B2-2-implementation.md)。不开发正式词典自动准入、审核前端、生产迁移、市场统计、B3/B4、M3 图谱或 M4 匹配。

## 阶段 B2 第一轮：离线技能要求语义

新增独立入口 `python -m app.job_analysis.semantics`，采用现有 Python/Pydantic/SQLite，无新增依赖。产品依据为 M2-32～36；只处理技能语义，不隐式重跑 B1 或接入旧 M2/生产服务。合成数据通过显式文件进入，可与 A/B1 使用同一阶段 A SQLite，也可新建库。

```json
[{"id":1,"source":"synthetic","job_title":"工程师","raw_text":"Java 或 Python 至少掌握一种。不要求精通 Python，但需了解 Python 基础。"}]
```

把样例保存到 `data/local/m2-b2/input.json`，从仓库根进入 backend：

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.job_analysis.semantics run --input ../data/local/m2-b2/input.json --dataset synthetic-b2 --state ../data/local/m2-b2/state.sqlite3 --output ../data/local/m2-b2/results
# 使用 stdout 的 run_id：
.\.venv\Scripts\python.exe -m app.job_analysis.semantics resume --run <run_id> --state ../data/local/m2-b2/state.sqlite3 --output ../data/local/m2-b2/results
.\.venv\Scripts\python.exe -m app.job_analysis.semantics replay --run <run_id> --state ../data/local/m2-b2/state.sqlite3 --output ../data/local/m2-b2/replay
```

run 可用 `--rules-version v2` 追加试验修订；不覆盖旧结果。无 venv 的工作树可使用已有环境 Python 的绝对路径。沿用 A 严格 JSON 数组/JSONL 输入、必填 id/source/job_title/raw_text、可选 requirements/duties/experience 及完整 payload 指纹；坏批次在创建语义 run 前拒绝，退出 2，不把解析失败当零技能成功。状态与输出仅允许仓库内 data/local 或仓库外独立目录；输入必须在输出目录外。状态库可在输出目录中，发布器只写 run_id.json。配置/执行/验证/发布失败退出 2；包含 partial/uncertain 的成功执行返回 0，须检查每条状态与覆盖，不能以进程码代表完整分析。

### 结果结构与保守规则

- `statements` 是原始陈述，含 id、skills（canonical 与逐次原词位置）、五态 state、relation、requirement_object、degree/degree_evidence、target、condition、section、reason、evidence/context/scope_evidence。原文字段的 Python 字符 `[start,end)`、namespace/jd_id/fingerprint 可确定性核对；重复引文保存各自位置。上下文保存章节到当前/相邻行的原文，不翻译改写；scope_evidence 另存可能跨字段作用的对象/条件限定证据。
- relation 为 null / any_of / all_of。组合保存自己的 state；成员通过 group_ids 引用，只有组关系时 effective 为 mentioned，reason=group_membership_only，不能投影成独立 required（all_of 也保留组合，不隐式展开）。另有独立陈述时分别保存，绝不覆盖组合证据。重复同一 canonical 不伪造两个候选；有效组合中的重复原词仍保留各自位置，但 group_ids 稳定去重。
- degree 为 basic / familiar / proficient / expert 或 null，对应基础了解/了解、熟悉、熟练掌握/熟练、精通。仅“掌握”不推断程度，年限不换算。未可靠解析的多技能句不把唯一程度词分发给全部技能，程度字段为空，原文仍保留。`不要求精通 Python` 是 expert 程度的 not_required，**不是整个技能不要求**；须按完整 effective 的 degree/target/condition 读取，不能按技能名粗暴折叠。
- `requirement_object` 区分 capability（技能掌握能力）、experience（相关经验）与 unresolved（未可靠判断）。明确“Python 经验优先/加分/为加分项”保存为经验对象；未支持的“有 Java 项目经验者优先”等变体仍可 uncertain/incomplete。target 表示面向的主体，degree 表示能力程度，均独立管理；不能用 candidate 或空程度代替要求对象。
- `effective` 按同 canonical + 同 requirement_object + 同 degree + 同 target + 同 condition 比较独立陈述。mentioned 不与明确要求冲突；同作用域 required/preferred/not_required 互异则标 conflict=true、state=uncertain，保留 statement_ids 全部证据。“必须掌握 Python。Python 经验优先。”按能力 required 与经验 preferred 分别保存，两种顺序均不冲突；“必须掌握 Python。不要求掌握 Python”仍是真实能力冲突。不同对象或程度可共存，调用者不得再按技能名折叠。任一未解陈述可令其所在组 uncertain，但不伪造冲突标记。不按强弱或顺序选句，不推断历史修订。
- 支持明确“必须/需要/要求/需/须/应 + [能力动词] + 技能”，任职要求章节的能力动词句，加分章节与明确“经验优先/加分”，明确“不要求/无需/不需要”，简单全部掌握及“至少掌握一种/任选其一”。已知章节支持带冒号及独立标题行（含方括号）；未知标题保留为未解析证据，不吞掉冒号前文字。裸列表、技术栈和工作使用只记 mentioned。完整匹配语法才给确定状态，不根据技能次数或相邻岗位结果推断。
- 复杂条件/多对象/嵌套/否定不清/公司属性/示例/教程/可能/待定等保留 uncertain 和原文。条件与对象未可靠解析时保存完整作用原文为 unresolved target/condition，不认定为同对象冲突，也不生成无条件 required。已识别“仅适用于/仅限/限于/仅对/当…时/不必满足”等限定时，保守影响本 JD 的所有技能陈述（包括独立 requirements 字段），作用范围无法可靠裁决时可能过度 uncertain。未解释的无技能正文片段阻断当前字段后续的旧章节继承，可靠新标题可重新建立章节；这是防误升的保守屏障，不是开放语义解析。唯一实现的跨分句程度对比是“不要求…，但需/需要/必须…”；其他复杂逻辑不建树。

`coverage` 为 complete/incomplete，始终附 `coverage_scope=known_aliases_and_supported_clauses_only`。complete 只说明本轮语法子集内的正文/职责/条件片段已解析；不能作为完整通用 JD 语义样本或正式统计样本。未解析文字（含未知技能）及 uncertain 陈述记入 issues，coverage=incomplete，可靠的部分陈述仍保留。标题和年限作为上下文/元信息，不按年限制造技能或程度。词典外不建立新本体/候选准入，不写 skill_dict；outcome=no_recognized_skills 与 status=failed/body=null 分开。

严格结构验证与逐次证据定位在 validation 完成；随后重新核对内置规则产出，不能仅凭引文匹配就接受任意 required。`semantic_validation=deterministic_rules_only` 不是独立人工语义验证；没有准确率阈值或真实 JD 评测结果。只有部分解析的任务为 partial，失败为 failed，支持范围内解析完为 completed；两者都没有正式统计资格。

### A/B1 兼容、版本与恢复

`SkillSemanticAnalyzer` 符合 A 的 Analyzer 调用协议，但返回独立 B2 Document，由 B2 runner/validation 处理。复用 InputRecord、不可变 snapshots、SQLite 文件锁/身份/触发器和原子 publish；附加 b2_versions/runs/heads/observations/members/attempts/reports，不改 A/B1 历史、heads、观察或事实。A user_version=1 不变，旧 StateDB 不迁移。A 原枚举（含 legacy_required/legacy_bonus）原样保持 unreviewed；B2 五态不回填或隐式升级旧事实。这是兼容扩展，不把 B2 响应送进 A 的旧 FactClaim 校验器。

完整输入、规则修订、实际词典/别名内容和 B2 源码（规则/结构/验证/执行）、所用 A 公共源码摘要共同参与版本。同输入同版本的 completed/partial 可精确复用，partial 不提升资格；失败通过新 run 重试。观察时间独立追加。B2 heads 仅来自显式输入，不隐式采用 A/B1 范围；增量缺项仍保留 B2 已登记成员。每 run 冻结范围与依赖，输入变化和新规则追加结果；旧结果 replay 不调用新规则，resume 则要求原依赖。B1 规则变化不因其标签直接使 B2 失效。

PR #6 审查修复后当前结构为 `b2-2`、规则为 `bounded-skill-clauses-v2`，显式标签及实际源码摘要均改变。旧 b2-1 文档不补字段、不重新解释；可 replay 旧结果，使用新实现 resume 旧运行会拒绝，新 run 对同快照追加新尝试。合成历史夹具 `tests/fixtures/semantics/b2-1-capability-experience-history.json` 捕获自修复前 `0b882eb` 的真实 runner 输出，仅证明历史兼容，不是语义真值。正式 SQLite 表结构/user_version 与 A/B1/legacy 保持不变。

每条先持久化 running，完整文档与终态在一次事务提交；重开库把残留 running 标 retryable，恢复只重做未提交结果。报告不可变保存后才原子发布，发布失败可 resume，不重复已提交分析；八处真实进程硬退出有回归。沿用 A 单进程串行锁与本地文件限制，不声称断电/损坏/网络盘恢复能力。正式 DDL、词典、exchange、生产 API/数据库及旧管道保持原样。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_semantics.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_foundation_inputs.py tests/test_job_analysis/test_foundation_validation.py tests/test_job_analysis/test_foundation_runner.py tests/test_job_analysis/test_foundation_cli.py tests/test_job_analysis/test_screening.py tests/test_job_analysis/test_semantics.py -q --tb=short
```

新增 fixture 在 finally 关闭并删除临时目录、断言目录不存在；仅合成 JD/临时 SQLite，无真实服务集成。全套回归用合成环境与 socket 阻断，具体命令/实际结果/内部检查及局限见 [阶段报告](../../../docs/superpowers/archive/2026-10-16-M2-stage-B2-1-implementation.md)。合成预期由人工逐例指定，不能作为独立准确率证明。复杂修辞、英文完整要求语法、跨句指代、任意编号/格式和开放技能覆盖尚未支持；该句描述第一轮边界；第二轮治理与评测基础见上节，B3/B4、真实标注评测和市场统计仍未启动。

## 阶段 B1：JD 有效性与分析范围的离线筛选

入口 `python -m app.job_analysis.screening` 与 A/旧管道分离，不调用模型或服务，不写技能事实。所有路径必须显式提供；可以使用已有阶段 A SQLite（只增 B1 表、共享不可变 snapshots），也可用新的独立库。旧 StateDB 仍拒绝打开，不迁移。

先在 Git 忽略的 `data/local/m2-b1/input.json` 准备合成数据：

```json
[
  {"id":1,"source":"synthetic","job_title":"开发实习生","raw_text":"负责开发软件，只要求 Python。","crawled_at":"2026-10-15"},
  {"id":2,"source":"synthetic","job_title":"行政助理","raw_text":"负责整理行政报表，使用 Excel。"},
  {"id":3,"source":"synthetic","job_title":"助理","raw_text":"具体工作待定。"}
]
```

从仓库根进入 backend：

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.job_analysis.screening run --input ../data/local/m2-b1/input.json --dataset synthetic-b1 --state ../data/local/m2-b1/state.sqlite3 --output ../data/local/m2-b1/results --scope app/job_analysis/screening/software-related.offline.json
# 使用 stdout 的 run_id：
.\.venv\Scripts\python.exe -m app.job_analysis.screening resume --run <run_id> --state ../data/local/m2-b1/state.sqlite3 --output ../data/local/m2-b1/results
.\.venv\Scripts\python.exe -m app.job_analysis.screening replay --run <run_id> --state ../data/local/m2-b1/state.sqlite3 --output ../data/local/m2-b1/replay
```

无本地 venv 的独立工作树，可指定已安装 requirements 的 Python 绝对路径。状态/输出仅允许仓库内的 `data/local/` 或仓库外独立目录。输出目录允许包含状态库（同层或子目录），发布器只写 `<run_id>.json`；禁止把状态文件本身或其子路径当成输出目录。输入/范围文件必须位于输出目录之外，不以“目录隔离”暗示状态库也必须在目录外。配置/路径/存储错误返回 2；输入或筛选失败仍发布有错误的审计并返回 2；成功筛选运行（包括无效/范围外/待复核）返回 0。若未获得 stdout，可只读查询 `b1_runs` 的 `id,status,error`，再 resume。已完成的失败尝试通过新 run 重试；resume/replay 不改写旧判断或旧审计。

范围配置为严格 JSON 对象：`scope_id/version/mode/description/activities`；mode 仅 `offline_experiment`。样例包含 software_development、software_testing、data、it_operations 四种工作活动。它们是规则证据组，不生成职业大类、标准岗位、方向或级别。可显式缩小 activities；未识别配置拒绝执行。更改配置的任意内容（即使 version 标签相同）也会产生新版本键。代码/语境规则变化应升级内部 RULESET；`--rules-version v2` 可另行标记试验修订。当前实现 `conservative-activity-v2` 对“我司/本团队开发的产品”和向客户演示/介绍产品语境保守复核，不能将产品属性直接归给岗位。新 run 不复用 v1 判断，旧报告仍可 replay；旧运行 resume 要求原实现依赖一致，不自动改写历史。

**分层判断**：validity 为 valid / invalid / undetermined；已完成判断的有效或待判断 JD 分别使用范围三态。无效 JD 的 scope_status 为 null；解析/执行错误的 validity 为 not_evaluated、scope_status 为 null。规则需要技术工作动作与对象关系，不能靠标题或 Python/Excel 单词纳入；明确非技术工作可排除。短文本无长度限制，无技能数量或实习限制。标题与正文冲突、混合活动、已识别否定/历史/教程/公司介绍语境、信息不足均保留复核。复用 M1 `is_valid_jd` 作为无实质内容信号；未知剩余文字不自动确认为有效招聘，M1 输入字段与状态原样保留，不回写。

**输入**：沿用 A 的 JSON 数组/JSONL、InputRecord 必填字段及完整指纹；B1 对坏行/缺字段/重复身份逐条保留 input_failed，不使后续合法行消失。JSONL position 为物理行号，空白行不算输入；整个容器损坏、空文件/空数组或根类型不符记 position=0 的一个失败单元，无法推测损坏容器内的记录数。解析失败无不可变 JD 快照时，用源文件 SHA-256、原始身份（能可靠获取时）和位置引用；任一输入单元失败时均不保存整文件原始字节，合法成员仍保存完整快照。禁止凭据字段的行只保存安全原因与位置。输入文件本身始终只读。

**输出**：每个 run_id 一份不可覆盖的 JSON，含 members 和 audit。每条保存数据集/JD/snapshot/fingerprint、来源、有效性/范围/执行、原因与说明、原文 field/start/end/quote（Python 字符偏移、左闭右开）、版本、决策 ID/时间及真实来源文件运行引用。源文件字节、完整快照、观察值与完整配置保存在 SQLite；只改观察时间复用原决定，另存观察。

audit 的顶层 validity_counts、scope_counts、reason_counts、input_failed、screening_failed 针对**冻结的 B1 数据集最后可解析成员 + 本次输入失败单元**；member_total 等于两组状态计数各自之和。current_input 使用同一口径仅核对本次输入，member_total 等于 input_total。not_applicable 包含无效和未执行判断；needs_review 包含有效性待判断，不与失败混算。增量缺席的旧成员继续纳入数据集审计，保留原输入文件引用；无法解析的更新不抹掉此前可解析快照，本次失败仍单独可见。范围/规则变化重判整个已登记 B1 数据集，历史决定保留。首次 B1 使用共享 A 库时，必须显式输入需要纳入 B1 的 JD；不从 A heads 隐式扩展范围。

B1 独立表为 b1_versions/runs/heads/observations/members/decisions/reports；A 的 application_id/user_version=1 和既有表结构不变。只复用 snapshots；不写 A 的任务、尝试、事实、观察、heads 或聚合。A 原有执行与重放可继续运行。结果事务提交后再原子发布文件；未提交判断中断后重做，已提交判断不重复；输出失败可 resume。单进程文件锁及终态/版本/报告历史保护复用 A 的安全机制。输出固定 `formal_statistics_eligible=false`，`analysis_status=not_executed_by_b1`，不生成技能统计或独立职位计数。

### B1 测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_screening.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_foundation_inputs.py tests/test_job_analysis/test_foundation_validation.py tests/test_job_analysis/test_foundation_runner.py tests/test_job_analysis/test_foundation_cli.py tests/test_job_analysis/test_screening.py -q
```

只用合成 JD、临时 SQLite 和 finally 清理的临时目录；包含真实子进程硬退出、输出失败恢复和 A/B1 共库重放。本轮实际计数与完整非集成回归的合成环境/网络阻断命令见 [B1 实施报告](../../../docs/superpowers/archive/2026-10-15-M2-stage-B1-implementation.md)。合成回归不能证明真实岗位分类准确率；复杂否定、转述、跨句指代、多职位拆分和最终范围目录仍需后续人工/语义验证，B1 不承担 B2/B3/B4。

## 第一阶段 A：独立离线事实基础层

新入口为 `python -m app.job_analysis.foundation`，与下方旧管道隔离。新库跨运行持久化，不读取或升级旧 StateDB，不连接数据库服务或外部模型；要求显式输入/状态/输出。仓库内运行产物只允许位于 Git 忽略的 `data/local/`，也可使用仓库外的独立目录。

在仓库根准备一个**合成** `data/local/m2-a/input.json`：

```json
[{"id":1,"source":"synthetic","source_detail":"fixture-a","job_title":"Engineer","raw_text":"Use Python","duties":"Build services","experience":"3 years","crawled_at":"2026-10-15T08:00:00+08:00"}]
```

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.job_analysis.foundation run --input ../data/local/m2-a/input.json --dataset synthetic-a --state ../data/local/m2-a/state.sqlite3 --output ../data/local/m2-a/results
# 使用上一步 stdout 的 run_id 或 aggregate_id：
.\.venv\Scripts\python.exe -m app.job_analysis.foundation resume --run <run_id> --state ../data/local/m2-a/state.sqlite3 --output ../data/local/m2-a/results
.\.venv\Scripts\python.exe -m app.job_analysis.foundation replay --aggregate <aggregate_id> --state ../data/local/m2-a/state.sqlite3 --output ../data/local/m2-a/replay
```

`run` 可加 `--analysis-version v2`、`--aggregate-version v2` 或 `--force`。状态文件始终使用同一路径才能跨运行复用；不要删除状态模拟增量。`resume` 沿用原运行的完整输入范围和两个版本，依赖不符则拒绝。失败或 partial 任务可通过新 `run` 重试；已有成功事实保留，但最新强制尝试失败时不会静默退回旧成功。输出发布失败保留 `publication_failed`，恢复可直接复用已提交事实。

若进程在输出 stdout 前退出，可重复同一 `run` 命令（已提交事实仍复用），或只读查询本地库取得原 run_id，再执行 `resume`：`.\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('file:../data/local/m2-a/state.sqlite3?mode=ro',uri=True); print(c.execute('SELECT id,status,error FROM runs ORDER BY rowid DESC').fetchall()); c.close()"`。库的恢复状态在 `AnalysisStore` 重新打开时更新。

CLI 只运行内置 `LiteralDemoAnalyzer`：在完整正文中定位 Python 字面词，记录 `unclassified`，未匹配返回的是该演示范围的零结果。它不能识别真实要求、否定、其他技能或岗位分类，**不代表模型分析效果或完整技能覆盖**。输出携带 `offline-demo` 依赖标识，统计范围限定 `offline_evidence_audit`。

### 输入与精确复用

- 支持 UTF-8（可带 BOM）JSON 数组、逐行 JSON 对象的 JSONL；空列表、坏行、重复 JSON 键、重复身份、非有限数字、缺必填字段及其他文件格式明确报错。JSON 包装对象、CSV、SQL/mysqldump 不在新入口支持范围。
- 必填 `id`（非空字符串或整数）、`source/job_title/raw_text`（非空文本）；`duties/experience/requirements` 如出现须为文本。其他 JSON 字段保守保留并参与指纹，包括 `source_detail/quality/dup_group/cross_source`。不假设存在职位 URL。整数 ID 转成十进制字符串，故同一数据集内 `1` 与 `"1"` 是同一身份，不能同时出现；不同数据集分别保存。
- `id` 与数据集构成身份；`crawled_at` 独立存为来源观察值，不进入分析器 payload/内容指纹，不作为发布时间、不补时区或虚构缺失时间。每次载入保留观察及其来源运行；相同来源时间重复出现只是重复导入证据，不宣称新的真实观察。
- 剩余全部字段按 UTF-8、key 排序、紧凑 JSON、不允许 NaN 稳定序列化后 SHA-256。完整字段不截断；快照正文不可变，整份源文件原始字节与 SHA-256 另存于运行记录。不按正文 hash 或 dup_group 删除身份，增量文件缺项不判下架。
- 分析版本为显式 revision + 解析/清洗/证据校验修订、实际词典内容摘要、分析器 extractor/prompt/model/configuration 修订的摘要。必填依赖缺失直接拒绝；任何依赖变化保守使所选数据集全部当前输入重新处理。分析器代码、模型参数或提示词改变时接入者必须更新相应修订，第一阶段不自动分析代码依赖。
- 聚合版本独立保存 revision 与 `offline-evidence-inventory-v1` 规则标识；仅改聚合版本可复用完整单条事实。成功终态、输入/依赖/事实/聚合记录受不可改写触发器保护，不能给旧成功直接改版本号。

### 分层状态与证据

尝试状态为 `running/completed/partial/failed/retryable`；准备后尚无尝试即 pending。partial 包括声明尚未完成、事实结构损坏或引文未通过；failed 包括调用异常、空响应或顶层解析失败。合法 `coverage=complete,facts=[]` 与失败分开。失败日志只存安全原因码，不保存供应商异常文本、API 密钥或任意原始响应；合法 claim 和未知技能的原名/证据保留，非法结构项保留审计记录。

每条 claim 必须指定 `kind/name/requirement`，证据含 `namespace/jd_id/field/quote`。程序核对具体身份、完整引文及字段，保存 Python 字符索引半开区间 `[start,end)`；重复引文取首个位置。当前分析输入不清洗、不分段、不翻译，位置直接对应不可变输入字段，不能当作原始网页位置。`verified` 模型自述被忽略。

`evidence_status` 区分 `matched/missing_evidence/foreign_jd/quote_not_found/invalid_structure`。`matched` 仅证明原文对应，`semantic_status=unreviewed` 始终保留；可承载五态标签，但本阶段没有五态识别算法，兼容 `legacy_required/legacy_bonus` 也不升级为新语义。已知技能复用共享 normalizer；未知项 `governance=candidate`，不改词典。

聚合成员的资格只针对离线证据审计：completed → included，partial/未完成 → incomplete，failed → excluded，逐条保留原因。partial 中合法事实仍可在 matched_facts 核对，不让该 JD 冒充完整样本。所有正式统计资格均为 false，并注明独立职位未关联、语义未复核；没有技能需求率或独立职位数。

### 持久化、恢复与接入边界

SQLite 包含 runs（源文件/版本/状态）、snapshots、heads、observations、versions、attempts、facts、tasks（冻结输入范围及复用选择）、aggregates（版本/完整成员/业务结果和摘要）。新库由 application_id/user_version 标识，旧库拒绝自动迁移。文件锁使用 Windows msvcrt / POSIX flock，仅支持单进程串行拥有；拒绝硬链接状态文件，符号链接/junction 先解析到实际路径，不适用于多机共享网络盘。store 连接开启 recursive_triggers，使 REPLACE 的隐式删除也受历史保护；终态尝试不能追加事实。

准备运行时原子保存快照、观察、当前身份指向与完整数据集任务范围；每次尝试先提交 running，事实与终态一次事务提交。进程退出后重新打开库将遗留 running 标为 retryable；已提交终态复用，未提交结果重做。恢复旧运行按原任务范围执行，后续输入变化不污染旧运行，也不会倒退最新 heads。聚合从完整任务范围构建，不只统计本轮新增项；成员按身份稳定排序，固定 attempt/fact ID 可逐条重放。

SQLite 先保存聚合，文件在同目录暂存、flush/fsync 后原子替换，最后才记运行完成。每个 run_id 独立 JSON，已有不同内容拒绝覆盖；恢复清理该 artifact 自有暂存文件。测试覆盖进程硬退出；断电、文件系统损坏、远程盘和跨机锁不在已验证范围。

可注入边界为 `models.Analyzer` 协议：提供完整 `AnalyzerSpec`，实现 `analyze(InputRecord) -> dict | str`，由 `runner.execute/resume` 编排、验证、落库和聚合。分析器拿到全部参与指纹的字段，观察时间在接口外独立保存；不得私自读取未纳入版本的外部依赖。后续按另行授权接入旧客户端即可复用此基础设施；旧 `ExtractionResult/StateDB/merge/export` 不足以表达完整证据和失败语义，本轮不直接复用这些行为，也不替换生产 API 或交接格式。

### 离线测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_foundation_inputs.py tests/test_job_analysis/test_foundation_validation.py tests/test_job_analysis/test_foundation_runner.py tests/test_job_analysis/test_foundation_cli.py -q
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
```

新增测试全部使用合成数据、可注入分析器、临时 SQLite 与临时文件；fixture finally 自动关闭/删除并断言目录不存在。包含真正子进程 `os._exit` 中断、事务回滚及发布失败恢复。不得去掉 integration 排除条件后指向演示库；真实数据库与模型效果验证需另获许可。详细本轮通过数、干净检出时的合成配置及网络阻断回归命令见 [历史实施报告](../../../docs/superpowers/archive/2026-10-15-M2-stage-A-implementation.md)（PR #4 审查存档）；原因与教训见 [恢复陷阱](../../../docs/superpowers/traps/2026-10-15-m2-facts-and-recovery.md)。

## 旧管道与既有交接

M2 岗位分析正式目录，已接入 2026-09-01 M2 回包管道源码兼容能力。主要流程为：数据解析/预筛 → 相关性与质量判断 → 技能提取与证据验证 → 合并 → 差异记录 → 交接导出。

- 交接数据：仓库根 `exchange/m2/`；2026-10-15 只读核对为 **717 条岗位定义、717 条按 `job_id` 合并的技能明细、275 条日志**。719/719/243 是 2026-09-01 原回包数字，09-05 演示基线已调整；不是本轮数据库实查。
- 帮助入口（在仓库根进入 backend）：`cd backend; .\.venv\Scripts\python.exe -m app.job_analysis.main --help`。这只验证帮助输出；`main.py` 完整执行路径仍使用 `from pipeline import ...` / `from db_state import ...` 等绝对导入，完整 CLI 不能据此宣称可运行，待 M2 专项修复。本轮未执行收费管道。
- 模块配置：LLM 密钥从环境变量读取（当前模块配置不自动加载本地 `.env`），禁止写入源码或回包；
- M2 输出的技能优先使用 `canonical_name`，无法进入 285 条词典的候选仍保留在证据 JSON 中，并在导入审计中记录，不静默删除；
- 旧的 `input/jd-filter-package/` 已被新回包替代并于 2026-08-30 删除，Git 工作树不再依赖该目录。

源码 `export._write_json()` 写带版本头的 `{items: [...]}` 包装；已核验交接文件为标准数组，集成加载器兼容两种格式。默认 `import_all()` 优先读本地原回包目录，可能覆盖演示基线；只在明确授权的隔离实例显式指定 `exchange/m2`，具体见根目录 `docs/V1恢复手册.md`。
