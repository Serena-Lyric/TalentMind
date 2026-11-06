# M2 P5/P6 连续交付实施计划

依据 [Issue #69](https://github.com/Serena-Lyric/TalentMind/issues/69) 自主连续执行，不设技术方案审批。基线为已审但未合并的 P4 `655859f0c1412ee1d73f3dec1d1b86afe48ecea9`，后续分支 `codex/m2-p5-p6-delivery`；master 仍为 `b363905`。不引入 #64。

## 实现与验证顺序

1. **冻结来源修复**：重现 canonical catalog 两项失败；保留 candidates.v1 与原始引用，新候选版本引用不可变来源。严格摘要/引文校验不变；验证 LF checkout、历史快照和新目录。
2. **独立入口**：`backend/app/job_analysis/delivery/` 复用 P1 understand、P2-1 align/compare 和 P3/P4 apply_batch。CLI 接受显式受控分析或本地记录处理器，Python 入口可传入实际 Processor；默认零网络，不加载 .env。沿用 m2-semantic-0.2，不修改旧 UI/API 契约。
3. **运行与恢复**：独立私有 SQLite 运行账本、不可变请求/逐条结果/最终消费者契约；复用已存在的 OS Lease。候选事务仍由 CandidateStore 负责，冻结批次 ID 和原基线，跨库提交间中断靠精确重试恢复。完整有效 P1 五维可复用，classification=not_run 单独保留；partial/失败不跨运行复用。知识变化重做 P2 和候选解释，输入或处理器/提示/源码变化保守重做 P1。历史读取只读已存结果。
4. **故障与连续运行测试**：新增 test_delivery.py / test_delivery_cli.py，真实 SQLite/子进程覆盖三批以上、新依据、反证、历史、观察时间、依赖变化、停止、提交前后强退、发布失败、重复/并发、过时基线及固定 run 消费。每项业务改动先观察失败测试，再实施。
5. **P6 评价**：最终入口读取已有授权 DEV 和 manifest-bound P1 缓存；新增可复用评价工具，保留输入/参照/运行摘要、未知分母和错误映射。人审标签不由 Agent 改写；零真实同组/演化人审分母为不可计算。独立 HOLD 和新付费调用不运行。与有限字面/技能基线比较时只使用可比受控参照，并说明开发污染。
6. **交接**：更新现有 README、P5/P6、总计划、资产与状态和陷阱，旧 #41/#47 去向写 Issue #69；不增加重复阶段报告。适用回归、全仓非 integration、编译和文档链接核验后，独立提交、推送、PR 和最终 head CI；不合并。

## 执行记录

- 2026-11-07：工作区干净，新分支已建立；两项 B3-5 失败实测重现（2 failed / 25 passed）。P4 PR #68 仍 OPEN、未合并。
- 实现选择：复用 CLI/本地消费者而不改旧工作台；旧原生业务报告与新语义契约不兼容，强行投影会丢失五态、证据等级和版本。旧入口继续保留，新增独立入口明确版本。
- 已落实独立编排、只追加账本、原基线精确恢复、只读消费、七批实际 CLI 和受控 DEV 评价。缺独立中文同组/演化真值及新模型/HOLD 权限的检验保留未验收，不扩大范围。
- 独立子代理审查（不替代 ChatGPT 产品验收）发现受控 not_run 误计失败、长驻提示漂移两项 P2，及完整 P1 记录重放可用性限制；三项均已有 RED→GREEN 回归，补充了精确绑定的评价 CLI 篡改/重复/错误 run 拒绝。未遗留已确认的审查阻断项。
- 首轮全仓为 2063 passed、2 skipped、24 deselected、6 failed（exit 1）：五项新评价夹具短路径和一项 Windows PID 发布竞态。前者只规范化测试路径，后者只原子发布睡眠 worker 夹具 PID；对应定向测试重新通过。最终整合回归及 CI 以 #69 的固定提交证据为准，不沿用首轮数字作通过证明。
- 同工作区出现其他任务的匹配/学习路由及前端修改，明确排除本提交；最终全仓验证从本任务提交建立隔离 worktree，避免夹带和混用并行变化。
- 整合 PR 为 [#70](https://github.com/Serena-Lyric/TalentMind/pull/70)，新增实现提交 `6f70f23ed1c202ce99786708fed6b4496a6dea63`，基于未合并 #68；最终提审 head 与 CI 在 #69 记录。干净检出不复制 .env，CI 显式使用回环端口 1 的合成设置，模型回退也限制到回环，不依赖真实服务。
- 干净 Windows checkout 实测暴露 P2-1 知识 JSON 的 CRLF 摘要失败，已在 .gitattributes 固定不可变资产 LF；新建检出相关 45 项通过。首次 Linux 全仓 CI 为 2045 passed/6 skipped/24 deselected/1 failed（exit 1），失败为 Windows 查询测试缺 OS 替身，已保留全部断言并补齐该边界；Windows 浏览器定向 64 项通过。最终全仓/CI 继续复验，不将首轮算通过。
