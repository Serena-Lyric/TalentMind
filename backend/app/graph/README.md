# graph

## 真实 JD 首轮贯通（2026-10-20，隔离候选）

`real_pipeline.py` 复用已合并 M2 B1/B2/B22，显式文件输入生成独立的原文陈述事实图、来源索引、派生相似/社区与布局；`verify` 核对冻结 M1/M2 并重算产物。所有完整数据放 `data/local/`，不调用被禁用的生产重建。离线算法固定依赖见 `requirements-offline.txt`；正式 Vue 通过显式预览开关加载，默认历史图不变。

真实 120 条首轮得到 22 条进入分析、71 节点/417 条规则陈述，416 uncertain/1 mentioned，相似边为零；不是开放域完成或可信需求图。输入、命令、版本/哈希、浏览器截图与既有测试失败见[完整交付](../../../docs/review/M1-M5-real-jd-e2e.md)。

## M3/M5-P2.1 原 ID 历史快照布局候选（2026-10-19）

`candidate_layout.py` 在完全不连接服务的独立进程中复用 PR32 的只读算法，消费显式历史 `graph.json`，输出 `exchange/m3/overlays/` 内的新文件。岗位相似/社区驱动展示坐标，共享技能保留全部相邻岗位和社区，无相似边孤点不强制分类。原始历史身份/语义不自动修复；结果不等同PR32修复投影的研究运行，也不作为正式职业分类。

复现、依赖与输入/源码摘要见 [候选产物说明](../../../exchange/m3/overlays/README.md)；正式Vue接入与实际验证见 [集成报告](../../../docs/review/M3-M5-P2-1.md)，相关问题记录见 [图层与密集命中陷阱](../../../docs/superpowers/traps/2026-10-19-galaxy-layer-and-dense-picking.md)。未加入生产requirements、未依赖GDS、未恢复重建入口、未覆盖正式graph.json。

M3 图谱正式目录。`builder.py` 从 M2 交接产出构建 Job/Skill 节点和 `REQUIRES`/`RELATED_TO` 边，输出 `exchange/m3/graph.json`；A 通过 `integration/import_graph.py` 导入 Neo4j。

- Job 节点 id/name 使用英文 `job_name`，可选 `name_zh` 用于中文展示；
- Skill 节点使用 `skill_dict` canonical；
- 前端 `GraphPanorama.vue` 消费 A 的 `/api/graph/data`，负责多视图和星云布局；
- 输入包 `input/图谱模块/` 仅作历史算法和视觉对照，不作为运行时源码。

## 当前交接与构建器边界（2026-10-15 核查）

根目录 `exchange/m3/graph.json` 实际为 **7845 节点 / 11412 边**：Job 717 / Skill 4671 / Industry 2457；REQUIRES 8866 / APPLIES_TO 2539 / RELATED_TO 7。岗位/技能/行业使用带前缀的稳定交接 ID；这是本轮文件计数，不是 Neo4j 实时查询。

上述 `job_name` / canonical 的裸 ID 描述适用于旧 `builder.py`。该构建器只产出 Job/Skill 和 REQUIRES/Job–Job RELATED_TO（Jaccard 阈值 0.25），不构建 Industry/APPLIES_TO；当前交接不能用它直接复现。不要运行默认 builder 覆盖正式 graph.json；统一构建流程留待 M3 专项处理，本轮只修说明。

## Issue #20：完整图纯函数离线修复（2026-10-17，待 PR 复审）

完整图算法是 `app.integration.rebuild_m2_graph.build_graph_data(rows, skill_rows)`；历史 `builder.py` 保留。该纯函数只投影传入数据和版本化只读 canonical 名称，不初始化数据库客户端，不写文件。

