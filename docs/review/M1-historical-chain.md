# M1 历史控制链路复用与 Gate 1 状态

2026-10-20，Asia/Singapore。基线 `cf187fe`，原工作树 `m1-m2-quality-replay`、分支及 Draft #40。先只读对照，随后最小修复。用户在当前会话确认猎聘验证**尚未处理，先完成离线修复**，因此第三阶段真实采集未执行；没有通过改身份、旧URL、请求模式或其他来源重新探测。

## 1. 历史启动入口及证据边界

- 早期长期运行主要由 PowerShell 后台启动器调用 `python -m app.collect.boss_collect_loop` 或 `cn_collect_loop --platform ...`；循环轮换关键词/城市，逐轮调用同一个平台 `run_fetch()`。`exchange/m1/collection-handover-20260825.md` 记录过猎聘恢复启动器及参数；不是另一套采集核心。
- 后期正式控制台通过 `/collection/start` → `control.start_task()` → 原平台循环子进程。mode once 映射 `--once`，limited 映射 rounds，continuous 映射 forever；watcher读取日志、保存任务状态和history。主仓本地历史控制状态有4条记录，当前保存的是2026-09-05的BOSS单轮完成、零新增；这不证明完整详情成功。
- `scripts/collect_daily.ps1` 的计划任务与 `collect_loop` 负责 fetch_all 的信号/HN等，是另一条调度入口，不能当作BOSS/CN控制台。本轮没有恢复它们，`PAUSE_COLLECT`保留。
- 只读解析现存日志：BOSS `boss_collect_loop-codex-20260823-191237.out.log` 有624条轮完成记录，首轮 listed/details/new/skipped=12/8/3/9；猎聘 `liepin_collect_loop-codex-recovery-20260826-071553.out.log` 有296条，首轮12/8/8/4；智联 `zhaopin_collect_loop-codex-20260823-201701.out.log` 有544条，首轮12/8/5/3。文件摘要和解析结果保留在本地私有证据，不上传原日志。
- 历史日志确实证明循环曾多轮运行、曾报告新增，但 `details` 是当时的尝试口径，历史listed与skipped也不必覆盖无效过滤项。不能把这些数字追认为cf187fe规则下的“完整且可回源JD”。

## 2. 历史链路与第三轮脚本差异表

| 方面 | 历史入口 | 第三轮 run_live.py | 结论 |
|---|---|---|---|
| 启动/管理 | 后台启动器→平台循环；后期由control管理子进程 | 直接调用正式CN run_fetch，脚本自己保存审计 | 任务管理确实未验收；不是另一种采集核心 |
| 浏览器身份 | 早期人工启动独立Edge，9333/Temp profile；后期控制台profile配置 | 复用54ae04f的当前工作树独立profile、动态2245 | 历史profile有差异；第三轮未新建身份。现不迁移Cookie或重开旧profile避限 |
| 目标页选择 | 老CDP按站点查页，缺失时有错误fallback；新版本严格域名/目标绑定 | 同一新版browser/CdpClient/target_id | 严格绑定是保留的修复，不能恢复误连其他平台 |
| 搜索 | 循环每轮仍调用fetch中的navigate；不是只采用户当前页 | 同run_fetch中同样navigate一次新搜索 | 换成循环不等于没有新搜索，不能保证解除验证 |
| 搜索配置 | 猎聘曾显式使用city/dq等自定义模板、全国410、7关键词 | 默认dqs模板、北京010、Python、1页 | 配置差异有据；没有受控因果或站点内部证据证明它造成验证，不能在受限会话改模板试绕过 |
| 节奏 | BOSS通常15–30秒页间/5–10秒稳定，轮间6–12分钟；猎聘恢复曾18–32秒/6–10秒/420–780秒 | delay15、settle6，单次不进入轮间等待 | 真实节奏不同，但仍在既有量级；第三轮阻断在搜索阶段，不应归因于从未执行的详情采集节奏 |
| 详情及质量 | 旧版允许列表/空详情和DOM面板弱身份；现在循环已调用cf187fe修复函数 | 同cf187fe函数和严格规则 | 接回历史循环不能恢复旧质量缺陷，也不能用旧新增数证明完整率 |
| 配置来源 | 正式进程从环境或backend/.env解析Settings，旧controller只复制os.environ | 脚本显式只在本进程加载主仓现有.env | 当父进程仅通过Settings读.env而未导出环境时，子进程配置可能丢失；已修复传播，不猜主仓路径 |
| 日志和状态 | control watcher解析、history归档 | 独立JSON/快照，没有control run_id、watcher或正式历史 | 真实差异和验收缺口；第三轮不能证明正式控制台正常 |
| 额外审计 | 旧模块日志/DB | 本机DB写白名单、on_event和详情原文读回 | on_event和额外详情读取在第三轮搜索阻断前未执行，不能据此认定是触发因素 |

