# BOSS 采集专项交接（2026-08-20）

> 交接对象：下一位负责 M1 采集、数据库核验或系统集成的 Agent。
> 本文件只记录采集模块和数据库状态，不包含账号、密码、验证码、Cookie 或任何登录态。

## 1. 结论

BOSS 采集模块已在用户人工登录的 Edge 求职端上通过正式 CDP 完成扩大采集；不是人工手工采集冒充。

- BOSS 入口：用户选择 **“我要投职”**（求职端），没有选择“我要招人”（招聘端）。
- CDP：`http://127.0.0.1:9333`。
- 当前数据库：`jd_pool=126119`，其中 `linkedin=123849`、`hn=1796`、`boss=474`。LinkedIn archive `postings.csv` 已全量导入；本次从既有 5000 行之外追加 118849 行。
- 原有 BOSS 151 条已保留；扩大批次新增 319 条，因此最终 BOSS 总量在持续循环首轮后为 474 条。
- 当前独立 Edge 仍保持 BOSS 登录；用户必须在同一窗口人工注销，注销时间尚未补录。

## 2. 本次正式扩大采集

执行目录：`D:/Application/ClaudeCode/repository/TalentMind/backend`

实际命令：

```powershell
cd D:\Application\ClaudeCode\repository\TalentMind\backend

.\.venv\Scripts\python.exe -m app.collect.fetch_boss_jobs `
  --cdp http://127.0.0.1:9333 `
  --user-data-dir "C:\Users\SERENA~1\AppData\Local\Temp\TalentMind-BOSS-Edge-9222" `
  --keywords "Python,Java,数据分析,后端工程师,数据工程师,AI工程师,机器学习,产品经理" `
  --cities "北京=101010100,上海=101020100,深圳=101280600" `
  --pages 5 `
  --detail-limit 300 `
  --delay 1 `
  --settle 4
```

CLI 结果：

```text
listed=415
details=300
new=319
skipped=96
```

采集范围为 8 个关键词 × 3 个城市 × 每组最多 5 页；详情尝试上限为 300。采集器负责列表提取、详情提取、清洗、去重和入库，未绕过登录、验证码或反爬。

## 3. 数据库核验

采集完成后已查询 MySQL：

```text
jd_pool 总量：7266
linkedin：5000
hn：1796
boss：470
status=cleaned：7266
```

BOSS 质量核验：

```text
原有 151 条仍存在：151
本次扩大批次新增：319
新增批次 raw_text 长度 > 100：215
新增批次 duties 非空：212
BOSS source_detail 空值：0
BOSS source_detail 重复超额：0
占位 URL（精确为 /job_detail/）：0
BOSS 最大 id：125915
```

说明：数据库自增 ID 不连续，存在历史删除和其他写入，不能用 ID 连续性推算采集数量。BOSS 数据的 `crawled_at` 均为 2026-08-20；所有 BOSS 行当前 `status=cleaned`。

测试数据安全核查：

```text
后端全量测试：216 passed，3668 warnings
测试岗位夹具残留：0
测试人才 identity_hint 残留：0
MVP 测试岗位残留：0
job_change_log 测试标记残留：0
生产 jd_pool：7266
生产 BOSS：470
```

不得按 `source='boss'` 做宽泛删除。测试或重跑清理必须按 URL、job_title、identity_hint 或其他唯一夹具特征精确处理，并放在 `finally`/fixture teardown 中。

## 4. CDP 和浏览器运行信息

- Edge 程序：`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- 用户目录：`C:\Users\SERENA~1\AppData\Local\Temp\TalentMind-BOSS-Edge-9222`
- 当前端口：`127.0.0.1:9333`，已验证 Edge 正在监听。
- `9222` 不可用：位于 Windows TCP 排除段 `9181-9280`。
- `127.0.0.1:15721` 是 CC Switch 健康接口，不是 CDP；`/json/version` 和 `/json/list` 返回 404。
- `3180` 不纳入正式采集协议。
- 不要索要或保存账号、密码、验证码、Cookie；用户人工登录是前置条件。

连接设计和历史故障记录：

