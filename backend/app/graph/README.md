# graph

M3 图谱正式目录。`builder.py` 从 M2 交接产出构建 Job/Skill 节点和 `REQUIRES`/`RELATED_TO` 边，输出 `exchange/m3/graph.json`；A 通过 `integration/import_graph.py` 导入 Neo4j。

- Job 节点 id/name 使用英文 `job_name`，可选 `name_zh` 用于中文展示；
- Skill 节点使用 `skill_dict` canonical；
- 前端 `GraphPanorama.vue` 消费 A 的 `/api/graph/data`，负责多视图和星云布局；
- 输入包 `input/图谱模块/` 仅作历史算法和视觉对照，不作为运行时源码。

## 当前交接与构建器边界（2026-10-15 核查）

根目录 `exchange/m3/graph.json` 实际为 **7845 节点 / 11412 边**：Job 717 / Skill 4671 / Industry 2457；REQUIRES 8866 / APPLIES_TO 2539 / RELATED_TO 7。岗位/技能/行业使用带前缀的稳定交接 ID；这是本轮文件计数，不是 Neo4j 实时查询。

上述 `job_name` / canonical 的裸 ID 描述适用于旧 `builder.py`。该构建器只产出 Job/Skill 和 REQUIRES/Job–Job RELATED_TO（Jaccard 阈值 0.25），不构建 Industry/APPLIES_TO；当前交接不能用它直接复现。不要运行默认 builder 覆盖正式 graph.json；统一构建流程留待 M3 专项处理，本轮只修说明。

## 历史验证（保留当时数字）

2026-08-30 刷新（历史快照）：builder 输出 588 节点/4003 条边；Neo4j MERGE 后统计 588 节点/3998 条边。
2026-09-04 复核：已按 M2 完整 719 回包重建，`exchange/m3/graph.json`=7852 节点/11423 边（Job 719/Skill 4671/Industry 2462；REQUIRES 8872/APPLIES_TO 2544/RELATED_TO 7），Neo4j 实测与其一致。
