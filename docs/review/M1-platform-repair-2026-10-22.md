# M1 分平台修复（2026-10-22）

## 第一阶段：智联

基线 `master@ce9e068`，分支 `codex/m1-platform-repair-20261022`。用户授权按平台逐步修复；只采用当前产品内容/身份规则，不执行正式 DDL、清理或高频采集。既有头像修改不纳入此阶段提交。

交付：[Draft PR #52](https://github.com/Serena-Lyric/TalentMind/pull/52)，面向master，未启用自动合并。智联提交`2f95bc3`，BOSS提交`2cf7702`；两阶段代码及独立复核证据在本报告归档，真实验收仍未完成，Codex自检不替代ChatGPT的GitHub审查。

修复慢面板提前稳定、空列表标题与正文资格混淆、整轮缓冲造成停止丢项、数据库故障事件缺失，以及父进程到智联 worker 的目标身份传递。复用了历史 `5a2cddb` 所指问题的修复思路，并补可见/非空/active 等待、逐条保存及控制器目标绑定；没有整合 PR49 或改变 BOSS。

### 验证

- 针对性失败回归：先出现 5 项业务失败、5 项绑定失败、1 项数据库 provider 失败；独立审查追加 2 项空面板/未激活失败。修复后相关后端离线 **267 passed**。
- 范围：CN detail/identity/fetchers、browser、controller/product/history、Windows worker 生命周期、batch、既有 BOSS fetcher/loop/interruption、collect repository。显式排除 integration，父进程 socket 阻网；真实子进程测试只用合成服务或 sleep，不调用平台。
- SQLite 夹具均在 finally 关闭并删除；有对应不存在断言。没有正式库写入，正式库因端口未监听无法重新计算内容摘要。
- 独立只读复核：没有当前 controller 单页/单组合路径下的 P1 缺陷；发现的空面板 P2 已补测试并修复，2 项复核通过。固定首 TARGET_URL 不用于未开放的多轮组合。
- 当前无前端业务变动，未为本阶段运行前端构建。既有 Python/SQLite/FastAPI 弃用警告保留。

### 未完成的真实验收

初查端口23306未监听；收尾时环境已恢复，本轮未执行启动数据库操作。按明确目标localhost:23306/talentmind执行只读事务，确认jd_pool=2988、identity_status/content_eligible/identity_evidence三列仍不存在；事务rollback、连接关闭。未执行字段迁移、未触发真实采集。

当前后端运行进程没有自动热重载。Agent尝试在核实无活动任务后重启本地后端，但整个命令在执行前被自动审批以`blocked by policy`拒绝，未提供更具体理由，停止/启动均未执行。不能把已打开页面当作新代码的实机验收。待用户重启经审查版本、身份字段许可与对应审核满足后，按控制台“准备→单次启动→结果/原文核对”验证；单平台、单关键词、单城市、1页、最多2条，间隔15–30秒，遇登录/验证立即停止。

## 第二阶段：BOSS

已复用既有PR49桥接、扩展、控制台及回环代理兼容（来源8de1e85/5ac2521/0fa3ed3/386b109/0dab513，原作者舒梦绘），未合并PR49、未改写原分支。

- 后台单轮/批次/桥接互斥，任务重启状态保留；创建会话不查询数据库或启动浏览器。
- 列表绑定任务关键词/城市/第一页；详情只能来自本轮列表，不能先采任意详情后自证标题。
- 旧schema不静默丢身份；数据库失败和验证阻断均结束会话。扩展的真实消息链已能报告blocked事件；无文字可见验证组件阻断，正常滚动不误标为截断。
- 配对信息可显式刷新，包含令牌的操作说明默认折叠；用户可以从BOSS单轮面板转入普通浏览器路径。扩展无后台导航、轮询、重试、Cookie权限或通配网站权限。

### 第二阶段验证与限制

- 最终相关后端 **312 passed**，前端完整 **177 passed**，vue-tsc/Vite构建通过。保留既有Python/SQLite/FastAPI弃用提示及Vite大chunk/导入提示；没有运行后端全量或integration。
- 原桥接28项基线通过后，新增范围、互斥、schema保存、提取和停止链路的失败回归；独立复核发现的三项P1逐项RED→GREEN，再次只读复核通过。
- 真实ASGI控制API、合成BOSS页面、隔离SQLite完成配对、2条上限会话创建、列表、1条详情保存、验证停止及后续拒绝。阻断外部/数据库网络连接；Windows asyncio自己的socketpair IPC为唯一例外。测试SQLite在finally关闭/删除并断言不存在，会话文件清理后计数为0。
- 未装载用户浏览器扩展、未登录/注销、未向BOSS或智联发起采集，不宣称平台真实入库通过。原库收尾只读2988行且三身份列缺失；实际平台烟测需用户手动装载扩展、人工打开页面，并另行满足迁移门禁。

长期边界及陷阱见[BOSS桥接记录](../superpowers/traps/2026-10-22-boss-bridge-scope-and-stop.md)。

长期记录见[修复陷阱](../superpowers/traps/2026-10-22-zhaopin-panel-persistence-target.md)；实施计划见[分平台计划](../superpowers/plans/2026-10-22-m1-platform-repair.md)。
