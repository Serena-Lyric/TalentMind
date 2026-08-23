# M1 采集与导入状态快照（2026-08-23）

> 核验时间：2026-08-23 09:49:45 +08:00（数据库容器时间为 UTC）。本文件是 `collection-status-20260822.md` 的后续快照；历史快照保留用于追溯。

## 1. BOSS 持续采集

- **已重启并持续运行**：启动时间 `2026-08-23 09:44:57 +08:00`。
- **进程**：启动器 PID `22980`，工作进程 PID `36524`；命令为：
  ```text
  backend/.venv/Scripts/python.exe -u -m app.collect.boss_collect_loop --cdp http://127.0.0.1:9333 --user-data-dir C:\Users\SERENA~1\AppData\Local\Temp\TalentMind-BOSS-Edge-9222 --forever
  ```
- **本次首轮**：第 1 轮 `北京/Python` 于 `09:47:37 +08:00` 完成，`listed=12/details=8/new=2/skipped=10`；随后等待随机 `648.3s` 切换下一个关键词/城市。
- **循环逻辑**：本次进程使用 `rounds=0`（不设轮数上限），首轮完成后进入切换等待，不会按一轮自动结束；遇到 CDP/登录状态异常才会安全停止。
- **CDP**：`127.0.0.1:9333` 正在监听，`/json/list` 可见 BOSS 页面目标。页面是否保持人工登录/是否出现验证页仍需以 Edge 当前状态为准；采集器不处理验证码、密码、Cookie 或反爬绕过。
- **日志**：
  - `D:\Application\ClaudeCode\repository\TalentMind\data\local\logs\boss_collect_loop-restart-20260823-094457.out.log`
  - `D:\Application\ClaudeCode\repository\TalentMind\data\local\logs\boss_collect_loop-restart-20260823-094457.err.log`（当前为空）

## 2. 数据库导入核验

本次没有执行破坏性全量重导；对当前 MySQL 集成库做了实时核验。BOSS 首轮完成后，新增 2 条已经落库：

| 指标 | 当前值 |
|---|---:|
| `jd_pool` 总量 | 126,330 |
| `jd_pool.source=linkedin` | 123,849 |
| `jd_pool.source=hn` | 1,796 |
| `jd_pool.source=boss` | 685 |
| `jd_pool.status=cleaned` | 126,330 |
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

BOSS 质量核验：`source_detail` 空值 `0`、重复值 `0`，`duties` 非空 `288` 条；BOSS 685 条全部为 `cleaned`。BOSS 最新 `crawled_at` 为数据库 UTC 时间 `2026-08-23 01:47:38`，对应本地 `09:47:38 +08:00`。

交叉验证方面，数据库实时 `cross_source=1` 为 `888` 行；自动任务生成的报告当前为 `887` 行，差异是已知的 1 条历史残留标记，未执行按 `source` 的宽泛删除。

## 3. 其他采集管线

- 通用持续循环 `collect_loop.py --hours 6 --forever`：父/工作进程 PID `34120/35004` 仍在运行；最近完成第 17 轮（`2026-08-22 10:57:40 +08:00`），按 6 小时节奏等待下一轮。
- HN 岗位已进入 `jd_pool`，当前 1,796 条；GitHub/博客信号当前 680 条，覆盖 `2026-08-17` 至 `2026-08-22` 共 6 个日期。
- `talent_raw=0`，人才线索线未持续运行；拉勾、猎聘、智联仍按 P6 暂不抓取。
- `scripts/check_collect_status.ps1` 已核验：MySQL、通用采集日志和数据量正常；SYSTEM 计划任务不可由普通权限读取，但采集循环不依赖该任务。

## 4. 本快照的结论

1. BOSS 已重新启动，首轮完成后仍存活并进入随机等待，持续循环逻辑正常。
2. BOSS 首轮新增的 2 条已导入 `jd_pool`，没有发现空 `source_detail`、重复 `source_detail` 或未清洗 BOSS 数据。
3. 当前数据库可作为 M2 交接快照；完整 SQL 导出及恢复说明见 `exchange/m2/m1-database-handover-20260823.md`。