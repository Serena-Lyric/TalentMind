# 采集状态快照（2026-08-22）

> 核验时间：2026-08-22 11:25:46（Asia/Singapore，进程/日志/数据库快照）
> 目的：覆盖旧交接文档中的“BOSS 未运行”和旧数量，作为当前运行事实；历史批次仍保留在专项交接文件中。本文件是时间点快照，不是实时 API。

## 一、数据库现状

| 指标 | 当前值 |
|---|---:|
| `jd_pool` 总量 | 126,266 |
| `jd_pool.status=cleaned` | 126,266 |
| `source=linkedin` | 123,849 |
| `source=hn` | 1,796 |
| `source=boss` | 621 |
| BOSS `status=cleaned` | 621 |
| BOSS `source_detail` 空值 | 0 |
| BOSS `source_detail` 重复数 | 0 |
| BOSS `duties` 非空 | 273 |
| BOSS `MAX(crawled_at)`（数据库原值） | 2026-08-22 03:25:20 |
| `signal` 总量 | 610 |
| `signal.source=github` / `blog` | 150 / 460 |
| signal 时间序列天数 | 6 |
| `signal.MAX(captured_at)`（数据库原值） | 2026-08-22 02:55:32 |
| `talent_raw` | 0 |
| `cross_source=1` | 888 |

交叉验证报告当前为 887 行；数据库仍有 1 条历史残留标记，未进行宽泛删除。报告见 `exchange/m1/cross_validate_report.md`。

## 二、BOSS 低速循环

- 进程：启动器 PID `33828`，采集工作进程 PID `26124`；父子进程属于同一 BOSS 任务，不是两份独立采集任务。
- 启动时间：2026-08-21 11:04:38（+08:00）。
- 命令：`python -m app.collect.boss_collect_loop --cdp http://127.0.0.1:9333 --user-data-dir C:\Users\SERENA~1\AppData\Local\Temp\TalentMind-BOSS-Edge-9222 --forever`
- 截至核验已完成第 116 轮；累计 `listed=1392`、`details=928`、`new=133`、`skipped=1259`。
- 第 116 轮于 11:25:20 完成：`listed=12`、`details=8`、`new=1`、`skipped=11`；随后等待 499.3 秒切换下一关键词/城市。
- 数据库 BOSS 总量由此前 488 条增至 621 条，增加 133 条，与循环日志累计 `new=133` 一致。
- 日志：`data/local/logs/boss_collect_loop-live-20260821.out.log`；错误日志当前为空。
- BOSS 使用独立 Edge + CDP `127.0.0.1:9333`，仅读取人工登录后页面可见内容，不处理账号、密码、验证码、Cookie，也不绕过反爬。

## 三、其他采集管线

- 通用循环：父进程 PID `34120`、工作进程 PID `35004`，命令为 `python -m app.collect.collect_loop --hours 6 --forever`；第 17 轮于 2026-08-22 10:57:40 完成，随后等待 6 小时。
- 通用循环最新日志记录：GitHub/博客 signal 追加 25 条、HN 处理 240 条，并重算交叉验证报告。
- `talent_raw` 当前为 0，人才线索管线未持续运行。
- 拉勾、猎聘、智联仍按 P6 暂不采集。

## 四、当前判断

BOSS 与通用采集进程都在运行，BOSS 循环已经从第 1 轮推进到第 116 轮，不存在“完成一轮后停止”的现象。低速循环的 6–12 分钟切换等待会造成日志静默，但不代表进程退出。
