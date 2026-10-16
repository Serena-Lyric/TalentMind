# B3-2 标准岗位候选治理实施计划

> 执行：使用 writing-plans / executing-plans 与 TDD，当前会话实施，完成后独立代码审查。用户已授权按 Issue #12 连续开发至 PR，不重复请求执行许可。

**目标**：有证据的显式岗位候选、名称关系和审核记录可离线保存、版本追踪及重放，正式目录为空。

**依据**：[Issue #12](https://github.com/Serena-Lyric/TalentMind/issues/12)、[产品决策](../../PRODUCT_DECISIONS.md) M2-07～11、41～43及 Issue 追加确认的多核心原则。

**架构**：新增 `backend/app/job_analysis/role_classification/governance/` 子包。复用 A 的严格 JSON、不可变 snapshots、路径/锁和原子发布；只追加 b32 表，打开时 recover=false。独立子包不会进入旧 B3-0/1 顶层源码 glob，旧 manifest 不变。沿用 Pydantic/SQLite/标准库，不加依赖。

## 约束与工程选择

- 只接收显式候选主张，不实现自然语言提取器或自动分类。源 JD 原文与完整字段上下文单独保留；引文可核验不表示语义真值。
- 配置含 revision 与空正式目录；合成记录显式 synthetic_only，不形成正式词表。候选稳定 ID、原名、可能规范名、提议者/来源类型、类别候选、多核心责任、未决原因及原文证据独立保存。
- 关系为 synonym / related_to / specialization_of / technology_direction_of / possible_composite_of；均待审，不做映射、合并、传递或拆职位。名称多目标/关系多目标保留审计。
- 主岗位保守 unresolved（无候选则 unknown）；候选责任标签是外部主张，不自动决定成熟复合/混合/多职位。possible_multiple_positions 也只来自显式标注。
- 审核事件绑定结果版本及候选/关系 ID，要求具名审核人、依据、本条来源引文，允许接受/驳回/延期/撤回；仅追加，接受不等于发布。原报告不随新审核变化；独立 review export 保存事件截面。
- 不改 A/B1/B2/B3-0/B3-1 代码及结果；不跑生产数据库、真实模型、真实采集或 B4/M3/M4。

## Review focus

1. 外部输入伪造完整身份/偏移/原始名称，整轮原子拒绝。
2. 标题与职责冲突、危险上下文与多个核心主张保留原文且不提升为事实。
3. 同名、多重别名及跨版本目标不得通过覆盖顺序消失。
4. 审核伪造目标版本或修改历史，拒绝且不改变报告。
5. 提交前硬退出、提交后发布失败，旧层历史与精确 replay 保持。

## Task 1：显式候选与关系契约

创建 models.py / validation.py，测试 test_role_governance.py；接口 validate_submission(batch, submission, catalog) 返回可持久化纯结构。

- [x] 写空目录/合成隔离、非法/重复 ID、名称冲突、非同义关系、技术栈、复合与多核心/多职位、标题职责矛盾、缺失/跨 JD/错位证据的失败测试。
- [x] 运行测试观察缺失模块 RED；最小实现后 GREEN。
- [x] 目录只接受空 formal_jobs，所有正式准入恒 false。

## Task 2：版本、存储、审核与 CLI

创建 runner.py / store.py / __main__.py，测试 test_role_governance_storage.py；execute(store,batch,submission,catalog,revision,output) 保存整轮事务，replay(store,run_id) 原样返回。record_review(result_id,event)、reviews(result_id)、review_export(store,run_id) 分离追加事件与旧报告。

- [x] 先写精确复用、输入/配置/源码/主张版本失效、观察独立保存、历史不可改、审核归因及版本拒绝的 RED 测试，再实现。
- [x] CLI 显式 run/replay/review/export-reviews；输出与所有输入路径互斥，原子发布恢复不需当前配置。
- [x] 合成共库跑 A/B1/B2/B22/B30/B31 后逐表/逐行与 manifest 比较；事务异常/硬退出与发布失败验证。

## Task 3：离线交付

- [x] 提交纯合成 input/submission 与空目录配置及使用说明；实际 CLI run/review/export/replay 验证，finally 清理专属临时文件。
- [x] 完整合成配置/socket 阻断非集成测试；本地链接、编码和 diff 检查。
- [x] 仅归档用户已确认的多核心原则为 M2-44 / D83；同步 M2 README、索引、资产与状态、实施报告及必要陷阱。
- [ ] 独立审查已完成，无阻塞问题；最终显式暂存、提交、推送和创建面向 master 的 PR。保留工作树与分支，不合并。
