# M2 Gate 3 人工复核粒度不足

## 症状

现有 M2 人工复核页只能对整条 JD 记录一次“接受/拒绝/跟进”。Gate 3C 要求分别判断 B1 范围、逐条 B2 技能陈述五态以及 B3 大类候选时，无法形成可对账的结构化人工真值；把逐项判断塞入自由文本备注也无法按 statement/category 计算覆盖。

## 根因

`product_reviews` 的早期契约只考虑 JD 级审核事件，`ReviewRequest`、Workflow 事件体和前端表单均没有维度级字段。页面同时展示机器阶段结果，但展示能力不等于可保存独立真值。

## 修复

- 保留原 JD 级决定和追加式 `product_reviews` 表，不改 DDL。
- 在审核事件新增可选 `human_annotations`：
  - B1 范围和依据；
  - 按 B2 statement 保存逐条人工状态与依据，并附带其零到多个规范化 Skill ID；
  - 按 `families-v3` 稳定 ID 保存的 B3 候选判断和机器漏判补充。
- B2 人工 `not_skill` 与机器五态分开表达。
- 后端拒绝不存在或 Skill/statement 不匹配的 B2 标注、重复标注和未知 B3 family。
- 前端逐项表格默认全空，提交后仍只追加事件；机器阶段、`machine_sha256` 和正式统计资格不变。

## 教训

“页面能看到机器结果”不能证明“页面能记录人工真值”。Gate 前必须按最终统计单位检查写入契约；人工标签要有稳定 ID、独立空状态和机器/真值分离，不能用单条总体决定或自由文本冒充逐项审核。按 Skill 行审核还会漏掉未规范化但已由 B2 输出的 statement，审核单位应是 statement，Skill ID 只能是可选绑定。
