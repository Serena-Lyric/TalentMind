# M1 多关键词×多城市批量任务实施计划

> 用户已确认交互范围并授权实现、完成后推送同一分支；不启动真实批量采集。执行writing-plans/executing-plans，按固定接口并行后端/前端，独立复审。

**目标：** 单平台多关键词、多城市生成笛卡尔组合，可创建未启动计划、显式开始、统一停止，查看逐项状态、原因、单项原文/日志与结果。

**架构：** 新batch薄编排复用原control.start_task/stop_task及其原fetch/pipeline，不改业务DDL或另建招聘库；批次JSON保存在忽略的data/local/collection/batches。每个组合仍是一关键词/城市、1页、最多5列表/详情。持续循环仍禁用；批次串行，沿用已有低速切换间隔，可中断等待。

## 固定接口

- POST `/api/collection/batches`：payload `{platform,keywords:string[],cities:{name,code}[],pages:1,max_jobs:1..5,detail_limit:1..5}`；只创建计划，无浏览器/数据库/单项启动调用。关键词trim去重，1..10；城市必须是该平台目录、去重；最多50组合。不接收CDP或任意私有配置覆盖。
- GET `/api/collection/batches`：返回 `{items:Batch[],total:number}`，最近在前。
- GET `/api/collection/batches/{batch_id}`：返回完整Batch。
- POST `/api/collection/batches/{batch_id}/start`：显式串行开始；拒绝重复启动或与单项/另一批次并发。
- POST `/api/collection/batches/{batch_id}/stop`：统一停止，包括正在准备/运行单项和待执行组合；等待实际单项停止/归档，无法立即完成则stopping。
- GET `/api/collection/batches/{batch_id}/items/{item_id}/task`：精确读取该条目真实CollectionTask形状与受控日志，沿用本地原文门禁；不依赖100条滚动历史，无run_id不伪造任务。
- Batch：`{batch_id,platform,status,created_at,started_at,finished_at,stop_reason,total,completed,current_item_id,next_run_at,items:BatchItem[]}`；状态queued/running/waiting_next_round/stopping/stopped/completed/blocked/error/interrupted。
- BatchItem：`{item_id,keyword,city:{name,code},status,run_id,started_at,finished_at,stop_reason,listed,detail_attempted,detail_obtained,complete,inserted,updated,skipped,rejected,failed}`；尚未执行计数null。条目状态queued/preparing/running/completed/error/blocked/cancelled/stopped/interrupted。
- 单项run_id继续复用原status/history/results/raw API（正文仍本地门禁）；批次本身不返回完整JD。

## 边界与审查重点

创建≠启动。所有真实任务只由用户之后点击；本轮UI只建一个3×2草稿。单项和批次共享控制器占用，停止不能遗留子孙进程或偷偷启动下一项。网站login/verification/content_limited立即终止后续条目、不自动重试；其他错误逐项记录后可继续。等待沿用get_config switch_interval_min/max，默认6–12分钟，stop可中断；不可用完成数0表示未执行。重启只归档中断、不自动恢复。批次不能修改已有single配置中的搜索模板/凭据。

## 任务与验证

- [x] 后端：batch.py、collection routes、control最小占用接口；tests先RED再GREEN，组合/去重/平台校验、创建零副作用、串行/互斥、失败/门禁、等待停止/子树归档、重启中断、原单项兼容。
- [x] 前端：CollectionBatch.vue 独立组件挂Collection页、api/collection新增类型方法；多标签关键词、多城市、组合预览、创建/显式开始/停止、逐项日志结果与原文复用。先行为测试再实现，前端139通过/type/build。
- [x] 本地浏览器只创建3×2未启动计划并截图；不prepare、不start、不网站访问；八表/Neo4j/正式图未变，专属草稿证据保留后清理运行夹具。
- [x] 独立复审并修阻塞；非集成阻网全量1423通过、保留既有B3两项失败分类；维护资产/产品决策/报告，精确暂存提交，普通推送codex/product-integration-20261020，更新原PR44、不新PR或合并master。
