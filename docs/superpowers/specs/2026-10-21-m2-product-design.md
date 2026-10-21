# 新版 M2 本地产品工作流

依据：负责人 2026-10-21 完整产品化任务。目标是先完成真实历史 JD 的工程处理闭环；规则准确率、正式目录和生产迁移不在本轮完成声明内。延续工作树、分支和 Draft PR #44，基线 2ac2856。

## 已授权范围

- 独立 `/#/m2` 页面：选择来源、ID 范围、数量或既有冻结 120/60 成员；创建快照与开始分析分开。
- MySQL 使用 `START TRANSACTION READ ONLY`，仅 SELECT jd_pool，finally ROLLBACK。保留实际空值、来源、完整字段、选取条件和 SHA-256；不补职位 URL、公司或详情。
- 运行控制和冻结输入保存于私有 workflow.sqlite3；B1/B2/B2.2/B3 共用私有 analysis.sqlite3 的原生不可变历史。
- 复用 screening/semantics/governance/role_classification.proposals，B3 使用 families.v3，只展示有限待审核职业大类建议。19 条草案不加载为发布目录。
- 原文、结果、历史任务和报告 API 统一受显式本地开关、loopback、Host、Origin 和 Sec-Fetch-Site 门禁保护。演示登录不算后端授权。

## 实施选择（工程判断）

每条 JD 使用 `mysql-jd_pool:<id>:<完整适配输入摘要>` 数据集，冻结原生成员范围并精确复用同内容结果。只按 ID 隔离仍会让 B1 在后续非法输入时带入旧有效 heads，因此同时绑定内容。单 worker 串行逐条、逐阶段提交；跨进程文件锁保护共同分析库，原生 Store 顺序关闭再打开。API 仅读取控制库。停止在阶段边界生效；未完成项显示 stopped，进程重启显示 interrupted，必须显式恢复。恢复校验冻结输入与 M2 源码、共享 skills 代码/词典、B1 cleaner 的摘要；版本变化需要新 run_id 重放，旧结果不改写。最终报告先在 SQLite 原子保存并进入 publishing，文件发布后才结束；发布窗口中断可恢复。

B22 冲突指标只报告已有 B2 effective 的语义冲突；目录治理冲突标记 not_evaluated。候选 JD 数、候选项数和未解决片段数分别统计。120/60 使用既有成员 ID，记录旧 input SHA 与当前 MySQL 内容差异，不把当前快照冒充旧字节重放。

每条原始 JD 都保留最终去向：processed / partial / needs_review / input_invalid / failed；尚未执行为 pending，停止为 stopped。B1 未决与范围外不删除原文；只要输入满足新版解析契约，就继续 B2/B22/B3 以候选证据方式保存。B1 不通过时 `confirmed_demand_eligible=false`；当前所有输出 `formal_statistics_eligible=false`。缺字段不伪造成空文本，不可解析项保留输入错误及其他阶段 blocked 原因。

B2 保留原始五态、组合与证据偏移；B22 保留候选、冲突、未解决片段；B3 保留未决与待审核。工程四阶段完成计数与完整语义覆盖分开；汇总保留总分母、输入异常、阶段失败/阻断、无识别技能和证据校验数，不输出 precision/recall。

## 验收

隔离合成测试覆盖输入异常不丢失、只读参数化选择、停止恢复、进程中断、版本重放、报告篡改、逐条证据和 API 门禁；前端测试覆盖显式启动、错误与旧响应竞争。统一 start-local 入口启动后在真实页面运行小样本，再运行冻结 120/60 集与重复执行；产物/截图只存 data/local，不提交 JD。核对 MySQL 原始/正式表计数与内容摘要前后相同。更新资产、产品决策和 PR44 交付报告，提交现有分支，不合并。
