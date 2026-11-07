# 图谱视觉对照链接保留数据身份

- 症状：从指定 delivery 运行图进入技术面板的 P2.1–P2.5 视觉对照后，页面丢失运行和快照参数，静默读取默认历史交接图。
- 根因：五个链接硬编码整个查询串，把视觉切换误作数据集切换；相邻空间回退虽然复制查询参数，但仍固定路由 hash。
- 修复：复用复制当前 `URLSearchParams` 的方式，统一只覆盖链接指定的视觉参数；保留 `graphDataset`、`m2DeliveryRun`/`m2Run`、`m2Graph`、其他参数和当前 hash，使用相对查询链接保留部署路径。显式切换历史数据集仍是独立操作，未恢复旧 Canvas 入口。
- 教训：视觉对照应针对同一输入版本。回归必须编译并渲染真实 SFC 模板，再解析实际链接；只测 URL 帮助函数无法发现模板仍绑定硬编码地址。

回归：`frontend/tests/graphRecovery.test.ts` 覆盖五个链接 × delivery、real、显式 legacy、默认历史数据集，检查原运行/摘要、重复及编码参数、已有视觉参数、部署路径和 hash；`galaxyFieldLifecycle.test.ts` 继续验证相邻空间回退。