确认的接口缺口见下一节；“恢复历史URL/延迟/循环即可解除网站验证”仍是猜测，本轮不据此访问。

## 3. 最小修复及接入结果

1. `control` 保存并向CN子进程转发已有 `search_url_template`，保留默认None、现有用户配置和CLI能力；没有自动切换当前URL或执行历史模板。此前CLI支持、controller缺少传递，是既有集成缺口，不声称由#40新增造成。
2. 子进程接收父进程**已解析的Settings**，解决仅.env加载而os.environ未导出、工作树无.env时的父子目标不一致；不复制配置文件、不查找/修改主仓.env、不输出连接秘密。父进程自身配置无效仍须先处理，不能猜默认库。
3. worker固定 `PYTHONIOENCODING=utf-8/PYTHONUTF8=1`，匹配watcher UTF-8读取。普通Windows环境下曾复现“子进程成功但中文完成标记/质量计数未解析”；私有runner本身已设UTF-8，最初掩盖了此问题。现有无父进程编码变量的回归和普通pytest均通过。
4. cf187fe的尝试/取得/完整/INSERT/UPDATE/拒绝/失败/未尝试计数及stop_reason进入任务和历史；payload保留在log_summary。`quality_metrics_available`区分新完整口径与老BOSS/历史不可知计数，新任务未取得质量统计时为None而非伪造成功/零。明确停止原因置error，不被watcher的exit0覆盖；旧日志字段保持兼容。
5. 原两平台循环的单轮业务异常现在返回非0，避免 `--once` 异常后仍被控制台记completed。明确CdpError（含login/verification/page_error）仍立即停止，不进入低频重试；未改变其他长期轮询策略，更未恢复continuous。
6. CDP连接/发送/接收的WebSocket关闭及超时统一为兼容CdpError的 `CdpConnectionError`，整个响应等待有上限。BOSS原详情分支遇传输中断即抛出供循环停止，不继续后续详情；之前已提交的good记录保留。普通单条页面脚本故障的既有有限容错未恢复成传输重试。

54ae04f浏览器自启动、正面访问证据、独立profile/回环归属和严格目标选择均保留；cf187fe的完整正文/换行/身份/游客限制规则均保留。fetch_cn_jobs的业务质量代码没有因本轮回退或放松。

前端无需覆盖页面源码；API新增可选配置 `search_url_template` 和质量计数/stop_reason/quality_metrics_available。旧 `details/new/skipped` 口径兼容，新口径不能从旧details反推。现有控制台仍只在显式start时启动任务，prepare永不启动采集。

## 4. 离线原入口验收

