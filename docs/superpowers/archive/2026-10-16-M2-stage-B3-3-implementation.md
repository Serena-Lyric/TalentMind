# TalentMind M2 B3-3 实施报告

日期：2026-10-16（Asia/Singapore）。任务：[Issue #14](https://github.com/Serena-Lyric/TalentMind/issues/14)。本报告现作为 B3-3 实施和独立复审历史归档；文中“交审中/未合并”为原开发时点状态，最终结果以 PR #15 为准。正式标准岗位名单仍由产品讨论确定。

## 基线与范围

- 已 fetch 最新 master：`bbe5309c44189b1b0d811363320b9df6f37574c9`（PR #13 合并）。独立工作树 `C:/Users/Serena Lyric/.codex/worktrees/m2-b3-3-eight-families/TalentMind`，独立分支 `codex/m2-stage-b3-3-eight-families`。
- 原工作区 `D:/Application/ClaudeCode/repository/TalentMind` 保持 M1 分支及未提交资产文档；不覆盖、不回滚、不夹带。只暂存本轮明确文件。
- 实现提交：`eb90780fa0daf509e5837dc9f1a52ab1cf2a0021`；报告、产品决策与导航另作交付文档提交。
- 本轮只升级职业大类目录及 B31/B32 校验、版本与候选路径；无新依赖、无存储 schema 迁移、无生产接口替换，不执行真实 JD/模型/采集/数据库操作。
- 实施计划及工程选择见 [计划](../plans/2026-10-16-m2-b3-3-eight-families.md)。本轮追加已确认产品原则 M2-45～47 / D84～86（基线末号确为 M2-44 / D83，无重号），不擅自确定正式岗位名单。

## 需求到实际行为

| 要求 | 实现及证据 |
|---|---|
| 保留七类 v1 | `families.v1.json` 原字节不改；其余七个 ID 与中文名在 v2 完全保留；原 B30/B31/B32 归档报告不改 |
| 独立八类配置 | 新 `families.v2.json`，新增 hardware_integrated_circuits / 硬件与集成电路；沿用结构 schema，revision 注册表核对精确集合，拒绝缺失/重复/错标签或 ID/错 revision |
| 按职责区分岗位 | 产品 M2-45 保存职责/技术交付/职业功能原则；技术方向多选且独立，不解释为技能熟练度或硬要求；代码不发布任何 canonical_job |
| 八类同步建设基础目录 | 产品 M2-46 记录已确认方向、不规定等量；两版 canonical_job/technology_tracks/seniority 目录及 B32 formal_jobs 仍空；具体名单尚未发布 |
| 有限硬件职责建议 | B31 v2 增加硬件电路/FPGA/数字 IC 三个封闭句式；标题仅对照，技术栈/历史/培训/销售不提供确定职责；跨界双核心、主次不明与标题冲突 unresolved |
| B32 显式版本 | 可选 CLI `--family-taxonomy` / Python `taxonomy=`，省略解析固定 v1，旧提交继续使用；显式验证 v2 才接受新 ID，完整目录快照进入 manifest/result_version |
| 审核与正式准入隔离 | 版本/目录/提交变更追加结果，不能复制旧审核；审核接受也不修改候选 pending_review，formal_admitted 恒 false，正式目录仍空 |
| 历史与混合执行 | v1/v2 同库按 manifest 分开；旧输入、版本、结果、报告、审核及导出截面逐行/逐字段不变，历史 replay 不加载新目录或重新计算 |
| 旧阶段与证据隔离 | A/B1/B2/B22/B30 源码及 manifest 构造未改；共库测试核对旧表/报告。namespace/jd_id/完整 fingerprint/字段字符跨度与原输入字节沿用确定性校验；错位整轮回滚 |
| CLI 与恢复 | 两入口用三条新合成示例 run/replay；新增 B31/B32 各四处真实硬退出，提交前回滚、提交后可原样 replay；显式目录输出路径保护和既有发布恢复回归通过 |

`families-v2.input.json/submission.json` 为 Codex 合成的三条 JD、四个显式候选、一条待审技术方向关系。第三条销售培训反例没有候选标注；不能把样例看成正式职业目录或人工真值。`technology_stack` 仍排除在主岗位候选集合之外，不反写 B2 技能事实，不生成 vacancy 数或正式需求率。

## 兼容策略与历史可信性

- `FamilyTaxonomy` 保留 schema `b31-family-taxonomy-1`；新增 revision 注册表而非升级全局“最新合法集合”。此前自由 revision 中只有实际交付的 families-v1 是受保护历史；新运行未知 revision 明确拒绝，存储的历史 replay 不经新校验。
- B32 报告新增 `manifest.family_taxonomy`，正式空 catalog 与 family 目录分开。完整配置、显式 revision、实际源码、完整 submission、结果正文参与版本绑定。
- 共享 `proposals/models.py` 等源码摘要变化影响**后续新运行** B31/B32 的 manifest，即使输入和 v1 正文相同也保守追加版本与结果。没有复用旧审核、伪造旧源码版本或修改旧 manifest。A/B1/B2/B22/B30 清单源码未变。
- 修改源码前在 master `bbe5309` 实际执行合成 B31/B32，导出 `history.families-v1.json` 中旧表行（含原 manifest、结果、审核与审核截面）。测试恢复临时库后逐行比对，旧报告精确 replay，新运行正文与旧正文逐字段相等但版本/结果 ID 不同。
- 独立审查另用 `git archive bbe5309` 的基线源码，在阻网子进程重算两份历史正文，完全相等；夹具全部 source hash 与基线源码匹配（Windows 检出 CRLF）。不是用升级后源码重生“旧结果”。
- v1 交付前后原始 SHA-256：`C56CE892CC5C4347D117160D6C6E76CB1A2CB6FFA31FA88B8E41362A939AF1BA`。测试内容哈希兼容 Git 的 LF/CRLF 检出差异，另以原字节及 Git diff 核对本轮未动 v1。

版本绑定陷阱见 [记录](../traps/2026-10-16-m2-b33-taxonomy-version-binding.md)。

## RED → GREEN 与实际回归

1. 首组版本/职责/候选/历史/CLI/中断测试 **26 failed / 8 passed**：缺 v2 文件、七类可假冒 v2、八类被旧校验拒绝、B32 无 taxonomy 参数。
2. 最小实现后 **203 passed / 1 failed**。剩余旧测试把七类 revision 改为 families-v2，这已是新要求明确禁止的配置；改为加载真实八类文件，定向 B3 **253 passed**。
3. 补齐历史正文再计算/审核隔离、两个入口各四处真实硬退出和仓库新样例 run/replay 后，B3 定向 **258 passed（13.96s）**；本轮新增测试共 39 项。其他旧测试保持。
4. 完整阻网非集成 **971 passed / 2 skipped / 23 deselected / 190 warnings（58.86s）**，外部/服务连接尝试 **0**。两项 skip 为未随仓提供的私有原 M2 回包；23 项真实服务 integration 按授权边界排除；警告为既有依赖弃用。

定向命令（backend，工作树无 venv，实际使用已安装 requirements 的原仓 Python 绝对路径）：

```powershell
python -X utf8 -m pytest tests/test_job_analysis/test_role_family_versions.py tests/test_job_analysis/test_role_proposals.py tests/test_job_analysis/test_role_governance.py tests/test_job_analysis/test_role_governance_storage.py tests/test_job_analysis/test_role_classification.py -q --tb=short
```

完整回归合成环境与网络阻断，未加载原仓 `.env`；仅允许 Python Windows 内部 socketpair 初始化：

```powershell
$b33Regression = @'
import os, socket, sys, pytest
os.environ.update(MYSQL_URL="sqlite:///:memory:", NEO4J_URI="bolt://127.0.0.1:1", NEO4J_USER="offline", NEO4J_PASSWORD="offline", REDIS_URL="redis://127.0.0.1:1/0", OPENAI_API_KEY="offline-test", OPENAI_BASE_URL="http://127.0.0.1:1", LLM_API_KEY="", DS_API_KEY="", LLM_BASE_URL="http://127.0.0.1:1", DS_BASE_URL="http://127.0.0.1:1", GITHUB_TOKEN="", JD_DATA_PACK="__offline_no_data_pack__")
original_connect = socket.socket.connect
denied = []
def offline_connect(sock, address):
    caller = sys._getframe(1).f_code
    if caller.co_filename == socket.__file__ and caller.co_name == "_fallback_socketpair":
        return original_connect(sock, address)
    denied.append(str(address))
    raise RuntimeError("offline regression: service/network connection prohibited")
socket.socket.connect = socket.socket.connect_ex = offline_connect
result = pytest.main(["-m", "not integration", "-q", "-rs", "--tb=short"])
print("Blocked external/service attempts:", len(denied))
raise SystemExit(result or bool(denied))
'@
$b33Regression | python -X utf8 -
```

测试 `area` fixture 均在 finally 关闭临时连接并删除本次临时目录，断言路径不存在；新增真实硬退出子进程也阻断网络。生产 MySQL/Neo4j/Redis 未连接，无生产写入，因此没有执行或声称执行生产夹具计数/行数核查；本轮存储只在自动清理的临时 SQLite。

最终额外通过阻网子进程实际执行两个模块入口：B31/B32 run→replay，B32 review→export-reviews→replay export，原字节完全相同。临时库 b31_reports/results=1/3，b32_reports/results/reviews/exports=1/3/1/1；finally 精确清理专属临时根并核对剩余 0。21 个变更文件 UTF-8/替换字符/Python AST/JSON 检查及 148 个本地 Markdown 链接通过，`git diff --check` 通过，远端 master 仍为 bbe5309。原工作区仍仅有原资产文档未提交修改，其期末 SHA-256 为 `F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B`。

## 独立内部审查

独立只读代理审查本轮代码与新增版本测试，自行运行 **209 passed（10.64s）**，未发现可复现 Critical/Important/Minor；另完成上述基线源码及夹具核验。该审查发生于最终文档与额外样例补齐期间，没有代替最终文档核验、完整 971 项回归或交付后 ChatGPT 集中复审。没有延期的已知审查缺陷。

最终补充只读审查核对产品/实现边界、版本说明、86 个所选本地链接、v1 原始 SHA 与历史归档，自行运行本轮新增测试 **39 passed（2.38s）**，未发现新增阻塞或实质遗漏，未重复完整回归。

## 工程选择与限制

- 复用现有 schema 与表结构，revision 注册表约束集合；后续新版本需要显式注册，不自动将旧配置解释为最新目录。代价是新运行共享校验源码变化时保守重算，不能精确只失效新增类别。
- 新硬件职责是三条封闭中文句式，不覆盖任意 FPGA/SoC/IC 自然语言；未知语境保留未决。B32 只核对显式外部主张，能定位原文不证明语义真实，不能认证审核人身份。
- 八类同步建设基础目录的产品原则已落文档，具体正式名单、例外、别名、方向/级别值集、跨职能边界、人工发布/准入与真实质量阈值仍待讨论；正式目录保持空。
- 未验证真实 JD 语义准确率、开放覆盖率、真实模型、生产集成、前端/图谱/匹配、断电/磁盘损坏/网络盘或跨机并发，不输出正式职位数量或市场指标。不启动 B4，不合并，不删除原分支/工作树。

## 交付核查

- 实现提交 `eb90780`，文档与实施证据提交 `59096e3`；本节及计划/资产交付状态另以收尾文档提交补录。
- [PR #15](https://github.com/Serena-Lyric/TalentMind/pull/15) 已创建并附到当前聊天，base=master，head=codex/m2-stage-b3-3-eight-families。创建后实际查询 OPEN/MERGEABLE、mergedAt=null、autoMergeRequest=null，statusCheckRollup 为空，没有远端 CI 结果可引用。
- 保留实施报告、独立工作树与分支供 ChatGPT 复审；不合并、不启用自动合并、不删除分支。正式标准岗位名单仍待产品讨论，本地测试与内部审查不等同 ChatGPT 验收。

## ChatGPT 独立复审、产品后续增量与归档（2026-10-16）

[PR #15 ChatGPT Review #5550332006](https://github.com/Serena-Lyric/TalentMind/pull/15#pullrequestreview-5550332006) 独立核对七类 v1 字节和旧历史兼容、八类 v2 注册及有限硬件交付句式、B3-1/B3-2 显式版本绑定、旧审核隔离、不可变报告和离线故障恢复，未发现新的 Critical/Important 合并阻塞项。Codex 报告 B3 定向 258 passed、完整离线阻网 971 passed / 2 skipped / 23 deselected、外部连接尝试 0；ChatGPT 未在同一 Windows 环境独立重跑全部测试，真实 JD 分类准确率仍未验证。用户已授权归档及合并 PR #15，实际状态以 GitHub 为准；保留原分支与工作树。

**B3-3 开发完成之后确认、留待后续独立实现的产品决策：** 「硬件与集成电路」研发及工程技术并重，承担核心技术职责的工艺、封装、制造及测试岗位纳入，普通产线操作排除；宽泛岗位信息只能支持 job_family 时 canonical_job 留 unknown、不强行细分；成熟复合职业必须有跨领域一体化完整技术交付责任的证据，不能只看标题/技能或辅助兼任；同一 JD 只有具备多个**明确独立招聘目标**的证据才允许拆分，否则保留原 JD/待复核，识别职位目标不等于推定招聘人数。此前的 v2 范围文字及合成规则不倒填为已覆盖新边界，待下一阶段另行版本化建设。
