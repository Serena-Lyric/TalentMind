# 2026-10-22 M1 真实采集验证与 P0 数据恢复归档

归档日期：2026-10-26。本文保留旧 M1 分支的重要事实与可定位来源，不恢复旧代码，也不构成采集、DDL 或数据恢复授权。
除第 8 节的合入关系及本轮边界外，数据、测试和运行状态均指 2026-10-22 当时，不能当作当前环境复核结果。

## 1. 来源与时间顺序

旧交付为 [PR #49](https://github.com/Serena-Lyric/TalentMind/pull/49)，最终报告来源提交为完整 SHA `5701b1553cea945557eb9ba5edcdcb395288086b`。
旧分支名为 `codex/m1-real-collection-20261022`，早期报告记录的工作分支为 `codex/phase1-m1-real-collection-20261022`；分支删除后仍应通过 PR 与固定提交定位。

| 当时源路径（不是当前本地文件链接） | 固定版本与用途 |
|---|---|
| `docs/review/Phase1-M1-real-collection-2026-10-22.md` | [5701b155 版本](https://github.com/Serena-Lyric/TalentMind/blob/5701b1553cea945557eb9ba5edcdcb395288086b/docs/review/Phase1-M1-real-collection-2026-10-22.md)：三平台尝试、run ID、身份迁移隔离验证与后续状态 |
| `docs/review/P0-data-incident-restore-rehearsal-2026-10-22.md` | [5701b155 版本](https://github.com/Serena-Lyric/TalentMind/blob/5701b1553cea945557eb9ba5edcdcb395288086b/docs/review/P0-data-incident-restore-rehearsal-2026-10-22.md)：事故调查与隔离预演，正文“待批准恢复”属于恢复前时点 |
| `docs/review/P0-formal-restore-final-2026-10-22.md` | [5701b155 版本](https://github.com/Serena-Lyric/TalentMind/blob/5701b1553cea945557eb9ba5edcdcb395288086b/docs/review/P0-formal-restore-final-2026-10-22.md)：另行授权后的正式恢复结果 |
| `docs/review/M1-platform-repair-2026-10-22.md` | [PR #52 合入版本](https://github.com/Serena-Lyric/TalentMind/blob/8017039e97d76389df751571800ec76adf75b5f2/docs/review/M1-platform-repair-2026-10-22.md)：后来按平台重新修复的范围与离线证据 |

关键原始提交：采集报告 `a6cdf1fd4e0cbcbb592c719838ba7a33d7eec277`；测试默认门禁 `843952a1708aa15501ef43d133de282053f59b37`；目标绑定导入授权 `239383cc5e7adc14bb83e449d649e4bfe3a0fff9`；正式恢复报告 `a51b05dddafb759f8dc47f1592e92ab7548aa39d`；恢复前后完整 SHA 补录 `5701b1553cea945557eb9ba5edcdcb395288086b`。

顺序为：真实轻量采集尝试 → 错误全量测试造成事故 → 只读调查与隔离预演 → 用户单独批准 → 02:49 正式四表恢复。
预演报告中的“未恢复正式库”不能覆盖后续“已恢复”结论；后续恢复授权也不能倒推为事故测试已获授权。

## 2. 三平台真实结果与限制

| 平台 | 当时已确认事实 | 当时限制与结果 |
|---|---|---|
| 智联 | Java/北京530 页面 `public_accessible`；取得真实列表与正确详情，形成一条证据完整的 `pending + content_eligible` | 正式库当时没有身份三列，写入前停止；另有空标题与面板不稳定问题，未通过整体真实入库验收 |
| 猎聘 | Java/北京、Python/北京搜索目标均检查到登录墙，可见职位卡片 0 | `login_required / manual_login_gate`；未启动任务、INSERT=0，需用户正常登录 |
| BOSS | 正式采集页创建普通浏览器桥接任务，桥接及扩展完成离线验证 | 用户尚未装载并点击扩展；实机列表/详情/身份/入库均为 0，不宣称真实采集通过 |

智联关键运行保留完整 ID：

| run_id | 当时结果 |
|---|---|
| `zhaopin-54b29041709b47e1abdc9851fc2c6e14` | 修复前列表 5，详情尝试/取得/内容合格 3/3/3；3 条因旧面板未及时更新而拒绝，用户停止 |
| `zhaopin-4f7022878e774f9b8a5b2d7f69b7997f` | 慢面板修复后列表 5，详情 2/2/2；1 条面板短暂不稳定拒绝，1 条正确绑定为 pending，用户停止 |
| `zhaopin-8ac0cae954e54beaaae15ab5fe550025` | 列表 2、详情取得 2、内容合格 2；1 pending、1 panel_unstable；写库前 `identity_schema_migration_required`，INSERT/UPDATE=0 |
| `zhaopin-6bb7cd1bb2c84273a66a5e6d7893e974` | 后续出现列表标题为空；虽有详情正文，因缺目标卡片标题而拒绝为 `invalid_detail_body` |

BOSS 桥接任务为 `bridge-be5013de302e410d97bf54fce2621dc1`，目标 BOSS/Java/北京，等待人工采集。
真实 pending 样本的标题、目标卡片、面板变化和两次稳定采样一致；其完整正文仅保存在忽略的 `data/local/collection/`，未进入公开仓库或 `jd_pool`。
当时没有绕过登录、验证码或反爬，也没有代用户装载扩展或操作普通浏览器实采。

## 3. 当时的身份字段验证

采前只读核查的 `jd_pool=2988`，其中 BOSS 1137、智联 1088、猎聘 763。
当时正式库未执行 `identity_status/content_eligible/identity_evidence` 三列 DDL；后续 P0 四表恢复也未新增它们。
这仅是当时状态，不表示本次整理时点或未来正式库仍缺列。

临时 MySQL 8.0 恢复 2988 行后，旧 schema 写 pending 明确返回 `identity_schema_migration_required`。
隔离实例应用当时的 `2026-10-21-jd-pool-identity-status.sql` 后，三列和 `idx_identity_status` 存在；历史行保持 `unknown/NULL/NULL`，pending 夹具成功写入 1 条。
临时容器随后清理并核验不存在。该结果证明隔离迁移兼容性，不等于正式迁移已执行，也不代替三平台真实入库验收。

## 4. 测试事故原因与影响

事故命令为后端 `.\.venv\Scripts\python.exe -m pytest -q`，未排除 integration；完成时间记录为 2026-10-22 01:56:12 +08（2026-10-21 17:56:12 UTC）。
当次结果 `1548 passed / 3 failed`，不是安全通过证据；MySQL 导入审计在 01:50:04 被改写为 719 定义、243 日志。
`test_import_exchange_idempotent` 调用默认 `import_all()`，读取本地旧回包并改写分析层。
`test_import_graph_idempotent` 依次调用两次 `import_graph()`；两次均实际执行 `MATCH (n) DETACH DELETE n` 后重导，不能表述为“Neo4j 从未被写入”。

MySQL 实质受影响四表为 `skill_dict/job_definition/job_skill/job_change_log`：

- `skill_dict` 285 个 canonical 及业务字段相同，但全部主键 +570；`AUTO_INCREMENT` 57001→57571。
- `job_definition` 717 个既有 m2_job_id 的业务字段不变、主键 +1440；多导入两个旧回包岗位，行数 717→719。
- `job_skill` 既有内容不变、主键 +1438、jd_id 跟随重映射，并多出对应两条记录，行数 717→719。
- `job_change_log` 原回包 243 条保留并重映射，32 条演示趋势日志（原 ID 9067–9098）被移除，行数 275→243；这些演示日志不是新核验的真实趋势。

`jd_pool/signal/resume/talent_raw` 行内容 SHA 未变；测试夹具清理后仍留下 `jd_pool AUTO_INCREMENT` 258123→258126、`talent_raw` 147→149 的自增间隙。
因此不能说所有表对象、全部元数据或所有物理状态完全未变。

## 5. 正式恢复范围与八表摘要

只读调查及隔离恢复、回退预演完成后，用户另行批准正式恢复；目标为 `localhost:23306/talentmind`，容器内部端口为 3306。
2026-10-22 **02:49:27.298942–02:49:29.053319 +08:00**，直接导入已验证四表 SQL，退出码 0。
只恢复 `skill_dict/job_definition/job_skill/job_change_log`，从 `285/719/719/243` 回到 `285/717/717/275`；没有整库回灌、调用 `import_all()` 或恢复中写入 Neo4j。
下表“前”指正式恢复前的事故状态，“后”指正式恢复完成；算法为每行字段规范 JSON、整表行规范排序后的 SHA-256。

| 表 | 恢复前/后行数 | 恢复前 SHA-256 | 恢复后 SHA-256 |
|---|---:|---|---|
| `jd_pool` | 2988 / 2988 | `2533192d7257866f94c348628b62a14ec09590bc21af27824a7feb399810c111` | `2533192d7257866f94c348628b62a14ec09590bc21af27824a7feb399810c111` |
| `signal` | 1540 / 1540 | `f31598d5eb542e3329c1955f55f6262f7d81435daa8a9372d3a33f3eb6baa1d3` | `f31598d5eb542e3329c1955f55f6262f7d81435daa8a9372d3a33f3eb6baa1d3` |
| `skill_dict` | 285 / 285 | `2291976da2bfca90d1316ce08a70f7ad3e7b367203806fb3830728190088bc22` | `eb3ef5c193d71379fb69a5b2708773acf2cd291e5fa92debd3aecd1892f0d8c5` |
| `job_definition` | 719 / 717 | `b91fa68b0d3394b0fcd312d2a856a426500c165a79d40fa704741f52fb7213da` | `f3d362a93099cd414e3d6fb8e9b9dce4bff74748a97525b02344b10340ec5a76` |
| `job_skill` | 719 / 717 | `357b7984b661a5f84710fea13def76c3677866b8bf4fb551a3006a6a0a8abf77` | `517f313455a0270fc26921927dfc59d316824b96ab50d07e0dbfcdf3305dd185` |
| `job_change_log` | 243 / 275 | `327edd357ec389c1b589ecae3b59e20fd98af9876523fce46f08e4a0a7d47425` | `1e9c3b8b3e4d707eb286e88a055a55035129a2d256290328ab237e8e707d6ef9` |
| `resume` | 0 / 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `talent_raw` | 0 / 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

恢复后八表内容与事故前源实例一致；四表结构与主键恢复，既有 `jd_pool/talent_raw` 自增值 **258126/149 未重置**。
四表恢复后主键范围依次为 56716–57000、61061–61779、60895–61613、8823–9098；自增值依次为 57001、61782、61614、9099。
717 条 `job_skill.jd_id` 和 717 条 `job_skill.m2_job_id` 均关联有效岗位；275 条日志中 272 条非空 job_id 有效、3 条为空，与事故前一致。
日志 m2_job_id 不是全部直接等于岗位表 m2_job_id，前后均有 237 条不能直接匹配，属于既有回包语义，不能新增断联结论。
当时外键、触发器、视图数量均为 0；恢复断言通过，未触发回退，服务重启后再次审计通过。

## 6. Neo4j：事故确有重导，恢复阶段没有再写

事故前、事故后以及四表恢复后的 Neo4j 核验均为 7,845 节点 / 11,412 关系。
Job/Skill/Industry 为 717/4,671/2,457；REQUIRES/APPLIES_TO/RELATED_TO 为 8,866/2,539/7。
包含 elementId、标签、类型和属性的完整物理 SHA 均为 `4cad52d3a81c2a2649b1446014e21687dcbf9cc6ff776c43dbdfacbf548d7e8a`；事故后语义 SHA 为 `0d6a80fe54bacb78c263c9a28de95c252562ed0efbff9ef621d4bc985b95557d`。
与当时 `exchange/m3/graph.json`（SHA `6565D56DBC5A267EB90144F078C54F3D0C761C9A98CA29A18B4DC9C6CDDE38E2`）逐项比较，节点/关系多出和缺少均为 0，空/重复 node_id 均为 0。
结论是两次清图重导没有留下可观测内容差异；调查、预演及正式四表恢复阶段仅只读核验 Neo4j，没有再次清图、重建或属性写入。

## 7. 历史备份与摘要定位

以下是原报告当时记录的本地资产及 SHA；本轮未新建或复查备份，不承诺这些路径现在仍存在或可用，也不要求把私有备份入库。

| 历史记录 | 大小（bytes） | 当时 SHA-256 |
|---|---:|---|
| 事故前摘要：`D:\backup\TalentMind-unify-20261021-1930\integration-data\product-integration-20261020\after-batch-ui-20261021\summary.json`（2026-10-21 12:47:08 +08） | 2,121 | `76DA99714FF7D7F4C623EC9F0A616FD89C49D473D903A4D03270FE35BEDDB415` |
| 首选恢复源：`D:\backup\TalentMind-mysql-start-20261017-090847\mysql_data.tar.gz` | 459,457,425 | `BB4FF89071C72DB41A7109572E1ADF0A706F99F899B227BA7F7E6D04EBC485B3` |
| 采前 jd_pool 私有 dump | 6,158,017 | `09A4F0ACF583FC9E48B668FA93028B8244FFCAA199551051B6382A62C5F82C66` |
| 事故后三表 dump（原报告 `analysis-after-accidental-integration-20261021T175645Z.sql`） | 2,069,818 | `AE587AB5D719F2D5154B586AC41276174EEC1D880BD5734B9A34E76E068F82DD` |
| 已验证的事故前四表恢复 SQL | 2,095,833 | `D0EF1770ECB7C0A7D4360CACE75780EBCCA83FDE7FCA39F81F02B239D9C03CFA` |
| 恢复前全库 `formal-full-before-restore.sql` | 8,357,566 | `DEF2CD8EEEAEB941616E7A4E03A35D0CDF7DDE120B40C015349C1FA22DF013F4` |
| 恢复前四表 `formal-four-tables-before-restore.sql` | 2,082,295 | `0C2F53185CF093CB0B82CFEE317B3C9BE9F6ED77DC099CDB2E892BC8773F5714` |
| 恢复前卷备份 `talentmind_mysql_data-before-restore.tar.gz` | 17,946,012 | `C6885937293441E3FEE6A8C217C6110F782965B47CA62E8AD2BD682BAF90F0FA` |

后三项位于当时新建的 `D:\backup\TalentMind-p0-restore-20261022-0246`；全库、四表回退及冷卷均在隔离实例恢复验证。
该目录的 `SHA256SUMS.txt` 当时 SHA 为 `1C65629BF36B46B1EBF4C297FA3ABB706D5433A123FC5C87CB10F2C326A47AA7`，`backup-manifest.json` 为 `9288E949BFDADFDCF66F1EF5BC7796FBC58C3985B00FBCA5EC0C7612D3058280`。
首选冷卷隔离复算的八表行数及 SHA 与 10-21 12:47 摘要逐表一致；9 月 4 日旧 SQL 的 jd_pool=2984，未因三表行数相同而直接用作恢复源。

## 8. 后续合入关系与本轮边界

截至本轮核对的 `master@698999ce1a84218016681090de5d855fa52fd2c6`，以下已合入关系可由 Git 历史定位：

- [PR #50](https://github.com/Serena-Lyric/TalentMind/pull/50)，合并提交 `0414a93329b1cbd1a4666783c8c44cc7af90a709`：M2 真实分析及人工复核；独立带入默认测试隔离与破坏性导入授权门禁，并修正宿主/服务端端口指纹，没有整合 PR #49 的 M1 适配。
- [PR #51](https://github.com/Serena-Lyric/TalentMind/pull/51)，合并提交 `74fa18e0235d83f6488284b4d1a03786755122be`：M2–M3 Gate 3 与人工复核改进，不替代 M1 实采证据。
- [PR #52](https://github.com/Serena-Lyric/TalentMind/pull/52)，合并提交 `8017039e97d76389df751571800ec76adf75b5f2`：智联 `2f95bc3426234aed9625ea394df9d71b0f6304cc` 重新修复慢面板、逐条保存和目标传递；BOSS `2cf77021ee763036e3168af1b3e52b8d74b8a589` 复用并收紧旧桥接，未整包合并 PR #49。
- [PR #53](https://github.com/Serena-Lyric/TalentMind/pull/53)，合并提交 `698999ce1a84218016681090de5d855fa52fd2c6`：用户头像调整，与 M1 实采、身份迁移及数据库恢复无直接关系。

PR #52 的离线证据为后端最终相关 312 passed、前端 177 passed 与类型/构建通过；其源报告明确当轮未装载用户扩展、未向平台采集，不可据此补称真实入库通过。
旧阶段专项测试数字仅保留在固定来源中；本轮不重跑，不把历史通过数累加成新结果。
负责人此前说明 M1 已完成功能实测；本轮保留该说明，不新增三平台精确实测计数或追认旧阶段“全部通过”。当前实现与授权仍应核对现行代码、正式文档和具体执行证据。
本文仅归档必要事实、恢复证据及旧方案与后续交付关系；旧报告内的人工安装、正式 DDL、“待批准恢复”等条目均不是本轮执行清单。
本轮只做文档归档与 Git 整理，未操作正式数据库，未运行真实采集、数据库迁移、恢复或业务测试。
