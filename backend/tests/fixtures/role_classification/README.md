# B3-0 合成输入

`input.json` 是一条手写合成 JD；`annotations.json` 显式声明四维未知并保留 pending_review；`taxonomy.empty.json` 的四个集合全部为空。此目录没有正式职业目录、真实 JD、人工真值或模型输出。

数据集必须显式使用 `synthetic-b30`，以匹配标注中的 namespace。fingerprint 是 A InputRecord 的完整 payload SHA-256，不包含 id/crawled_at；修改来源字段后须显式重建标注指纹，不能改证据来迁就旧输入。多方向/主辅/冲突/多职位案例在合成单元测试中，词值只有 family-a/role-a/track-a/level-a 等占位符。

运行命令与事务/重放语义见 [M2 README](../../../app/job_analysis/README.md)。位置通过只证明引文对应，不证明岗位语义正确。
