# integration

`python -m app.integration.real_jd_export --sql <已有备份> --output <新私有目录> --per-platform 40` 仅解析 jd_pool，不执行 SQL；也提供显式 `--env` 的 READ ONLY 导出。用于[真实链路隔离验证](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/review/M1-M5-real-jd-e2e.md)，不连接旧导入器或恢复生产重建。

A 负责的交接导入、模块编排和完整系统组装入口。

已实现交接导入与编排：`validate_exchange.py`（schema/change_type 枚举硬校验、canonical 软校验）、`import_exchange.py`（M2 全量重建导入：job_definition/job_skill/job_change_log）、`import_graph.py`（先清空 Neo4j 再按 graph.json 重建，属于破坏性导入；不是仅 MERGE 的无损同步）。详见代码与 `docs/superpowers/资产与状态.md`。

## 破坏性导入授权（2026-10-22）

`import_all()`、`import_skill_dict()`、`import_job_definitions()`、`import_job_skills()`、`import_change_logs()` 和 `import_graph()` 会在任何插入、清空/DDL/重建写入前调用 `destructive_guard.py`。pytest 的 `integration` 标记和 `TALENTMIND_ALLOW_INTEGRATION=1` 只控制收集与是否进入测试，**不能授权写入**。

每次操作必须同时满足：

1. `TALENTMIND_DESTRUCTIVE_AUTHORIZATION_FILE`（或显式传入的授权文件）存在；
2. 文件中的 `operation` 与本次操作完全一致；
3. 文件中的 `target`、`target_fingerprint` 与实际连接实例完全一致；
4. `expires_at` 尚未到期，且 `authorized_by`、`purpose` 非空。

MySQL 目标身份同时保存 SQLAlchemy 配置的 `host`、实际连接宿主 `connection_port`，以及服务端 `@@hostname`、`@@server_uuid`、`DATABASE()`、`@@port`（`server_port`）和 `VERSION()`。宿主映射端口与容器/服务端端口分别参与指纹；即使克隆卷的 `server_uuid` 相同，不同宿主连接端口也不能复用同一授权。Neo4j 目标身份来自实际数据库 `db.info()`、`dbms.components()` 和脱敏后的 URI。

当前操作名：

- `mysql.import_all`
- `mysql.import_skill_dict`
- `mysql.import_job_definitions`
- `mysql.import_job_skills`
- `mysql.import_change_logs`
- `neo4j.import_graph`

授权文件示例见根目录 `docs/部署与导入说明.md`。授权文件是显式人工步骤；代码不会自动创建，也不会因环境变量或测试标记自动放行。
