# M2 B3-0 Implementation Plan

> **For agentic workers:** Use executing-plans to implement task by task with TDD and one fresh whole-branch review.

**Goal:** 实现 Issue #8 已授权的四维分类标注、证据校验与不可变离线历史。

**Architecture:** 独立 role_classification 包消费 A InputBatch 与显式 annotations/taxonomy，不调用分类器。追加 b30_* SQLite 表，共享不可变 snapshots；整轮事务提交后发布，失败可 replay，无长期 running/resume 状态。

**Tech Stack:** 现有 Python/Pydantic/SQLite 与标准库，无新依赖。

**Spec:** GitHub Issue #8；docs/PRODUCT_DECISIONS.md M2-07～11、25～40。

## Global Constraints

- 仅合成 JD / 人工待审离线断言；taxonomy 为空或显式合成示例，不能作为正式目录。
- 无模型、网络、生产数据、正式迁移、B4/M3/M4 或旧事实改写。
- formal_statistics_eligible=false；引文校验不等于语义正确。
- 仅追加版本，输入/标注/目录/实际实现摘要变化失效；观察独立保存。

## Review Focus

- 伪造跨 JD/指纹/偏移及空白引文拒绝，不把引文匹配当语义复核。
- 部分标注及完全未知仍保存；缺标注成员可见，不能冒充完整分类。
- 多方向、主辅关联及多职位待审不产生独立职位数量。
- 事务/硬退出/发布失败后可重跑或重放，无历史覆盖。
- 共库打开不能恢复或改写旧 A/B1/B2 的运行状态。

### Task 1: 严格模型与证据验证

**Files:** role_classification/models.py, validation.py; tests/test_job_analysis/test_role_classification.py。
**Interfaces:** validate_annotation(record, annotation, taxonomy) -> dict；Taxonomy 严格四维合法值，Annotation 显式身份/指纹。

- [x] 写四维未知、多方向、主辅、冲突、多职位、非法身份/位置/值/结构测试，运行确认 RED。
- [x] 实现严格输入及逐字原文字段/字符偏移核验；已知值要求证据，冲突维度保留 unresolved。
- [x] 局部测试通过，提交本任务。

### Task 2: 持久化、复用与恢复

**Files:** role_classification/store.py, runner.py, __main__.py, __init__.py；foundation/store.py 仅增加默认兼容的 recover 开关；同测试文件。
**Interfaces:** execute(store,batch,annotations,taxonomy,revision='v1',output=None) -> report；replay(store,run_id) -> 原报告。

- [x] 先写追加版本/复用/历史保护/旧运行隔离/事务/子进程硬退出/发布失败/CLI 测试并确认 RED。
- [x] 复用 A 路径/锁/快照/原子发布；B3 打开不触发旧 A 恢复。每轮一次事务，无未提交运行；replay 不加载新目录或规则。
- [x] 相关 A/B1/B2/B3 离线回归通过，提交本任务。

### Task 3: 交付与独立审查

**Files:** M2 README、根 README、docs/README、资产与状态、docs/review/M2-stage-B3-0.md；合成输入示例。

- [x] 同步边界、命令、版本失效、事务语义和未决产品项。
- [x] 阻断网络、合成配置运行完整非集成回归；确认临时目录清理及原工作区保护。
- [ ] 独立只读审查，重要问题按 RED→GREEN 修复，明确暂存、提交、推送并创建 PR；不合并。

## Execution ledger

- Task 1: 29 failed（模块缺失）→29 passed；候选需要直接原文依据，修正一处合成 fixture 补齐候选引用。没有真实识别或语义复核结论。
- Task 2: 新组 16 failed→45 passed；另修正 SQLite 测试连接关闭后清理通过。CLI/输入字节一致性新组 RED→GREEN，总计49 passed。五处真实 os._exit、历史不可变/REPLACE、共库旧表逐行对比与发布失败恢复均已执行。
- Task 2 gate: A/B1/B2/B3 定向回归421 passed（42.12s）；原工作区资产文档SHA-256仍为F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B。
- Task 3 verification: 完整非集成762 passed / 2 skipped / 23 deselected，外部连接0；合成CLI run/replay报告一致、临时SQLite及输出清理remaining=false。原工作区未提交文件保持原样。
- Final gate: 交付树同命令762 passed / 2 skipped / 23 deselected（46.12s），外部连接0；新增文档链接/编码/暂存diff通过，远端master仍93508b0。
- Final review: 独立只读审查93508b0..1f76348无Critical/Important/Minor；独立49 passed。两个非阻断覆盖建议留报告，未扩写产品规则；README明确不完整待审断言共存，不作完整分类或职位数量。

- 2026-10-16：用户已明确授权立即实施并交付独立 PR；不再等待产品目录定稿。工程实现自行完成，最终按 requesting-code-review 派独立审查。
- 工程选择：已知分类值仍为未语义复核的输入断言；人工输入只能 pending_review，合成输入不当准确率真值。
- 工程选择：全轮事务，无长期 running；提交前中断重跑，提交后 replay 恢复发布。不隐式展开增量成员范围。
