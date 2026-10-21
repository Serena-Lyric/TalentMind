# P0 数据事故影响与隔离恢复预演报告（2026-10-22）

> **执行边界：** 本报告对应的本轮只执行正式 MySQL/Neo4j 只读核查、本机备份鉴定、隔离 MySQL 恢复与回退预演。未恢复正式库，未执行正式身份字段 DDL，未修改正式 Neo4j，未重新采集智联 pending 证据。

## 1. 结论

1. 2026-10-21 的全量 pytest 确实执行了 MySQL 默认导入和 Neo4j 清图导入。
2. 正式 MySQL 的四张表发生实质变化：`skill_dict/job_definition/job_skill/job_change_log`。
3. `jd_pool/signal/resume/talent_raw` 行内容未变，但 `jd_pool/talent_raw` 的 `AUTO_INCREMENT` 因测试插入后清理而前移，不能表述为表对象“完全未变”。
4. 正式 Neo4j 虽有清空重建执行，但当前 7,845 节点、11,412 关系及其全部 ID、标签、关系类型和属性与事故前一致；没有观测到图内容差异。
5. 2026-10-17 MySQL 冷卷在隔离实例复算后，八张表 SHA-256 与 2026-10-21 12:47 的事故前摘要逐表完全一致，可作为首选恢复源。
6. 仅恢复四张受影响表即可在隔离实例精确回到事故前内容；预先保存的事故后四表 dump 也能精确回退。
7. 正式恢复仍待用户下一次单独批准。本报告不构成执行授权。

## 2. 本轮授权与未执行事项

- 已执行：正式库只读查询、备份文件哈希与压缩完整性检查、隔离 MySQL 启动与恢复、Neo4j 只读全内容比对、代码安全门禁加固。
- 未执行：正式 `DELETE/TRUNCATE/ALTER/INSERT/UPDATE`、正式 DDL、正式 Neo4j 清图或重建、正式 M2 数据重导、真实采集、PR #48/#49 合并。
- PR #48 保持独立，等待合并授权；PR #49 保持 Draft Hold。

## 3. 当次测试执行证据

上一 Codex 会话记录的完整命令与结果：

| 项目 | 证据 |
|---|---|
| 本地时间 | 2026-10-22 01:56:12（UTC 2026-10-21 17:56:12） |
| 命令 | `.\.venv\Scripts\python.exe -m pytest -q` |
| 结果 | `3 failed, 1548 passed, 20249 warnings in 416.10s` |
| Neo4j 用例 | warnings 明确列出 `tests/test_integration_mvp.py::test_import_graph_idempotent`，来源 `app/integration/import_graph.py:23` |
| MySQL 审计 | `data/local/m2-import/2026-09-02-full-import.json` 于同日 01:50:04 被改写，记录导入 719 定义、243 日志，结果 `285/719/719/243` |

`test_import_graph_idempotent()` 依次调用两次 `import_graph()`，每条路径都会执行 `MATCH (n) DETACH DELETE n`；该用例线性执行并通过，warning 又直接点名该用例，因此两次清图导入均实际发生。

仓库根目录旧文件 `data/local/pytest_verbose.log` 的修改时间是 2026-08-15 00:08:18，是旧日志，不能作为本次事故证据。

私有摘录：[incident-test-evidence.md](../../data/local/phase1-acceptance-20261022/forensics/incident-test-evidence.md)。

## 4. 事故前原像与恢复源

### 4.1 最近事故前摘要

首选证据为：

`D:\backup\TalentMind-unify-20261021-1930\integration-data\product-integration-20261020\after-batch-ui-20261021\summary.json`

- 文件时间：2026-10-21 12:47:08 +08:00
- 大小：2,121 bytes
- SHA-256：`76DA99714FF7D7F4C623EC9F0A616FD89C49D473D903A4D03270FE35BEDDB415`
- 覆盖：八张 MySQL 表的行数、全行规范 SHA-256；Neo4j 完整物理哈希；`graph.json` 文件哈希。

