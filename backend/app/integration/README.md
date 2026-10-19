# integration

`python -m app.integration.real_jd_export --sql <已有备份> --output <新私有目录> --per-platform 40` 仅解析 jd_pool，不执行 SQL；也提供显式 `--env` 的 READ ONLY 导出。用于[真实链路隔离验证](../../../docs/review/M1-M5-real-jd-e2e.md)，不连接旧导入器或恢复生产重建。

A 负责的交接导入、模块编排和完整系统组装入口。

已实现交接导入与编排：`validate_exchange.py`（schema/change_type 枚举硬校验、canonical 软校验）、`import_exchange.py`（M2 全量重建导入：job_definition/job_skill/job_change_log）、`import_graph.py`（先清空 Neo4j 再按 graph.json 重建，属于破坏性导入；不是仅 MERGE 的无损同步）。详见代码与 `docs/superpowers/资产与状态.md`。
