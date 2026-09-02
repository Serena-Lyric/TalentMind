# job_analysis

M2 岗位分析正式目录，已接入 2026-09-01 M2 回包管道源码兼容能力。主要流程为：数据解析/预筛 → 相关性与质量判断 → 技能提取与证据验证 → 合并 → 差异记录 → 交接导出。

- 交接数据：`exchange/m2/`；当前包含 719 条岗位定义和 719 条按 `job_id` 合并后的岗位技能明细，243 条能力更新日志；
- 运行入口：`cd backend && .\.venv\Scripts\python.exe -m app.job_analysis.main --help`；
- 模块配置：LLM 密钥只从环境变量/本地 `.env` 读取，禁止写入源码或回包；
- M2 输出的技能优先使用 `canonical_name`，无法进入 285 条词典的候选仍保留在证据 JSON 中，并在导入审计中记录，不静默删除；
- 旧的 `input/jd-filter-package/` 已被新回包替代并于 2026-08-30 删除，Git 工作树不再依赖该目录。
