# M2 岗位分析

网页与CLI新分析统一使用[delivery](delivery/README.md)：P1事实理解、P2知识对齐/技能候选治理、P3/P4工作研究候选。现行目标见[产品决策](../../../docs/PRODUCT_DECISIONS.md)，分段历史审核见[总表](../../../docs/superpowers/plans/2026-10-28-m2-core-delivery-plan.md)。新旧语义/效果的验收范围不因代码整合扩大。

## 实际入口

- 网页`/#/m2`经`routers/m2.py`与`delivery/http_service.py`调用真实统一运行器。选择原始JD、冻结输入、显式开始、停止/恢复/放弃、历史读取分开；原始MySQL只读，新状态只写私有delivery目录。
- [P1单条理解](understanding/README.md)保留事实、五态、组合、条件、作用域、证据和实际模型/输入版本。
- [P2知识](knowledge/README.md)观察技能候选、按现行治理规则形成有效投影，再用于知识解释；争议不自动解除，名称解释不改写原要求。
- [P3/P4研究](work_candidates/README.md)保存原分析引用、研究版本、撤回/纠正及后续投影。网页可为来源核心职责建立独立研究假设，不自动确认不同JD同组、不发布正式职业。
- [P0基准](baseline/README.md)与delivery评价工具保留受控签审输入及独立历史评价；不将工程完整率当语义准确率。

完整运行配置、HTTP/CLI契约、恢复及精确读取见[delivery说明](delivery/README.md)。#63真实中文同组、角色归属和市场准确率优化继续搁置。

## 历史与退役

`product/workflow.py`仅提供`History`只读读取、旧证据/审核解释及新账本共用的OS租约，不再提供旧Workflow执行器。`data/local/m2-product/`中的两个数据库、冻结输入、原生报告、人工审核和图谱保留；读取校验原摘要，不按当前代码重算，也不修改排队/停止任务状态。旧未完成任务必须由用户在新页面显式选择输入另建运行。

`graph/product_bundle.py`只读旧图；新图用`graph/delivery_bundle.py`按运行快照固定manifest和三个artifact。历史Gate3工程可读性、无人工语义真值的边界见[固定历史证据](https://github.com/Serena-Lyric/TalentMind/blob/33d5df43c89371684d53bfa7a3465fddd13ca558/docs/review/M2-M3-Gate-3-acceptance-2026-10-22.md)。

顶层旧`main/pipeline`及专属LLM/清洗/提取/聚合/导出链已退役，不能再运行旧`--reset`清表入口。交接导入仍由`app/integration/`维护，具有单独破坏性许可边界；SQL原件解析工具移到`integration/sql_values.py`，不保留旧分析DB模块。

M3 离线来源图链已退役：`graph/real_pipeline.py`、`graph/real_quality.py` 及仅被其消费的 `screening/`、`governance/`、`semantics` 运行器（rules/runner/store/validation）删除，`semantics/models.py` 继续供现行 M2 链使用。历史实现保留在 Git 历史；线上 M3 历史图与 M2 delivery/product 图读取不依赖该离线链。

## 必要支撑保留

| 模块 | 现行消费者/用途 |
|---|---|
| `foundation.inputs/store` | 新输入规范、摘要、路径边界与只追加存储共用。 |
| `foundation.runner.publish/dictionary` | delivery CLI原子导出及DEV基线对照。 |
| `semantics.models.Evidence`、`baseline.contract` | 新语义契约及研究比较直接复用的证据/候选结构。 |
| `product/source.py` | 新网页只读连接与来源身份归一化。 |

B3 旧角色层（`role_classification/`）与 `canonical_catalog/` 草案目录已退役：没有路由、前端、脚本或现行 M2 链消费者，原实现与草案资产保留在 Git 历史。重复模型路由 `app/llm/`、无调用者的 `app/db/redis.py` 及 `OPENAI_*`/`REDIS_URL` 配置已删除；M2 模型仍只走 `understanding.cloud` 的显式配置与密钥文件。

所有测试只使用合成输入和隔离存储。正式库迁移、真实数据删除、外部采集和新收费模型运行须对应许可。私有原文、数据库与报告不提交。
