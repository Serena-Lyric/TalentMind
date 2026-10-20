# TalentMind 统一产品集成实施计划

> 执行：沿用用户本轮完整任务书，普通实现不再请求确认。使用 executing-plans，前后端按冻结接口并行；最终独立审查。

**目标：** 指定工作树单入口启动，页面显式准备和单轮采集，真实状态、来源正文与 MySQL 映射可核验。

**架构：** 保留 Vue/FastAPI、原 M1 fetch/pipeline、jd_pool。任务事件/历史和私有正文存在忽略的 data/local/collection；授权本地 API 读取，不新增业务表。保留既有图谱候选与历史快照。

**约束：** 仅当前工作树，master 不动，主仓10项改动不动；不迁移、不清理真实数据；BOSS/智联各最多一关键词/城市/页、5列表/详情；人工验证停止；持续能力保留但 Gate1 前锁定。

## 接口约定（并行修改边界）

- 原 /api/collection 的 status/config/history/database-stats/recent/prepare/start/stop 保留。
- GET /platforms 返回数组：{platform,label,supported,cities:[{name,code}]}。BOSS代码与智联代码分别维护。
- prepare 返回 {access_state,can_collect,cdp,message}；cdp.platform_access[platform] 包含访问状态。准备无写库。
- status/history 计数：listed/detail_attempted/detail_obtained/complete/inserted/updated/skipped/rejected/failed；未知为 null，stop_reason 明确。保留 details 仅兼容旧调用。
- GET /results?run_id=… 返回数组 {source,job_title,source_detail,crawled_at,raw_text,duties,requirements,quality,rejection_reason,outcome,jd_pool_id}；只返回该轮实际事件，不混入旧JD。
- GET /raw/{id} 返回 jd_pool 完整原文（含相同字段），仅显式本地开发开关+回环+来源检查。
- start 浏览器阻塞亦创建有 run_id 的历史任务，记录 waiting_for_browser/error 与实际原因；接口不长时间阻塞浏览器UI。
- database-stats 增加 available/error；DB失败不以零值冒充。

## 任务与验证

- [x] 1. Git：从 origin/master 建唯一 codex/product-integration-20261020，真实 merge #40/#42/#37及依赖；逐段合并冲突。
- [x] 2. 后端：先补城市切换、访问门禁、未知统计、结果隔离/本地访问测试，观察RED；实现最小控制器/事件薄封装，定向GREEN。
- [x] 3. 前端：重构 Collection.vue 与 api/collection，配置→准备→启动→状态/结果→历史；先补关键行为测试，再运行前端测试/类型/构建。
- [x] 4. 启动：本工作区 .env/venv/依赖；start-local.ps1/stop-local.ps1，回环绑定、端口归属检查、健康与代理数据库读取、私有日志。
- [x] 5. 实验：采前目标核验、全表摘要+jd_pool可恢复原像；BOSS准备遇人工验证停止；智联一轮取得1详情但身份未核实拒绝，显式停止。八表/Neo4j/正式图未变。完整JD入库门禁未通过，不扩大试采。
- [x] 6. 图谱：历史/node-field/legacy/真实来源基本回归；保留独立既有失败并分类。
- [x] 7. 文档：资产/决策/README/陷阱、脱敏验收报告与截图；独立代码审查；精确暂存，产品提交d93941d，临时分支审查，不合并master。

## 审查重点

平台切换丢弃异平台城市；未知统计不补业务0；准备不采集；验证/游客截断不得再导航试探；停止不丢已提交结果；重启不把旧PID当当前任务；原文接口禁止远端/跨站访问；生产集成测试禁用。

## 执行账本

2026-10-20：真实合并 f7816b8、a184d60、4e28faf；#40=9f829bd、#42=fd2325f、#37=72b673a。已取得远端分支没有前端成员新增业务提交，仅有接入文档#34；不触及她的独立工作。

2026-10-21：后续只读排查→用户授权修复准备/重新检查；传当前配置与目标绑定、旧轮询世代、失败提示保留、跳转后同tab检查已落地。最终前端128通过；后端1373通过/2既有B3失败。BOSS人工验证停；智联run zhaopin-98c0d0f1f91c4dac9c675f06338d426d 列表5/尝试1/取得1/拒绝1/完整0，页面stop→历史成功。SQL行级0/0/0，八表/Neo4j/正式图/主仓10项未变，原像仅私有。后续完整JD身份绑定仍待验证。
