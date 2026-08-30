# M1 采集工作交接（2026-08-25）

> 面向下一位 Agent 的可执行交接。当前任务：报告所有采集管线、恢复猎聘、留下可复核的运行入口。

## 1. 当前结论

- 通用信号/HN 循环、BOSS、智联、猎聘均已核验为存活。
- 猎聘已从“因详情页人工登录/验证而停止”状态恢复；恢复首轮已完成：`listed=12`、`details=8`、`new=8`、`skipped=4`，循环正在等待下一组关键词。
- 没有关闭任何用户页面；`about:blank` 不作为采集目标，也没有发现当前 `about:blank` 目标。
- 采集边界保持不变：只读用户已登录页面渲染出的可见 DOM；不读 Cookie/密码/Token/本地存储，不拦截网络请求，不调用官方或私有接口，不绕过验证码、登录或反爬。

## 2. 运行中的管线

| 管线 | 进程（父/工作） | 当前参数/节奏 | 日志 | 状态 |
|---|---|---|---|---|
| 通用 6 小时 | `34120/35004` | `python -m app.collect.collect_loop --hours 6 --forever` | `data/local/logs/collect_loop.out.log`、`.err.log` | 存活；最近第 32 轮后等待 6 小时 |
| BOSS | `20560/23120` | `python -u -m app.collect.boss_collect_loop --cdp http://127.0.0.1:9333 --user-data-dir C:\Users\SERENA~1\AppData\Local\Temp\TalentMind-BOSS-Edge-9222 --forever` | `data/local/logs/boss_collect_loop-codex-20260823-191237.out.log`、`.err.log` | 存活；第 288 轮完成后等待 |
| 智联 | `21840/9724` | 北京 `530`；7 个关键词；每轮 1 页、最多 12 条/8 条详情；页间 18–32s；切换 420–780s | `data/local/logs/zhaopin_collect_loop-codex-20260823-201701.out.log`、`.err.log` | 存活；第 249 轮完成后等待 |
| 猎聘 | 启动器 `14840`；父/工作 `11064/12220` | 全国 `410`；同 7 个关键词；使用自定义可见搜索 URL 模板；页间 18–32s；切换 420–780s | `data/local/logs/liepin_collect_loop-codex-recovery-20260826-071553.out.log`、`.err.log` | 存活；第 1 轮完成后等待 |

> 进程父/工作 PID 是当前核验值，不应写死到未来运行。下一位 Agent 接手时必须重新用 `Get-CimInstance Win32_Process` 按命令行定位，不按 PID 猜测。

## 3. 数据库快照（以数据库时间为准）

最近一次 `SELECT NOW()`：`2026-08-25 23:21:47`。

| 来源/指标 | 数量 | 质量核验 |
|---|---:|---|
| `jd_pool` 总量 | 127709 | 全部 `cleaned` |
| LinkedIn | 123849 | `source_detail` 全局空值 0 |
| HN | 1794 | 全部 `cleaned` |
| BOSS | 967 | 全部 `cleaned`；中文平台 source_detail 空值 0 |
| 猎聘 | 477 | 全部 `cleaned`；空值 0；同源重复 source_detail 0 |
| 智联 | 622 | 全部 `cleaned`；空值 0；同源重复 source_detail 0 |
| `cross_source=1` | 886 | 数据库实时值 |
| `signal` | 1087 | GitHub 264；Blog 823 |
| `skill_dict` | 285 | — |
| `job_definition` / `job_skill` | 22 / 22 | — |
| `job_change_log` / `resume` / `talent_raw` | 0 / 0 / 0 | 当前为空态 |

最近时间：`jd_pool.crawled_at=2026-08-25 23:19:54`；`signal.captured_at=2026-08-25 21:29:31`。

## 4. 猎聘恢复记录与复现

### 停止原因

旧恢复循环最后在本机日志 `2026-08-26 03:05:50` 停止，原因是详情页被判断为需要人工登录或验证：

```text
liepin CDP/登录状态异常，停止循环: liepin 详情页需要人工登录或处理验证: https://www.liepin.com/a/77338733.shtml
```

### 本次恢复

使用临时启动器：

```text
C:\Users\SERENA~1\AppData\Local\Temp\TalentMind-restart-liepin.ps1
```

本次启动器 PID：`14840`；循环父/工作 PID：`11064/12220`。启动参数由启动器传入：

```text
python -u -m app.collect.cn_collect_loop \
  --platform liepin \
  --keywords Python,Java,数据工程师,AI工程师,产品经理,后端工程师,机器学习 \
  --cities 全国=410 \
  --search-url-template "https://www.liepin.com/zhaopin/?city={city}&dq={city}&pubTime=&currentPage={page}&pageSize=40&key={keyword}&suggestTag=&workYearCode=0&compId=&compName=&compTag=&industry=&salaryCode=&jobKind=&compScale=&compKind=&compStage=&eduLevel=&otherCity=&scene=input&sfrom=search_job_pc" \
  --cdp http://127.0.0.1:9333 \
  --pages 1 --detail-limit 8 --max-jobs 12 \
  --page-delay-min 18 --page-delay-max 32 \
  --settle-min 6 --settle-max 10 \
  --switch-interval-min 420 --switch-interval-max 780 --forever
```

