# job_analysis

M2 岗位分析正式目录，已接入 2026-08-30 回包管道源码。主要流程为：数据解析/预筛 → 相关性与质量判断 → 技能提取与证据验证 → 合并 → 差异记录 → 交接导出。

- 交接数据：`exchange/m2/`；当前包含 470 条岗位定义和 470 条岗位技能明细；
- 运行入口：`cd backend && .\.venv\Scripts\python.exe -m app.job_analysis.main --help`；
- 模块配置：LLM 密钥只从环境变量/本地 `.env` 读取，禁止写入源码或回包；
- 当前回包中的技能尚有大量未进入 285 条 canonical 词典的候选，属于待 M2 修复的问题，不在集成层静默改写；
- 旧的 `input/jd-filter-package/` 已被新回包替代并于 2026-08-30 删除，Git 工作树不再依赖该目录。
