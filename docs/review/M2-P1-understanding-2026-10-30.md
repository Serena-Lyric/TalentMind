# M2 P1 单条理解：实现与真实 DEV 验证

日期：2026-10-30，Asia/Singapore；首轮至第五次 Review 定向修复及复审准备完成于 2026-11-02、2026-11-03。真实调用跨 10-29～11-03。基线 `master@cacf00f138a0512c4ef6c643fc90c0232159e1bb`，开发分支 `codex/m2-p1-jd-analysis`。主入口 `1ef25b8`、显式补充 `f2683e8`、字段级保留 `963c676`；最新复审 head 以 PR 描述中的固定 SHA 为准。

**结论：独立入口、证据/版本校验、失败与部分保存已经实现，并实际运行九例 DEV。首轮 Review 对固定 head `6f1575b1629075499893d6eedc543233ad2ad361` 指出的五条错误 explicit、六项要求语义偏差和字段级作用域风险已完成定向修复；九例当前缓存重编译结果按冻结参照逐项对照为 199/199 个单位、184/184 条条件通过，四条已审直接用途 explicit 保留。** 该结论仍是 Agent 对照，不能记为 P1 业务通过；关系等级仍有 7 条保守 unknown 与冻结 inferred 精确不一致，5 条具体新增/原组边保持未决。本报告交 ChatGPT 独立复审；不自行合并，不启动 P2。

第二轮 Review（固定 head `d638e73`）要求的 R1/R2/R3 已完成有限补证：无锚点关系不再生成新 inferred，DEV-05/DEV-09 已在最终源码上完成真实默认入口各两次请求，7 条 unknown 差异与 5 条未决关系已逐条归因。两例真实结果合计 40/43 单位完整匹配、3 部分、0 漏答，37/39 条件通过；R13 程度和 R04/R07 组合/共同条件仍有真实模型偏差，因此本轮仍不申请由 Codex 自行判定业务通过。

第三次 Review 指定的 Flash-1017 迁移已完成：新调用只使用 `deepseek-flash`，稳定主理解/审计前缀和协议 Mock 已落地。真实 DEV-05/DEV-09 Flash 回包经最终策略编译后为 42/43 单位完整、1 部分、0 漏答，39/39 条件通过；R13、R04 AND 条件和 R07 开放组合已修复，剩余 R01 的 target/condition 结构误配仍如实保留，因此仍不自行宣告完整业务通过。

第四次 Review 的 F1/F2/F3 已完成限定收尾；第五次 Review 进一步补上“同一句但两个分句各自带优先作用域”的反例。申请材料/证明在现有 target 枚举无法精确表达时改为有界 `unresolved` 并移除“投递时”伪 condition；受控 DEV-09 fresh Flash full flow 为 19/20 单位匹配、1 个明确有界 partial、22/22 条件。两例合计才是 42/43 单位、39/39 条件；审计 coverage 保持 partial，不把单项数值当作完整业务通过。

## 1. 范围与实际执行路径

