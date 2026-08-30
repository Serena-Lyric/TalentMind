# M2 交接（2026-08-30 回包）

当前交接产出来自 `input/M2交付包/交付岗位数据/`，已复制到本目录作为当前 M2 数据源：

- `job_definition.json`：470 条岗位定义；
- `job_skill.json`：470 条对应技能明细；
- `pipeline_report.json`：管道统计与双模型验证摘要；
- `rejected.json`：拒绝记录；
- `job_change_log.json`、`manual_review.json`：本次回包未提供，当前为空数组；
- `m2-handover-20260830.md`：模块交接说明；`job_definition_zh.json` 为旧 22 条兼容快照，仅保留给历史测试，当前 API 在与主数据条数不一致时不会消费。

注意：回包手册写“488 个岗位”，但文件实际为 470 条；当前以文件实际条数为准。回包技能中存在大量未进入 `backend/app/skills/skill_dict_seed.json` 的 canonical 候选，属于待 M2/A 复核的问题，不在本次迁移中擅自修正。
