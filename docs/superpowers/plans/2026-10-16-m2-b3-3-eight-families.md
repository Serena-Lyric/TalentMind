# B3-3 八类版本升级实施计划

> 执行方式：按用户授权由当前 agent 连续实施，使用 executing-plans、test-driven-development；结束时独立只读审查。

**Goal:** 保全七类历史，增加显式八类配置及跨 B3-1/B3-2 的待审候选路径。

**Architecture:** 沿用 taxonomy schema，以 revision 注册精确 ID/中文标签集合。B3-2 接受可选 taxonomy，默认明确解析 families-v1；完整配置快照参与 manifest 与 result_version。保留旧存储结构、历史 replay 与审核隔离。

**Tech Stack:** Python、Pydantic、标准库、临时 SQLite、pytest；无新依赖。

**Spec:** [Issue #14](https://github.com/Serena-Lyric/TalentMind/issues/14) 与本轮用户指令。

## 约束与审查重点

- `families.v1.json` 原字节与历史报告不可改；新配置 revision=families-v2，新增 hardware_integrated_circuits。
- 正式 canonical_job/方向/级别目录为空；八类同步建设是已确认方向，具体名单仍未决。
- 新增硬件职责只支持封闭句式，标题/技术栈/历史/培训/销售不产生确定职业；多核心、跨界不明及冲突 unresolved。
- 八类和七类共库时按完整目录追溯；源码变化保守追加版本，不改旧报告、审核或上游层。
- 显式配置位于输出目录内必须拒绝；任一错位证据整轮回滚；中断与发布失败后原样 replay。
- 全部测试仅合成 JD、临时库、阻网；不接生产/真实模型，不启动 B4，不合并。

## Task 1：目录注册与有限职责建议

文件：`proposals/models.py`、`proposals/rules.py`、新增 `proposals/families.v2.json`、`tests/test_job_analysis/test_role_family_versions.py`。

接口：`FamilyTaxonomy` 依 revision 验证精确集合；`suggest(record,taxonomy)` 只启用当前目录允许的职责句式。

- [x] 固化旧 master 的纯合成 B31/B32 结果与审核截面；写 v1 字节、v2 八类、错版本/缺失/重名/错映射拒绝测试。
- [x] 写 FPGA/数字 IC/硬件电路、嵌入式/SoC 跨界及标题/非职责反例，运行观察 RED。
- [x] 最小实现注册表与 v2 配置、封闭硬件职责线索；保留 v1 原规则输出，运行 GREEN。

## Task 2：显式候选版本与历史兼容

文件：`governance/validation.py`、`governance/runner.py`、`governance/__main__.py` 及同一新增测试文件。

接口：`validate_submission(..., *, taxonomy=None)`、`execute(..., taxonomy=None)`、`version_manifest(..., taxonomy=None)`；CLI run 新增可选 `--family-taxonomy`。None 明确解析 v1。

- [x] 写第八类候选待审、v1 拒绝新 ID、默认旧输入、混合版本共库、审核失效、旧历史精确 replay 与 CLI 配置路径保护测试，观察 RED。
- [x] manifest 保存完整 family_taxonomy；配置参与版本，旧报告 replay 不加载新配置；最小实现后运行 GREEN。
- [x] 验证新目录全文变化/源码/规则/候选变化追加，审核只绑定新结果；测试中断/发布恢复、整轮回滚与旧 A/B1/B2/B30 表保护。

## Task 3：回归、文档与 PR

- [x] 完整阻网非集成回归；检查 skip/警告、临时文件清理与 v1/历史归档字节。
- [x] 追加 M2-45～47 / D84～86（核实无重号）；同步 README、资产、导航与 `docs/review/M2-stage-B3-3.md`。
- [x] 独立只读审查并修复实际阻塞问题，记录 RED→GREEN 证据。
- [ ] 只暂存本轮明确文件，提交并推送独立分支，创建面向 master 的 PR、附到当前聊天，核查未合并/未启用自动合并。

## 执行记录

- 基线：`bbe5309c44189b1b0d811363320b9df6f37574c9`，原工作区资产文档未提交修改保留。
- 工程选择：复用 schema；revision 必须为已注册版本，不能用 v2 标签包装七类。职责范围文字变更仍参与内容摘要。
- 工程选择：实现少量封闭硬件职责句式，提供可执行 B31 建议及 B32 显式候选路径；不建立正式岗位名单。
- Task 1/2 complete：首组 RED 26 failed / 8 passed，最小实现后旧七类冒充 v2 的测试改为真正 v2；最终 B3 定向 258 passed。实现提交 eb90780。
- Task 3 验证：完整阻网非集成 971 passed / 2 skipped / 23 deselected，连接尝试 0；独立审查 209 passed，最终补充 39 passed，无已知延期缺陷。两入口实际模块 smoke 及审核截面 replay 通过，临时文件剩余 0。
