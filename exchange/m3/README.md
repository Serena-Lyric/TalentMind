# M3 交接

`graph.json` 为已核验的完整演示交接图，2026-10-15 只读计数为 7845 节点 / 11412 边，含岗位、技能、行业。`overlays/p2-1-layout.json` 是当前 `/#/graph` 使用的只读布局候选。两者均保留；P5 只删除了旧 `builder.py` 的测试回退输入 `mock_job_data.json`，禁止用旧构建器默认输出覆盖正式图。当前交接口径与保留边界见仓库根 `backend/app/graph/README.md`。
