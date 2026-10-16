# 技能掌握能力与相关经验被误判为冲突

## 症状

PR #6 的 ChatGPT Review #5541520990 指出：“必须掌握 Python。Python 经验优先。”两种顺序均可能变成 conflict=true/state=uncertain。原测试也错误断言冲突成立。另有有效组合的重复 canonical 导致 group_ids 重复。

## 根因

target=candidate 仅表示面向候选人，不表示要求的是能力还是经验。冲突键仅含技能/程度/主体/条件，两个程度都为空的不同对象被合并。组合解析则将同一组中多次出现的技能逐次附加为重复组引用。

## 修复

新增 requirement_object（capability/experience/unresolved），陈述与 effective 都保存，并进入冲突分组键。明确“技能经验优先/加分/为加分项”标 experience；复杂未解析对象保留 unresolved，不强制归类。程度字段继续独立，真正相同能力上的 required/not_required 仍保留全部证据并判冲突。group_ids 稳定去重，原文成员不删。

结构升为 b2-2，规则升为 bounded-skill-clauses-v2，实际源码摘要继续参与失效。用真实旧 runner 捕获的合成历史 JSON 验证新尝试不复用旧误判，旧报告原样重放、旧运行不能用新依赖静默 resume。A/B1/legacy 不迁移或改写。

关键回归从 9 failed / 4 passed 变为 13 passed / 79 deselected；B2 92 passed，相关回归 270 passed，完整离线回归 611 passed / 2 skipped / 23 deselected、外部连接尝试 0。命令见 [阶段报告](../archive/2026-10-16-M2-stage-B2-1-implementation.md) 的本次定向修复节。测试覆盖两种顺序、真实 SQLite、程度独立、真冲突、未解析经验、版本历史与重复引用。

## 教训

冲突判断前必须比较“要求什么”，不能把“面向谁”或“程度相同”当作对象相同。历史回归的期望也必须接受产品规则核查，不能因已有测试认可错误语义就保留错误。
