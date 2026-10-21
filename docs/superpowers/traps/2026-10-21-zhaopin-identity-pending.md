# 智联 DOM 详情身份与迁移门禁

日期：2026-10-21。

## 症状

智联搜索完成且正文取得，但 5 条全部显示 `unverified_dom_identity`，M2 无法读取；任务仍显示 `completed`。

## 根因

当前智联 `.job-card` 没有职位详情链接，只有公司详情链接；点击卡片后右侧 `.job-detail-panel` 异步更新，页面 URL 仍是搜索页。旧实现把所有 DOM-only 卡片直接判为不可验证身份，导致正文、标题即使已经取得也不入库。“任务完成”“详情取得”“正文合格”“身份已验证”“入库”是不同事实。

## 修复

身份采用 `verified / pending / unknown`；DOM pending 必须同时满足点击前后面板变化、目标卡 active、两次连续稳定、标题一致和正文有效性/截断检查。最终 SHA-256 fingerprint 包含列表页、卡片位置、标题、公司、薪资地点、正文摘要和观察时间，只定位观察，不证明唯一岗位。事件用 `_observation_key` 关联，M1 新增 content/identity 统计，M2/M3 透明携带但不计正式统计。

旧 schema 缺新列时，pending/内容证据必须在 INSERT 前明确报 `identity_schema_migration_required`，不得静默写 unknown。数据库迁移、冷备与回退需另行授权。

## 教训与验证

不能把卡片 active、标题相同、固定等待或详情 URL 仍是搜索页当成稳定绑定；也不能因正文看起来正确就跳过异步残留检查。旧事件没有点击前面板快照时，离线回放只能验证决策逻辑和内容资格，不能认证历史绑定。

相关设计见 [身份待审设计](../specs/2026-10-21-zhaopin-identity-pending-design.md)，完整验证与回放见 [报告](../../review/Zhaopin-identity-pending-2026-10-21.md)。

## 2026-10-21 审查收口

### 症状

目标卡片点击前已经 active 且点击后面板未变化时，同一标题的残留面板仍可能被判为 `pending`。两张标题、公司、薪资、地点和标签完全相同的智联 DOM 卡片，在详情采样前只剩一张。

### 根因

身份门禁把“点击前 active”错误实现成“面板必须变化”的豁免条件，使 `target_active_before=true + panel_changed=false` 绕过规则。列表临时 URL 只哈希展示字段，随后 JavaScript `seen` 和 Python URL 去重都会把位置不同但展示相同的卡片合并。

### 修复

面板变化改为无条件门禁；`target_active_before` 只保留为证据，不再豁免。临时 DOM URL 与 `_observation_key` 共用“列表 URL + 卡片下标 + 列表卡摘要”的哈希；最终 `source_detail` 仍在详情和绑定通过后按完整观测重新生成。新增已 active 的同标题残留和展示字段完全相同的双卡失败回归。

### 教训

前置状态不是后置门禁的豁免理由；临时观察身份必须包含位置或观察键，不能用展示字段推测唯一职位。缺少稳定职位 URL 时，详情采样前的去重只能去除同一观察，不能合并“看起来一样”的不同卡片。
