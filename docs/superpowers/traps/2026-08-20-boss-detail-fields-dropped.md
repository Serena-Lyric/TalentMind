# BOSS 详情字段未进入数据库

- 症状：BOSS CDP 采集命令显示已补采详情，但新写入 `jd_pool` 的 `raw_text` 只有薪资/地点等列表元数据，职位描述为空。
- 根因：采集器把详情字段合并到列表字典后调用 `normalize_boss_job(job)`；归一化函数只从独立 `detail` 参数读取 `description` 和 `company_info`，没有回退读取已合并的 `raw` 字段。
- 修复：`normalize_boss_job()` 对两个字段同时支持 `detail` 与合并后的 `raw`；新增纯函数测试覆盖合并详情路径。
- 教训：详情采集与归一化之间要明确字段传递契约；统计“详情已采集”不能代替检查最终入库的正文长度。
