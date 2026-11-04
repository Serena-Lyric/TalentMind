# P2-1 版本化知识与候选治理

本包把 P1 已保存的机器候选事实对齐到独立知识快照，不修改 P1 的
`claims/requirements/relations`、五态、程度、条件、组合、证据或
`machine_unreviewed`。默认入口是纯离线 CLI，不连接 MySQL/Neo4j、不调用模型，
也不发布正式技能或岗位目录。

## 当前交付

- `catalog/backend-foundations.v1/`：小范围外部知识快照。来源包含 Python 3.14.10
  中文文档、MDN 中文 JavaScript/TypeScript 页面和 Kubernetes 中文概述；两条 P0
  候选岗位参照保留原来源、字节摘要和许可未明限制。快照只保存短引用，不复制整页/整本资料。
- `align_analysis`：只做 NFKC + 空白/大小写归一后的精确标准名或显式别名匹配。
  模糊名称、共同出现和同一模型重复输出都不会建立同义；一个原始 member 同时含多个已知概念时
  返回 `ambiguous`，不擅自拆分。
- `compare_roles`：按职责短语和显式边界比较。覆盖缺口保持 `unresolved`；
  `not_supported` 必须带本地职责证据与知识边界证据。
- `CandidateRegistry`：只从有明确能力上下文的未知表达建立候选。独立证据按规范化正文去重，
  平台名称或转载次数不会增加独立性。候选修订、争议和撤回都只追加版本，旧版始终可读。
- `locate_impact`：别名、概念、关系、角色或来源变化可定位受影响对齐；角色、来源或无法证明范围时
  保守标记全部。
- `build_profile`：只从已支持的角色比较与显式版本对齐重建候选画像，保留成员原始五态和组合，
  不把单个成员的 `required` 推广为全体岗位要求。

知识状态只允许 `test / candidate / formal`。当前发布快照没有正式条目；正式条目缺少逐项批准证据
会加载失败。候选合并、拆分、身份确认、正式准入和正式发布都返回
`requires_human_decision`，本段不开放自动正式准入。

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
