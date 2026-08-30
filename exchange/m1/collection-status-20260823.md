# M1 采集与导入状态快照（2026-08-23）

## 最新实时复核（2026-08-25 23:21:47，数据库时间）

- **通用 6 小时循环**：父/工作 PID `34120/35004`，仍存活；日志最近完成第 32 轮后等待 6 小时。
- **BOSS**：父/工作 PID `20560/23120`，仍存活；本机日志时间 `2026-08-26 07:17:07` 完成第 288 轮，`listed=12/details=8/new=2/skipped=10`，随后等待 `535.3s`。
- **智联**：父/工作 PID `21840/9724`，仍存活；本机日志时间 `2026-08-26 07:10:55` 完成第 249 轮，`listed=12/details=8/new=0/skipped=12`，随后等待 `683.8s`。
- **猎聘**：此前因详情页需要人工登录/验证停止；本次使用现有人工登录 Edge CDP 恢复，启动器 `pwsh` PID `14840`，父/工作 PID `11064/12220`。本机日志时间 `2026-08-26 07:19:53` 完成第 1 轮：`listed=12/details=8/new=8/skipped=4`，错误日志为空，已进入等待 `452.1s`。
- **CDP 与页面保护**：`127.0.0.1:9333` 监听于 Edge PID `24300`；按 `/json/list` 页面身份核验包含智联、BOSS、猎聘，未发现 `about:blank` 目标；本次未关闭用户页面。
- **时钟说明**：数据库 `NOW()` 为 `2026-08-25 23:21:47`；采集进程日志显示 `2026-08-26 07:19:53`，本机系统时钟与数据库时间约相差 8 小时。业务数据时间以数据库 `NOW()` 为准，进程心跳以进程/日志为准。

## 最新数据库快照

| 指标 | 数量/值 |
|---|---:|
| `jd_pool` 总量 | 127709 |
| `jd_pool.status=cleaned` | 127709 |
| `source=linkedin` | 123849 |
| `source=hn` | 1794 |
| `source=boss` | 967 |
| `source=liepin` | 477 |
| `source=zhaopin` | 622 |
| `source_detail` 空值 | 0 |
| `cross_source=1` | 886 |
| `signal` 总量 | 1087 |
| `signal.source=github` | 264 |
| `signal.source=blog` | 823 |
| `skill_dict` | 285 |
| `job_definition` | 22 |
| `job_skill` | 22 |
| `job_change_log` | 0 |
| `resume` | 0 |
| `talent_raw` | 0 |
| `jd_pool` 最新 `crawled_at` | 2026-08-25 23:19:54 |
| `signal` 最新 `captured_at` | 2026-08-25 21:29:31 |

## 当前日志

- 通用：`data/local/logs/collect_loop.out.log` / `collect_loop.err.log`
- BOSS：`data/local/logs/boss_collect_loop-codex-20260823-191237.out.log` / `.err.log`
- 智联：`data/local/logs/zhaopin_collect_loop-codex-20260823-201701.out.log` / `.err.log`
- 猎聘本次恢复：`data/local/logs/liepin_collect_loop-codex-recovery-20260826-071553.out.log` / `.err.log`

## 恢复结论

猎聘已恢复，首轮真实完成并新增 8 条，当前循环仍存活。恢复没有读取 Cookie、密码或 Token，没有拦截网络请求，没有调用官方/私有接口，也没有处理验证码或安全验证。若后续日志再次出现“详情页需要人工登录/处理验证”或 `CDP/登录状态异常`，必须停止重试并请用户在猎聘标签页人工登录/完成验证后再启动；不得绕过。

---

## 最新复核（2026-08-24 23:48，数据库时间）

- 采集总览：通用 6 小时循环、BOSS、智联均仍在运行；猎聘原循环曾因详情页需要人工登录/验证而停止。
- 猎聘已恢复：启动器 PID 21024，循环 PID 31256，子进程 PID 9516；恢复首轮 listed=12/details=8/new=10/skipped=2，当前进入随机等待，错误日志为空。
- 当前数据库：jd_pool=127334，oss=890、liepin=357、zhaopin=443、linkedin=123849、hn=1795，全部 cleaned；signal=934（github 234、blog 700），cross_source=887。
- 通用循环父/工作 PID 34120/35004；BOSS PID 20560/23120；智联 PID 21840/9724。
- 当前 9333 /json/list 页面快照包含智联、猎聘、BOSS，未发现此前的 bout:blank 目标；本次未关闭、未创建或导航该页面。
## 最新复核（2026-08-23 20:21:53 +08:00）

- 智联页面循环已完成首轮：`listed=12`、`details=8`、`new=5`；当前进程 PID `21840`，等待约 422 秒后切换关键词/城市。
- 猎聘页面循环已完成首轮：`listed=12`、`details=8`、`new=6`；当前进程 PID `5068`，等待约 758 秒后切换关键词/城市。
- 两个错误日志均为空；循环仍存活，未发现登录失效或 CDP 错误。
- 当前数据库：`jd_pool=126408`，其中 `boss=708`、`liepin=34`、`zhaopin=22`；三类来源均为 `cleaned`，智联/猎聘 `source_detail` 空值均为 0。
- BOSS PID `20560/23120` 仍在运行，本次未重复启动；保留页面 `about:blank`（目标 ID `BA87FDA2CAA0F5D94057B0258BCAFA96`）未关闭、未导航。

> 2026-08-23 20:16 运行核验：智联/猎聘循环 PID `21004/17792` 仍存活，BOSS PID `20560/23120` 仍存活；`about:blank` 页面目标仍存在且未被关闭。此时 `jd_pool=126397`，其中 `boss=708`、`liepin=28`、`zhaopin=17`，均为 `cleaned`。

