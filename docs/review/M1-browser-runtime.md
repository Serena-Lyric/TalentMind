# M1 浏览器自动启动与三平台访问状态

日期：2026-10-20，Asia/Singapore。基线 `284bb62`；在 `codex/m1-m2-quality-replay` 原 #40 中追加，待 ChatGPT 与负责人审查。没有创建工作树、分支或 PR，没有合并。

## 实现与边界

- 抽取 `backend/app/collect/browser.py`，复用原 Edge 参数、CdpClient 和平台选择器；控制台、单次 CLI、循环的 run_fetch 共用。Windows 仅核对 Edge 主进程，一次查询监听表，避免 renderer 继承调试参数导致逐进程查询超时。
- 独立 profile 置于 `data/local/edge-boss-cdp-profile`；启动动态端口，监听地址仅回环。复用须同时匹配 profile/活跃主进程/实际回环监听，不仅凭 DevToolsActivePort。日常 Edge 用户目录被拒绝，无关端口不接管。
- HTTP 与 browser WebSocket 的目标页严格匹配平台主机及子域；缺失即失败，不回退其他平台。HTTP 发现的 WS 必须是同一回环地址和端口；采集锁定准备返回的 target_id/endpoint，禁用旧 profile fallback。旧登录标签不再遮蔽同平台新就绪标签；显式 URL 绑定自己的目标页。
- 准备、状态查询与显式采集分离；`auto_start` 保留形参但不采集。`--prepare-only` 不需要关键词/城市/.env；原 run_fetch 在准备完成后才进入持久化层。验证码立即停止；手动登录等待超时仍保留浏览器供下一次准备恢复。
- 正面可见正文/卡片证据与认证证据分开；认证仅使用明确账户/注销控件，不读取 Cookie/凭据。登录入口存在不强制登录，JD 中“安全验证系统开发/处理服务异常”不再误判。可见登录/验证 iframe 优先阻断，隐藏 iframe 不阻断；三平台匿名访问按实际内容判定。游客截断单独记录。
- 清洗、评分、去重、INSERT/UPDATE 规则与 DDL 未变。猎聘当前 `.jobCardPcContainer` 作为原选择器集合的一项兼容补充，不新增抓取通道。没有修改前端、M2/M3/Neo4j、B3、正式 .env、Docker 或主仓库。

## 接口与前端同步

`GET /collection/cdp-status` 保留 `endpoint/reachable/boss_page_count/platform_pages/platform_login_required/login_required/page_targets/last_checked_at`。`page_targets` 保留 `type/url/title`；新增 `platform_access: Record<平台, Access>`。旧登录 boolean 只表示已识别的登录门禁，false **不能**表示已认证或可采集。

`Access` 字段：

| 字段 | 含义 |
|---|---|
| `access_state` | `cdp_unavailable`、`starting`、`page_missing`、`loading`、`public_accessible`、`authenticated_accessible`、`login_required`、`verification_required`、`empty_results`、`page_error` |
| `can_collect` | 当前页面有公开/认证内容，或明确空结果；不能据此推定详情完整，也不授予自动采集许可 |
| `authentication` | `authenticated` 仅有正面认证控件证据；否则 `unknown`，并非“未登录”定论 |
| `content_limited` | 页面显示游客截断/局部登录门禁；列表可以公开但详情不完整 |
| `reason` | 状态依据，例如 `visible_job_content`、`no_access_evidence`、`manual_login_gate` |
| `evidence` | 可见卡片/正文 DOM 容器计数，可重叠；不是独立职位、详情尝试或采集成功数量 |
| `target_id` | 准备所选目标的运行期标识；采集必须使用这个受控目标 |
| `timed_out` | prepare 超时标记；下一次准备会复用同一独立 Edge |

`POST /collection/prepare` 保留 `status/message/cdp`，新增 `access_state/can_collect/auto_start_ignored`；可用时顶层 status 为 `ready`，否则为具体访问状态。旧 `auto_start=true` 不产生采集任务。控制台继续轮询 CDP 状态即可观察人工登录后的状态恢复；显式 `/start` 单独校验并启动原有任务。`check_cdp_before_start` 配置字段保留，但 false 不再绕过门禁。无需覆盖前端页面工作，成员后续可扩展 TS 类型并根据 platform_access 展示操作提示。

CLI：`fetch_boss_jobs`、`fetch_cn_jobs` 新增 `--prepare-only`、`--browser-timeout`、`--login-timeout`。准备状态退出码 0/2；只有显式采集模式要求关键词/城市。准备成功不会自动把 prepare-only 升级为采集。

## 真实浏览器烟测

复用主仓现有 Python 3.14.5 依赖，仅加载本工作树源码。本工作树没有 `.env`，烟测也未加载主仓配置。首先实际执行：

```text
python -B -m app.collect.fetch_boss_jobs --prepare-only --browser-timeout 25 --login-timeout 0
python -B -m app.collect.fetch_cn_jobs --platform liepin --prepare-only --browser-timeout 20 --login-timeout 0
python -B -m app.collect.fetch_cn_jobs --platform zhaopin --prepare-only --browser-timeout 20 --login-timeout 0
```

