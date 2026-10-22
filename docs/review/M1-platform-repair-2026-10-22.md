# M1 分平台修复（2026-10-22）

## 第一阶段：智联

基线 `master@ce9e068`，分支 `codex/m1-platform-repair-20261022`。用户授权按平台逐步修复；只采用当前产品内容/身份规则，不执行正式 DDL、清理或高频采集。既有头像修改不纳入此阶段提交。

修复慢面板提前稳定、空列表标题与正文资格混淆、整轮缓冲造成停止丢项、数据库故障事件缺失，以及父进程到智联 worker 的目标身份传递。复用了历史 `5a2cddb` 所指问题的修复思路，并补可见/非空/active 等待、逐条保存及控制器目标绑定；没有整合 PR49 或改变 BOSS。

### 验证

- 针对性失败回归：先出现 5 项业务失败、5 项绑定失败、1 项数据库 provider 失败；独立审查追加 2 项空面板/未激活失败。修复后相关后端离线 **267 passed**。
- 范围：CN detail/identity/fetchers、browser、controller/product/history、Windows worker 生命周期、batch、既有 BOSS fetcher/loop/interruption、collect repository。显式排除 integration，父进程 socket 阻网；真实子进程测试只用合成服务或 sleep，不调用平台。
- SQLite 夹具均在 finally 关闭并删除；有对应不存在断言。没有正式库写入，正式库因端口未监听无法重新计算内容摘要。
- 独立只读复核：没有当前 controller 单页/单组合路径下的 P1 缺陷；发现的空面板 P2 已补测试并修复，2 项复核通过。固定首 TARGET_URL 不用于未开放的多轮组合。
- 当前无前端业务变动，未为本阶段运行前端构建。既有 Python/SQLite/FastAPI 弃用警告保留。

### 未完成的真实验收

本次端口23306未监听，未启动数据库、未执行字段迁移、未触发真实采集。当前后端运行进程没有自动热重载，不能把已打开页面当作新代码的实机验收。待原环境、身份字段许可与对应审核满足后，重启到经审查版本，按控制台“准备→单次启动→结果/原文核对”验证；单平台、单关键词、单城市、1页、最多2条，间隔15–30秒，遇登录/验证立即停止。

## 第二阶段：BOSS

尚未实施。将单独审查、复用既有 PR49 的普通浏览器桥接、扩展及控制台入口；不以反复CDP探测解决安全跳转，也不宣称原扩展已完成真实验收。

长期记录见[修复陷阱](../superpowers/traps/2026-10-22-zhaopin-panel-persistence-target.md)；实施计划见[分平台计划](../superpowers/plans/2026-10-22-m1-platform-repair.md)。
