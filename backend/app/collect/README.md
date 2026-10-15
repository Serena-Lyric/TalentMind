# M1 采集模块（backend/app/collect/）

> 多源数据采集（D39/D40）：岗位 JD + 信号数据 → MySQL 原始层（jd_pool / signal / talent_raw）。
> 合规红线：只读取公开数据或用户人工登录后页面可见内容；不绕过登录/验证码/反爬，不伪造 source（D17/D38）。

## 一、数据源与产出

| 来源 | 类型 | 产出表 | 实现 | 状态 |
|---|---|---|---|---|
| LinkedIn postings.csv（本地数据集） | 岗位 JD | jd_pool（source=linkedin） | `fetchers/dataset.py` + `import_csv.py` | ✅ archive 全量导入（断点续导） |
| HN "Who is hiring"（Algolia 公开 API） | 技术岗 JD | jd_pool（source=hn） | `fetchers/hn_hiring.py` + `fetch_hn_jobs.py` | ✅ 1796 行（2026-08-19） |
| GitHub Trending（公开页面） | 信号 | signal（source=github） | `fetchers/trending.py` | ✅ 语言热度 |
| 技术博客 RSS（InfoQ/掘金；OSCHINA 403 待换源） | 信号 | signal（source=blog） | `fetchers/blog_rss.py` | ✅ 技能提及 |
| GitHub Trending 贡献者 → 人才线索 | 人才 | talent_raw（source=github） | `fetchers/github.py`（保留） | 按需 |
| BOSS 直聘（人工登录 Edge + CDP） | 岗位 JD | jd_pool（source=boss） | `fetch_boss_jobs.py` + `fetchers/boss.py` / `fetchers/cdp.py` / `boss_collect_loop.py` | 2026-09-04 复核：主库 boss=1133 cleaned，采集已暂停（历史 703/488/967 等数字见下，均为快照） |
| 智联招聘（用户已登录 Edge + CDP，页面可见 DOM） | 岗位 JD | jd_pool（source=zhaopin） | `fetch_cn_jobs.py` + `fetchers/job_sites.py` + `cn_collect_loop.py` | ✅ 已冒烟：3 条落库 |
| 猎聘（用户已登录 Edge + CDP，页面可见 DOM） | 岗位 JD | jd_pool（source=liepin） | `fetch_cn_jobs.py` + `fetchers/job_sites.py` + `cn_collect_loop.py` | ✅ 已冒烟：6 条落库 |

## 二、常用命令（均在 `backend/` 下，需 venv）

```powershell
# 全部采集（信号 + HN 岗位）——推荐入口
.\.venv\Scripts\python.exe -m app.collect.fetch_all

# 单独采集信号（GitHub Trending + 博客 RSS）
.\.venv\Scripts\python.exe -m app.collect.fetch_signals --sources github,blog

# 单独采集 HN 岗位
.\.venv\Scripts\python.exe -m app.collect.fetch_hn_jobs --limit 50

# LinkedIn CSV 导入（本地数据集）
.\.venv\Scripts\python.exe -m app.collect.import_csv --csv ..\docs\originalfile\archive\postings.csv --offset 0 --limit 0 --batch-size 5000

# BOSS（需用户先在独立 Edge 中人工登录“我要投职”）
# 注意：本机 Windows 已排除 TCP 9181-9280，9222 无法监听；建议启动 Edge 使用 9333。
.\.venv\Scripts\python.exe -m app.collect.fetch_boss_jobs `
  --cdp http://127.0.0.1:9333 `
  --user-data-dir "C:\Users\<用户>\AppData\Local\Temp\TalentMind-BOSS-Edge-9222" `
  --keywords "Python,Java,数据分析,后端工程师,数据工程师,AI工程师,机器学习,产品经理" `
  --cities 北京=101010100,上海=101020100,深圳=101280600 `
  --pages 5 --detail-limit 300 --delay 1 --settle 4

# 若 9222 未监听，`--user-data-dir` 会读取 DevToolsActivePort 的动态端口，
# 并兼容浏览器级 WebSocket；也可将 --cdp 设为 auto 或直接传 ws:// 地址。
```

## 三、幂等与增量（D44 更新）

- `fetch_signals`：**追加式时间序列**——每次运行在 signal 表追加一份快照（captured_at 不同），不再当日覆盖；同一天多次跑会积累多个时间点（M2 evolution 需要）；
- `fetch_hn_jobs`：**按帖清理**——本次抓取的帖子先删旧行再插入（历史帖保留），当月帖刷新、历史月份不误删；
- LinkedIn CSV 导入支持**流式追加和断点续导**：`--offset` 跳过已导入的有效岗位，`--batch-size` 控制分批提交，`--limit 0` 表示剩余全量。由于 `jd_pool` 契约没有 `job_id` 唯一列，续导必须记录并复用准确 offset，禁止重复执行同一范围。2026-08-20 已核对既有 5000 行并从 `offset=5000` 追加 118849 行，数据库 LinkedIn 总量为 123849。