- `docs/superpowers/specs/2026-08-20-boss-cdp-connection-design.md`
- `docs/superpowers/traps/2026-08-20-edge-cdp-port-excluded.md`
- `docs/superpowers/traps/2026-08-20-edge-cdp-active-port-stale.md`
- `docs/superpowers/traps/2026-08-20-boss-detail-fields-dropped.md`
- `docs/superpowers/traps/2026-08-20-boss-duties-not-extracted.md`

## 5. 代码位置

- 采集 CLI：`backend/app/collect/fetch_boss_jobs.py`
- BOSS 列表/详情清洗和归一化：`backend/app/collect/fetchers/boss.py`
- CDP 连接层：`backend/app/collect/fetchers/cdp.py`
- 采集模块说明：`backend/app/collect/README.md`
- BOSS 采集测试：`backend/tests/test_boss_fetcher.py`
- CDP 测试：`backend/tests/test_cdp.py`

当前正式采集模块的设计原则：用户提供已登录浏览器，模块通过 CDP 读取页面可见内容；不接收凭据，不绕过安全措施。其他中文招聘平台（拉勾、猎聘、智联）仍按 P6 暂不抓取。

## 6. 下一个 Agent 的接手步骤

1. 先读根目录 `AGENT_START_HERE.md`，再按路线读 `docs/superpowers/决策跟踪.md`、`docs/superpowers/资产与状态.md`、`backend/app/contracts/ddl.sql` 和 `A_AGENT_HANDOVER.md`。
2. 阅读本文件和 `backend/app/collect/README.md`，确认当前 BOSS 总量应以数据库实时查询为准；本次记录为 474，历史首轮 151 已包含在内。
3. 运行状态检查：

   ```powershell
   cd D:\Application\ClaudeCode\repository\TalentMind\backend
   .\.venv\Scripts\python.exe -m pytest -q
   cd ..
   powershell -ExecutionPolicy Bypass -File scripts\check_collect_status.ps1
   ```

4. 如果用户要求新的 BOSS 增量采集，先确认独立 Edge 仍由用户人工登录“我要投职”，确认 9333 可监听，再复用上述 CLI 并缩小到明确的关键词/城市/页数；不要重复宽泛扫描以制造重复请求。
5. 增量采集后重新查询 `jd_pool` 总数、`source` 分布、`source_detail` 重复/空值、占位 URL、`status`，并把结果同步到 `backend/app/collect/README.md`、`docs/superpowers/资产与状态.md`、`docs/superpowers/决策跟踪.md` 和本交接文件。
6. 若不再继续采集，通知用户在同一独立 Edge 中人工点击 BOSS 的“退出登录”，再关闭该浏览器窗口；记录格式：`YYYY-MM-DD HH:mm:ss +08:00`。

## 7. 当前唯一待办：补录人工注销时间

本次扩大采集已经完成，但当前独立 Edge 尚未注销。用户操作完成后，需要将实际时间补入：

- `backend/app/collect/README.md`
- `docs/superpowers/资产与状态.md`
- 本文件
- 如形成新的决策，再同步 `docs/superpowers/决策跟踪.md`

不要把 `2026-08-20 10:48:55 +08:00` 当作本次独立 Edge 的注销时间；它只代表此前 Codex 内部浏览器会话退出。


## 2026-08-20 低速持续采集

- 已新增 `backend/app/collect/boss_collect_loop.py`，BOSS 独立于通用 `collect_loop.py` 运行。
- 默认单关键词/城市、1 页、最多 12 条岗位/8 条详情；页面间隔 15–30 秒，关键词/城市切换间隔 6–12 分钟，默认不间断运行。
- 检测到登录页或验证页立即停止；不实现验证码/登录/反爬绕过。日志为 `data/local/logs/boss_collect_loop.out.log`。
- 当前运行记录（2026-08-20 17:20:11 +08:00）：BOSS 低速循环已按新默认节奏重启，启动器 PID 20544、工作进程 PID 35472；首轮北京/Python 于 17:23:46 完成，`listed=12/details=8/new=0/skipped=12`，随后等待 575.8 秒切换。
