# TalentMind 文档导航

本页只负责定位现行资料。历史计划、阶段日志和旧报告以 Git 提交历史追溯，不在导航里重复记录。**文档应优先更新既有权威页面，而不是为每次修复新建文件。**

## 权威入口

| 需要了解 | 入口 |
|---|---|
| 项目是什么、怎么启动 | [根 README](../README.md) |
| 当前生效的产品决策 | [PRODUCT_DECISIONS.md](PRODUCT_DECISIONS.md) |
| 当前模块进展、资源位置和限制 | [资产与状态](superpowers/资产与状态.md) |
| 需要负责人进一步裁决的事项 | [未决问题清单](superpowers/未决问题清单.md) |
| 产品决策的前后替代关系 | [决策跟踪](superpowers/决策跟踪.md) |
| 历史事实时间索引 | [历史时间线](superpowers/历史时间线.md) |
| 测试安全、数据库和协作规范 | [AGENTS.md](../AGENTS.md) |
| 安装、部署、数据导入、恢复 | [部署与导入说明](部署与导入说明.md)、[V1 恢复手册](V1恢复手册.md) |

## 模块使用与维护

| 模块 | 权威说明 |
|---|---|
| M1 数据采集 | [采集 README](../backend/app/collect/README.md) |
| M2 岗位分析 | [现行分析 README](../backend/app/job_analysis/README.md)；[新底座设计草案（待整体审阅）](superpowers/specs/2026-10-28-m2-analysis-candidate-design.md)；[设计输入](superpowers/specs/2026-10-27-m2-core-foundation-design.md) |
| M3 图谱 | [图谱 README](../backend/app/graph/README.md) |
| M4 简历与人岗匹配 | [匹配 README](../backend/app/matching/README.md) |
| M5 前端 | [前端 README](../frontend/README.md) |
| 跨模块 API/数据结构 | [契约目录](../backend/app/contracts/ddl.sql)、[集成说明](../backend/app/integration/README.md) |
| 人工语义审核标准 | [M2→M3 审核规范](superpowers/specs/M2-M3-human-review-protocol.md) |

## 当前分段交付计划

| 范围 | 计划与审核依据 |
|---|---|
| M2 新底座（计划已编制，尚未实施） | [P0～P6 总计划及各段入口](superpowers/plans/2026-10-28-m2-core-delivery-plan.md)；[ChatGPT 交付审核标准](superpowers/specs/2026-10-28-m2-delivery-review-standard.md) |

## 近期阶段验收（最多五份）

| 日期 | 验收报告 |
|---|---|
| 2026-10-22 | [M1 分平台修复](review/M1-platform-repair-2026-10-22.md) |
| 2026-10-22 | [M2 真实分析与复核](review/M2-real-analysis-2026-10-22.md) |
| 2026-10-22 | [M2→M3 Gate 3](review/M2-M3-Gate-3-acceptance-2026-10-22.md) |
| 2026-10-21 | [主仓统一与功能验收](review/Unified-product-2026-10-21.md) |
| 2026-10-21 | [M2 工作台](review/M2-product-2026-10-21.md) |

这是全仓库的阶段性测试/验证/验收报告上限，不是每个模块五份。以后有新报告时，优先将长期有用的结论更新到模块 README、规范、陷阱或当前状态，再淘汰最旧报告及其独有附件。**不将旧报告移动到 archive 变相规避上限。**

## 其他目录与记录原则

- `superpowers/specs/`：仍适用的设计规范；更新原规范而不是逐次新增版本。
- `superpowers/plans/`：当前有效、尚未完成的计划；完成后不再囤积任务书。
- `superpowers/traps/`：仍有复用价值的安全/技术陷阱；同类问题在既有文档持续补充。
- `superpowers/archive/`：历史事故与重要不可替代的事实性记录，不作为报告回收站。
- `archive/competition-v1/`：旧版本所需的公开历史背景；正式 Release 见 [固定版本](https://github.com/Serena-Lyric/TalentMind/releases/tag/competition-v1-2026-09-05)。

### 文档分类和归属

README = 使用入口；产品决策 = 当前规则；模块说明 = 当前用法；资产与状态 = 当前事实；决策跟踪/时间线 = 历史变更；specs = 有效规范；plans = 活跃计划；traps = 可复用教训；review = 近期验收。一个事实选定一处权威记录，其他位置只引用它。

新的有效决策直接修订现有对应章节，并在决策跟踪中登记替代关系；阶段报告中的日期和测试数量永远只代表当次验证，不当作最新实时状态。重要内容首先通过 Git commit/PR 历史保留，不默认另存相同报告。

**私有正式交付物：** 比赛申报书、展示 PPT、视频、完整项目成品与正式提交包等在仓库外的统一私有目录管理；不自动创建或上传 `docs/submit/` 或 `docs/originalfile/` 作为正式交付仓。`input/`、`output/`、`data/local/`、真实简历、浏览器配置和数据库也不上传公开仓库。
