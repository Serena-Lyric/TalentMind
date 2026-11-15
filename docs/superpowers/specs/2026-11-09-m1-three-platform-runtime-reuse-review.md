# M1 三平台隔离持续采集：开源复用与 Gate 0 证据

日期：2026-11-09（Asia/Singapore）

依据：[Issue #79](https://github.com/Serena-Lyric/TalentMind/issues/79) 顶部固定方案。本文只记录源码、许可证和本机 Gate 0 证据，不把 README 自报能力当作真实站点验收，也不授权正式库迁移或三站真实持续采集。

## 1. 开源实现核查

核查方式：浅克隆默认分支后读取实际源码、许可证、测试目录和提交时间；未安装或运行第三方项目，未复制第三方源码。

| 项目 | 核查提交/时间 | 许可证 | 实际实现 | 复用结论 |
|---|---|---|---|---|
| [OpenCLI](https://github.com/jackwener/OpenCLI) | `9bc5f5c` / 2026-11-08 | Apache-2.0 | Node/TypeScript CLI + Chrome 扩展/CDP；BOSS 搜索和详情有适配与测试；搜索使用 CDP network capture；未发现智联/猎聘适配 | 可参考目标/会话管理、失败分类和测试结构；不引入其 network capture，不整包引入 |
| [lastsunday/job-hunting](https://github.com/lastsunday/job-hunting) | `045f891` / 2026-10-09 | MIT（README 另有仅供学习/禁止商业用途表述，复制前须法律核对） | WXT Chrome MV3；BOSS、智联、猎聘均有内容脚本；智联用 jobId 匹配卡片，测试覆盖 SSR/XHR 去重、卡片追加和延迟挂载 | 可参考智联卡片身份匹配和测试样例；不复制 fetch/XHR hook；许可证表述存在冲突，暂不直接复制代码 |
| [fanfansong123/career-ops-cn](https://github.com/fanfansong123/career-ops-cn) | `18e188b` / 2026-06-01 | MIT | BOSS/猎聘 provider 主要是 URL、城市码和解析框架；BOSS 列表解析为空实现；未发现智联 provider | 仅参考 URL/城市码和来源 URL 规则；不满足持续采集引擎复用条件 |
| [JobsIn](https://github.com/Chinaduanyun/JobsIn) | `7630ea8` / 2026-05-08 | 仓库未发现 LICENSE | Chrome MV3 + 系统 Chrome 独立 Profile；BOSS 已实现，智联/猎聘仅为架构预留；含 anti-detection 模块；未发现项目测试 | 只读参考；不复制源码，不采用反检测逻辑 |
| [BossHunter](https://github.com/shengjidaguai-china/BossHunter) | `12d6891` / 2026-11-06 | PolyForm Noncommercial 1.0.0 | Python CDP；BOSS/智联/猎聘/51job 采集、轮换、检查点和较多测试；同项目支持多站经验可参考 | 非商业许可，禁止复制源码；只参考状态机、检查点和错误隔离经验 |
| [get_jobs](https://github.com/loks666/get_jobs) | `36bf5f9` / 2026-11-03 | PolyForm Noncommercial 1.0.0 | Java + Playwright；多平台共用一个 BrowserContext；含 Patchright/反检测和投递逻辑 | 非商业许可，禁止复制；其共享 Context 不满足三平台进程/Profile 隔离，只参考慢速轮换经验 |

固定结论：

- 不整包引入任何求职产品；不复制无许可证、非商业许可或与 README 冲突的源码。
- 可复用范围仅为思路、URL/城市码、身份匹配测试样例和错误经验；实际代码继续由 TalentMind 自有实现。
- 不为获得网络字段引入第二套浏览器引擎、请求拦截/重放或私有接口调用。

## 2. Gate 0 本机证据

环境：Windows；Microsoft Edge `157.0.4341.42`；独立 Profile 根目录 `data/local/collection/gate0/profiles/`（忽略目录）。原始证据只保存时间、进程/端口、可脱敏 URL、状态和结果，不保存 Cookie、账号、页面原文或 Profile 文件。

| 组 | 条件 | 结果 | 备注 |
|---|---|---|---|
| A | 独立 Profile；普通 Edge；无调试端口；用户手动搜索 BOSS | 正常 | 记录于 `data/local/collection/gate0/evidence/A.json` |
| B | 完整关闭 A 后复用同一 Profile；9333 调试端口；不连接 CDP；用户手动搜索 BOSS | 正常但存在旧标签页 | 记录于 `B.json`；未重复搜索，旧标签使可比性降低 |
| C | B 上附加只读 CDP；不导航、不拦截/重放；用户手动搜索 BOSS | 正常但城市不一致 | C 前为北京，C 后为深圳；关键词均为 Python；记录于 `C.json`，不能宣称严格同条件因果证明 |
| D | BOSS 普通进程/Profile；智联独立进程/Profile + 9334 CDP；交叉观察 | 通过 | 智联 `public_accessible`（20 卡/2 详情）；BOSS 普通窗口保持正常 |
| E | 仅在 B/C 正常时，BOSS 与智联双 CDP 独立进程/Profile/端口交叉观察 | 通过 | BOSS `authenticated_accessible`、智联 `public_accessible`；BOSS PID 39168/9333，智联 PID 6508/9334 |

按 Issue #79 固定判断树，A/B/C/D/E 均未出现站点阻断，主引擎唯一选型为复用现有 Edge CDP 引擎。B 的旧标签和 C 的城市不一致保留为可比性限制，不宣称严格因果证明。\n\n### 补充单次低频采集\n\n2026-11-09 16:16–16:17 通过现有 `fetch_boss_jobs.run_fetch` 执行一次 BOSS 单页、单关键词/城市、最多 1 条详情、15 秒动作间隔的真实采集；目标数据库为 `data/local/collection/gate0/real-smoke/20261109-161658/jd_pool.sqlite3`，频率账本同目录，未连接正式 MySQL。\n\n- 机械采集：列表 16 条，`listed=1`、`detail_attempted=1`、`detail_obtained=1`、`inserted=1`，隔离库可读回 1 行。\n- 内容证据：标题长度 15，正文长度 227，`source_detail` 长度 67（未公开原文/URL）。\n- 严格契约：**失败**。该行 `identity_status=unknown`、`content_eligible=null`，现有 BOSS 入口没有把稳定详情 URL 和正文准入写入身份字段。\n- 结论：不能把本次实测写成端到端通过；新运行时必须以隔离测试修复“内容有效但身份/内容字段缺失”，真实重试需另行授权。

## 3. 已确认的工程边界

- 频率门禁不得删除；正式旧账本未获许可不删除、不迁移。
- 每个平台使用独立频率账本和排他锁，避免跨平台 SQLite 长锁。
- 页面动作 15–30 秒，关键词/城市组合切换 360–720 秒，页面稳定至少 5 秒。
- 每个有效详情在下一页面动作前逐条提交；数据库失败只停止该平台。
- 不可靠身份保持 pending/unknown；不得按 DOM 位置、相似标题或公司猜测稳定岗位身份。
- 正式库、真实数据删除、跨版本身份升级和 PR 合并仍不在本文授权范围。



## 4. 历史 RED→GREEN 回归映射

以下均为实际测试入口；离线测试不连接真实招聘站点或正式 MySQL。

| 事故/缺陷 | 回归入口 |
|---|---|
| 测试误删正式 JD | `test_collection_runtime_three_sites.py::test_three_site_round_trip_idempotency_and_stop_restart` 使用临时 SQLite；`test_collection_runtime_state.py` 使用临时目录 |
| 裸 pytest 改写分析表/清图 | 全量命令限定 `pytest -m "not integration"`；`test_collection_runtime_scheduler.py::test_start_fails_closed_when_legacy_migration_is_required` |
| BOSS 安全循环/CDP 端口误判 | Gate 0 E 实机证据；`test_collection_runtime_browser.py::test_cdp_engine_maps_block_and_login_without_retry`；既有 `test_browser_runtime.py` |
| BOSS 整轮缓冲丢已采项 | `test_boss_interruption.py::test_detail_commit_survives_later_failure_and_empty_card_is_discarded`、`test_committed_list_survives_next_page_browser_failure` |
| 智联旧面板/缺标题/目标丢失 | `test_cn_detail_gate.py::test_slow_panel_update_waits_past_stable_old_content`、`test_dom_same_title_without_stable_panel_binding_is_not_complete` |
| 智联同卡假稳定/公司不一致 | `test_zhaopin_dom_pipeline.py::test_stable_list_detail_company_conflict_is_rejected`、`test_same_title_panel_company_changes_after_stability_are_rejected` |
| 猎聘推荐字段/元数据正文混入 | `test_cn_detail_gate.py::test_real_detail_script_preserves_lines_and_never_reads_recommendation_metadata`、`test_normalization_preserves_actual_paragraphs_and_duties_boundary` |
| 三平台空卡/福利/广告误放 | `test_pipeline.py::test_cn_jd_validity_before_insert` 的参数化样例 |
| 跨站动作 SQLite 长锁 | `test_collection_frequency.py::test_platform_actions_use_independent_ledgers`、`test_collection_runtime_three_sites.py::test_boss_blocked_does_not_prevent_other_platform_persistence` |
| 许可动作中断/恢复 | `test_collection_frequency_recovery.py::test_exception_is_explicitly_recoverable_without_refunding_cooldown`、`test_legacy_flight_migration_preserves_unfinished_and_cooldown` |
| 控制台执行结束但入库 0 | `frontend/tests/collectionRecovery.test.ts::执行结束与实际结果分开，全拒绝、部分写入、无结果和未知分母均有明确摘要` |
| 插件重复点击/提交结果未知 | `frontend/tests/bridgeBackground.test.ts::background rejects overlapping popup requests before reading the page`、`timeout during fetch aborts without retry and reports uncertain submission` |
| 长来源键静默截断 | `test_boss_fetcher.py::test_boss_normalization_rejects_overlong_source_detail`、`test_cn_job_fetchers.py::test_normalize_job_rejects_overlong_source_detail`、`test_collect_repo.py::test_build_insert_params_rejects_overlong_job_source_detail` |

补充实测结论仍为：机械采集写入 1 行，但旧 BOSS 入口身份字段为 `unknown/NULL`，严格契约失败；修复代码和隔离回归已完成，真实重试未授权。
