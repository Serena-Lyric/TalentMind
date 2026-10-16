# B3-1 跨字段语境与辅助标题掩盖冲突

日期：2026-10-16。仅合成离线材料，无真实 JD 或生产写入。

## 症状

- duties 为“核心职责：开发后端接口并交付服务”，raw_text 为“历史项目：”加同句，旧候选建议仍 proposed/software_engineering；公司介绍、培训同样复现。
- 标题“测试工程师”，软件核心职责原本冲突，追加“协助设计测试用例并交付测试报告”后冲突消失。
- 实际源码失效测试复制文件到 Windows 临时目录时，短路径 __file__ 与 resolve 后长路径混用导致 relative_to 失败。

## 根因

按字段分别解析，却把非职责语境仅作为旁路上下文，提取 duties 失去来源语境后重新获得技术责任。标题比较了全部候选，辅助候选成为虚假的冲突消解证据。manifest 源码目录一处未 resolve。

## 修复

有限规则升级 closed-delivery-clauses-v2。候选分句逐字落入另一字段的排除/未解析语境时，撤销该分句候选并标 cross_field_context_conflict；完整输入/排除引文保留，不篡改原始 duties。存在唯一核心家族时标题直接与其比较；多个核心或无核心仍未决，不按条数加权。manifest 所有路径统一 resolve 后计算相对路径。

内部审查两项 Important 回归 RED 14 failed / 1 passed → GREEN；新增源码实字节测试发现路径问题 RED 1 failed / 86 passed → GREEN 87 passed。另有事务中途伪造跨 JD 证据测试验证整轮回滚。

## 教训

字段名不保证事实语境，提取后仍须保留来源限制。辅助责任不能解释主责任的标题冲突。Windows 路径先统一再比较，SQLite connection 的 with 只提交/回滚事务，脚本清理前仍要显式 close 或使用 contextlib.closing。
