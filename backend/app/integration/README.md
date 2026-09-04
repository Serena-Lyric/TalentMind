# integration

A 负责的交接导入、模块编排和完整系统组装入口。

已实现交接导入与编排：`validate_exchange.py`（schema/change_type 枚举硬校验、canonical 软校验）、`import_exchange.py`（M2 全量重建导入：job_definition/job_skill/job_change_log）、`import_graph.py`（graph.json → Neo4j MERGE 幂等）。详见代码与 `docs/superpowers/资产与状态.md`。