### 4.2 首选可恢复实例

`D:\backup\TalentMind-mysql-start-20261017-090847\mysql_data.tar.gz`

- 大小：459,457,425 bytes
- SHA-256：`BB4FF89071C72DB41A7109572E1ADF0A706F99F899B227BA7F7E6D04EBC485B3`
- gzip/tar 完整性：通过，191 个条目
- 隔离启动后复算：八张表的行数和 SHA-256 均与 2026-10-21 12:47 摘要一致

因此它不是“凭三表行数猜测可用”的旧 SQL，而是经过全内容摘要交叉验证的最近事故前实例。复制卷保留原 `server_uuid`，所以隔离身份同时使用容器 hostname、端口和隔离部署记录区分。

### 4.3 其他备份定位

| 来源 | 日期 | 用途判断 |
|---|---|---|
| `TalentMind-mysql-start-20261017-090847/mysql_data.tar.gz` | 2026-10-17 | **首选**；与 10-21 八表摘要完全一致 |
| `TalentMind-2026-10-14/snapshots/mysql-current-20261014.sql` | 2026-10-14 | 备选全库 SQL；比首选旧，未选为主恢复源 |
| `TalentMind-2026-10-14/snapshots/neo4j.dump` | 2026-10-14 | Neo4j 历史备份；本轮未恢复，因为正式图完整内容未变 |
| `data/local/talentmind-db-full-20260904.sql` | 2026-09-04 | 历史基线；`jd_pool=2984`，**不用于直接恢复** |
| 本轮 `current-incident.sql` | 2026-10-22 | 回退/事故后状态，不是恢复原像 |

9 月 4 日 SQL 与 10 月 17 日冷卷、10 月 21 日摘要均不同；没有因三张分析表行数同为 717/717/275 而直接采用。

## 5. MySQL 事故前后精确差异

哈希算法与事故前审计一致：取每行字段的排序 JSON，对全表行规范排序后再做 SHA-256。

| 表 | 前→后行数 | 前 SHA-256 | 后 SHA-256 | 主键范围前→后 | AUTO_INCREMENT 前→后 |
|---|---:|---|---|---|---|
| `jd_pool` | 2988→2988 | `2533192d7257866f94c348628b62a14ec09590bc21af27824a7feb399810c111` | 同前 | 125132–258122→同前 | 258123→258126 |
| `signal` | 1540→1540 | `f31598d5eb542e3329c1955f55f6262f7d81435daa8a9372d3a33f3eb6baa1d3` | 同前 | 141–1680→同前 | 1681→1681 |
| `skill_dict` | 285→285 | `eb3ef5c193d71379fb69a5b2708773acf2cd291e5fa92debd3aecd1892f0d8c5` | `2291976da2bfca90d1316ce08a70f7ad3e7b367203806fb3830728190088bc22` | 56716–57000→57286–57570 | 57001→57571 |
| `job_definition` | 717→719 | `f3d362a93099cd414e3d6fb8e9b9dce4bff74748a97525b02344b10340ec5a76` | `b91fa68b0d3394b0fcd312d2a856a426500c165a79d40fa704741f52fb7213da` | 61061–61779→62501–63219 | 61782→63222 |
| `job_skill` | 717→719 | `517f313455a0270fc26921927dfc59d316824b96ab50d07e0dbfcdf3305dd185` | `357b7984b661a5f84710fea13def76c3677866b8bf4fb551a3006a6a0a8abf77` | 60895–61613→62333–63051 | 61614→63052 |
| `job_change_log` | 275→243 | `1e9c3b8b3e4d707eb286e88a055a55035129a2d256290328ab237e8e707d6ef9` | `327edd357ec389c1b589ecae3b59e20fd98af9876523fce46f08e4a0a7d47425` | 8823–9098→9342–9584 | 9099→9586 |
| `resume` | 0→0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 同前 | — | 1→1 |
| `talent_raw` | 0→0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 同前 | — | 147→149 |