## 三·五、持续采集循环（D44，不依赖计划任务）

- `python -m app.collect.collect_loop --hours 6 --forever`：每 6 小时跑一轮 fetch_all，无限循环（后台可用隐藏窗口启动）；
- 已启动实例（2026-08-18）：PID 见 `collect_loop.out.log`；停止：`Stop-Process -Id <PID>`；
- signal 时间序列由此自动积累；计划任务（SYSTEM 02:00）保留为尽力触发。
- `fetch_all` 与循环每轮末尾**自动执行交叉验证**（cross_validate），保证 hn 刷新后 `cross_source` 标记与当前 jd_pool 一致。

## 三·六、BOSS 低速持续采集（2026-08-20）

BOSS 不再混入通用 `collect_loop.py`，使用独立循环 `boss_collect_loop.py`。默认每轮只采一个关键词/城市组合、最多 1 页/12 条岗位/8 条详情；列表与详情之间等待 15–30 秒，页面稳定等待 5–10 秒，切换下一个组合前等待 6–12 分钟。随机范围是低负载节奏控制，不是验证码或反爬绕过。

```powershell
# 独立 Edge 已人工登录 BOSS 后，在 backend/ 下启动；默认不间断运行
.\.venv\Scripts\python.exe -m app.collect.boss_collect_loop `
  --cdp http://127.0.0.1:9333 `
  --user-data-dir "C:\Users\<用户>\AppData\Local\Temp\TalentMind-BOSS-Edge-9222" `
  --forever *> ..\data\local\logs\boss_collect_loop.out.log

# 连通性验证：只跑一轮
.\.venv\Scripts\python.exe -m app.collect.boss_collect_loop `
  --cdp http://127.0.0.1:9333 --once
```

- 日志：`data/local/logs/boss_collect_loop.out.log`；停止：`Get-Process -Name python` 后按命令行确认 PID，再 `Stop-Process -Id <PID>`。
- 检测到登录页/验证页时循环停止；普通单轮异常记录后继续低速运行。
- 采集不会自动退出 BOSS；完成后必须由用户在同一 Edge 窗口手动注销。
- 2026-08-23 运行核验：BOSS 低速循环已重新启动，当前 PID `20560`；第 1 轮于 19:15:46 +08:00 完成，`listed=12/details=8/new=3/skipped=9`，随后等待 541.0 秒切换；当前进程仍存活，错误日志为空。最新快照见 `exchange/m1/collection-status-20260823.md`，M2 数据库完整导出说明见 `exchange/m2/m1-database-handover-20260823.md`。

## 三·六、BOSS 人工登录、采集与注销记录（D45/D49）

- 本次 BOSS 入口：用户选择 **“我要投职”**（求职端），不是“我要招人”（招聘端）；采集器只读取求职端登录后可见的公开岗位信息。
- 采集前提：用户在独立 Edge 配置中人工登录；采集器优先使用标准 CDP `/json/list`，固定端口不可用时从 `--user-data-dir/DevToolsActivePort` 自动发现动态端口，并支持浏览器级 WebSocket 的 `Target.getTargets`/`Target.attachToTarget`。未接收账号、密码、验证码或 Cookie。
- 采集结束后：必须由用户在同一浏览器窗口中人工注销 BOSS，再关闭采集窗口；不得把登录态提交 Git 或发送到外部。
> 历史数据记录（2026-08-20，+08:00）：Codex 内部浏览器快照读取了 7 个关键词共 105 条列表记录，与 2026-08-19 快照 45 条合并去重后将 77 条写入数据库，合计 122 条；这 122 条不计作 CDP 正式采集模块的首轮结果。快照：`data/local/boss_inapp_raw_20260819.json`、`data/local/boss_inapp_live_20260820.json`。
- CDP/路由核查：`127.0.0.1:9222` 位于 Windows TCP 排除段 `9181-9280`，不可监听；`127.0.0.1:15721` 属于 CC Switch（`cc-switch.exe`），仅返回 `/health` 200，`/json/version` 与 `/json/list` 均 404，不是 CDP；3180 不纳入正式协议。正式连接使用 `http://127.0.0.1:9333`，用户目录为 `C:/Users/SERENA~1/AppData/Local/Temp/TalentMind-BOSS-Edge-9222`。
- 首轮正式 CDP 批次（2026-08-20）：3 个关键词（Python、Java、数据分析）× 北京 × 2 页；CLI `listed=50, details=47, new=29, skipped=21`。该批次入库后 `jd_pool=6947`、`source=boss=151`；新增 29 条中 26 条含 `duties` 与详情正文。
- 扩大正式 CDP 批次（2026-08-20，历史记录）：8 个关键词（Python、Java、数据分析、后端工程师、数据工程师、AI工程师、机器学习、产品经理）× 北京/上海/深圳 × 5 页，详情尝试上限 300；CLI `listed=415, details=300, new=319, skipped=96`。原有 BOSS 151 条全部保留，批次完成后 `jd_pool=7266`、`source=boss=470`。低速循环随后又新增 14 条，当前 `source=boss=488`。
- 批次质量核验（历史记录）：BOSS 470 条全部 `status=cleaned`；`source_detail` 空值 0、重复组 0、占位 URL 0；本次新增 319 条中 `raw_text` 长度>100 的 215 条、`duties` 非空 212 条；最大 id=125915。ID 不连续是历史删除/其他写入造成，不按 ID 连续性判断采集数。当前数据库复核为 BOSS 488 条、全部 `status=cleaned`，`source_detail` 空值 0、重复 URL 0、占位 URL 0；`duties` 非空 243 条。
- 注销记录：当前独立 Edge 的 BOSS 求职端仍保持登录，尚未注销。必须由用户在同一窗口人工执行“退出登录”，随后把实际注销时间（含时区）补入本文、`资产与状态.md` 和专项交接文件。未输入或处理验证码；不得复用登录态。