最终使用私有 `data/local/m1-browser-runtime/smoke.py` 调用同一 prepare 接口，显式准备 BOSS 搜索目标；猎聘最多打开一个当前可见详情链接；智联没有独立详情链接，检查现有分栏。脚本禁止导入 app.db、禁止数据库服务连接，仅许可本机 CDP。

| 平台 | 结果 | 对登录的结论与限制 |
|---|---|---|
| BOSS | `verification_required`，`can_collect=false` | 显式搜索触发安全验证，立即停止该平台；未处理验证、不重试、不证明登录后可采集 |
| 猎聘 | 搜索和一个详情均 `public_accessible` | 本次未人工登录即有可见内容；不强制登录，也不推定所有职位/地区永久公开 |
| 智联 | 搜索 `public_accessible`，`content_limited=true` | 公开列表可访问；分栏详情存在游客截断/登录提示，不能声称完整详情匿名可读；独立详情未检查 |

独立 Edge 实际监听 `127.0.0.1:2245`（动态运行值，不是固定配置）；主进程 PID 21268，重复准备未另起主进程。烟测 Python 的网络连接只到 2245；`app.db` 未导入。没有运行 fetch、循环或任何数据库 SQL，`jd_pool` 写入为 0；未为证明无写入而连接生产库。现有生产数据和先前备份保留。

私有状态、原始可见页面快照、详情 URL、进程/listener 与导入/连接证据保存在本工作树 `data/local/m1-browser-runtime/`；不得加入 Git。公开材料仅给聚合与状态，未公开 JD/账号标识/访问凭据。

## 测试与独立审查

- 先 RED：目标域误连、远程端点、旧 auto_start、状态/生命周期/CLI 准备缺失；后续 6 项审查边界以及 2 项真实页面形状回归均经历失败到通过。没有用真实数据库或网站作自动测试。
- 当前 M1 定向回归：232 passed，含实际 JavaScript 在合成 DOM 中执行、临时 SQLite 的中断/补全提交回归。阻网执行器证明外部/服务连接与 DNS 尝试 0、专属临时测试目录已删除。
- 全量非集成在本机主仓 venv：1266 passed / 10 failed / 2 skipped / 23 deselected；88 个 Python 进程，阻网尝试 0、内部 socketpair 12，专属临时目录删除成功。2 项 `test_canonical_catalog` 来源摘要/引文失败为已有问题；8 项 `test_real_pipeline`/`test_real_quality` 因此 venv 缺少可选 networkx（以及 igraph/leidenalg）依赖失败。没有为此修改或安装图谱依赖，不宣称全仓绿。
- 早期自建防护脚本误阻 Python 子进程和 Windows socketpair，其失败日志保留，弃用该执行方式；正式结果复用仓库已有 `quality-execution/verify_offline.py`，不把防护故障归为产品缺陷。
- 独立内部审查发现 5 项 Important：端点/profile 回退、覆盖卡片的门禁 iframe、正文误判、BOSS 选择器缺失、多标签恢复。均补测试并修复；外部 ChatGPT/负责人验收尚未完成。
- 复审补充“旧错误标签遮蔽登录状态/初建未知标签隐藏登录后新页”两条恢复路径，经 2 RED→GREEN 后静态复查无遗留 Critical/Important。全量失败名称为：`test_repository_draft_covers_eight_families_and_empty_release`、`test_shipped_source_hash_matches_a_fresh_LF_checkout`、`test_pipeline_keeps_identity_states_and_source_evidence`、`test_pipeline_empty_scope_still_publishes_rejections`、`test_empty_real_body_is_audited_without_dropping_other_records`、`test_verify_recomputes_derived_and_layout_instead_of_trusting_rehashed_file`、`test_quality_comparison_requires_same_frozen_input_and_has_no_gold`、`test_review_card_excerpt_omits_company_and_personal_metadata`、`test_review_retains_section_context_and_each_skill_target` 的任职要求/加分项两个参数。
- 三个早期默认 pytest 临时目录（pytest-98/99/100）由创建时间与本轮日志精确对应；清理命令先核对绝对路径及重解析点，但被自动审批策略拒绝，工具只给出 `blocked by policy`，未尝试替代删除。目录保留，均为合成测试资料；正式阻网执行器的专属临时目录已自动删除。此项不涉及真实 JD 或数据库残留。

## 已知限制与回退

认证成功的真实交互、本机 BOSS 验证完成后的搜索/详情尚未验收；人工登录恢复只完成离线模拟。DOM 和门禁选择器依赖当前页面布局，未知布局保守返回 page_error，不假称可访问。智联游客详情完整性仍受限；未评测 JD 清洗质量，未运行真实采集。

源码回退只需在本分支反向提交本轮 browser-runtime 变更，保留此前 `284bb62` 的 M1/M2 质量工作。运行时可仅关闭本轮独立 Edge 窗口；不终止日常 Edge、不删除 profile、不恢复数据库。若关闭进程，先复核 profile 和 PID，不能按 msedge 名称全量停止。

到此停止。三平台真实写库采集需要下一步单独确认；本轮不授予该许可。
