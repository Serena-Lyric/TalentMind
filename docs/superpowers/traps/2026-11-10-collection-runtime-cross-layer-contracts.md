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