恢复首轮本机日志 `2026-08-26 07:15:54–07:19:53`：40 条列表 DOM、激活/读取 8 条详情，入库新增 8 条；错误日志为空。

### 再次恢复步骤

1. 先确认 `127.0.0.1:9333` 监听：`Get-NetTCPConnection -LocalPort 9333`。
2. 用 `Invoke-RestMethod http://127.0.0.1:9333/json/list` 按 URL 中的 `liepin.com` 定位页面；禁止按固定 tab index。
3. 如果页面是登录/验证码/安全验证，停止并让用户人工处理；不要输入密码、读取 Cookie 或绕过验证。
4. 用 `Get-CimInstance Win32_Process` 查找命令行包含 `app.collect.cn_collect_loop` 和 `--platform liepin` 的现有进程；仅在不存在时启动上述启动器。
5. 启动后等待日志出现 `第 1 轮完成` 且包含 `listed/details/new/skipped`，再向用户报告。
6. 如果进程已存在但日志停止增长，先检查错误日志和 CDP 页面，不要重复启动造成双重采集。

## 5. CDP / 页面操作边界

- CDP：`127.0.0.1:9333`，Edge 浏览器 PID 当前为 `24300`。
- 页面身份（本次快照）：智联 `706FD38EF6B9720ADB48B6BB95C5F5AD`；BOSS `9AE3D9E9E03C896EC82D661B4848FC9F`；猎聘 `8F893A2C7E8738581A05F4D1A2B77A87`。页面 ID 会变化，接手时按 URL/域名重新发现。
- 用户页面保护：不关闭、不复用、不导航 `about:blank`；不按标签页序号选择；不触碰与目标域名无关的页面。采集器可以为已授权恢复任务在目标平台标签页内导航到搜索页/详情页，但不创建新标签页。
- 采集器只通过 `CdpClient` 读取/操作渲染页面 DOM；详情卡片激活失败、登录状态异常或验证出现时应安全停止。

## 6. 监控命令

```powershell
# 进程
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'app\.collect' } | Select-Object ProcessId,ParentProcessId,CommandLine

# CDP
Get-NetTCPConnection -LocalPort 9333
Invoke-RestMethod http://127.0.0.1:9333/json/list

# 数据库（不要执行宽泛 DELETE）
docker exec talentmind-mysql-1 mysql -uroot -ptalentmind -D talentmind

# 已有状态脚本
powershell -ExecutionPolicy Bypass -File scripts\check_collect_status.ps1
```


## 7. 禁止事项与风险

- 禁止 `taskkill`/文本解析 `netstat`；Windows 进程、端口按项目约定使用 `Get-Process`、`Get-CimInstance`、`Get-NetTCPConnection`。
- 禁止按 `source` 宽泛删除测试或生产数据；测试行必须按唯一夹具特征在 `finally` 清理。
- 禁止提交 `backend/.env`、真实简历、`input/` 大型/敏感资产；禁止 `git add -A`。
- 不要为“修复”登录验证而修改绕过逻辑；登录/验证码必须交给用户。
- 本次没有修改 DDL，没有执行全量重导，没有停止/重启 BOSS、智联或通用循环。

## 8. 接手验收清单

- [ ] 先读根目录 `AGENT_START_HERE.md` 及其路线文件，再读本交接文档。
- [ ] 用进程命令行确认四条管线各有且仅有一组有效父/工作进程。
- [ ] 确认 CDP 9333 正在监听，并按 URL 找到智联、BOSS、猎聘页面。
- [ ] 检查四组日志最近 50 行，确认没有登录/验证异常或错误日志增长。
- [ ] 查询数据库并记录 `NOW()`、各 source、cleaned、source_detail 空值、signal、cross_source。
- [ ] 若猎聘再次停止，只在用户完成人工登录/验证后恢复；恢复后必须等待一轮 `listed/details/new/skipped`。
- [ ] 更新 `docs/superpowers/资产与状态.md` 和 `exchange/m1/collection-status-20260823.md`，保留旧快照，不覆盖历史事实。
- [ ] 最终报告明确区分数据库时间与本机进程日志时间。

## 9. 文件索引

- 采集入口：`backend/app/collect/fetch_cn_jobs.py`、`backend/app/collect/cn_collect_loop.py`
- 平台适配：`backend/app/collect/fetchers/job_sites.py`
- CDP：`backend/app/collect/fetchers/cdp.py`
- 通用循环：`backend/app/collect/collect_loop.py`
- BOSS：`backend/app/collect/fetch_boss_jobs.py`、`backend/app/collect/boss_collect_loop.py`
- 测试：`backend/tests/test_cn_job_fetchers.py`、`backend/tests/test_boss_fetcher.py`、`backend/tests/test_cdp.py`
- 状态快照：`exchange/m1/collection-status-20260823.md`
- 本交接：`exchange/m1/collection-handover-20260825.md`
- 资产索引：`docs/superpowers/资产与状态.md`
