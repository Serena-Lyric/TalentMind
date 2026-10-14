# 岗位能力图谱示例（赛题测试数据要求）

> 要求：提供 1 个新岗位和 1 个既有岗位的能力图谱及岗位数据源（含输入输出示例）。
> 数据来源：系统 MySQL job_definition/job_skill 真实数据（2026-08-31 导出）。

## 示例 1：新岗位发现与定义

- 文件：`新岗位_Data Architect.json`
- 岗位：Data Architect
- 特征：`is_emerging=true`，`evolution.stage=growth`，`skill_novelty=high`，由 4 条 JD 聚合
- 输入：LinkedIn 原始 JD（流式/批式数据平台架构、AWS/ETL/数仓等要求）
- 输出：岗位定义五要素（名称/核心职责/必备技能/加分技能/典型场景）+ 28 条技能证据链（weight/confidence/evidence/is_required）

## 示例 2：既有岗位能力动态更新

- 文件：`既有岗位_Senior PHP Developer.json`
- 岗位：Senior PHP Developer
- 特征：`is_emerging=false`，`evolution.stage=mature`，由 3 条 JD 聚合
- 输入：多轮采集的 PHP 岗位 JD
- 输出：13 条技能证据链；动态更新机制（differ 指纹对比 → change_type added/removed/modified + evidence 原文）已实现，变更日志待 M2 增量数据

## 图谱可视化截图

**待补**：需从系统 Graph 页面（http://127.0.0.1:18080/#/graph）导出这两个岗位的图谱截图，替换/补充本节。