- 新文件15项回归覆盖配置转发、父子Settings/UTF-8、当前/历史质量统计、两循环三种访问门禁停止、单轮业务异常、传输断线，以及真实控制器子进程生命周期。
- 关键集成用例实际调用 `control.start_task(mode=once)`，使用真实 `Popen -m app.collect.cn_collect_loop --once`、原loop、原run_fetch、原pipeline/SQL和watcher/history。仅浏览器/服务边界为合成实现，写隔离临时SQLite：一条完整合成JD、详情尝试1/完整1/INSERT1，原文与职责边界核对通过，history为completed且保留质量计数。它证明**原控制链路接入**，不是真实招聘来源或MySQL验收。
- 子进程测试自带仓内生成的阻网/禁原生helper hook，不依赖未入库sitecustomize；普通pytest的新文件15项通过。写入的临时SQLite在finally精确关闭/删除并断言不存在，专属测试目录也已清除；没有真实数据库夹具。
- BOSS新增实际run_fetch回归：第一条详情提交、第二条传输中断后停止，第三条不尝试，已提交首条仍可查询。原14项BOSS中断/补全用例保持通过。
- 最终M1定向 **263 passed**，父子2个Python进程服务/外网/DNS尝试0、专属目录删除成功。完整非集成 **1297 passed / 10 failed / 2 skipped / 23 deselected**，89个Python进程连接/DNS尝试0，内部socketpair12，专属目录清理成功。残留仍是2项已有B3摘要和8项缺少可选图谱依赖，名称见[前轮报告](M1-browser-runtime.md#测试与独立审查)，未改M2/M3/B3修绿。
- 独立只读审查提出“测试依赖私有hook”和“BOSS吞传输断线”两项Important，均修复；复查无遗留Critical/Important。全量/定向测试没有访问真实平台或生产库。

## 5. 真实状态与是否恢复日常运行

在用户回复前，只读检查原会话，没有navigate/search/create tab：当前独立Edge可达，BOSS主页有认证标记但没有可采岗位正文（page_error/no_access_evidence）；智联公开列表可见但游客详情受限；猎聘目标页缺失。缺失不等于上轮安全验证已解除。

用户随后明确“尚未处理，先完成离线修复”。依此本轮不调用真实 `control.start_task`/平台loop，不重开猎聘、不新建profile/身份、不恢复旧URL试探。**没有本轮真实任务run_id、候选、详情或INSERT/UPDATE结果；不能将离线合成任务当真实系统成功，也不能说重新跑原循环后仍触发验证，因为没有发出新请求。**

本轮没有真实MySQL连接、采前新备份或真实写SQL；第三轮2988行原像仍是历史证据，不能自动当作下一次采前实时状态。主仓10项未提交文件逐字节摘要保持，主仓配置/状态/历史日志只读；未操作Docker、数据库、Neo4j、正式图谱或B3，未启动M2/M3。

**不能恢复日常自动采集。** 当前可以确认原控制器/单轮循环的离线闭环与门禁停止语义；日常准入仍缺：

1. 用户通过正常方式解除站点限制，在原会话确认一个具有完整详情、稳定身份的可访问来源。智联DOM面板绑定缺口和游客截断未解决，不降低cf187fe门槛。
2. 正式父进程解析好配置，核实实际目标localhost:23306/talentmind、无并发写入并保存新的全字段原像；旧备份不替代新核查。
3. 经已有start(mode once)或平台--once完成一个平台/关键词/城市/页、≤5候选/≤5详情的真实验收，逐条核对原文/身份/清洗/去重/数据库及下游不变，再由负责人审查。
4. Gate 1通过后，日常调度、continuous和暂停开关是否恢复仍需单独确认，不能由本轮离线结果自动放行。未证明跨服务重启后的进程恢复/跨工作树并发互斥；本轮未重构这些既有能力。

## 6. 证据及回退

代码基线cf187fe；本轮源码/测试/报告在原#40追加。私有目录 `data/local/m1-historical-chain-20261020/` 保留历史文件摘要/脱敏解析、当前访问状态、用户分支选择、RED/GREEN/普通pytest/阻网日志及主仓文件摘要；不提交配置、原文或原日志。

本轮无业务写入，无需数据库回退。源码仅反向提交本轮历史链路修复即可恢复cf187fe，不回退54ae04f/cf187fe的浏览器与质量能力；不删除profile/历史日志/主仓改动，不启停原服务或清理数据。下一轮继续原对话、工作树和#40，真实采集待访问条件正常后再确认执行。
