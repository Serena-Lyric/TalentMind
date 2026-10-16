# TalentMind M2 B3-2 实施报告

日期：2026-10-16（Asia/Singapore）。任务：[Issue #12](https://github.com/Serena-Lyric/TalentMind/issues/12)。本报告保留至 ChatGPT 独立复审，合并前归档及清理须遵循 AGENTS 后续授权流程。

## 基线与交付范围

- 从已 fetch 的最新 `origin/master` **327c5349413b5d566db0257cf8b612c6b4e3f576**（PR #11 合并）建立独立工作树、分支 `codex/m2-stage-b3-2-canonical-governance`。原仓库 `codex/m1-stage-02` 的未提交资产文档未改动、未夹带；本轮仅显式暂存列出的文件。
- 新增 `role_classification/governance/`：严格候选/关系/审核契约、证据验证、版本、SQLite、run/replay/review/export-reviews CLI、空正式目录配置。复用 A 的输入规范、快照、锁与发布；无新依赖，无生产契约迁移。实现提交 **6d57ba0596766962d255f0827b80cb2f0c90d4ec**；本报告与验证材料随同提交，交付状态补录另为文档提交。
- 新增两份测试和三条纯合成 JD/四个显式候选/一条 related_to 关系。样例不是标准岗位名单、人工真值或真实招聘材料。
- 产品主文档只追加用户在 Issue 中确认的 M2-44 多核心未决原则，索引 D83；名单/粒度/成熟复合边界/正式发布仍未决。同步 M2 README、根 README、导航、资产和陷阱。

## 需求到行为

| 要求 | 实际行为与验证 |
|---|---|
| 空正式目录、合成隔离 | 配置 formal_jobs 只允许空数组；候选 synthetic_only 与来源类型一致，合成模式拒绝伪造人工来源，所有 formal_admitted 恒 false |
| 稳定 ID、原名及候选类别 | 显式候选 ID 整轮唯一；原名须精确原文，可能规范名只是主张；0～多个七类 ID，无单父映射 |
| 名称冲突与关系 | 逐 JD 和整轮同名审计；synonym 多目标单列；related/specialization/technology/composite 均不合并、映射或传递；无正式别名映射 |
| 技术方向、复合与多职位 | technology_stack 不进入主岗位候选集合；mature_composite_candidate 不自动变成熟职业，不拆分；possible_multiple_positions 须显式证据，不生成 vacancy |
| 多个同等核心/标题职责冲突 | 外部责任主张全部保留；有候选时主岗位保守 unresolved，无候选 unknown；不使用条数/词频或唯一候选自动定主岗；显式冲突有分字段证据 |
| 原文与危险上下文 | 保存完整 source_payload、标题/职责引文与所引字段全文；核对 namespace/jd_id/fingerprint/字符区间，拒绝跨 JD、缺证据/错位；语义判断不自动执行 |
| 候选、审核、准入分离 | 具名审核人、依据和本 JD 原文引用；绑定 result_id + 目标 + manifest/完整提交/正文摘要；接受/驳回/延期/撤回均只追加；原候选和报告待审状态不改 |
| 历史、恢复、旧层隔离 | b32 六表追加且 UPDATE/DELETE/REPLACE 拒绝；完整输入/提交/目录/规则/源码保存，整轮事务；旧层逐表、manifest、replay 比较不变；不恢复旧 A running |

没有实现自然语言岗位候选提取器或 B3-0/1 自动来源适配。可核验的引文是外部主张的出处，不代表当前招聘语义已独立验证；历史、公司介绍和否定原文保留给审核，不由候选层升级为事实。程序不能认证审核人身份或证明其依据正确。

## RED → GREEN

1. 先写契约/证据回归，**47 failed**（治理包缺失）→最小实现 **47 passed**。首次 GREEN 中修正了测试辅助函数提前构造默认引文及按数组序号取上下文的测试假设，未改变产品行为迁就断言。
2. 持久化、版本、审核、CLI、共库及中断首组 **32 failed**（store/runner 缺失）→合并契约 **79 passed**。
3. 增加跨 JD 同名审计、不可变审核导出与候选内容变更审核绑定，观察失败后实现，**82 passed**。
4. 再增规则变更但正文不变的审核复制回归，**1 failed / 1 passed**：仅正文摘要不足。修复为 manifest + 完整提交 + 正文联合 result_version，最终 **83 passed**。记录见 [陷阱](../superpowers/traps/2026-10-16-m2-b32-review-result-version.md)。

定向命令（backend；工作树无 venv，实际使用原仓已安装环境 Python 绝对路径）：

```powershell
python -X utf8 -m pytest tests/test_job_analysis/test_role_governance.py tests/test_job_analysis/test_role_governance_storage.py -q --tb=short
```

独立只读审查代理对当前实现自行运行同两份测试：**83 passed（5.18s）**，未发现可复现 Critical/Important/Minor；没有延期审查问题。该审查不替代交付后 ChatGPT 集中复审。

## 完整离线回归

实际 **932 passed / 2 skipped / 23 deselected / 190 warnings，57.65s，外部/服务连接尝试 0**。两项 skip 为未随仓提供的私有原 M2 回包；23 项真实服务集成未运行；警告为既有依赖弃用。未加载原仓 `.env`，使用合成服务配置与 socket 阻断；仅允许 Python Windows 内部 socketpair 初始化：

```powershell
$b32Regression = @'
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
$b32Regression | python -X utf8 -
```

四处真实子进程 `os._exit(71)`（after_result/before_commit/after_commit/after_output），提交前无局部结果、提交后原报告可 replay；另有事务异常、发布失败及删除当前输入后原样重放测试。审核事件截面独立保存/重放，后续事件不改变旧截面。共库测试实际跑 A/B1/B2/B22/B30/B31，再比较所有既有表逐行、旧版本清单及旧报告重放。

提交树最终复跑同一阻网完整非集成命令：**932 passed / 2 skipped / 23 deselected / 190 warnings，55.04s，外部/服务连接尝试 0**。本地 UTF-8/替换字符/Python 语法核验覆盖全部 21 个变更文件，Markdown 本地链接 134 项通过，`git diff --check` 通过。核验脚本最初使用未解码的 Git 引号转义路径报错，改用 NUL 分隔 UTF-8 路径后获得有效检查结果，未修改产品代码。远端 master 在提交前复核仍为 327c534。

实际模块入口经阻网子进程运行仓库合成示例：run → replay、review → export-reviews → replay export 均一致，临时库 reports/results/reviews/exports **1/3/1/1**。临时根先核对位于系统 TEMP 且带本任务前缀，再在 finally 清理并断言不存在，**剩余 0**。测试 area fixture 同样 finally 清理；未访问生产库，不声称查询过生产行数/夹具计数。

## 工程选择与未决

- 共库只追加 b32 六表，复用共享 snapshots/锁/发布，避免复制整个框架；没有改旧上游源码或版本 glob。完整 submission 变更保守失效所有本轮结果，成本是多重算，避免未经确认的依赖裁剪。
- 候选关系限同一 JD/同版本的显式候选；跨 JD 的同名可审计，但尚无跨 JD 关系编辑。稳定 ID 必须结合 result_id/result_version 读取，不能只取“最新同名”。
- 所有主岗位候选都保守 unresolved，本轮不选择单核心主岗；无岗位语义提取、自动标题矛盾检测或成熟职业判定。具体名单、命名粒度、复合职业边界、跨职能细则与正式审核/发布准入由用户与 ChatGPT 继续决定。
- 未验证真实 JD 语义准确率、自然语言覆盖率、真实模型、生产迁移、前端/图谱/匹配、断电/损坏/网络盘恢复；不输出需求率、独立职位数量或匹配分数。
- 不合并 master、不启用自动合并、不启动 B4/M3/M4，不用生产数据/真实模型/付费 API，不覆盖 exchange，不删除原分支/工作树。PR 交付后等待 ChatGPT 独立复审与用户授权。

## PR 交付核查

[PR #13](https://github.com/Serena-Lyric/TalentMind/pull/13) 已创建并附到当前聊天，base=master、head=codex/m2-stage-b3-2-canonical-governance。创建后独立查询 state=OPEN、mergeable=MERGEABLE、mergedAt=null、autoMergeRequest=null；远端没有可引用的 CI 检查结果，本报告测试为本地执行证据。源码/测试实现提交 6d57ba0，最终补录仅修改本报告、计划状态与资产索引；不因此重跑业务测试。工作树与分支保留，等待 ChatGPT 复审；未自行合并。