## 三·七、智联/猎聘低速页面采集

已实现共享的页面可见 DOM 适配器：`fetch_cn_jobs.py` + `fetchers/job_sites.py` + `cn_collect_loop.py`。采集器只连接用户已人工登录的 Edge CDP 页面，读取当前渲染 DOM；不读取密码/Cookie，不拦截网络请求，不调用未公开接口，不处理验证码或其他验证。

```powershell
# 单轮冒烟：先人工登录对应平台，再执行；城市值必须按当前平台页面确认
.\.venv\Scripts\python.exe -m app.collect.fetch_cn_jobs `
  --platform zhaopin `
  --cdp http://127.0.0.1:9333 `
  --user-data-dir "C:\Users\<用户>\AppData\Local\Temp\TalentMind-CN-Edge" `
  --keywords "Python,后端工程师" `
  --cities "北京=530" `
  --pages 1 --detail-limit 5 --max-jobs 8 --delay 15 --settle 6

# 低速持续循环：每轮一个关键词/城市，默认 15–30 秒页面间隔、6–12 分钟切换间隔
.\.venv\Scripts\python.exe -m app.collect.cn_collect_loop `
  --platform liepin `
  --cdp http://127.0.0.1:9333 `
  --user-data-dir "C:\Users\<用户>\AppData\Local\Temp\TalentMind-CN-Edge" `
  --keywords "Python,数据工程师" `
  --cities "北京=北京" `
  --forever
```

`--search-url-template` 可覆盖平台当前搜索 URL，支持 `{keyword}`、`{city}`、`{page}`。默认 URL 仅作为启动模板；若页面结构或搜索 URL 变化，应先用 `--once` 做小批量验证。检测到登录页、验证码、安全验证或页面异常时，循环安全停止，不尝试绕过。

## 四、字段语义（D38/D39）

- `jd_pool.source`：来源平台（linkedin / hn / boss / zhaopin / liepin），仅记录平台（D17）；
- `jd_pool.source_detail`：来源细节（posting_domain / HN item URL / 数据集标识 / 智联稳定 DOM 身份或职位详情 URL）；
- `signal.source`：github / blog / …（D39 新增列）；
- 技能匹配严格限定 `backend/app/skills/skill_dict_seed.json`（285 canonical + aliases），不自由命名（反幻觉）。

## 四·五、多源交叉验证（D42）

- `cross_validate.py`：当前跨来源（linkedin/hn）同岗位比对 → 命中行 `cross_source=1` + `quality=MAX(原, 0.85)`；BOSS 已可入库，但尚未纳入该匹配规则；报告输出 `exchange/m1/cross_validate_report.md`；
- 运行：`python -m app.collect.cross_validate`（`--dry-run` 只分析）；
- 规则：normalize_title + hn 段（≥2 词、≥6 字符）↔ linkedin 双向包含 + 长度比 ≥0.6；0.85 为多源一致置信下界（明确定义）。

## 四·六、监控采集情况

- **一键查看**：`powershell -ExecutionPolicy Bypass -File scripts\check_collect_status.ps1` —— 显示 ①定时任务状态 ②最近采集日志 ③数据库采集量（jd_pool/signal 按 source、cross_source、最近时间）；
- **日志文件**：`data/local/logs/collect_daily-YYYYMMDD.log`（每日 02:00 定时任务自动落盘，gitignore）；
- **定时任务**：`schtasks /Query /TN TalentMindCollect /V`（状态/上次运行/结果）。

