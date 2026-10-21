# P0 正式数据库恢复最终报告（2026-10-22）

> **状态：** 已按用户单独授权完成一次限定范围的正式 MySQL 四表恢复。八张表内容、主键、结构和关联均与 2026-10-21 事故前基线一致。未执行身份字段 DDL、M2 重导、Neo4j 重建、真实采集或 PR 合并。

## 1. 授权与实际目标

授权目标为 `localhost:23306/talentmind`。执行时独立核实：

| 项目 | 实际值 |
|---|---|
| Windows 宿主端口 | `23306`，监听进程为 Docker/WSL 代理 |
| Docker 容器 | `talentmind-mysql-1` |
| 容器 ID | `c31378b0d6d0808ec3371ca28297a4d7d702a0fd762c496bafaa74225656606a` |
| MySQL 内部端口 | `3306` |
| MySQL `@@hostname` | `c31378b0d6d0` |
| `@@server_uuid` | `037f3e19-85df-11f1-9c85-4692776d435c` |
| 数据库 | `talentmind` |
| 版本 | `8.0.46` |

宿主 `23306` 与内部 `3306` 分别核实，没有把 MySQL 内部端口误当成宿主映射端口。

## 2. 写入冻结

- 使用项目自带的 `scripts/stop-local.ps1` 只停止本工作区后端和前端；后端 PID 28468/24428、前端 PID 11708 退出。
- `18000/18080` 停止监听；MySQL `23306` 保持运行以执行备份和恢复。
- 本机没有匹配 `TalentMind` 的计划任务。
- `data/local/PAUSE_COLLECT` 在冻结前已存在，保持不动。
- 独立 BOSS CDP Edge、智联 pending 证据和文件均未修改。
- MySQL 临时全局 `read_only` 从 `0` 设为 `1`；恢复完成后已还原为 `0`。
- 冻结期间 `information_schema.PROCESSLIST` 只包含 event scheduler 和本次只读审计查询，没有业务连接。

## 3. 恢复源复核

恢复源：

`D:\backup\TalentMind-mysql-start-20261017-090847\mysql_data.tar.gz`

- 大小：459,457,425 bytes
- SHA-256：`BB4FF89071C72DB41A7109572E1ADF0A706F99F899B227BA7F7E6D04EBC485B3`
- 隔离启动后八表行数与完整内容 SHA 均与 2026-10-21 12:47 事故前摘要一致。
- 重新导出的四表 SQL 与预演文件逐字节一致：2,095,833 bytes，SHA-256 `D0EF1770ECB7C0A7D4360CACE75780EBCCA83FDE7FCA39F81F02B239D9C03CFA`。

## 4. 新备份与恢复验证

新的独立备份根：

`D:\backup\TalentMind-p0-restore-20261022-0246`

| 备份 | 大小 | SHA-256 | 验证 |
|---|---:|---|---|
| 全库逻辑备份 `formal-full-before-restore.sql` | 8,357,566 | `DEF2CD8EEEAEB941616E7A4E03A35D0CDF7DDE120B40C015349C1FA22DF013F4` | 恢复到隔离 MySQL，八表 SHA 与正式库一致 |
| 四表回退 `formal-four-tables-before-restore.sql` | 2,082,295 | `0C2F53185CF093CB0B82CFEE317B3C9BE9F6ED77DC099CDB2E892BC8773F5714` | 先恢复全库、再覆盖四表，八表 SHA 与正式库一致 |
| MySQL 卷级冷备 `talentmind_mysql_data-before-restore.tar.gz` | 17,946,012 | `C6885937293441E3FEE6A8C217C6110F782965B47CA62E8AD2BD682BAF90F0FA` | tar 可读取，192 条目；恢复到新隔离卷后八表 SHA 和主键/自增元数据一致 |

卷级冷备恢复使用独立容器 `talentmind-formal-cold-verify-20261022` 和新卷 `talentmind_formal_cold_verify_20261022`，未连接正式库。

备份目录另含：

- `backup-manifest.json`
- `SHA256SUMS.txt`
- 恢复前全库审计、四表回退验证、卷级冷备验证、正式恢复后审计 JSON

`SHA256SUMS.txt` 中 12 个文件逐一重算通过；清单文件本身 SHA-256 为 `1C65629BF36B46B1EBF4C297FA3ABB706D5433A123FC5C87CB10F2C326A47AA7`，`backup-manifest.json` 为 `9288E949BFDADFDCF66F1EF5BC7796FBC58C3985B00FBCA5EC0C7612D3058280`。备份目录共 13 个文件，约 30.79 MB。

## 5. 正式恢复执行

| 项目 | 值 |
|---|---|
| 开始时间 | 2026-10-22 02:49:27.298942 +08:00 |
| 完成时间 | 2026-10-22 02:49:29.053319 +08:00 |
| 操作 | 直接导入已验证的四表 SQL |
| 退出码 | `0` |
| 调用 `import_all()` | 否 |
| 调用 `import_graph()` | 否 |
| 恢复前回退 | 已准备但未触发 |