完整 64 位哈希和逐行数据在私有审计输出 `data/local/phase1-acceptance-20261022/forensics/current-run/summary.json`。

### 5.1 `skill_dict`

- 285 个 `canonical` 集合完全相同。
- 全部 285 行的 `canonical/aliases/category` 内容相同，无新增、删除或字段变化。
- 全部主键统一后移 570：56716–57000 → 57286–57570。
- 唯一变化是主键及 `AUTO_INCREMENT`。因此“285 行未变”在业务集合层面成立，在身份和物理状态层面不成立。

### 5.2 `job_definition`

- 717 个既有 `m2_job_id` 的业务字段完全不变。
- 全部既有主键统一后移 1440。
- 新增两项原回包岗位：

  | m2_job_id | 岗位 | 当前主键 | 当前 job_skill 主键 |
  |---|---|---:|---:|
  | `j_acb705a6c9d5c774` | AI测试开发工程师 | 62549 | 62381 |
  | `j_a8a3f7c81b344626` | 博士后 | 62762 | 62595 |

### 5.3 `job_skill`

- 717 个既有 `m2_job_id` 的 `skills/duties/extracted_at/job_name` 等内容不变。
- 717 行的 `jd_id` 全部随 `job_definition.id` 重映射。
- 全部既有主键统一后移 1438。
- 新增上述两个岗位对应的两条技能记录。

### 5.4 `job_change_log`

- 243 条原回包日志全部保留，除 `id/job_id` 外的全部业务字段和关联岗位一致。
- 243 条主键统一后移 519。
- 删除的 32 条全部是原演示趋势日志，原 ID 为连续的 9067–9098：

