# graph

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

只读诊断入口（从 backend 执行，不需要 .env 或服务）：

```powershell
python -m app.graph.diagnose_snapshot ../exchange/m3/graph.json
python -m pytest tests/test_m3_graph_integrity.py tests/test_m3_snapshot_diagnostic.py tests/test_graph.py -q
```

诊断只读显式快照并向 stdout 输出 JSON（包括完整映射和关系差异），在内存中分别比较旧 ID 的完整候选与修复身份后的候选，以独立全对穷举校验无漏算。岗位节点的历史技能数组与已有行业边不能恢复丢失的原始明细或被覆盖的场景名称；不代表生产重建的最终结果。

**兼容与迁移边界：** 新实体 ID 会变化，冲突边 nullable 字段及附加审计须消费方保留；不能使用 bool(null) 或默认 weight 把冲突当加分/必备。现有 API/导入器未在本轮适配，部分路径可能丢弃这些字段，因此新输出仅用于离线。未来需审核映射，回到原始事实拆分一对多关系，在隔离实例验证消费方与迁移，并另获生产操作许可；不能只重命名旧节点。已核验 graph.json 本轮不变。`rebuild()` 仍会写文件并清空正式图，**禁止把它当诊断入口运行**。

测试结果、快照数字、限制和后续复审见 [阶段报告](../../../docs/review/M3-issue-20.md)；根因见 [陷阱记录](../../../docs/superpowers/traps/2026-10-17-m3-identity-and-relations.md)。

## 历史验证（保留当时数字）

2026-08-30 刷新（历史快照）：builder 输出 588 节点/4003 条边；Neo4j MERGE 后统计 588 节点/3998 条边。
2026-09-04 复核：已按 M2 完整 719 回包重建，`exchange/m3/graph.json`=7852 节点/11423 边（Job 719/Skill 4671/Industry 2462；REQUIRES 8872/APPLIES_TO 2544/RELATED_TO 7），Neo4j 实测与其一致。
