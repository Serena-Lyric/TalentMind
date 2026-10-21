# 智联岗位身份待审交付报告

日期：2026-10-21，Asia/Singapore。分支：`codex/zhaopin-identity-pending`；原开发基线：`34fb9e613746be50caf9491a552c75e2377a240d`；审查收口已合入主线 `920e1747ef4c806f5e4df06e6a6e192ae25cc6ba`，并保留星云视觉与 M1/M2/M3 功能。

交付：[Draft PR #46](https://github.com/Serena-Lyric/TalentMind/pull/46)。

## 范围与结果

本次按负责人确认实现“进入分析，但明确标为身份待审”。内容资格与身份可信度分开：身份为 `verified / pending / unknown`；待审记录可进入 M2 单条分析和 M3 候选观察图，不计正式独立岗位或已确认技能需求。

本次 5 条智联事件此前全部为 `unverified_dom_identity`。原因已复核：`.job-card` 只有公司链接，没有稳定职位 URL；点击后使用搜索页异步详情面板。旧逻辑只要 `_dom=true` 就在检查正文前直接拒绝。

## 实现

- 智联 DOM 详情：点击前记录面板，点击后轮询面板变化；要求目标卡 active、面板可见、连续两次稳定、面板/详情标题一致。面板变化是无条件门禁，目标卡点击前已 active 也不豁免。
- 列表阶段的临时 DOM URL 使用列表页、卡片位置和展示摘要哈希；标题/公司/薪资/地点/标签完全相同的两张卡片仍分别进入详情采样，最终身份 fingerprint 不变。
- 正文独立经过现有有效性、截断和错岗检查。只有正文合格才计 `content_eligible`；只有内容合格且 URL 身份匹配才增加 `complete`。
- pending fingerprint 使用 SHA-256，覆盖列表页、卡片位置、标题、公司、薪资地点、正文摘要、观察时间和策略版本。事件 `_observation_key` 只负责关联，不落为职位身份。
- M1 新增 `content_eligible / identity_pending / identity_verified`；M1 结果和数据库原文读取携带身份状态与证据。
- M2 item/report/前端携带身份；`content_eligible=false` 在 B1 前成为 `input_invalid/content_ineligible`；身份不影响 B1/B2/B3 的正常语义状态。
- M3 sources、job 节点、manifest 和前端详情携带身份；节点与源记录身份不一致时拒绝加载。
- `jd_pool` 契约新增 `identity_status`（历史默认 `unknown`）、`content_eligible`（历史 NULL）、`identity_evidence`，并提交追加式迁移 SQL。

## 离线回放

私有事件：`data/local/collection/zhaopin-5f7079ff40394431b084ca07f55e2d5e.events.jsonl`。

私有输出：`data/local/identity-pending-replay-20261021-v2/replay.json`。

结果：

- 5/5 在合成合法面板绑定与内容输入下得到 `pending + content_eligible`。
- 异步错岗 5/5 拒绝 `title_mismatch`。
- 相同标题但面板不更新 5/5 拒绝 `panel_not_updated`。
- 空正文 5/5 拒绝 `empty_detail`。
- 截断正文 5/5 拒绝 `truncated_description`。
- 相同观察 fingerprint 相同，跨观察时间 fingerprint 不同。

边界：旧事件没有记录点击前后面板状态，所以本次回放只验证决策逻辑与内容资格，不能认证这 5 条历史上的真实点击绑定，也不能把 5 条预先认定全部符合真实待审入库条件。

## 验证

- 审查新增失败回归先分别复现 `pending` 错放和双卡只保留 1 张，修复后两项均通过。
- 相关后端离线回归：205 passed / 7 deselected / 0 failed。
- 全量非集成：1494 passed / 2 failed / 24 deselected。两项失败仍为既有 B3 `PRODUCT_DECISIONS` 固定来源摘要/引文失配，本次未改候选来源或修绿。
- 前端完整测试：154 passed / 0 failed。
- `vue-tsc --noEmit && vite build`：通过；保留既有大 chunk、动态/静态 import 提示。
- 当前 MySQL 只读核查：目标为 `localhost:23306/talentmind`；`jd_pool=2988`、`signal=1540`、`skill_dict=285`、`job_skill=717`、`job_definition=717`、`job_change_log=275`、`resume=0`、`talent_raw=0`；`identity_status/content_eligible/identity_evidence` 三列均不存在，迁移状态为未应用。

## 未执行与下一步

- 未执行 DDL、迁移或真实采集。
- 当前代码在旧 schema 上继续读取历史；若尝试写入 pending/内容/身份证据，会在 INSERT 前明确报 `identity_schema_migration_required`。
- 下一步需另行提交迁移执行申请：核实目标、冻结写入、记录 schema/八表摘要、创建 mysqldump 冷备、在隔离实例恢复并核对。获批后才执行追加列 SQL 与迁移后对账。
- 迁移通过后，再申请一次单平台/单关键词/单城市/一页、最多5列表/5详情的真实智联验收。最终 pending/入库数由新绑定和正文校验实际决定。

## 数据安全

没有修改正式 `job_definition`、`job_skill`、`job_change_log` 或 Neo4j，没有提升 B3，没有真实数据删除、迁移、全量采集、收费模型调用或全量 M2 重跑。回放输出与真实事件继续位于 Git 忽略的私有目录。
