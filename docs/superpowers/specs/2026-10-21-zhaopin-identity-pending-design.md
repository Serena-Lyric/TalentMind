# 智联 DOM 身份待审设计与迁移边界

日期：2026-10-21，Asia/Singapore。

## 目标

允许智联 DOM 搜索结果在正文合格、详情面板绑定证据成立时，以 `identity_status=pending` 进入 M2 单条分析和 M3 候选观察图；同时保持身份透明、来源可追溯，并确保它不被计入已确认的独立岗位、正式技能需求或正式职业分类。

## 已确认业务规则

- 内容质量与岗位身份可信度是两个独立维度。
- 身份枚举固定为 `verified / pending / unknown`。
- 采集拒绝和失败属于采集结果，不加入身份枚举。
- 历史数据默认 `unknown`，不得批量推断为 `verified`。
- `detail_obtained` 仅表示取得正文；正文是否合格使用独立的 `content_eligible`。
- 不重新定义已有 `complete` 统计口径；身份待审记录不增加 `complete`。
- `pending` 可进入 M2 单条分析与证据展示，也可进入 M3 候选观察图。
- `pending` 不计入已确认独立岗位数、已确认技能需求或正式统计分母。
- 不修改正式 `job_definition`、`job_skill`、`job_change_log` 或 Neo4j，不自动提升 B3。
- 本次先完成代码、兼容方案和离线回放；不执行数据库 DDL，不进行新的真实采集。

## 非目标

- 不把 `dom://` 临时身份包装成唯一招聘岗位身份。
- 不把标题、公司、卡片 active 或固定等待时间单独作为绑定证据。
- 不自动合并跨轮观察，也不自动补写历史记录。
- 不提升语义精准度、正式岗位统计或 B3 发布资格。
- 不执行生产备份恢复演练、DDL、迁移或真实数据删除。

## 身份与内容模型

### 身份状态

- `verified`：存在可匹配的来源职位 URL，或存在可验证的站点唯一职位标识。
- `pending`：正文合格，但只有本次 DOM 观察身份；卡片与详情面板绑定证据成立。
- `unknown`：历史遗留或缺乏身份证据；不得被代码默认成 `verified`。

### 内容状态

- `content_eligible=true`：正文非空、未截断、与目标岗位无明显错岗，并通过现有 `is_valid_jd()`。
- `content_eligible=false`：正文不合格；不得因身份待审而放行。
- 历史记录没有内容资格证据时为 NULL，API 展示为 `unknown`，不得补造。

## 智联 DOM 绑定协议

每次详情尝试按以下顺序取得证据：

1. 点击前记录目标卡片位置、卡片标题、公司、列表页 URL，以及当前详情面板标题和正文摘要。
2. 通过卡片下标点击目标卡片。
3. 轮询读取目标卡片 active 状态、详情面板可见性、面板标题和正文摘要，直到状态稳定；不得仅等待固定秒数。
4. 要求目标卡片 active、面板可见，并连续两次观察到相同面板状态。
5. 无论目标卡片点击前是否 active，点击前后的面板状态签名都必须发生变化；点击前已 active 不豁免本门禁。
6. 面板规范化标题必须与目标卡片规范化标题完全一致。
7. 若仍出现上一条详情残留、面板不更新、标题不一致或状态不稳定，则拒绝，不进入分析。

公司名不能作为强绑定条件。本次真实样本中列表公司可能是招聘中介，详情公司可能显示客户公司，因此公司差异本身不是错岗证据；但公司、列表位置和面板状态均作为证据保留。

## DOM fingerprint

身份待审记录的 `source_detail` 使用：

`dom://zhaopin/<64 位 SHA-256>`

SHA-256 输入为规范化 JSON，至少包含：

- `platform`
- `list_page_url`
- `card_index`
- 规范化列表标题
- 规范化列表公司
- 规范化地点与薪资
- 正文 SHA-256
- `observed_at`
- 绑定策略版本

完整证据另存为规范化 JSON，包含点击前后面板摘要、active 状态、稳定性样本数、列表页、卡片位置和观察时间。临时身份只定位本次观察，不证明唯一招聘岗位，也不用于跨轮自动合并。

事件层另使用不落库的 `_observation_key` 关联同一次列表观察。该键由平台、列表 URL、卡片位置和列表卡摘要组成，只用于把 `listed → detail → persisted` 事件关联到同一观察。详情采样前的临时 `dom://` URL 也使用列表 URL、卡片位置和列表卡摘要的哈希，不能只按展示字段生成；因此标题、公司、薪资、地点和标签完全相同的两张 DOM 卡片仍会分别进入详情采样。最终 `source_detail` 仍由包含正文摘要和 `observed_at` 的 SHA-256 fingerprint 生成。

`--no-details` 或任何未执行详情校验的路径不得产生 `pending` 或 `content_eligible=true`。本次有界产品入口仍要求详情校验。