| 原 ID | 关联 m2_job_id | 类型 | 技能/字段 | 原 created_at |
|---:|---|---|---|---|
| 9067 | `j_c367c6127a78f75b` | added | 大模型能力边界认知 | 2025-09-12 10:20:00 |
| 9068 | `j_c367c6127a78f75b` | added | 提示词工程 | 2025-12-20 10:20:00 |
| 9069 | `j_c367c6127a78f75b` | added | 模型输出评测与幻觉治理 | 2026-03-16 10:20:00 |
| 9070 | `j_c367c6127a78f75b` | scenarios_added | 面向企业客户的生成式AI落地 | 2026-05-20 10:20:00 |
| 9071 | `j_c367c6127a78f75b` | duties_changed | core_duties | 2026-07-28 10:20:00 |
| 9072 | `j_4c494818f30839fe` | added | AI辅助开发 | 2025-08-25 10:20:00 |
| 9073 | `j_4c494818f30839fe` | added | DevSecOps | 2025-11-18 10:20:00 |
| 9074 | `j_4c494818f30839fe` | scenarios_added | AI辅助下的安全关键系统软件交付 | 2026-04-14 10:20:00 |
| 9075 | `j_4c494818f30839fe` | duties_changed | core_duties | 2026-06-30 10:20:00 |
| 9076 | `j_f6dd5eb6f9c5c2e4` | added | 实时流处理 | 2025-07-08 10:20:00 |
| 9077 | `j_f6dd5eb6f9c5c2e4` | added | 数据湖仓 | 2025-10-15 10:20:00 |
| 9078 | `j_f6dd5eb6f9c5c2e4` | added | DataOps | 2026-01-20 10:20:00 |
| 9079 | `j_f6dd5eb6f9c5c2e4` | scenarios_added | 实时行情/风控数据管道 | 2026-03-25 10:20:00 |
| 9080 | `j_f6dd5eb6f9c5c2e4` | duties_changed | core_duties | 2026-06-05 10:20:00 |
| 9081 | `j_08fba6baee0305fa` | added | Microsoft Entra ID | 2025-06-30 10:20:00 |
| 9082 | `j_08fba6baee0305fa` | added | 条件访问与MFA策略管理 | 2025-10-22 10:20:00 |
| 9083 | `j_08fba6baee0305fa` | added | Intune现代端点管理 | 2026-01-16 10:20:00 |
| 9084 | `j_08fba6baee0305fa` | scenarios_added | 混合云身份与零信任端点环境 | 2026-03-20 10:20:00 |
| 9085 | `j_08fba6baee0305fa` | duties_changed | core_duties | 2026-06-12 10:20:00 |
| 9086 | `j_37038210e90a03bd` | added | AI辅助测试 | 2025-08-05 10:20:00 |
| 9087 | `j_37038210e90a03bd` | added | Playwright | 2025-12-03 10:20:00 |
| 9088 | `j_37038210e90a03bd` | scenarios_added | AI辅助的UI/API回归自动化 | 2026-02-27 10:20:00 |
| 9089 | `j_37038210e90a03bd` | duties_changed | core_duties | 2026-05-15 10:20:00 |
| 9090 | `j_f8c008d68b929d6b` | added | 车辆网络安全合规 | 2025-06-20 10:20:00 |
| 9091 | `j_f8c008d68b929d6b` | added | OTA灰度发布与回滚编排 | 2025-09-25 10:20:00 |
| 9092 | `j_f8c008d68b929d6b` | scenarios_added | 软件定义汽车整车软件持续升级 | 2026-02-12 10:20:00 |
| 9093 | `j_f8c008d68b929d6b` | duties_changed | core_duties | 2026-05-08 10:20:00 |
| 9094 | `j_aef49d734b627053` | added | Microsoft Fabric | 2025-05-28 10:20:00 |
| 9095 | `j_aef49d734b627053` | added | 湖仓交付与运维 | 2025-09-10 10:20:00 |
| 9096 | `j_aef49d734b627053` | added | DataOps/数据管道CI-CD | 2026-01-14 10:20:00 |
| 9097 | `j_aef49d734b627053` | scenarios_added | Microsoft Fabric湖仓平台交付与运维 | 2026-04-22 10:20:00 |
| 9098 | `j_aef49d734b627053` | duties_changed | core_duties | 2026-07-30 10:20:00 |

关联岗位分别为技术产品经理、软件工程师、金融数据工程师、高级 Windows 系统管理员、质量保证工程师、Java 后端工程师（OTA）、Azure 数据 DevOps 工程师。完整 reason/detail 在私有审计 JSON 中保留。

## 6. 关联完整性与表结构

- 当前 719 条 `job_skill.jd_id` 全部能在 `job_definition.id` 中找到。
- 当前 719 条 `job_skill.m2_job_id` 全部能在 `job_definition.m2_job_id` 中找到。
- 当前 `job_change_log` 243 条中，240 条非空 `job_id` 全部有效，3 条为空；与事故前 272 条有效、3 条为空的规则一致。
- `job_change_log.m2_job_id` 是原回包引用，不少记录不是 `job_definition.m2_job_id` 直接值；前后均为 237 条不能直接匹配，属于既有语义，不是本次新增的断联。
- 数据库当前没有外键、触发器或视图。
- 六张有数据的表结构除 `AUTO_INCREMENT` 值外一致；`jd_pool` 仍无 `identity_status/content_eligible/identity_evidence` 三列。

## 7. 其他表影响

`jd_pool` 与 `talent_raw` 的内容 SHA 前后完全相同，但 `AUTO_INCREMENT` 变化可由当时执行的集成夹具精确解释：

| 测试 | 未提交保留的夹具写入 |
|---|---|
| `test_collect_integration.py::test_csv_to_jd_pool_via_pipeline` | 2 条 `jd_pool` |
| `test_talent_pipeline_integration.py::test_talent_raw_to_database` | 1 条 `talent_raw` |
| `test_talent_pipeline_integration.py::test_mixed_batch_saves_to_both_tables_independently` | 1 条 `jd_pool` + 1 条 `talent_raw` |