依据：[P1 方案](../superpowers/plans/2026-10-28-m2-core-delivery/P1-jd-analysis.md)、[总计划](../superpowers/plans/2026-10-28-m2-core-delivery-plan.md)、[产品决策 §3.11～3.13](../PRODUCT_DECISIONS.md#311-新底座最小职责组织与候选管理2026-10-28)、[P0 评价规范](../superpowers/specs/M2-P0-baseline.md)及[交付审核标准](../superpowers/specs/2026-10-28-m2-delivery-review-standard.md)。

| P1 目标 | 实现与检查 |
|---|---|
| 单条 JD 独立理解 | `understanding.analyze(namespace, row, input_version, processor)` 接受 P0 InputRecord；云端完整理解目标/对象/职责/要求，无岗位目录或旧 B1/B2 前置 |
| 五态、程度、条件、否定、组合及对象 | 保持 `m2-semantic-0.2`；原成员/未知映射不丢；能力类别与行业/学历/经验/其他条件分开。结构能保存不等于语义已全部正确，误判见逐例对照 |
| 稀疏关系 | explicit/inferred/unknown 保留证据及理由，不生成矩阵；定向修复撤销五条同名动作/共同对象/共现误升，保留四条已审真实直接用途，并以正反例约束同句/明确承接与局部工作对齐 |
| 证据与输入身份 | 程序决定 Unicode 代码点半开区间；引文重复须 occurrence；实际字段 Schema、缺失字段逐字唯一全文重定位有审计记录；已有字段不符及歧义拒收 |
| 失败与有效部分 | 单项坏结构/引文不抹除其他有效项；区分空、坏 JSON、截断、超时、拒绝、全部失败、未执行、无识别、部分完成；不补 JSON 括号 |
| 替换、版本和读取 | Processor 协议、显式端点/模型/推理配置；源码载入摘要、契约/提示/依赖版本、实际返回模型/用量；独占私有 run、manifest 最后写、只读校验历史 |

本段实施选择及代价（不是新的产品裁决）：

| 选择 | 依据与边界 | 判断有误时的代价/处理 |
|---|---|---|
| 复用P0契约、新增独立处理器，不包装旧规则链 | 负责人授权结果优先，保持新语义与旧历史分开 | 替换处理器/提示；不需迁移正式库 |
| 干净检出上使用独立分支 | 无用户未提交内容、并行任务仅写私有评价 | 只有分支隔离，发现外来修改须停下核对，不能覆盖 |
| 缺失字段仅唯一逐字全文改绑 | 记录调整，拒绝歧义，不把定位当语义确认 | 需复核章节归属；可收紧为拒收，不改原文 |
| 模块载入时固定源码依赖 | 长驻进程不能被磁盘编辑错标新版本 | 新代码生效必须重启worker；旧结果仍按旧版本读 |
| 正向程度字段级部分保留 | 完整陈述/证据可用，未解析信息显式降覆盖，负向/条件不删除 | 消费者必须读issue/coverage，不能把null当无程度要求 |

正式实现位于 [understanding](../../backend/app/job_analysis/understanding/README.md)，无新增依赖、GPU/本地模型权重或正式数据库迁移。知识对齐保留 unknown、分类 not_run；P1 五维完成时 aggregate outcome 仍为 partial，是 P0 契约的真实语义。未接入旧产品页面、M3/M4、候选维护或岗位发布。

首次完整链路使用 DEV-09 实际 CLI：单条冻结快照 → 官方 API → 引文/契约验证 → 私有保存 → `read`。首轮 Review 后，默认 `analyze` 会在明确风险时最多执行一次限定编辑审计；主阶段先持久化，审计只改既有要求/关系，不改职责、目标或对象。`--raw` 保留单阶段诊断入口。显式 `refine` 仍是绑定旧输入身份及内容版本的一次完整补充，不是自动重试。

从 `backend/` 运行（私有配置与 Key 只传路径）：

```powershell
python -X utf8 -m app.job_analysis.understanding analyze <单条冻结快照.json> --namespace <manifest namespace> --input-version <content_version> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录>
python -X utf8 -m app.job_analysis.understanding analyze <单条冻结快照.json> --namespace <manifest namespace> --input-version <content_version> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录> --raw
python -X utf8 -m app.job_analysis.understanding read <私有run目录>
python -X utf8 -m app.job_analysis.understanding refine <旧私有run目录> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录>
python -X utf8 -m app.job_analysis.understanding audit <旧私有run目录> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录>
```

退出码 0 表示可读执行结果，包括部分或无识别；2 表示已保存的执行失败/截断等；1 表示本地拒绝。所有 stdout 是安全汇总，正文/模型回包及异常原文不进入公开日志。中断仅 pending 的目录不伪称完成；已有目录在收费请求前拒绝。固定原文与 P0 标签未改。

## 2. 数据、提供商与版本边界

- 只使用受控 DEV-01～09；当前 manifest SHA `ff53b82ce3b5f42e764f9abe70768866a8d822e7edb4e25717200147a089dda7`，批准 release SHA `84987f03d289b5e22bbcd0d516b968595bd55508cfe74de7dd9031e5b2376d2a`。签审与其他依赖见 P0 §3.3。受控审计实际返回 9例、106A/48B/21C/9D=184条件、199适用单位。
- 外发白名单为 job_title/raw_text/duties/requirements/experience；不发送来源身份/URL、人工标签、签审或完整库。九例发送字段的手机号/邮箱筛查匹配均为 0，无文本变换、偏移映射变化或 HOLD/历史 ZIP 内容读取。
- 负责人选择 DeepSeek 官方账户并本地配置 Key。端点固定 `https://api.deepseek.com/chat/completions`，不继承旧代理网关、环境代理、重定向或自动收费降级。账户账单区域接口未提供，不补造；不能把中国通用存储说明当账户区域实测。
- 调用前核对官方 [模型/价格](https://api-docs.deepseek.com/quick_start/pricing/)、[开放平台条款](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html)、[隐私政策](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html)，核对日期 10-29，继续调用时 10-30 再核模型/价格/错误码。所查来源未提供明确适用于本 API 输入的固定保留期限/不训练承诺，不宣称零保留；通用隐私政策也不能直接替代下游 API 数据协议。
- 文档宣称映射：`deepseek-v4-pro` → DeepSeek-V4-Pro-0813，`deepseek-flash` → DeepSeek-V4.1-Flash-1017；实际返回名/系统指纹逐 run 记录，别名不是固定权重证明。Pro 高推理、早期 Flash 非思考试探、Pro max 与当前 Flash-1017 thinking+max 分开保存；本地模型仍是“暂未尝试”。

私有根 `data/local/m2-p1-20261029/` 保存原交付请求、机器内容、源依赖、阶段配置、调用费用审计和逐例对照；Review 修复证据另在 `data/local/m2-p1-review-20261030/`，保留 12 次实际请求、当前九例缓存重编译、逐项评价、费用和 SHA 绑定。Key 文件不进入任何提交/证据清单。P0 根仍为 `data/local/m2-p0-20261028/`。可按输入/分析/原字节 SHA 受控复核；公共报告只提供安全汇总，不公开真实全文或回包。

## 3. 真实 DEV 对照方法及结果

人工参照只来自冻结 annotations；两名独立 Agent 分别检查 01～04 与 05～09，对全部 D/R、全部 A/B/C/D 以及每条实际预测关系做配对，保留拆并理由和未决。它们是 **Agent 对已有人工真值的对照**，不是新增负责人签审或模型自评。主 Agent 另校验 analysis/run/annotation/case 摘要、单位与预测/条件/关系全集。

单位分母始终是 72职责+127要求=199，9个目标通过条件单独检查，不另增 TP。失败及部分项不从分母移除。配对允许语义等价拆并，不按字符串或引文覆盖机械计 TP。`supported_extra` 是有原文支持但未在冻结人工单位内的新预测，仍列未独立人审，不直接当已确认 TP。

### 3.1 首轮 Review 定向修复结果

Review 固定 head 为 `6f1575b1629075499893d6eedc543233ad2ad361`。修复轮新增 **12 次真实请求**：默认入口 DEV-01 主理解/审计 2 次、第一轮审计 DEV-01 成功与 DEV-05 网络失败 2 次、第二轮审计 DEV-05 重试及其余 7 例 8 次。11 次返回用量，1 次网络错误无用量；没有使用 HOLD。当前 `review-final-20261102-final` 是在这些真实回包上做零网络请求的确定性重编译，逐例校验完整请求及 origin run SHA，并逐键确认相对已完整对照结果仅 analyzer 摘要变化。

| Review 项 | 定向修复与当前证据 |
|---|---|
| P1-01 五条 explicit 误报 | DEV-01 `d6→r13/r14/r17`、DEV-02 `d4→r13`、DEV-03 `d2→r10` 均改为限定范围的 `inferred`；四条已审真实直接用途仍为 explicit。合成回归同时要求同名动作/共同对象/共现不升级，以及“使用/利用/基于/运用 X 完成 Y”不丢失。 |
| P1-02 六项要求偏差 | DEV-01 `R08/category`、DEV-05 `R12/combination`、`R13/degree`、`R15/state`、DEV-07 `R02/combination`、DEV-09 `R07/combination` 已逐项复测；当前 127 个要求单位和全部 184 条件通过 Agent 对照，未删除原分母或扩大未知。 |
| P1-03 限定词与关系作用域 | 删除“引文任意位置包含限定词即扩大 scope”的路径。审计必须给 target、qualifier 和局部谓词/共享修饰/明确承接证明；全部成员、否定极性、ASCII 实体边界、兼容字形实际代码点与同局部子句工作对象均校验。跨分句、后置否定用途、新增 unknown、`same_activity` 完整笛卡尔矩阵、竞争修饰、反向极性、重复编辑、擦除既有 degree/condition、逗号后独立谓语及遗漏既有关系端点均有公开正反例；量词只在覆盖全部成员的同一局部句取证，否定式“全部/每项”不算正向 all_of；完整职责×要求矩阵整体拒收，遗漏关系至少降 coverage partial，不能静默报 complete。 |
| P1-04 证据边界 | 9 份冻结 prompt/回包、12 次实际请求、缓存重编译、199 单位、184 条件和逐项关系对照分别保存；人工标签、HOLD、Key、原文与完整回包只在私有目录。 |

当前关系精确对照为：explicit 4/4 正确；冻结 inferred 范围中 16 条正确、4 条未决；7 条实际保守 unknown 与冻结 inferred 不一致，另有 1 条 unknown 未决、1 条冻结 unknown 正确。七条保守 unknown 集中在 DEV-02 的同标题技术背景（2）和 DEV-05 的标题/自驱/团队上下文（5），没有升级 explicit，也不冒充 inferred TP；四条未决是 DEV-04 一条组外具体边和 DEV-09 三条未单独人审的具体推断。这是当前仍保留的关系误差，不能写成关系全对。

### 3.2 原提审基线结果

主轮 `pro-v5` 是同一固定源码/提示与 max 配置的一次完整理解。随后只对已发现问题的 01/02/03/05/06/07/09 各显式补充一次，04/08 保留主轮。交付对照统一采用这些补充结果，即使比主轮差也不择优退回；同时完整报告主轮结果及全部费用。这是开发复核流程，不宣称已实现自动触发或 HOLD 泛化。

最终产物为 `runs/final-compiled`：在上述固定选择的真实缓存回包上运行最终字段级编译器，没有新增模型请求。逐例断言完整请求 canonical SHA 等于原请求，另绑定 origin run 原字节 SHA、旧分析器及 source_execution；原 API 时长/用量与本地重编译时间分开保存。此轮恢复了因程度片段/不适用类别而整项拒收的有效事实；正向非连续程度仍明确 partial/unresolved，不删除条件/负向程度。不能把它称为新模型复跑或引文归属的语义证明。

| DEV | A通过/总数 | B通过/总数 | C通过/总数 | D通过/总数 | 职责匹配；要求匹配/部分/漏 | 主轮/补充 API秒 | 遗留 |
|---|---:|---:|---:|---:|---|---|---|
| DEV-01 | 16/16 | 6/6 | 2/2 | 0/1 | 11；24/1/0 | 306.2 / 180.7 | 类别差异；3条关系误升明确 |
| DEV-02 | 13/13 | 4/4 | 2/2 | 1/1 | 6；15/0/0 | 323.9 / 210.4 | 1条关系误升明确 |
| DEV-03 | 18/18 | 5/5 | 3/3 | 1/1 | 14；15/0/0 | 202.1 / 130.5 | 1条关系误升明确 |
| DEV-04 | 7/7 | 5/5 | 2/2 | 1/1 | 2；12/0/0 | 241.6 / — | 冻结范围未见剩余阻断错误 |
| DEV-05 | 9/9 | 5/5 | 0/2 | 0/1 | 7；13/3/0 | 190.3 / 191.2 | 组合/共用程度/行业未知仍错；部分关系未决 |
| DEV-06 | 16/16 | 5/5 | 3/3 | 1/1 | 10；11/0/0 | 183.0 / 114.7 | 冻结范围未见剩余阻断错误 |
| DEV-07 | 13/13 | 5/5 | 2/2 | 0/1 | 9；15/1/0 | 175.0 / 142.5 | 专业任选普通项未知化，待业务判断 |
| DEV-08 | 5/5 | 4/4 | 2/2 | 1/1 | 6；4/0/0 | 158.4 / — | 冻结范围未见剩余阻断错误；模型覆盖partial |
| DEV-09 | 9/9 | 9/9 | 3/3 | 0/1 | 7；12/1/0 | 190.9 / 103.6 | 工具开放举例的选择关系过定；结构化程度partial，关系/对象未决 |

**全部 184 条条件**：A 106/106、B 48/48；C 19/21（2项未达冻结合理未知口径），D 5/9组满足、4组仍有普通覆盖误差；没有未评估条件。全部A/B通过仍不等于整体P1通过。

| 对象 | 参考/预测单位 | 完整匹配 / 部分 / 漏答 | 已配对预测 / 明确误提 / 新增未独立人审 | P保守下界～上界 | R完整下界～含部分覆盖上界 |
|---|---|---|---|---|---|
| 职责 | 72 / 60 | 72 / 0 / 0 | 60 / 0 / 0 | 100.00%～100.00% | 100.00%～100.00% |
| 要求 | 127 / 164 | 121 / 6 / 0 | 148 / 7 / 9 | 90.24%～95.73% | 95.28%～100.00% |

P下界仅计冻结配对，P上界加尚未独立人审的有据新增；R下界仅计完整匹配，上界另含部分覆盖，**不是置信区间或已确认准确率**。配对粒度/作用域错误按记录归因，不因60条职责聚合覆盖72人审单位就重复计预测TP。最终199单位无整项漏答，但6条要求仍只有部分正确；新增9项不作人审已确认真值。

要求语义错误归因：五态 1、组合 3、程度 1、类别 1；均基于全体127个已配对且逐项检查的要求单位，含合理未知/未提及的预期。对象/条件/开放集合本次未另记录独立错误，不外推为一般零错误；同单位可多标签，不相加成统一准确率。

关系：explicit共10条，正确4、错误5、未决1，已确认误报/全部明确预测=5/10；inferred共28条，正确23、未决5。没有把未决新增边当TP。主要阻断是把同名活动/对象的联系升级为雇主明确用途；普通组合/分类与未决对象也保留逐项证据。

最终共核对561个引用实例，P0身份/代码点/引文校验错误0，缺证据输出事实0；这只证明位置与结构。原主轮对照：A 101/106、B 43/48；要求112完整/14部分/1漏；explicit错误8。改善、补充及字段保留都有可追溯前后记录，未只报告最好的一轮。

最终P1 coverage：7条五维complete、2条存在partial；classification全部not_run，故9条aggregate outcome均partial、未执行/失败0。两条部分分别含模型自报覆盖不足、正向程度字段未解析等真实原因，不能读成无程度要求。主轮/补充实际API时间如上；缓存编译0网络请求，耗时单独记录，不混入模型速度。

有无已知阻断错误需同时看全部条件、D 项系统性缺口及关系；A/B 都通过不能掩盖误报明确关系。D 的单个错误不机械一票否决，交业务复核范围和系统性。真实关系缺口按稀疏人工记录逐项复核，不将组备注展开成全矩阵来制造召回分母。

### 3.3 第二轮 Review：R1、R2、R3 有限修复

Review 固定 head 为 `d638e7317bce34253714c9e3c6f656a81308768d`。本轮只处理该评论的 R1～R3，未修改 P0 标签、184 条件或 199 单位分母，也未读取或调用 HOLD。

**R1 已解决。** [audit.py](../../backend/app/job_analysis/understanding/audit.py) 不再把缺少 `means/work` 的 `same_activity/shared_context` 直接发布为 `inferred`：新关系端点被拒收；原先已存在的稀疏端点若仍没有局部锚点，只保留有界 `unknown` 并将 relations 降为 partial。具备明确 `means/work` 和局部活动对应的跨句推断仍可为 `inferred`，原文直接表达“运用方法完成工作”的 explicit 仍保留。对应公开回归包括无实际工作关联、同名活动/共同对象/普通共现、带锚点跨句 inferred、直接 explicit、缺锚点补丁和新增 dense matrix 拒绝。真实 DEV-09 还暴露并修复了模型将嵌套 `requirement.reason` 省略、只提供外层 `reason` 的结构兼容问题；外层理由会确定性写入修订项，不改变模型语义。

**R2 已完成两例最终源码真实默认入口。** 使用 DeepSeek 官方 `deepseek-v4-pro`、`reasoning_effort=max`、同一冻结 P0 输入，当前 `understanding.analyze` 默认入口真实执行主分析并在风险命中时执行一次审计；两次均为真实请求，不是缓存回放。

最终两例 run 的 `analyzer_sha256` 均为 `2bb19b28bec2837922331d75106a0934d50490b507892c720b8bf7245563b508`；输入 SHA 分别为 DEV-05 `de95cc71bd3ef16cdebe237e647247c35db1c542f31c6500db705f8f99ea817f`、DEV-09 `7eaf74d95302cfa94e389fe1ca3b6ab31aa768765e568737694fabc2a03db174`，冻结 manifest SHA 为 `ff53b82ce3b5f42e764f9abe70768866a8d822e7edb4e25717200147a089dda7`。

| DEV | 调用/阶段 | 最终 claims/relations | 单位匹配/部分/漏 | A/B/C/D | 真实新请求 Token；本地 pipeline 秒 | 发现 |
|---|---:|---|---:|---|---:|---|
| DEV-05 | 2（primary ok + audit partial） | 33 / 3 | 22 / 1 / 0 | 9/9、5/5、2/2、0/1 | 49,103；331.824 | R13 自驱/热情/钻研全保留，但“强烈”只结构化在技术热情，钻研精神 degree 丢失；D01 因此不通过 |
| DEV-09 | 2（primary ok + audit partial） | 34 / 0 | 18 / 2 / 0 | 9/9、9/9、3/3、0/1 | 57,983；416.581 | R04 任一框架和可运行产出被拆成两个独立 preferred，AND/共同条件丢失；R07 工具开放清单被压成一个成员且为 single；D01 因此不通过 |

两例合计 43 个人工 D/R 单位：40 完整匹配、3 部分、0 遗漏；37/39 条冻结条件通过。DEV-05 的三条最终关系为：问题排查方法→根因定位修复为正确 explicit；快速代码实现→平台开发为未独立人审的同句自关联；Java 经验→平台开发为有理由 unknown。DEV-09 最终没有发布关系；三条未冻结的具体推断只记为关系召回限制，不作为 TP 或负例。

为了保留首轮九例证据的可复算性，本轮还用当前编译器对历史九例回包做了一次零网络重编译；除 analyzer 摘要外，九例分析逐字节语义相等，因此既有 199/199 与 184/184 Agent 对照仍按缓存口径保留。但这与上面的 DEV-05/09 fresh default 运行分账，不能用缓存结果声称九例默认流程全通过。

所有第二轮真实请求逐组记录如下；“首次”只用于说明发现问题的真实失败，不作为最终效果。

| 运行 | primary 秒 / tokens | audit 秒 / tokens | 总 pipeline 秒 / tokens | 结果 |
|---|---:|---:|---:|---|
| DEV-05 首次 | 194.910 / 26,160 | 130.667 / 23,429 | 325.797 / 49,589 | 31 claims、1 relation |
| DEV-09 首次 | 180.307 / 26,061 | 150.323 / 26,338 | 330.863 / 52,399 | 29 claims、1 relation；14 条审计编辑结构拒收 |
| DEV-05 最终 | 190.107 / 24,429 | 141.333 / 24,674 | 331.824 / 49,103 | 33 claims、3 relations |
| DEV-09 最终 | 306.180 / 35,518 | 110.045 / 22,465 | 416.581 / 57,983 | 34 claims、0 relations |

首次真实执行还额外暴露 DEV-09 审计编辑因缺少嵌套 reason 被整批拒收；该结构问题已先以失败测试复现、修复后重跑两例。DEV-05 首次结果 31 claims/1 relation，最终 33/3；DEV-09 首次 29/1 且 14 条要求编辑全部结构拒收，最终 34/0，只保留 3 条由 scope 证明不足导致的要求编辑拒绝。两次首次尝试和两次最终源码尝试共 8 次真实请求，均返回用量：209,074 tokens（命中 25,344、未命中 24,966），按 11-02 官方峰谷价估算 USD 0.3314～0.6628。最终两例的模型响应名均为 `deepseek-v4-pro`，系统指纹均为 `a307abda487cd1b463329ccb945ce396`；请求已核对仅含白名单 JD 字段和必要机器草稿，不含人工标签、Key、HOLD 或指纹。

**R3 已逐条归因，未修改人工真值。** 原 7 条 `unknown`/冻结 `inferred` 差异中：DEV-02 编码/调试及可维护代码→开发维护 2 条，以及 DEV-05 书面表达→交付文档 1 条属于“错误保守”，来源有具体活动/对象联系但当前模型仍记为 unknown 或未输出；DEV-05 另外 4 条 Java 经验/基础/JVM→平台开发只由岗位标题和正文共同背景支撑，按 R1 判定为“合理未知”。原 5 条未决中：DEV-04 的单一 Java 技术→授课是未冻结的具体边，不得从组级参照展开；DEV-05 快速代码实现→平台开发是同一职责句的自关联，不增加 TP；DEV-09 的 RAG→知识库治理、数据敏感→评分口径、文字表达→对比报告均可作为带局部锚点的有限 inferred，但无具体人审边，本次默认运行未覆盖，只计关系召回限制。逐项 ID、原文上下文和裁决保存在私有 `r3-relation-adjudication.json`，公开报告不复制真实 JD。

| 私有裁决 ID | 受控索引 | 裁决 |
|---|---|---|
| R3-01 / R3-02 | DEV-02：编码调试、可维护代码 → 开发维护 | 错误保守；需要局部锚点后恢复有限 inferred，本轮不计 TP |
| R3-03～R3-06 | DEV-05：Java 经验、基础、框架、JVM → 平台开发 | 合理 unknown；标题/同岗位背景不足，不制造用途边 |
| R3-07 | DEV-05：书面表达 → 交付文档 | 错误保守；具体文档输出有有限联系，模型未覆盖 |
| R3-08 | DEV-04：单一 Java 基础 → 线上授课 | 未独立人审；冻结仅确认技术栈组级关系，不展开 |
| R3-09 | DEV-05：快速代码实现 → 平台开发 | 同一职责句自关联；不增加关系 TP |
| R3-10～R3-12 | DEV-09：RAG→知识库治理；数据敏感→评分；文字表达→对比报告 | 未独立人审的有界推断，本次未输出，只计召回限制 |

本轮建议：R1 工程风险已关闭，R2 真实默认入口验证已完成，R3 的 12 条关系均有明确归因；P1 仍不应由 Codex 宣告业务通过。DEV-05 R13、DEV-09 R04/R07 是真实模型在当前固定配置下的局部语义偏差，且两例 D01 均未通过，是否构成阶段阻断由 ChatGPT 与负责人决定。

### 3.4 第三次 Review：Flash-1017 迁移与有限质量验证

ChatGPT 第三次 Review（head `9bf52753d308d5a6b5f4bba134716a6ea3178b5f`，review `5731294245`）接受 R1/R2/R3 的工程修复，但要求后续新调用仅使用 `deepseek-flash`、优化自动上下文缓存，并针对 DEV-05/DEV-09 的核心语义边界给出真实结果或明确不可修复边界。

2026-11-02 直接核对 DeepSeek [更新记录](https://api-docs.deepseek.com/updates/)、[模型与价格](https://api-docs.deepseek.com/quick_start/pricing/)、[Chat API](https://api-docs.deepseek.com/api/create-chat-completion/)、[thinking](https://api-docs.deepseek.com/guides/thinking_mode/)、[JSON output](https://api-docs.deepseek.com/guides/json_mode/)与 [KV cache](https://api-docs.deepseek.com/guides/kv_cache/) 官方文档：2026-10-17 更新页明确 `deepseek-flash` 对应 `DeepSeek-V4.1-Flash-1017`；Flash 支持 thinking/非 thinking、`reasoning_effort=low/high/max` 和 `response_format={"type":"json_object"}`。磁盘缓存自动启用，按完整 cache prefix unit best-effort 命中，响应提供 `prompt_cache_hit_tokens`/`prompt_cache_miss_tokens`。本轮未发送 `prompt_cache_key`，未将历史 Pro 结果改标为 Flash。

协议与缓存改动：

- [config.example.json](../../backend/app/job_analysis/understanding/config.example.json) 改用 `model="deepseek-flash"`，MockTransport 覆盖 thinking、max effort、JSON object、cache hit/miss、禁止 `prompt_cache_key` 和实际返回模型校验。
- 主理解/审计的 Locator Schema 固定列五个公开文本字段，不再把“当前字段是否存在”嵌入 system Schema；真实非空字段仍只在后续 user 内容发送，定位器引用缺失字段仍会被程序拒收。主理解和审计各自拥有一个跨样本稳定的 system 前缀，公共提示与可共享 Schema SHA 写入 run 与私有缓存报告。
- 主理解提示版本从 `1` 升为 `2`；历史 Pro run 保留原版本。固定前缀分别为主理解 `be7dd686a157f9892304cda9363d065d9e6c914cf0a1caabdc2da1bd297c7b91`（14,000 bytes）和审计 `69f089a0bd6064bc431f6e898c1bbc4cec3835734439a3d0091718e231ccc88a`（7,056 bytes）；canonical Schema SHA 分别为 `f3821b5832d8d15925b89b4874bc5333b1146ada1b9689c3790e066edaba1f0a` 与 `96a52dc43ead330cca5727c0bd6227d30ecdc432a0f3b2ffe99913a83a3bdd48`。没有为缓存删除原文、职责作用域或 JSON 语义。
- [policies.py](../../backend/app/job_analysis/understanding/policies.py) 增加来源章节约束：“期望/更看重”下的 required 降为 preferred，并在后续招聘/申请/联系方式等明确标题处结束软性范围；同一软性任选能力与可运行产出共享同句时，将产出作为能力 requirement 的精确 condition，避免两个 preferred 拆分丢失 AND。

Flash 真实默认入口共执行 5 次请求：DEV-05 primary+audit；DEV-09 首次 primary；DEV-09 同配置/同输入一次重试的 primary+audit。首次 DEV-09 返回 HTTP 200、`finish_reason=stop`、39,393 completion tokens，但缺少一个右花括号，程序保留 `invalid_json`，未补括号。因该失败不是长度截断，执行一次不修改提示词/模型/输入的诊断重试；若再次失败会停止。

| 运行 | primary 秒 / tokens（hit/miss） | audit 秒 / tokens（hit/miss） | pipeline 秒 / tokens | 缓存命中率 |
|---|---:|---:|---:|---:|
| DEV-05 Flash | 170.340 / 36,583（0/3,934） | 272.455 / 58,956（0/7,746） | 443.113 / 95,539 | 0% / 0% |
| DEV-09 首次 invalid | 216.613 / 44,322（3,200/1,729） | — | 216.628 / 44,322 | 64.9% |
| DEV-09 retry1 | 181.835 / 37,766（4,736/193） | 135.497 / 34,504（1,664/7,197） | 317.553 / 72,270 | 96.1% / 18.8% |

5 次请求均有用量：总计 212,131 tokens（cache hit 9,600、miss 20,799、completion 181,732），按 Flash 官方峰谷价估算 **USD 0.1122～0.2244**。实际返回模型均为 `deepseek-flash`，系统指纹均为 `bc19ba97cbe016479903222bb1578db6`。DEV-09 重试输入和请求 SHA 与首次 primary 相同，命中率变化来自服务端缓存状态，不宣称固定命中保证。

真实 Flash 原始运行的 `analyzer_sha256` 为 `dff81c819902b2963a4fc7b36a8d547fc02ab8435f09a0b40770769c72ded961`；加入最终软性章节、开放示例尾词和共享产出约束（`p1-source-constraints-3`）后，当前确定性与零网络重编译的 `analyzer_sha256` 为 `a825df31ffaba77d5baa42531cec37bc430e1f0c50e507038efc008440aee853`。重编译目录为私有 `runs-compiled-20261102-final-head/`；源码固定 commit 以 PR 描述中的完整 head 为准。

最终策略对真实 Flash 回包作 0 网络请求重编译，结果如下：

| DEV | 单位匹配/部分/漏 | A/B/C/D | 关键结果 |
|---|---:|---|---|
| DEV-05 | 23 / 0 / 0 | 9/9、5/5、2/2、1/1 | R13 技术热情与钻研精神均保留“强烈”；17/17 条件通过 |
| DEV-09 | 19 / 1 / 0 | 9/9、9/9、3/3、1/1 | R04 任一框架保留且“可运行产出”成为 condition；R07 恢复四项成员、open_set 与 unresolved；R08-R10 恢复 preferred；22/22 条件通过 |

两例合计 **42/43 单位完整、1 partial、0 missing，39/39 条件通过**。唯一 partial 是 DEV-09 R01：可验证产出的四项材料、any_of 和总括文本均保留，但 target 被模型写成 experience、condition 写成“投递时”，没有准确保存“有可验证产出是申请人条件”的字段语义。该偏差没有通过硬编码 DEV 文本或追满分掩盖。

最终建议：Flash-1017 路径在指定两例上将核心 R13/R04/R07 边界修正到冻结合格，工程与缓存协议可用；P1 仍不应自我批准为完整业务通过，需 ChatGPT 判断单条 R01 结构误配和既有 sparse-relation 召回限制是否构成验收阻断。

### 3.5 第四次 Review：shared condition 收紧、R01 有界化与 fresh 验证

ChatGPT 第四次 Review（fixed head `2093688ae52d08f4956d595a201cceb579ae7fc2`，review `5744995084`）接受 Flash-1017 迁移、缓存协议、失败/用量记录及真实请求与重编译分账，要求处理 F1 shared-output 误绑、F2 DEV-09 R01 的 target/condition 错配，并用最终固定代码对至少一条相关受控 DEV 再走 Flash 默认 full flow。

**F1 已修复。** 旧策略只要两项 preferred claim 共用同一 `scope_evidence` 跨度，且跨度任一处出现选择量词和另一 experience 成员，就会自动写 condition。新策略要求：

- 选择项与产出同时落入同一个以 `。；;\n` 分隔的局部句，且该局部句本身包含选择量词；
- 产出前后由逗号分开的局部分句不得只剩“也/另外/此外/还/再（优先/加分…）”等独立偏好标记；
- 不满足时保留两条独立事实，不把长引文共享或普通共现当作共同约束。

公开回归先复现“两个独立句”和“同一句但明确也优先”两个错误 condition，再转为通过；原先同句、无独立标记的正面共享产出案例继续保留。真实旧回包重编译中 DEV-09 R04 condition 仍被保留。

**F2 已按契约边界处理。** 申请阶段要求提交项目链接、GitHub、作品集或技术文章等材料证明时，不把材料类型强行归为 candidate experience，也不把“投递时”扩张为资格 condition。最终保留 `required`、`any_of`、四个成员及原文证据，`target` 有界设为 `unresolved`，`condition=null`；带明确年限或工作经历的合成反例仍保留 `experience`。因此 DEV-09 R01 是契约表达能力不足的有界 partial，不是 43/43 完整匹配。

**F3 fresh 验证。** 先用最终 `p1-source-constraints-4` 和合成正反例验证；再对两组成功保存的旧 Flash run 共 4 个 primary/audit 回包做 0 网络重编译（DEV-05 0 个 claim 变化，DEV-09 retry1 6 个预期变化；首次 malformed primary 不作审计输入），随后在 2026-11-03 重新核对官方文档、余额及联系人扫描（DEV-05/09 手机号/邮箱均为 0）后，对受控 DEV-09 执行一次最终代码的真实 Flash 默认入口。程序 primary 后因 `qualification_requires_subject_binding` 与 `source_constraint_conflict` 触发一次审计，共 2 次请求，无自动/人工重试。

| 阶段 | 模型/指纹 | 秒 | prompt（hit/miss） | completion | total |
|---|---|---:|---:|---:|---:|
| DEV-09 round4 primary | `deepseek-flash` / `bc19ba97cbe016479903222bb1578db6` | 265.483 | 4,929（4,736/193） | 53,112 | 58,041 |
| DEV-09 round4 audit | `deepseek-flash` / `bc19ba97cbe016479903222bb1578db6` | 188.551 | 9,093（1,664/7,429） | 37,437 | 46,530 |

本次 fresh 请求合计 **104,571 tokens**，缓存命中 6,400、未命中 7,622、输出 90,549；按官方 Flash 峰谷价估算 **USD 0.05549～0.11098**。pipeline 耗时 454.349 秒，analyzer SHA 为 `24661f50587341f737081585777fc0b40e5db35d04fb59c2b8f56f93b584b4fb`。

fresh primary 到 audit 的关键变化：

| 单元 | primary | final |
|---|---|---|
| R01 | `experience`，condition=`投递时` | `unresolved`、condition=null，四项材料与 `any_of` 保留 |
| R04 | 框架选择被压为 `any_of`，可运行产出丢失 | `all_of` 同时保留框架选择和可运行产出 |
| R07 | `unresolved`，尾词被当成成员 | 单个开放 experience 成员串、`open_set=true`，工具名与 `等 AI 工具` 保留 |
| R08～R10 | required | 正确降为 preferred |

audit 仍为 partial：5 个 requirement 编辑（R01、R03 的两项、R05、R13）因 `qualification_scope_not_uniquely_bound` 被拒收，1 个 `d2→R10` relation 因 `context_roles_not_uniquely_bound` 被拒收；relations 从 primary 的 4 条变为 final 3 条，coverage 为 partial。程序保留可用 primary 事实并显式降覆盖，没有把拒收编辑伪造成成功。

对冻结 DEV-09 人审单位的 Agent 对照为 **19 matched / 1 partial / 0 missing，22/22 A/B/C/D 条件通过**；R01 的 `target=unresolved` 是唯一 partial。加上前一轮同一策略下 DEV-05 源回包的零网络重编译 23/23、17/17，两例合计才是 **42/43 单位、1 partial、39/39 条件**；后者不是两例都在最终头 fresh API 运行。不能表述为 43/43 或完整业务验收。

### 3.6 第五次 Review：同句独立优先作用域与统计口径

ChatGPT 第五次 Review（fixed head `11ec9903f84527c97645f042dc2c437837ecaa5e`，review `5745257628`）接受 F2 与 F3 执行证据，仅要求修正 F1 的一个确定性边界并校正统计口径；明确不需要新模型请求、Prompt 扩写或九例重跑。

新增两个同句负例，均先 RED 后 GREEN：

- `熟悉 Atlas 或 Orion 框架优先，做出过能运行的项目优先。`
- 无“也”的同义变体：`熟悉 Atlas 或 Orion 框架可加分，做出过能运行的项目亦可加分。`

新规则把局部句继续拆成逗号分句：若包含选择项的局部分句与包含产出的局部分句各自带有“优先/加分/更佳/最佳/最好/受青睐”作用域，则拒绝建立 condition。原有“用过 Atlas 或 Orion 框架，做出过能运行的项目”无独立优先标记正例继续成立；单一共同优先谓词仍可表达共同约束。策略版本升为 `p1-source-constraints-5`。

最终策略对两组旧 Flash run 再次执行 0 网络重编译：DEV-05 仍为 23/23 单位、17/17 条件且 0 claim 变化；DEV-09 仍为 19/20 单位、22/22 条件，6 个既有预期变化保留，R04 condition 未被新规则误删。最终重编译 analyzer SHA 为 `dee2937f84534efb349f6e10fb240fc4faa85f360faa89b72443319e7fbca4f1`。本轮没有新增 API 请求或 Token。

## 4. 合成实际模型检查与工程回归

公开 [三例合成输入](../../backend/tests/fixtures/understanding/semantic-cases.json) 实际调用同一 Pro max：

| 合成输入 | 实际结果 |
|---|---|
| SYN-CHOICE | 两组选一保留，开放组含词典外选项且 preferred，无成员独立 required |
| SYN-NEGATION | 精通否定与了解要求分开；项目经验仍 preferred/experience；资格排除保持 required 条件 |
| SYN-RELATION | Redis mentioned、无虚构熟练/必备；只直接关联状态存储恢复，摄影不关联智能体，门店背景未生成职责 |

上述是模型在人工构造场景下的实际结果，不加入真实 DEV 199单位或市场准确率；不能替代复杂职责/条件的真实效果。

运行环境：Python 3.14.5，pydantic 2.12.0，httpx 0.27.2；复用已有 backend/.venv，无依赖安装。实际命令及结果：

| 命令（backend下） | 结果 |
|---|---|
| `python -m pytest tests/test_job_analysis/test_understanding.py tests/test_job_analysis/test_understanding_io.py tests/test_job_analysis/test_understanding_audit.py tests/test_job_analysis/test_understanding_pipeline.py tests/test_job_analysis/test_understanding_policies.py -q --tb=short` | **173 passed，退出0（最终 `p1-source-constraints-5`）** |
| `python -m pytest -m "not integration" -q --tb=short` | 上一提交 `11ec990` 基线为 **1881 passed、2 skipped、2 failed、24 deselected、1017 warnings，退出1**；第五次 Review 仅要求局部回归，该全量未在最后两项测试后重跑 |
| `python -m app.job_analysis.baseline approved-assertions <受控release> --manifest <冻结manifest> --approval <签审凭据>` | structurally_valid，9例/184条件/199单位，退出0；不代表本轮模型语义通过 |
| `python -m compileall -q app/job_analysis/understanding` | 退出0 |
| 修改 Markdown 相对链接只读检查 | 5个文件、48个相对链接、0 broken，退出0 |

两项全量失败均在本次修改前的基线已复现，路径未改，原因是旧 canonical catalog 对产品决策文档的固定来源SHA已过期：

- `test_repository_draft_covers_eight_families_and_empty_release`
- `test_shipped_source_hash_matches_a_fresh_LF_checkout`

没有为P1重签旧岗位知识或顺带修改旧目录。它们在[旧统一报告](https://github.com/Serena-Lyric/TalentMind/blob/cacf00f138a0512c4ef6c643fc90c0232159e1bb/docs/review/Unified-product-2026-10-21.md)中亦已记录，不能声称全后端全绿。1017项警告按原输出保留，未作为新功能通过依据。

独立工程审查的畸形 kind 全局中断、公开路径保存、全失败/未执行成功退出、坏 manifest traceback 均先复现失败再修复。补充入口另有独立合成执行检查：身份/版本四项不符不请求、已有目录不请求、超时保留旧 run 且新 run 真实失败。载入时源码摘要、字段重定位及定向补充均有回归。陷阱与长期规则见 [P1 边界记录](../superpowers/traps/2026-10-30-m2-understanding-boundaries.md)。

## 5. 请求量、成本与性能

尝试有明确目的：Pro 主入口试通、Flash 速度/效果探查、结构/字段/语义修订的九例主运行、max 九例回归、三例公开合成、已知问题的有限补充。没有重跑 HOLD/全库或无限重试。Flash 虽快但有坏结构/状态/关系误判，未因此宣布所有 Flash/本地路线无效。

共 **40次真实请求**：Pro试通1、Flash试通1、pro-v3九例、pro-v4九例、402后单例重试1、最后主轮九例、已知问题补充7、公开合成3；**39次有Token用量，1次402无用量**。最后9份缓存重编译不计新请求、不重复计Token。

- 实际输入 213,143 tokens（缓存命中 79,232、未命中 133,911），输出 717,511 tokens；总计 930,654。
- 依据当日官方缓存/峰谷单价，对有用量响应估算 **USD 1.5027～3.0054**，不作CNY换算或账单实付声明；1次无用量响应未被伪填0费用。
- 原API执行状态：ok 26、partial 13、http_error 1。这些是工程状态，不是40份独立语义样本；同一DEV多版本不增加真实样本分母。
- 主轮九例单条实际API约158.4～323.9秒，必要补充约103.6～210.4秒；三合成约54～78秒。阶段样本很少，不报告稳定分位数/市场吞吐。

10-29 有一次真实 HTTP402，按官方[错误码](https://api-docs.deepseek.com/quick_start/error_codes/)保留失败。10-30 只读余额确认可用后才单独新 run 重试；没有自动重试、充值或覆盖失败。未取得可核销供应商账单，费用仅以实际 Token 和当日官方缓存/峰谷价格给估算区间；缺用量响应的费用保持未知，不能填 0。API 原始推理内容未用于人工真值。

Review 修复轮另执行 **12 次真实请求**，11 次有Token用量、1 次网络错误无用量：实际输入 83,809 tokens（缓存命中 28,416、未命中 55,393），输出 188,784 tokens，总计 272,593。按 10-30 官方峰谷价估算新增 **USD 0.4110～0.8220**。当前 9 例 `review-final-20261102-final` 和默认入口 REPL 都是缓存重编译，0 网络请求、0 新增Token；单独保存原 API 时长/用量和本地编译耗时。加上原试通/主轮/补充，本阶段至今累计 52 次请求尝试、50 次返回用量、2 次无用量尝试，总计 1,203,247 tokens；这只是试通与修复成本，不作为每 JD 稳定成本。

第二轮 Review 又执行 **8 次真实默认入口请求**（两轮 DEV-05/DEV-09，各 primary+audit），全部返回用量：209,074 tokens（缓存命中 25,344、未命中 24,966），按 11-02 官方峰谷价估算 **USD 0.3314～0.6628**。其中前一轮 DEV-09 的结构兼容失败已保留，最终两例另起新 run 重跑；没有用缓存结果冒充默认入口。当前阶段累计 60 次请求尝试、58 次返回用量、2 次无用量尝试，总计 1,412,321 tokens；累计估算 USD 2.2451～4.4901，仍不是供应商账单。

第三轮 Flash-1017 真实调用共 5 次（含一次 malformed JSON 失败和一次同输入诊断重试），均返回用量：212,131 tokens（缓存命中 9,600、未命中 20,799、输出 181,732），按 Flash 官方峰谷价估算 **USD 0.1122～0.2244**。阶段累计 65 次请求尝试、63 次返回用量、2 次无用量尝试，共 1,624,452 tokens；累计估算 USD 2.3573～4.7145，仍不是供应商账单。

第四轮在最终代码上新增 **2 次真实默认入口请求**（primary+audit，无重试）：104,571 tokens（cache hit 6,400、miss 7,622、output 90,549），估算 **USD 0.05549～0.11098**。第三、四轮正式证据合计 7 次真实尝试、全部返回用量，316,702 tokens，估算 USD 0.16768～0.33536。阶段累计 67 次请求尝试、65 次返回用量、2 次无用量尝试，共 1,729,023 tokens；累计估算约 USD 2.4128～4.8255，仍不是供应商账单。

少量 DEV 的时长不能证明 3,000条/12小时、稳定吞吐或真实服务器资源能力；当前实现轻量但没有完整批处理/服务性能验收。

## 6. 私有证据、维护及审核交接

- `runs/pro-v1`、`flash-v2`、`pro-v3`、`pro-v4`、`pro-v4-retry` 保留原始试验，`pro-v5` 为最后主轮，`pro-v5-refined` 为显式补充。早期 v3 在开发编辑期间曾按磁盘字节重算 worker 版本，是原型记录限制；最后主轮和补充已在载入时固定实际代码摘要，不借后续源码改标旧结果。
- `evaluation/pro-v4`、`pro-v4-retry`、`pro-v5`、`pro-v5-refined`、`final-compiled` 是有摘要绑定的逐项 Agent 对照，不改变 annotations。`evaluation-summary.json` 汇总完整配对；`delivery-manifest.json` 绑定最终证据及选择方案（187文件，清单SHA `07fdcf7006591ab91eb7f6781102b2b0826aa28e1a18a3c45179e51af67961b2`）；费用清单记录所有真实请求，排除重编译的重复 Token，而非只计成功或最好结果。
- Review 修复私有根 `data/local/m2-p1-review-20261030/` 保存 `runs/audit-v1`、`runs/audit-v2` 原请求/回包，`runs/review-final-20261102-final` 最终确定性重编译，`evaluation/review-final-20261102-final` 逐项对照，`review-final-20261102-final-verification.json` 的 199/184 完整性断言、费用审计及待推送 head 的证据清单。目录内 `api-key.txt` 仅本地存在，绝不进入公开清单。
- Flash 私有根 `data/local/m2-p1-review3-20261102/` 继续保存前轮 5 次回包、`runs-round4/DEV-09-final-code/` 的 fresh primary/audit，以及 `runs-compiled-20261103-review5/` 对两组源 run 的最终策略零网络重编译、逐单位对照、缓存/费用/请求安全复算。第五轮私有证据清单为 `evidence-manifest-round5-20261103.json`（72 个文件），SHA-256 `a93743af8d3eb6580fc36a10f5f79bde31884fbc3723ded87ae58c2bab8316b0`；清单排除 API Key、HOLD、未批准数据、self-referential 阶段报告和过时测试日志，最终代码 head 以 PR 描述为准。
- 本次全量业务测试沿仓库安全默认跳过需隔离实例的 integration；没有启动正式 DB/Neo4j、迁移、真实采集或导入。文件夹具用唯一名并 finally/临时目录精确清理，残留核对为 0；不虚报正式库计数/未查询的健康状态。
- 阶段报告保持全仓五份：移除最旧 2026-10-21 统一报告，相关引用固定到原 Git 提交；长期使用入口与限制更新到模块 README/资产状态/陷阱。未移动、删除真实数据、P0 原件或私有旧回包。
- P2/P3 可以审阅 P1 接口/覆盖/部分结果，但不能将当前仍有关键问题的机器语义当已审依赖或自动开工；无正式知识归一化/岗位判断、无真实市场/HOLD 独立验收，B/C 仍未裁决。

审核请求：请以 PR 描述固定 head 的真实代码、P0 受控评价和本报告为依据，优先核对第五次 Review 新增的同句独立优先反例、单例/合计统计更正，以及 F2/F3 既有边界保持；不要以 Developer Agent 对照或单个 42/43、39/39 数值替代独立审查。作者不合并、不启用自动合并，不启动 P2。
