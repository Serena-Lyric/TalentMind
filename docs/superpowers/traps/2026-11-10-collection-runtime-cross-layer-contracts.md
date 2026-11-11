# 采集运行时跨层契约：默认配置、页游标、检查点与 writer lease

## 症状

PR #80 首轮独立复审发现六类可确定的生产控制流问题：

- 前端发送空 `{}` 启动时，后端把默认关键词/城市清空，启动必然失败。
- BOSS 纯函数已能记录稳定身份，但真实 `run_fetch` 丢弃详情 URL，写库仍是 `unknown/NULL`。
- worker 显示第 2 页，执行器仍固定 `pages=1`，实际重复第 1 页。
- scheduler 每次 start 新建状态，覆盖已提交游标、`next_run_at` 和最后身份；列表/详情尝试事件还会被冒充保存身份。
- 旧共享频率账本门禁只在新 scheduler，旧单轮/批次/bridge 仍可从空新账本绕过旧 cooldown/unfinished。
- 新 runtime 与旧可写入口没有同平台跨进程互斥，可能并发导航/重复写库。

## 根因

各层分别“看起来正确”，但契约没有沿真实调用链贯通：前端→ASGI→config、detail→normalize→SQLite、worker→engine→URL、scheduler→state→restart、legacy ledger→bottom reservation、runtime/legacy entrypoints→writer ownership。测试多数停在纯函数或 fake 边界，未覆盖实际生产分派。

## 修复

- `config_from_payload` 缺省字段使用默认值，部分城市覆写合并默认平台；显式空值仍拒绝；慢于默认值的合法间隔允许。
- BOSS `run_fetch` 将已验证详情对象单独传给 `normalize_boss_job`。
- BOSS/智联入口新增 `start_page`，`CdpEngine` 传递 worker 指定页。
- scheduler 保留既有游标/`next_run_at`/身份/统计；blocked/needs_login/failed 不自动清除；`last_saved_identity` 只接受 persisted inserted/updated/skipped。
- `frequency.assert_legacy_migrated` 下沉到真实预约底层，旧单轮、批次、bridge 创建均提前 fail closed。
- 新增 `runtime/lease.py` 每平台 writer lock；runtime、control/batch、bridge 统一占用，使用 PID+创建时间识别 stale lock。
- 回归覆盖 ASGI 默认请求、真实 `run_fetch`+合成 CDP+隔离 SQLite、指定页 URL、scheduler 重启、三入口旧账本门禁、runtime↔旧入口双向抢占。

## 教训

不要让“纯函数通过”替代生产分派证据。跨层参数必须在最靠近真实副作用的位置验证；检查点、保存身份和 writer ownership 都必须有确认回执或可核验 owner，不能用尝试事件或进程内标志冒充。测试必须隔离真实 `data/local`，否则本机旧账本会让 CI 与本地结果不一致。


## 第二轮补充（2026-11-10）

- writer lock 不能先创建空文件再写 JSON；改为原子目录锁 + owner 文件原子替换，未发布/损坏 owner fail closed。
- lease 必须从启动者重绑定到实际 worker 根 PID；终止必须由 worker_process/job 或可核验进程句柄确认，失败时保留锁和待处理状态。
- stop 不是人工恢复确认：blocked/needs_login/failed 必须保持门禁，不能通过 Stop→Start 重访。
- 自定义关键词/城市计划必须随 scheduler 保存；空 payload 重启复用原计划，配置改变时要求显式 reset_checkpoint，避免旧 index 解释新计划。


## 第三轮补充（2026-11-11）

### 症状

- 两个进程同时读到同一个 dead writer owner 后，后来的 `os.replace` 会移走先行者刚创建的新 lease；相同读后改名模式也出现在 `release` / `release_if_dead`。
- Windows 接管只保存包装进程 PID；包装进程退出不代表 Job Object 中的 Python child 已退出。
- 只要一个平台保留人工处理状态，`start` 就拒绝启动其他平台；旧 checkpoint 在 scheduler 配置缺失或损坏时还会按默认计划解释。

### 修复

