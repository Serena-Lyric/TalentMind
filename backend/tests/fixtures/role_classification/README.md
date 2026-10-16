# B3-0 合成输入

`input.json` 是一条手写合成 JD；`annotations.json` 显式声明四维未知并保留 pending_review；`taxonomy.empty.json` 的四个集合全部为空。此目录没有正式职业目录、真实 JD、人工真值或模型输出。

数据集必须显式使用 `synthetic-b30`，以匹配标注中的 namespace。fingerprint 是 A InputRecord 的完整 payload SHA-256，不包含 id/crawled_at；修改来源字段后须显式重建标注指纹，不能改证据来迁就旧输入。多方向/主辅/冲突/多职位案例在合成单元测试中，词值只有 family-a/role-a/track-a/level-a 等占位符。

运行命令与事务/重放语义见 [M2 README](../../../app/job_analysis/README.md)。位置通过只证明引文对应，不证明岗位语义正确。

## B3-1 职责建议示例

`proposals.input.json` 为十条手写合成材料：七类简单核心技术交付、客户演示反例、标题职责冲突、疑似多职位。使用独立入口 `app.job_analysis.role_classification.proposals`、显式目录 `families.v1.json` 与 dataset=synthetic-b31；不消费 annotations.json，不改变上述 B3-0 示例。

这些句式只作程序回归与使用演示，不是人工真值或真实 JD。预期仅为待审 family 线索，canonical_job/技术方向/级别均不定案，正式统计资格关闭。

## B3-2 合成候选治理示例

`governance.input.json` 为三条纯合成 JD；`governance.submission.json` 为 Codex 编写、待人类复核的显式候选主张，namespace=`synthetic-b32`。含多个核心、待核查的复合候选与纯技术栈，4 个候选/1 条 related_to 关系；不是正式岗位名单或人工真值。正式目录使用源码包 `governance/catalog.empty.v1.json`，始终为空。CLI 用法见 M2 README。