## 四·七、三平台有效 JD 判定（2026-10-15）

- BOSS、智联、猎聘在已有详情合并后，经 `run_pipeline()` 清洗，再由 `cleaner.is_valid_jd()` 判定，通过后才参与去重、质量评分与写入；其他来源保持原行为，平台 URL/DOM 身份处理仍由各自适配器负责。
- 不设置最低字数、不要求完整职责与任职要求同时出现、不用质量分作门槛；公司、薪资、地点缺失不影响判定。简短职责、技能要求或技能标签可保留，例如“熟悉 Java、Spring Boot、MySQL”。
- 判定副本中排除公司介绍段、带标签的薪资/地点/公司/经验/学历/福利行、仅重复岗位名、已识别的学历年限、福利及“暂无／面议”等占位。排除后没有文字或数字则拒绝；原始入库文本不被这些判定规则改写。
- 验收修复：按完整片段排除“详情请咨询”“招聘中”“欢迎投递简历”“岗位长期招聘”“投递简历请联系 HR”“待遇优厚”“工作轻松”、K/千/万薪资及北京/上海/广州/深圳/杭州/成都地点名；与技能或职责混合时保留其余内容，不要求命中固定岗位词表。公司介绍仅在行首或句末/冒号边界，且标题后有冒号或换行时识别，不截断“公司简介页面开发”“公司介绍页的开发”等正文。
- 命中扫码领券、扫码加群、加微信咨询、限时促销、欢迎购买、培训招生、包就业、刷单返佣、招商加盟或明确无招聘意图的已知短语时，先按标点分句排除命中这些短语的句子；其余句子没有“熟悉／熟练／掌握／具备／负责／参与／承担／协助 + 内容”则拒绝。广告开发岗位、正常岗前培训不按单个“广告／培训”词拒绝。
- 未识别的剩余内容保守放行，因此不是完整的招聘意图识别器；陌生广告话术、未标记的公司宣传或福利仍可能漏放。只剩元信息的卡片本轮不入库，不自动追加详情请求或重试。

## 五、测试

### BOSS 中断保护（2026-10-15）

每页列表结束后通过公共管道保存有效 JD，每条成功详情后再次提交。无效列表可以在本轮详情成功后入库；详情失败不重试该条、不写入空卡片，已提交的数据保留。列表保存不会挡住同 URL 的详情补全：本轮新增行可精确更新，跨轮仅补全可明确识别的纯元信息列表行；未知历史文本和已有详情保留。列表不会覆盖已有详情，详情重定向不改变列表稳定 URL。写库异常回滚当前记录并上报。

`listed/new/skipped/details` 保留原接口，`new` 只计新增行，更新不重复计数，`details` 计详情尝试。串行 URL 查重依赖现有字段，不保证并发采集唯一性。智联/猎聘仍使用原整轮缓冲，本轮未修改，浏览器中断丢失风险待专项验证。

离线验证：`cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_boss_interruption.py -q`。仅用合成卡片和临时 SQLite，fixture 自动关闭并删除测试文件；不连接正式 MySQL。

- `backend/tests/test_signal_fetchers.py`、`test_hn_hiring.py`：纯函数单测（mock，不联网不写库）；
- `test_collect_integration.py` / `test_talent_pipeline_integration.py`：管道集成（D37 精确清理）；
- 三平台有效 JD 离线回归：`cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_cleaner.py tests/test_boss_fetcher.py tests/test_cn_job_fetchers.py tests/test_collect_repo.py -q`（内存数据库替身，不联网、不写真实数据库）；
- 全量：`cd backend; .\.venv\Scripts\python.exe -m pytest -q`（历史记录 221 passed；2026-09-04 collect-only=237：unit 214 / integration 23，实际通过数以全量运行为准）。

## 六、设计参考（crawl4ai 评估，2026-08-17）

- 评估结论：**不引入 crawl4ai 依赖**（当前数据源均静态/API/XML，无需 JS 渲染；其 stealth 反检测不改变合规红线；引入需 Playwright/Chromium 重型依赖）；
- 可借鉴设计：内容清洗策略（fit-markdown 噪声过滤 → 已由 cleaner `_strip_noise`/`_fix_fused_prefix`/`_extract_duties` 覆盖）；缓存与幂等（已由当日先清后写覆盖）；
- 若未来出现"robots 允许但需 JS 渲染"的合规源，再评估 Playwright 直连（无需 crawl4ai）。
- 历史运行记录（2026-08-20）保留于专项交接文档；当前运行记录（2026-08-22）见 `exchange/m1/collection-status-20260822.md`：BOSS 已完成第 116 轮，数据库 `source=boss=621`；通用循环已完成第 17 轮并继续每 6 小时运行。
