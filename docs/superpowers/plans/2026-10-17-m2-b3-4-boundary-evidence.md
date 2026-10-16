# B3-4 工程边界与岗位材料证据实施计划

> 执行方式：按用户和 Issue #16 的既有授权连续实施；使用 executing-plans、TDD，交付前独立只读审查。

**Goal:** 表达八类工程范围，并独立保存宽泛、竞争、复合及多职位待审证据，不发布标准岗位或拆分实体。

**Architecture:** 注册 families-v3，原 v1/v2 文件不改。新增 boundaries 子包和 b34 SQLite 表，复用证据/输入/文件保护；不改 B32 schema 或报告。结构化显式主张优先，不做开放语义识别。

**Tech Stack:** Python、Pydantic、标准库、pytest、临时 SQLite；无新依赖。

**Spec:** [Issue #16](https://github.com/Serena-Lyric/TalentMind/issues/16)，其四项已确认规则为实现依据。

## 全局约束与审查重点

- 仅合成数据与临时 SQLite；阻网，不接生产/模型/B4，不改正式 DDL、词典或 exchange。
- v3 仍同八 ID/标签，仅硬件工程范围增量；不得重解释 v1/v2 历史。
- 宽泛岗位 unknown，竞争岗位 unresolved；family/方向/级别独立，自动 hint 不成为人工分类。
- 标题/技能罗列/辅助不能单独支持复合；共同交付仅待审候选。
- 多职位须独立分段标题/职责/要求及一致证据（同名可用不同编号区分）；无证据只 unresolved，不产生 vacancy/headcount/需求率。
- 身份、指纹、字段 span、全上下文、冲突、来源字节及内容版本必须可审计。
- 禁区/错位提交整轮拒绝，审核绑定结果版本，只追加；硬退出与输出失败可恢复重放。

## Task 1：v3 范围与封闭工程职责

文件：proposals/models.py、rules.py、families.v3.json；test_role_boundaries.py。
接口：现有 load_taxonomy/suggest 保持签名，v3 独立启用三项工程职责句式。

- [x] 写 v1/v2 保全、v3 八类注册与工艺/封装/良率正反例测试，运行 RED。
- [x] 最小实现 v3 与封闭句式，运行 GREEN。

## Task 2：独立显式证据层与生命周期

文件：role_classification/boundaries/{models,validation,store,runner,__main__}.py；test_role_boundaries*.py。
接口：validate_submission(batch,submission,taxonomy)、execute(store,batch,submission,taxonomy,revision,output)、replay/review_export；BoundaryStore.record_review/reviews。

- [x] 写四类主张及独立维度、复合责任、多目标门禁、冲突/错位/禁区测试，观察 RED。
- [x] 实现严格 schema、保守待审结果及完整原文上下文，运行 GREEN。
- [x] 写原子回滚、混合历史、版本审核隔离、不可变导出/重放、真正硬退出和发布失败测试，观察 RED 后最小实现生命周期。
- [x] 提供完整合成 CLI 样例，验证 run/review/export/replay 和路径保护。

## Task 3：文档、回归与独立 PR

- [x] 核实编号追加 M2-48～51 / D87～90，更新待决、M2 README、资产、导航、必要陷阱与实施报告。
- [x] 完整非集成阻网回归，记录通过/跳过/排除/连接尝试和清理证据。
- [x] 独立只读审查；实质修复均 RED→GREEN，核对源码/历史字节与文档链接。
- [x] 仅暂存明确文件，提交推送独立分支，创建并附 PR，确认未合并/自动合并关闭。

## 执行记录

- 基线 814c99168390f6d3ae476d814d9adddee36223df；原工作树与现存修改保留。
- 工程选择：独立 b34 层，生命周期采用既有 B32 的事务/不可变模式，避免扩展旧 schema 后影响历史解释。
- 工程选择：显式结构只验证原文和主张的一致性，不能证明语义真值；示例不成为正式岗位名单。

- Task 1/2 complete：目录 16 RED、主张 26 RED、生命周期 21 RED 后逐组 GREEN；重复证据 2 RED→GREEN。B3 联合 337 passed。
- Final review：fresh reviewer 独立 79/209 passed；同名不同编号目标误拒 Important 经 1 failed / 1 passed→GREEN 修复，署名遗漏 1 failed→GREEN。最终全量阻网 1057 passed / 2 skipped / 23 deselected、连接尝试 0。
- Ruling：结构门禁只验证显式主张与原文位置，不证明开放自然语言语义；生产目录/职位发布/人数统计保持关闭，代价为真实材料仍需后续人工复核及授权。

- Task 3 complete：实现 7bbe8a2 已推送，[PR #17](https://github.com/Serena-Lyric/TalentMind/pull/17) 已附当前聊天，实查 OPEN/MERGEABLE、未合并/未启用自动合并；远端暂无 CI。保留原工作树/分支等待 ChatGPT 集中复审。
