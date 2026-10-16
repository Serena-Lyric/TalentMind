# B3-1 七类目录与职责建议实施计划

> 执行方式：本会话直接实施，采用 executing-plans 与 test-driven-development。用户已通过 Issue #10 授权连续开发、提交和独立 PR；产品讨论继续并行，未决项不补定。
> For agentic workers: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 七类受控目录及有限、可追溯、待审职责建议，保留 B3-0 历史。
**Architecture:** 在 role_classification/proposals/ 子包独立实现，不修改 B3-0 源码及其 glob 版本依赖。复用 A 输入/锁/原子发布、B3-0 证据校验，追加 b31 表。
**Tech Stack:** 现有 Python / Pydantic / SQLite / JSON，无新增依赖。
**Spec:** GitHub Issue #10，PRODUCT_DECISIONS M2-07～11、25～40及本轮确认三点。

## Global Constraints

仅合成 JD、临时 SQLite、阻网测试；不动 DDL、旧 exchange、前端或旧断言。不运行 B4、真实模型、生产库。所有候选 pending_review，classification_complete=false、formal_statistics_eligible=false。标准岗位/方向/级别不创建值。保留工作树/分支，不合并。

## Review Focus

- 产品归属、否定/历史/培训/示例、非职责章节不得伪装当前技术交付。
- 多个核心、仅辅助或无明确主辅、标题冲突不得硬定主岗；条数/词频不赋权。
- duties 与 raw_text 不一致和未知句式保留未决证据；不跨字段拼造语义。
- 输入身份/字节/证据必须对应；输出保护输入与目录文件。
- 源码/目录/规则变化追加，旧 B3-0 manifest/replay 与旧表保持原样。

## Task 1：目录与有限职责建议

Files: proposals/models.py、rules.py、families.v1.json、__init__.py；tests/test_job_analysis/test_role_proposals.py。
Interfaces: load_taxonomy(path) -> dict；suggest(record, taxonomy) -> dict；validate_proposal(record, body, taxonomy) -> dict。

- [ ] 写七类正例、技术服务反例、目录非法/重复、主辅不足/冲突/多职位/全栈及跨 JD 证据测试。
- [ ] 运行 pytest tests/test_job_analysis/test_role_proposals.py -q，观察 RED。
- [ ] 实现严格目录、精确动作/对象/交付句式、原文证据及保守 family 主辅提示。标题线索绝不单独生成候选。
- [ ] 同命令 GREEN，提交本任务。

## Task 2：持久化及 CLI

Files: proposals/store.py、runner.py、__main__.py；同测试文件。
Interfaces: ProposalStore(path)；execute(store, batch, taxonomy, revision="v1", output=None, input_paths=())；replay(store, run_id)。

- [ ] 写真实 run/replay、观察/内容/规则/目录/源码失效、全部旧表隔离、输入伪造、失败原子性/硬退出、输出恢复和保护测试。
- [ ] 观察 RED；实现 b31_versions/inputs/results/reports，只追加共享不可变 snapshots，不调用旧分析执行。
- [ ] GREEN；旧 B3-0 manifest 与解析/replay 完全不变；提交本任务。

## Task 3：验证与交付

Files: PRODUCT_DECISIONS、决策跟踪、M2 README、资产与状态、docs/review/M2-stage-B3-1.md；发现业务缺陷时补陷阱。
- [ ] 追加 M2-41～43 与 D80 后实际可用索引；不把试验句式写成产品规则。
- [ ] 跑完整阻网非集成回归，报告 skipped/deselected/警告/连接尝试与 finally 清理。
- [ ] 独立只读内部代码审查，定向 RED→GREEN 修复，保留 ChatGPT 外部复审。
- [ ] 检查链接/diff/原工作区；独立提交推送，创建 master PR 并附实施报告。