恢复对象仅为 `skill_dict/job_definition/job_skill/job_change_log`。没有整库回灌，没有覆盖 `jd_pool/signal/resume/talent_raw`。

## 6. 八表恢复结果

哈希算法与本项目 P0 审计脚本一致：每行字段规范 JSON，整表行规范排序后计算 SHA-256。

| 表 | 恢复前/后行数 | 恢复前完整 SHA-256 | 恢复后完整 SHA-256 |
|---|---:|---|---|
| `jd_pool` | 2988 / 2988 | `2533192d7257866f94c348628b62a14ec09590bc21af27824a7feb399810c111` | `2533192d7257866f94c348628b62a14ec09590bc21af27824a7feb399810c111` |
| `signal` | 1540 / 1540 | `f31598d5eb542e3329c1955f55f6262f7d81435daa8a9372d3a33f3eb6baa1d3` | `f31598d5eb542e3329c1955f55f6262f7d81435daa8a9372d3a33f3eb6baa1d3` |
| `skill_dict` | 285 / 285 | `2291976da2bfca90d1316ce08a70f7ad3e7b367203806fb3830728190088bc22` | `eb3ef5c193d71379fb69a5b2708773acf2cd291e5fa92debd3aecd1892f0d8c5` |
| `job_definition` | 719 / 717 | `b91fa68b0d3394b0fcd312d2a856a426500c165a79d40fa704741f52fb7213da` | `f3d362a93099cd414e3d6fb8e9b9dce4bff74748a97525b02344b10340ec5a76` |
| `job_skill` | 719 / 717 | `357b7984b661a5f84710fea13def76c3677866b8bf4fb551a3006a6a0a8abf77` | `517f313455a0270fc26921927dfc59d316824b96ab50d07e0dbfcdf3305dd185` |
| `job_change_log` | 243 / 275 | `327edd357ec389c1b589ecae3b59e20fd98af9876523fce46f08e4a0a7d47425` | `1e9c3b8b3e4d707eb286e88a055a55035129a2d256290328ab237e8e707d6ef9` |
| `resume` | 0 / 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `talent_raw` | 0 / 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

恢复后八表与事故前源实例逐表内容相同。

## 7. 主键、结构与关联

| 表 | 恢复后主键范围 | AUTO_INCREMENT |
|---|---|---:|
| `skill_dict` | 56716–57000 | 57001 |
| `job_definition` | 61061–61779 | 61782 |
| `job_skill` | 60895–61613 | 61614 |
| `job_change_log` | 8823–9098 | 9099 |
| `jd_pool` | 125132–258122 | 258126（未重置） |
| `signal` | 141–1680 | 1681 |
| `resume` | 空 | 1 |
| `talent_raw` | 空 | 149（未重置） |

- 只恢复四张表的表结构与其事故前结构一致。
- `jd_pool` 身份三列仍不存在：`identity_status/content_eligible/identity_evidence` 均未新增。
- 当前数据库外键、触发器、视图数量均为 0，与恢复前一致。
- 717 条 `job_skill.jd_id` 全部关联有效 `job_definition.id`。
- 717 条 `job_skill.m2_job_id` 全部关联有效 `job_definition.m2_job_id`。
- 275 条 `job_change_log` 中 272 条非空 `job_id` 全部有效，3 条为空；与事故前一致。
- 恢复前后逻辑关联统计完全相同。

## 8. Neo4j 只读核验

| 项目 | 结果 |
|---|---|
| 节点 / 关系 | 7,845 / 11,412 |
| Job / Skill / Industry | 717 / 4,671 / 2,457 |
| REQUIRES / APPLIES_TO / RELATED_TO | 8,866 / 2,539 / 7 |
| 含 `elementId` 物理 SHA | `4cad52d3a81c2a2649b1446014e21687dcbf9cc6ff776c43dbdfacbf548d7e8a` |
| 节点内容一致 | 是 |
| 关系多重集一致 | 是 |
| 空或重复 `node_id` | 0 / 0 |

未执行 Neo4j 清图、重建或属性写入。

## 9. 回退结果

本次恢复所有关键断言通过，未触发回退。新四表回退备份已经在隔离 MySQL 中实测可恢复到事故后 `285/719/719/243` 状态，八表 SHA 与冻结时正式库一致。

## 10. 服务与当前状态

- 正式 MySQL 健康，`read_only` 已恢复为原值 `0`。
- 本地后端和前端已按原入口重启：后端健康 `up`，`/api/jobs` 返回 717，前端监听 18080。
- 采集状态为 `stopped`，`PAUSE_COLLECT` 仍存在。
- 智联 pending 事件、日志与私有截图均保留，没有重新采集或覆盖。
- 三个隔离 MySQL 容器均以退出码 0 停止，命名卷保留。
- PR #49 仍为 Draft，PR #48 未改动；本次没有合并任何 PR。

## 11. 额外变化

除四张授权表的恢复外，没有发现额外业务数据变化。`jd_pool` 和 `talent_raw` 的既有自增间隙未被重置。Neo4j 只读内容未变化。

最终恢复后与服务重启后的两次独立全量审计均通过，正式状态已稳定。
