# M2 产品编排：输入成员、依赖版本与报告发布

## 症状

独立审查发现：同一 JD 合法输入后再读到缺字段行时，原生 B1 同 namespace 会同时返回旧有效 heads 与新 input_failed；产品层把它误归为执行失败。原编排摘要漏掉共享词典/normalizer 和 B1 cleaner；停止后这些依赖变化仍可能恢复。最终报告原先先标 completed，再写 report，进程在两者之间退出会变为无法恢复的无报告任务。页面创建冻结输入的迟到响应还可能覆盖后来选择的历史任务。

## 根因

原生 B1/B2 是数据集增量状态，不是单次列表；只按 JD ID 划分 namespace 无法隔离非法输入与旧 heads。分析依赖跨越 job_analysis 子树。业务完成、持久化报告与文件发布是不同事务边界。创建操作未与其他异步页面选择共用请求序号。

## 修复

- namespace 同时绑定 JD ID 和完整适配输入 SHA；四阶段引用固定报告/结果，最终产品报告不从 heads 重建。
- 原始行保留 NULL，版本化适配副本仅省略可选 NULL。字段异常留在 input_invalid 分母，B1 待复核原文继续候选分析。
- 版本摘要覆盖 M2、共享 skills 代码/词典和 cleaner；依赖变化拒绝原地恢复，创建冻结输入的新版本任务。
- 最终报告与 publishing 状态在同一 SQLite 事务提交；文件发布成功再结束，重启把 publishing/running/stopping 归 interrupted。停止/中断的未完成项显式标记，已提交阶段保留。
- 创建响应沿用请求序号，旧响应不能覆盖后来的任务选择。

## 教训与验证

复用组件前先核查其数据集和恢复语义，不能只调用 execute。使用真实原生模块与临时 SQLite 的回归复现并覆盖合法→非法输入、共享依赖漂移、发布提交后模拟进程退出、同版本精确复用、停止恢复；页面迟到创建测试先失败再通过。真实任务版本变化后保留旧停止记录，用新 run_id 重放；详见[本轮报告](https://github.com/Serena-Lyric/TalentMind/blob/36655eef617db1c80f007f4a9bb7423c58c6fc75/docs/review/M2-product-2026-10-21.md)。
