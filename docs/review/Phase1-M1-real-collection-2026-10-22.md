# Phase 1 M1 原版采集适配与三平台真实验收（2026-10-22）

本报告记录 `codex/phase1-m1-real-collection-20261022` 的真实运行结果。阶段整体**未通过**：智联已证明可以取得列表、正确详情和 `pending` 身份，但正式库缺少身份列；猎聘当前为登录墙；BOSS 扩展尚未由用户装载并点击验证。

## 基线与交付

- 基线：`origin/master@2de9c42`，最新 PR #46 已包含智联身份待审机制。
- 图谱独立 PR：[#48](https://github.com/Serena-Lyric/TalentMind/pull/48)，分支 `codex/graph-node-field-default-20261022`，只包含 `c9608bc`。
- M1 分支保留桥接、扩展、控制台入口、代理回环兼容和 CN 修复；未合并 `master`。
- 正式数据库目标：`localhost:23306/talentmind`。未执行 DDL、未删除或回填真实数据。
- 开发过程中曾错误裸跑后端全量 pytest，触发 integration 默认导入并改写分析层；事故、当前状态和待批准恢复方案见下文，不能把本轮描述为“所有真实表均未变化”。

## 三平台结果

| 平台 | 页面访问 | 列表提取 | 有效详情 | 身份校验 | 数据持久化 | 最终状态 |
|---|---|---|---|---|---|---|
| BOSS | 本轮未重复 CDP 探测；普通浏览器桥接任务已创建，等待用户装载扩展 | 扩展实机 0 | 0 | 0 | 0 | 阻塞：等待用户安装并点击扩展 |
| 智联 | `public_accessible`，目标 Java/北京530 | 真实取得 2–5 条；其中一次标题渲染为空 | 已取得正确正文；慢面板修复后形成 `pending + content_eligible` | 1 条 `pending` 证据完整；错位面板明确拒绝 | 正式库无三列，`identity_schema_migration_required`；INSERT=0 | 阻塞：正式迁移未授权，且标题渲染稳定性仍需复核 |
| 猎聘 | Java、Python/北京均返回登录墙；0 张职位卡片 | 0 | 0 | 无输入 | 未启动任务，INSERT=0 | 阻塞：需要用户在独立 CDP Edge 中正常登录 |

### 智联真实运行

| run_id | 操作与结果 |
|---|---|
| `zhaopin-54b29041709b47e1abdc9851fc2c6e14` | 修复前现场：列表 5、详情尝试/取得/内容合格 3/3/3；3 条均因旧面板未及时更新被拒绝，用户停止 |
| `zhaopin-4f7022878e774f9b8a5b2d7f69b7997f` | 慢面板修复后：列表 5、详情尝试/取得/内容合格 2/2/2；1 条因面板短暂未稳定拒绝，1 条正确绑定为 `pending`；用户停止 |
| `zhaopin-8ac0cae954e54beaaae15ab5fe550025` | 2 列表、2 详情取得、2 内容合格、1 pending、1 panel_unstable；worker 在写库前退出 `identity_schema_migration_required`，INSERT/UPDATE=0 |
| `zhaopin-6bb7cd1bb2c84273a66a5e6d7893e974` | 后续复测出现列表标题为空；详情正文存在但目标卡片无标题，正确拒绝为 `invalid_detail_body`，停止；说明当前站点渲染稳定性仍未完全收口 |

真实 pending 样本为“产品架构师”，其详情标题、目标卡片、面板变化和两次稳定样本一致；完整正文只保存在忽略的 `data/local/collection/`，不进入公开仓库。`pending` 没有写成已验证岗位，也没有进入 `jd_pool`。

### 猎聘真实运行

- Java/北京与 Python/北京均打开正常搜索页，但页面显示“没有合适职位”及右侧 `APP扫码 / 打开猎聘APP` 登录墙。
- 最终准备状态：`login_required / manual_login_gate`，可见卡片 0。
- 未点击开始任务，未尝试验证码、扫码登录或绕过限制。
- 私有截图：`data/local/phase1-acceptance-20261022/liepin-python-beijing.png`。

### BOSS 普通浏览器桥接

- 本地桥接任务 `bridge-be5013de302e410d97bf54fce2621dc1` 已由正式采集页创建，配置为 BOSS/Java/北京，当前等待人工采集。
- 扩展代码、固定公钥 ID、令牌、Origin/Host/跨站门禁、列表/详情抽取和复用 M1 入库管道的测试均已完成。
- 本轮没有由 Codex 操作用户普通 Edge 或安装扩展；实机页面输入、真实事件和入库仍等待用户点击。

## 数据库迁移隔离验证

正式库采前只读核查：

- `jd_pool=2988`，其中 BOSS 1137、智联 1088、猎聘 763。
- 三列 `identity_status/content_eligible/identity_evidence` 均不存在。
- 私有采前 `jd_pool` dump：6,158,017 bytes，SHA-256 `09A4F0ACF583FC9E48B668FA93028B8244FFCAA199551051B6382A62C5F82C66`。

临时 MySQL 8.0 容器结果：

- 恢复 2988 行后，旧 schema 下 pending 写入明确失败：`identity_schema_migration_required`。
- 应用 `backend/app/contracts/migrations/2026-10-21-jd-pool-identity-status.sql` 后，三列和 `idx_identity_status` 存在。
- 历史行保持 `identity_status=unknown`、`content_eligible=NULL`、`identity_evidence=NULL`。
- 隔离夹具 pending 行成功写入 1 条，随后随临时容器删除。
- 临时容器清理核验为不存在；全程未连接或修改正式 Neo4j、M2 正式表或其他业务表。

正式迁移仍需用户另行批准。建议批准内容：冻结 M1 写入、重新采集正式 schema/八表计数与摘要、生成冷备、完成隔离恢复、执行追加 SQL、行数和历史含义对账；默认回退为应用回退并保留新增列。

## 验证事故与当前正式数据

在后续验证中，Codex 错误使用裸 `pytest -q`，未排除 integration。当次结果为 `1548 passed / 3 failed`；`test_import_exchange_idempotent` 调用默认 `import_all()`，`test_import_graph_idempotent` 的 warning 也直接证明两次清图导入实际执行：

| 项目 | 事故前/批准基线 | 事故后当前值 | 状态 |
|---|---:|---:|---|
| `jd_pool` | 2988 | 2988 | 内容 SHA 未变；`AUTO_INCREMENT` 258123→258126 |
| `signal` | 1540 | 1540 | 内容 SHA 和自增均未变 |
| `skill_dict` | 285 | 285 | 业务内容相同，但 285 个主键统一 +570 |
| `job_definition` | 717 | 719 | **被测试改写** |
| `job_skill` | 717 | 719 | **被测试改写** |
| `job_change_log` | 275 | 243 | **被测试改写** |
| Neo4j | 7845 / 11412（Job 717） | 7845 / 11412（Job 717） | 节点/关系/属性及物理哈希均一致 |

- 事故后三表私有 dump：`data/local/phase1-acceptance-20261022/analysis-after-accidental-integration-20261021T175645Z.sql`，2,069,818 bytes，SHA-256 `AE587AB5D719F2D5154B586AC41276174EEC1D880BD5734B9A34E76E068F82DD`。
- 首选恢复源改为 `D:\backup\TalentMind-mysql-start-20261017-090847\mysql_data.tar.gz`：隔离复算八表 SHA 与 2026-10-21 12:47 事故前摘要完全一致。不能整库回灌；若获批准，应仅恢复四张受影响表，保留当前 2988 条原始 JD。
- 未执行任何恢复、DELETE、TRUNCATE、DDL 或 Neo4j 重建。
- 隔离 MySQL 已完成候选恢复与回退预演，正式库仍未变。新增 `backend/tests/conftest.py` 和破坏性导入授权门禁；`TALENTMIND_ALLOW_INTEGRATION=1` 单独存在也不能放行清库。
- 完整差异、备份哈希、关联核对和恢复/回退证据见 [P0 数据事故报告](P0-data-incident-restore-rehearsal-2026-10-22.md)。

## 验证

- CN/浏览器/控制器相关：168 passed。
- 浏览器运行专项：63 passed。
- CN 详情专项：21 passed。
- 回环桥接安全、schema、会话和用例：28 passed。
- 测试入口门禁：2 passed；无许可 integration 收集结果 `24 skipped / 1529 deselected`。
- 两个既有 B3 文档来源摘要失败未通过修改历史依据来“修绿”。

## 需要用户完成或批准

1. 猎聘：在独立 CDP Edge（控制台打开的采集浏览器）中完成一次正常登录，随后告知可“重新检查猎聘”。Codex 不处理账号、验证码或扫码。
2. BOSS 扩展：在 `edge://extensions` 开启开发人员模式，加载 `frontend/bridge-extension`；从 TalentMind 采集页读取当前桥接任务 ID 和配对令牌，填入扩展。用户在普通 Edge 手动打开一个正常可访问的 BOSS 岗位详情并主动点击“采集当前详情”。
3. 正式 DDL：审查本报告和隔离恢复结果后，单独批准正式迁移；批准前不得执行正式 DDL。
4. 测试事故恢复：审查 P0 报告后另行批准正式冻结与四表恢复；当前 `285/719/719/243` 不得称为基线。正式 DDL 与本项恢复仍分别授权。

在这些人工/授权条件完成前，不宣称三平台真实采集整体通过。