- 对每个平台的 acquire、rebind、release 和 stale 回收统一使用稳定 sidecar OS 锁，并在锁内复核 owner token；同一进程的线程也串行化。Windows worker 使用可按名字重新打开的 Job Object，名称同时保存在 scheduler 与 lease owner 中；接管后按 Job Object 终止并等待整棵树。没有可验证句柄时保留 lease 并 fail closed。
- `start` 为 blocked/needs_login/failed 平台保留 STOP 和状态，只启动其余可运行平台；受限 worker 若仍在运行，只发 STOP，不为其新建 worker。
- 有 cursor、已保存身份或统计而找不到可信 scheduler config 时，`start` 和 `resume` fail closed；须先通过 `start(reset_checkpoint=true)` 显式复位，再恢复，不再静默回落默认计划。
- 回归使用临时目录、隔离 SQLite 和合成 wrapper/child，没有连接真实招聘站或正式数据库。

### 教训

所有基于路径的 lock 代次变更都必须在同一跨进程临界区内完成“检查 owner→改名/删除”，并验证 owner token。Windows PID 只标识一个进程；需要停止 worker 时，应持有可验证的 Job Object 句柄，等待成员进程全部退出后才释放写入权。多平台状态分别准入，配置与 checkpoint 必须有可证明的绑定。

## 第四轮补充（2026-11-11）

### 症状

三站都处于 `blocked` / `needs_login` / `failed`，且旧游标仍有进度，但 `scheduler.json` 缺计划或损坏时，`start(reset_checkpoint=true)` 原先先因没有可运行平台而拒绝；逐站 `resume` 又因计划不可信而拒绝。合法的本地恢复入口因此不可达。

### 根因

计划复位复用了正常启动路径，放在“必须至少有一个可运行平台”的检查之后。全站都需要人工处理时，尚未执行游标复位就被启动准入拦截。

### 修复

把显式复位分支移到正常 worker 启动门禁之前。确认没有运行中的 worker/state，并取得全部平台 writer lease 后，只写本地计划、状态 SQLite、scheduler 文件和受限站 STOP 标记：可信旧计划可沿用，缺失/损坏时写入默认计划；复位关键词/城市/页游标及关联运行计数、最近保存身份和运行时间记录。原 `status`、`stop_reason` 与 STOP 标志完整保留，不检查业务数据库就绪或频率、不 spawn worker，也不进行浏览器动作。前端仅在三站都受限时显示显式确认入口；之后仍由原单站人工恢复流程清除对应门禁。

回归通过真实 ASGI scheduler API + 临时 SQLite 状态覆盖旧格式/损坏计划、全站受限复位后 resume 可达、未显式复位仍 fail closed、活 lease 阻止复位；站点 worker spawn 被断言为零。

### 教训

运维复位是本地状态变更，应与启动 worker 的准入路径分开。组合门禁既要保留阻止自动恢复，也要给显式、可审计的本地修复留入口；成功复位不能顺手改变人工恢复状态或启动外部动作。

## 第五轮补充（2026-11-11）

### 症状

HTTP body 的 `reset_checkpoint` 接受任意 JSON 值时，`bool(value)` 会把字符串 `"false"`、`"0"` 及其他 truthy 值转换成真；在停止状态下，它们会触发清除游标、保存身份和统计的本地复位。

### 根因

接口将 body 声明为 `dict[str, Any]`，调度器又以通用 Python 真值转换代替 JSON 类型检查，因而把“字段存在且为真值”误当成“调用方显式发送布尔 true”。

### 修复

在 `scheduler.start` 读取任何运行态前，要求 reset 字段为原生 `bool`。缺省视为 `false` 并执行普通启动；原生 `false` 不复位；字符串、数字、数组、对象和 `null` 直接拒绝，不触碰 SQLite 状态、scheduler 文件或 STOP 标记。ASGI/临时 SQLite 测试同时覆盖可信与损坏计划下的无效参数、正常 false 路径及 true 复位。

### 教训

破坏性控制字段必须按 wire type 校验，不能用语言层真值转换推断操作者意图；无效输入应在任何状态写入之前失败。