合计正好对应 `jd_pool AUTO_INCREMENT +3`、`talent_raw AUTO_INCREMENT +2`。这些测试在 `finally` 中清理了夹具行，因此行数和内容 SHA 相同，但 InnoDB 不因 `DELETE` 回退自增序列。

## 8. Neo4j 完整内容核查

| 项目 | 事故前摘要 | 当前复算 |
|---|---|---|
| 节点 | 7,845 | 7,845 |
| 关系 | 11,412 | 11,412 |
| Job / Skill / Industry | 717 / 4,671 / 2,457 | 717 / 4,671 / 2,457 |
| REQUIRES / APPLIES_TO / RELATED_TO | 8,866 / 2,539 / 7 | 8,866 / 2,539 / 7 |
| 含 `elementId` 的完整物理 SHA | `4cad52d3a81c2a2649b1446014e21687dcbf9cc6ff776c43dbdfacbf548d7e8a` | `4cad52d3a81c2a2649b1446014e21687dcbf9cc6ff776c43dbdfacbf548d7e8a` |
| 去 `elementId` 的语义 SHA | — | `0d6a80fe54bacb78c263c9a28de95c252562ed0efbff9ef621d4bc985b95557d` |

进一步以 `exchange/m3/graph.json`（SHA-256 `6565D56DBC5A267EB90144F078C54F3D0C761C9A98CA29A18B4DC9C6CDDE38E2`）为期望值，比较全部节点属性、关系端点和关系属性：

- 实际多出节点：0
- 期望缺少节点：0
- 实际多出关系：0
- 期望缺少关系：0
- 空 `node_id`：0
- 重复 `node_id`：0

因此本次 Neo4j 清图重建没有造成可观测内容变化，不需要恢复或重建正式图。

## 9. 隔离恢复预演

### 9.1 隔离对象

| 角色 | 容器 | 端口 | 卷 |
|---|---|---:|---|
| 事故前源实例 | `talentmind-forensics-mysql-20261022` | 23307 | `talentmind_forensics_mysql_20261022` |
| 恢复目标实例 | `talentmind-recovery-rehearsal-mysql-20261022` | 23308 | `talentmind_recovery_rehearsal_mysql_20261022` |

两个实例均使用已核验的 `mysql@sha256:7dcddc01f13bab2f15cde676d44d01f61fc9f99fe7785e86196dfc07d358ae2b`，只绑定 `127.0.0.1`。

预演结束后两个容器均以退出码 0 停止，两个命名卷保留；可重新启动继续复核，不会自动连接正式服务。

### 9.2 预演步骤与结果

1. 正式库仅读生成事故后全库 dump：8,357,566 bytes，SHA-256 `DEF2CD8EEEAEB941616E7A4E03A35D0CDF7DDE120B40C015349C1FA22DF013F4`。
2. 导入恢复目标实例，八表计数与正式库一致。
3. 从事故前源实例只导出四张受影响表：2,095,833 bytes，SHA-256 `D0EF1770ECB7C0A7D4360CACE75780EBCCA83FDE7FCA39F81F02B239D9C03CFA`。
4. 恢复前保存恢复目标四表回退 dump：2,082,295 bytes，SHA-256 `0C2F53185CF093CB0B82CFEE317B3C9BE9F6ED77DC099CDB2E892BC8773F5714`。
5. 仅导入四表基线。结果八表 SHA 全部等于事故前摘要：
   - `jd_pool=2988`
   - `signal=1540`
   - `skill_dict=285`
   - `job_definition=717`
   - `job_skill=717`
   - `job_change_log=275`
   - `resume/talent_raw=0`
6. 导入回退 dump。结果四表恢复为 `285/719/719/243`，主键及内容与事故后正式库一致。
7. 再导入四表基线，恢复目标当前保留为“候选恢复后”状态。

## 10. 建议的正式恢复方案（未执行）

