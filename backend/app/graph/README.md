# graph

M3 图谱正式目录。`builder.py` 从 M2 交接产出构建 Job/Skill 节点和 `REQUIRES`/`RELATED_TO` 边，输出 `exchange/m3/graph.json`；A 通过 `integration/import_graph.py` 导入 Neo4j。

- Job 节点 id/name 使用英文 `job_name`，可选 `name_zh` 用于中文展示；
- Skill 节点使用 `skill_dict` canonical；
- 前端 `GraphPanorama.vue` 消费 A 的 `/api/graph/data`，负责多视图和星云布局；
- 输入包 `input/图谱模块/` 仅作算法和视觉对照；本次以新 M2 数据通过正式 builder 重建 `exchange/m3/graph.json`，不直接导入输入包旧快照。

2026-08-30 刷新（历史快照）：builder 输出 588 节点/4003 条边；Neo4j MERGE 后统计 588 节点/3998 条边。
2026-09-04 复核：已按 M2 完整 719 回包重建，`exchange/m3/graph.json`=7852 节点/11423 边（Job 719/Skill 4671/Industry 2462；REQUIRES 8872/APPLIES_TO 2544/RELATED_TO 7），Neo4j 实测与其一致。