> 核验时间：2026-08-23 19:55:15 +08:00（数据库容器时间为 UTC）。本文件是 `collection-status-20260822.md` 的后续快照；历史快照保留用于追溯。

## 0. 智联 / 猎聘页面采集（本次实时更新）

- 已通过用户人工登录的 Edge CDP 页面完成当前页面核验：猎聘当前页读到 40 条搜索结果，详情 8 条；智联当前页读到 20 条，详情 8 条。
- 已启动低速持续循环：智联 PID `21004`，日志 `data/local/logs/zhaopin_collect_loop-codex-20260823-201254.out.log`；猎聘 PID `17792`，日志 `data/local/logs/liepin_collect_loop-codex-20260823-201341.out.log`。
- 实时数据库核验（2026-08-23 20:14 +08:00）：`boss=707`、`liepin=28`、`zhaopin=17`；三者全部 `cleaned`，智联/猎聘 `source_detail` 空值均为 0。
- 猎聘正式循环使用从页面搜索框实测得到的可见搜索 URL 结构，当前以全国代码 `410` 运行；智联当前以北京代码 `530` 运行。两个循环均只读取 DOM，不读取 Cookie/密码、不拦截请求、不调用官方或私有接口、不处理验证码。

## 1. BOSS 持续采集

- **已重启并持续运行**：本次启动时间 `2026-08-23 19:12:37 +08:00`。
- **进程**：当前循环 PID `20560`；命令为：
  ```text
  backend/.venv/Scripts/python.exe -u -m app.collect.boss_collect_loop --cdp http://127.0.0.1:9333 --user-data-dir C:\Users\SERENA~1\AppData\Local\Temp\TalentMind-BOSS-Edge-9222 --forever
  ```
- **本次已完成前 4 轮**：第 1 轮 `北京/Python`、第 2 轮 `上海/Python`、第 3 轮 `北京/Python`、第 4 轮 `北京/Java`；第 4 轮 `listed=12/details=8/new=1/skipped=11`，随后进入随机等待。
- **循环逻辑**：本次进程使用 `rounds=0`（不设轮数上限），每轮完成后进入随机等待并切换关键词/城市，不会按一轮自动结束；遇到 CDP/登录状态异常才会安全停止。
- **CDP**：`127.0.0.1:9333` 正在监听，浏览器级 CDP 可用；当前循环已完成第 4 轮并进入等待。页面是否保持人工登录/是否出现验证页仍需以 Edge 当前状态为准；采集器不处理验证码、密码、Cookie 或反爬绕过。
- **日志**：
  - `D:\Application\ClaudeCode\repository\TalentMind\data\local\logs\boss_collect_loop-codex-20260823-191237.out.log`
  - `D:\Application\ClaudeCode\repository\TalentMind\data\local\logs\boss_collect_loop-codex-20260823-191237.err.log`（当前为空）

## 2. 数据库导入核验

本次没有执行破坏性全量重导；对当前 MySQL 集成库做了实时核验。BOSS 本次已完成前 4 轮，新增记录已持续落库；

| 指标 | 当前值 |
|---|---:|
| `jd_pool` 总量 | 126,371 |
| `jd_pool.source=linkedin` | 123,849 |
| `jd_pool.source=hn` | 1,795 |
| `jd_pool.source=boss` | 704 |
| `jd_pool.source=liepin` | 11 |
| `jd_pool.source=zhaopin` | 12 |
| `jd_pool.status=cleaned` | 126,371 |
| `jd_pool.cross_source=1` | 888 |
| `signal` | 680 |
| `signal.source=github` | 174 |
| `signal.source=blog` | 506 |
| `skill_dict` | 285 |
| `job_definition` | 22 |
| `job_skill` | 22 |
| `job_change_log` | 0 |
| `resume` | 0 |
| `talent_raw` | 0 |

BOSS 质量核验：`source_detail` 空值 `0`、重复值 `0`，`duties` 非空 `288` 条；BOSS 704 条全部为 `cleaned`。BOSS 最新 `crawled_at` 仍以运行日志和数据库实时核验为准。

交叉验证方面，数据库实时 `cross_source=1` 为 `888` 行；自动任务生成的报告当前为 `887` 行，差异是已知的 1 条历史残留标记，未执行按 `source` 的宽泛删除。

## 3. 其他采集管线

- 通用持续循环 `collect_loop.py --hours 6 --forever`：父/工作进程 PID `34120/35004` 仍在运行；最近完成第 17 轮（`2026-08-22 10:57:40 +08:00`），按 6 小时节奏等待下一轮。
- HN 岗位已进入 `jd_pool`，当前 1,796 条；GitHub/博客信号当前 680 条，覆盖 `2026-08-17` 至 `2026-08-22` 共 6 个日期。
- `talent_raw=0`，人才线索线未持续运行；智联/猎聘页面可见 DOM 采集已完成冒烟并可按低速循环扩大，拉勾仍按 P6 暂不抓取。
- `scripts/check_collect_status.ps1` 已核验：MySQL、通用采集日志和数据量正常；SYSTEM 计划任务不可由普通权限读取，但采集循环不依赖该任务。

## 4. 本快照的结论

1. BOSS 已重新启动，前 4 轮均完成并进入随机等待，持续循环逻辑正常。
2. BOSS 已持续进入后续轮次，当前 `source=boss` 为 704 条；没有发现空 `source_detail`、重复 `source_detail` 或未清洗 BOSS 数据。
3. 智联/猎聘当前页面扩大采集成功：zhaopin 12 条、liepin 11 条已落库，均为 `cleaned`，`source_detail` 非空。
4. 当前数据库可作为 M2 交接快照；完整 SQL 导出及恢复说明见 `exchange/m2/m1-database-handover-20260823.md`。