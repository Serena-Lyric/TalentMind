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