## M1 统计与事件

新增独立计数：

- `content_eligible`
- `identity_pending`
- `identity_verified`

保留并澄清：

- `detail_obtained`：取得正文数，不代表正文合格。
- `complete`：维持历史严格口径；只有 `verified` 且内容合格才增加。
- `rejected`：绑定、错岗、空正文、截断或有效性失败。
- `failed`：访问、CDP、网络或执行异常。
- `inserted`：完整且可分析的内容首次写入 `jd_pool`，可包含身份待审记录。

事件和采集结果 API 必须携带 `identity_status`、`content_eligible`、`identity_evidence`。

## 数据库兼容迁移方案

拟新增：

```sql
ALTER TABLE jd_pool
  ADD COLUMN identity_status VARCHAR(16) NOT NULL DEFAULT 'unknown',
  ADD COLUMN content_eligible TINYINT(1) NULL DEFAULT NULL,
  ADD COLUMN identity_evidence TEXT NULL,
  ADD INDEX idx_identity_status (identity_status);
```

约束：

- 旧行因列默认值成为 `unknown`，不推断为 `verified`。
- `content_eligible=NULL` 表示历史缺少证据，不解释成 false。
- `identity_evidence` 保存规范化 JSON 文本，不保存 Cookie、凭据或完整请求头。
- 应用必须检测列是否存在。迁移前：
  - 历史读取按 `unknown` 工作。
  - URL 可验证路径保持原行为。
  - 若准备写入 pending、内容资格或身份证据而目标库缺少列，必须明确失败并给出 `identity_schema_migration_required`，不能静默丢弃状态后写库。
- 新记录 `content_eligible=false` 时不得进入 B1/B2/B2.2/B3；历史 NULL 保持既有可分析行为，不能被解释为 false。

## 备份、迁移与回退

执行 DDL 前必须单独获得用户许可，并完成：

1. 停止该项目写入进程，确认无 M1/M2 写事务。
2. 记录代码 SHA、连接目标 host/port/database、`SHOW CREATE TABLE jd_pool`、八表行数和有序内容摘要。
3. 使用 `mysqldump --single-transaction --quick --routines --triggers` 生成私有冷备，记录 SHA-256、文件大小和时间。
4. 将备份恢复至隔离实例，核对 `SHOW CREATE TABLE`、八表行数和全字段有序摘要；恢复验证不得使用演示库或生产容器。
5. 仅在备份验证通过后执行追加列 DDL，并复查旧行 `identity_status='unknown'`、`content_eligible IS NULL`、行数和内容摘要不变。

回退设计：

- 默认回退是应用回退；新增列可被旧代码安全忽略，不删除字段。
- 新代码在旧 schema 下继续读取历史并保持 verified 路径，pending 写入显式关闭。
- 如果迁移后尚无 pending 数据且用户明确授权，才可评估 `DROP COLUMN`；已有 pending 或身份证据时必须先导出并再次获得删除许可。
- 不通过恢复整个数据库覆盖迁移后的合法新数据；只有迁移失败或内容摘要不一致时才按已核验冷备恢复。

## M2 行为

- pending 记录可完成 B1、B2、B2.2、B3 候选分析。
- item、report、逐条详情和下载报告携带：
  - `identity_status`
  - `content_eligible`
  - `identity_evidence`
  - `formal_statistics_eligible=false`
  - `confirmed_demand_eligible=false`
- 汇总增加 verified/pending/unknown 与 content_eligible 计数。
- pending 不增加已确认独立岗位数或正式技能需求统计。
- 身份状态不替换 B1 有效性、范围、B2 五态或 B3 审核状态。

## M3 行为

- `sources.json` 中每条源记录携带身份状态与证据摘要。
- M3 manifest 增加身份计数，并保持 `formal_statistics_eligible=false`。
- pending 可形成候选观察节点和技能陈述边，但节点/详情明确显示“身份待审”。
- 不把 pending 节点宣称为唯一岗位、正式职业或已确认能力需求。
- 不写 Neo4j，不提升正式目录。

## 离线回放验收

使用本次私有事件的 5 条真实标题和正文作为内容输入；旧事件没有点击前后面板快照，因此不能反推或宣称这 5 条原本已正确绑定。

回放必须覆盖：

- 合法 pending：面板变化、目标 active、两次稳定、标题一致、正文合格。
- 异步错岗：点击后仍显示上一条详情。
- 相同标题：同标题不同卡片但面板未更新。
- 面板不更新：点击前后摘要相同。
- 空正文与截断正文。
- 同一观察重复处理产生同一 fingerprint 并去重。
- 不同观察时间产生不同 fingerprint，不自动合并。

离线回放通过后，才能申请一次有上限的真实采集验收；真实入库数由新的绑定与内容校验实际决定，不预设 5 条全部合格。
