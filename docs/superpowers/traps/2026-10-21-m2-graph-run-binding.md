# M2 候选图与保存运行绑定

- 症状：M2工作台与M3 real_pipeline为独立入口；导航无法证明输入和分析版本一致。
- 根因：图谱不消费产品run保存报告；简单重新分析或接入其他bundle会丢失运行关联。
- 修复：product_bundle只读取不可变报告、冻结输入及原生阶段报告，校验身份/版本/证据，复用project/derive；候选API和前端共同校验run、manifest、逐产物与来源关联，不写Neo4j。
- 审查修复：历史读取验证保存版本，不强制等于当前源码，避免升级锁死旧图；异步导航绑定请求代次，创建/重放/切换后旧响应失效。两项均补充红绿回归并定向复审。
- 教训：输入、报告、阶段版本和图谱产物共同证明关联；源码升级不破坏历史。待审范围和uncertain陈述仍只作候选观察，不提升为正式要求或职业目录。

回归：test_m2_graph.py、test_m2_product_api.py、m2Product.test.ts、realSnapshot.test.ts。见[统一验收](https://github.com/Serena-Lyric/TalentMind/blob/cacf00f138a0512c4ef6c643fc90c0232159e1bb/docs/review/Unified-product-2026-10-21.md)。