获得下一次单独批准后，建议执行：

1. 再次暂停/冻结正式 MySQL 写入，记录应用进程和当前时间。
2. 再次只读核对正式目标 hostname、server_uuid、八表 SHA 和 Neo4j SHA 与事故后快照一致；不一致则停止并重新审计。
3. 新建当前全库冷备和四表回退 dump，计算并记录 SHA-256。
4. 仅从已验证的 2026-10-17 冷卷导出四表，不整库覆盖。
5. 导入 `skill_dict/job_definition/job_skill/job_change_log`，保留当前 `jd_pool=2988` 和 `signal=1540`。
6. 按本报告同一算法复算八表 SHA、主键范围、`AUTO_INCREMENT`、逻辑关联、表结构和身份三列缺席状态。
7. 期望结果：四表及主键回到事故前；其余四表行内容保持当前；Neo4j 不超过只读核验。

不建议为消除测试自增间隙而单独重置 `jd_pool/talent_raw` 的 `AUTO_INCREMENT`。自增间隙不影响业务身份；重置属于额外元数据写入，除非用户明确要求“连序列也精确回到事故前”，否则不应扩大恢复范围。

## 11. 回退方案

- 正式恢复前必须生成新的四表回退 dump；不能复用本报告的隔离回退文件代替正式执行前备份。
- 若恢复后任一断言失败，立即停止应用，按操作名和四表 dump 精确回退到事故后状态。
- 本轮隔离预演已验证该回退路径：四表可以精确恢复为 `285/719/719/243`，主键、业务内容和关联均一致。
- 由于 MySQL 表重建包含 DDL，DDL 会隐式提交，不能把整次恢复宣称为单事务原子操作；应使用完整恢复前冷备、逐表状态检查和可执行回退 dump。

## 12. 测试与破坏性入口安全加固

新增 `backend/app/integration/destructive_guard.py`，在任何写操作前完成：

- MySQL 实测身份：`@@hostname`、`@@server_uuid`、`DATABASE()`、端口、版本。
- Neo4j 实测身份：`db.info()`、`dbms.components()`、脱敏 URI。
- 独立授权文件：操作名、完整目标、目标指纹、授权人和目的、带时区有效期。

保护入口：

- `import_all()`
- `import_skill_dict()`
- `import_job_definitions()`
- `import_job_skills()`
- `import_change_logs()`
- `import_graph()`

`TALENTMIND_ALLOW_INTEGRATION=1` 或 pytest 标记单独存在时仍会拒绝。授权文件不会由代码自动创建。

## 13. 本轮验证

- 安全门禁专项：`15 passed`，覆盖缺失授权、集成环境变量替代授权、目标不符、操作不符、过期、有效授权、实测目标身份，以及所有 MySQL/Neo4j 写入口在拒绝时不执行 SQL。
- 默认 integration 收集：`24 skipped / 1544 deselected`，没有连接或写入正式库。
- 完整非集成回归：`1542 passed / 2 failed / 24 deselected`。两项失败仍是既有 B3 `docs/PRODUCT_DECISIONS.md` 来源哈希/引文不匹配，与本轮安全门禁无关，未修改历史依据“修绿”。
- 对正式 MySQL/Neo4j 实际调用安全门禁时不提供授权文件，二者均抛出 `DestructiveOperationDenied`，未进入写入。
- 全部验证结束后的只读复算显示，八表内容哈希和 Neo4j 物理哈希与审计前完全相同；本轮代码与测试没有新增正式数据库变化。

## 14. 当前状态与待审批

正式 MySQL 仍是事故后状态，正式 Neo4j 内容仍与事故前一致。正式恢复、自增序列处理、正式身份字段 DDL 均未执行。

待用户下一次明确批准的是：按第 10 节冻结写入并仅在正式库恢复四张受影响表，随后按第 6 节完成全量验证；如验证失败，按第 11 节回退。PR #48/#49 状态不变。
