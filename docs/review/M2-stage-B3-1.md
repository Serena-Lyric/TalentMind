# M2 B3-1 实施报告（Issue #10）

日期：2026-10-16。状态：独立开发交付，等待 ChatGPT 复审和用户合并授权。

## 范围与基线

- 任务书：[Issue #10](https://github.com/Serena-Lyric/TalentMind/issues/10)；最新 master 基线 `bbd698fc88a866b44f1c24dc974d85149ec96d56`，PR #9 合并后。
- 独立工作树 `C:\Users\Serena Lyric\.codex\worktrees\m2-stage-b3-1-family-proposals\TalentMind`，分支 `codex/m2-stage-b3-1-family-proposals`。原工作区 M1 分支及未提交文件保持；原资产文件 SHA-256 核对为 `F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B`。
- 实现提交 `d8de211`（目录与建议）、`1d53545`（存储与 CLI）、`6489756`（审查定向修复及额外来源/路径验证）；文档提交见 PR commit 列表。不修改正式 DDL、旧 exchange、前端、词典或旧 B3-0 源码。
- 产品仅追加用户已确认 M2-41～43，决策索引 D80～82。工程选择与执行记录见[计划](../superpowers/plans/2026-10-16-m2-b3-1-family-proposals.md)。

## 已实现及可检查产物

| 产物 | 行为 |
|---|---|
| role_classification/proposals/families.v1.json | 独立版本化七类 stable ID/中文名/范围说明；拒绝重复/缺项/目录外值，其他三维目录为空 |
| models.py | 独立严格 Proposal/schema；逐项 namespace、JD、指纹、原字段、字符区间引文校验；待审/未完成/无正式统计资格不可升级 |
| rules.py | 有限动作+工作对象+交付成果句式；核心/辅助/未明确责任线索、标题对照、未解析上下文和跨字段冲突 |
| runner.py / store.py | 独立 b31 四表、不可变历史、完整输入字节/版本清单/观察；源码/目录/规则变化追加，提交前整轮回滚，提交后原样 replay |
| __main__.py | 显式 input/dataset/taxonomy/state/output 的 run 与 replay；复用原子发布/路径/锁/硬链接保护 |
| test_role_proposals.py | 87 项合成真实执行路径回归，临时 SQLite，socket 阻断 |
| proposals.input.json | 十条手写合成 CLI 演示；非真实招聘语料或人工真值 |

七类稳定 ID 与全部封闭句式列于 [M2 README](../../backend/app/job_analysis/README.md)，避免在此复制维护。没有新增依赖。子包结构避免进入 B3-0 顶层 Python glob，旧 empty/synthetic_example、known 断言与旧 report/replay 保持原样。

### 核心交付与候选边界

- 七类简单核心句式可得到 family 候选与 primary_family_hint；只表示 family 层待审提示，**没有确定 canonical_job 主岗位**。已有 B3-0 人类/合成输入不被改写。
- 句式限定整分句：核心职责/主要职责/主要负责 + 已列动作/对象/交付；协助/辅助/配合为辅助；仅“负责”为主辅未明确。按职责条数或技术词频不评分、不推工作占比。
- 没有核心、多个核心、未明确职责、标题冲突、多职位或复合词、未知职责均未决；标题绝不独自生成候选。标题只匹配辅助类不能消除与核心类冲突。
- 技术实施、复杂故障诊断、架构/技术方案和客户生产系统交付有合成正例；技术销售、普通客服、商务、产品演示、操作培训、技术词列表为反例。否定/条件/他人动作及不支持句式保留上下文，不能强行分类。
- 已识别公司/历史/培训/示例等章节不作当前职责；跨字段相同分句落在排除/未解析语境时撤销该分句候选并保持 unresolved，原 payload 不变。并不承诺理解任意跨句否定、主体、未知章节或开放域语言。
- 全栈不新建 canonical_job，多职位材料不拆分，辅助家族不增加独立 vacancy。七类目录并不使 B1 范围重算，也不隐式执行 B2。
- 所有候选 pending_review，classification_complete=false、formal_statistics_eligible=false；canonical_job/seniority=unknown，technology_tracks=[]。不输出真实需求率、岗位占比、独立职位数、模型或匹配分数。

## 回归过程与结果

| 阶段 | 实际结果 |
|---|---|
| 目录/职责首组 RED | 52 failed / 1 passed（既有目录解析兼容原本通过） |
| 首组 GREEN | 53 passed |
| 持久化新增 RED → GREEN | 17 failed / 53 passed → 70 passed |
| 与旧 B3-0 合跑 | 119 passed |
| 内部审查两项 Important 定向 RED | 14 failed / 1 passed / 70 deselected |
| 定向修复后与旧 B3-0 合跑 | 134 passed |
| 实际源码失效复制路径检查 RED | 1 failed / 86 passed；短长路径统一后 87 passed |
| 首轮完整阻网非集成 | 832 passed / 2 skipped / 23 deselected，连接尝试 0 |
| 修复后完整阻网非集成 | **849 passed / 2 skipped / 23 deselected / 0 failed**，190 既有依赖警告，连接尝试 **0**（36.58s） |

两项 skipped：test_m2_return_package.py:15/:26 缺 Git 忽略的私有原回包。23 项真实服务 integration 未运行，未接触 MySQL/Neo4j/Redis。190 项警告来自现有 neo4j、starlette/fastapi 依赖弃用。

交付树最后复跑同一完整命令仍为 **849 passed / 2 skipped / 23 deselected / 190 warnings / 连接尝试 0**（36.67s）。新加本地 Markdown 链接 9 项核验无损坏；B3-0 六份顶层源码 diff 为空，原工作区资产哈希再次一致。

覆盖七类及技术服务反例、无匹配、主辅不足、重复辅助不改变主类、标题/正文冲突、多个核心、疑似多职位、复合职业、跨字段非职责语境、错误/跨 JD 证据、来源字节/记录/身份伪造整轮拒绝、目录版本和内容/规则/实际源码变更追加、观察复用及输入位置。事务中第二条伪造证据验证第一条也不残留；旧 A/B1/B2-1/B2-2/B3-0 逐表逐行对比、旧 B3-0 replay/manifest、A running 不恢复与旧 StateDB 拒绝均通过。

五处真实子进程 `os._exit(73)`：after_result、before_commit、after_commit、after_stage_output、after_output；提交前 reports/results=0，提交后原报告可重放、临时发布文件可恢复，不覆写不同内容的既有产物。

### 使用及复现

工作目录 backend；独立工作树无 venv，可替换为已安装 requirements 的 Python 绝对路径。本次 Python 3.14.5。

```powershell
python -m pytest tests/test_job_analysis/test_role_proposals.py tests/test_job_analysis/test_role_classification.py -q --tb=short
```

完整回归使用合成配置与 socket 阻断，沿用 B3-0 已审查方式，只允许 Windows Python 内部 socketpair 初始化。未加载原工作区 .env：

```powershell
$b31Regression = @'
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
$b31Regression | python -X utf8 -
```

实际模块入口经子进程 runpy 执行 run→replay（同时在子进程阻断 socket），十条仓库合成示例：b31_reports=1、b31_results=10、with_family_candidates=9、unresolved=3，重放 JSON 与原报告完全相同。finally 删除专属临时目录并核对剩余文件 0。

测试共用 area fixture 在 finally 关闭/删除专属临时目录并断言不存在。第一次额外 smoke 因 sqlite3 connection 的 with 不关闭句柄而清理失败，改用 contextlib.closing 后重新 smoke 成功；首次遗留两文件精确删除并核对目录不存在。一次递归清理请求被自动审批阻断，后按已列出的两个精确文件及空目录逐项清理成功，无权限绕过。一次根目录 pytest 路径调用没有找到测试，校正到 backend 后才获得有效结果。

没有生产写入或真实库访问，因此不声称查询过生产行数或生产夹具计数。

## 内部审查与工程裁定

独立只读子代理审查基线 bbd698f..1d53545 及全部新增代码、目录和测试，独立运行局部 70 passed。提出 2 项 Important、无 Critical/Minor：

1. 提取 duties 可绕过 raw_text 中的历史/公司介绍/培训语境。
2. 标题仅因匹配辅助家族而隐藏与核心家族的冲突。

两项均由上述失败回归复现并修复，规则标签升级 closed-delivery-clauses-v2；未延期已报告缺陷。新增实际源码测试发现的 Windows 路径问题也有失败证据并修复。[陷阱记录](../superpowers/traps/2026-10-16-m2-b31-cross-field-and-title-context.md)。修复由开发者测试验证，未声称审查代理重新审过最终修复，也不能代替交付后的 ChatGPT 独立复审。

工程裁定：新 schema/表/子包隔离旧断言；family 层主辅提示不填 canonical_job；封闭试验句式只作为待审建议。这些是 Issue 允许的实现选择，不新增技术程度、混合岗位阈值或标准岗位产品裁决。封闭语法的代价是大量真实表达无法命中，继续保留待复核。

## 遗留与交付

- 完整标准岗位名/别名、技术方向/级别、复杂混合岗位/同等核心细则、多职位拆分、目录外正式准入及人工审核流程仍未确认。
- 未验证真实 JD 语义准确率、模型效果、生产迁移、前端、跨机/网络盘/断电恢复；仅本地合成 SQLite 与进程中断。
- 未运行真实模型/收费 API/采集，未触碰生产数据，未启动 B4/M3/M4。
- [PR #11](https://github.com/Serena-Lyric/TalentMind/pull/11) 已创建并附到当前聊天，base=master、head=codex/m2-stage-b3-1-family-proposals；创建后核查 state=OPEN、mergedAt=null、autoMergeRequest=null，远端无 CI 检查结果可引用。实施报告保留至 ChatGPT 复审，不删除工作树或分支。合并前归档与清理由后续明确授权处理。