- 技能采用精确 canonical 名称（忽略大小写）或保留区分的原名，不自动采纳未核实别名、版本归并或输入 canonical_name 主张。技能/场景键是 `skill:` / `industry:` 加 UTF-8 百分号编码；例如 c++ → `skill:c%2B%2B`、c# → `skill:c%23`。首尾空白不参与身份；原技能名称仍保留。场景维持既有每岗位最多 8 项投影。
- Job ID 保留旧规则；若旧规则产生重复 ID，报错而不覆盖。实体 `audit.entity_mappings` 给出岗位、原名、身份、新旧 ID 和规范化状态；旧 ID 仅在审计中复现旧算法的逐岗位别名与最后写入行为。`legacy_id_collisions` 显式列出一对多映射。未知名称允许分开，不能据此声称已审核为不同技术或同义词。
- RELATED_TO 仍为 Job–Job 技能集合 Jaccard >= 0.35，完整倒排候选，没有 TopK；节点、关系及审计确定排序。
- REQUIRES 保留 `source_names/source_states/source_fields/source_row_indices/source_indices` 平行数组，逐次记录重复声明；字段来源为 required_skills、bonus_skills 或 skill_details。前两者 row_index=-1、index 对应岗位原输入列表；后者直接对应传入 skill_rows 的行和 skills 数组原索引，audit 同样保留两级位置。job_count 为不同岗位数。改变输入顺序会改变来源位置，但不会用顺序裁决技能身份或有效要求。
- `legacy_required/legacy_bonus` 仅是历史投影，不是新版 M2 五态。同一实体要求冲突时 `status_conflict=true`、`needs_review=true`，旧 `is_required` 与 `weight` 为 null；可直接对应的明细 bool 分歧也保留。原始技能明细及未应用的 canonical 主张留在 audit。
- 待审 canonical 主张按技能实体 ID 关联 REQUIRES；大小写、首尾空白及明细缺失布尔状态均不应导致漏标，不把未经核实的主张直接应用为事实。

只读诊断入口（从 backend 执行，不需要 .env 或服务）：

```powershell
python -m app.graph.diagnose_snapshot ../exchange/m3/graph.json
python -m pytest tests/test_m3_graph_integrity.py tests/test_m3_snapshot_diagnostic.py tests/test_graph.py -q
```

诊断只读显式快照并向 stdout 输出 JSON（包括完整映射和关系差异），在内存中分别比较旧 ID 的完整候选与修复身份后的候选，以独立全对穷举校验无漏算。岗位节点的历史技能数组与已有行业边不能恢复丢失的原始明细或被覆盖的场景名称；不代表生产重建的最终结果。

**兼容与迁移边界：** 新实体 ID 会变化，冲突边 nullable 字段及附加审计须消费方保留；不能使用 bool(null) 或默认 weight 把冲突当加分/必备。现有 API/导入器未在本轮适配，部分路径可能丢弃这些字段，因此新输出仅用于离线。未来需审核映射，回到原始事实拆分一对多关系，在隔离实例验证消费方与迁移，并另获生产操作许可；不能只重命名旧节点。已核验 graph.json 本轮不变。`rebuild()` 及 `python -m app.integration.rebuild_m2_graph` **已直接禁用**，在导入服务依赖、连接数据库或写文件之前报错，且没有确认参数或环境变量绕过入口。恢复生产重建须经后续适配、迁移设计与明确授权；只读诊断仍使用上面的独立入口。其他历史导入脚本未在本轮变更，不能据此认为它们也已安全化。

用户报告的技能节点散乱及大部分连线缺失，按 2026-10-17 指示集中留到下一轮前端算法修复；本轮不修改布局、连线呈现或 API，也不把本次离线修复宣称为已解决前端表现。统一跟踪于 [未决问题清单](../../../docs/superpowers/未决问题清单.md)。

测试结果、快照数字、限制和后续复审见 [阶段报告](../../../docs/review/M3-issue-20.md)；根因见 [陷阱记录](../../../docs/superpowers/traps/2026-10-17-m3-identity-and-relations.md)。

## 历史验证（保留当时数字）

2026-08-30 刷新（历史快照）：builder 输出 588 节点/4003 条边；Neo4j MERGE 后统计 588 节点/3998 条边。
2026-09-04 复核：已按 M2 完整 719 回包重建，`exchange/m3/graph.json`=7852 节点/11423 边（Job 719/Skill 4671/Industry 2462；REQUIRES 8872/APPLIES_TO 2544/RELATED_TO 7），Neo4j 实测与其一致。
