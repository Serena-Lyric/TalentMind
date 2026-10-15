# M2 阶段 B1：JD 分层筛选实施与验证

日期：2026-10-15。基线：master `d10fce2`（PR #4）。本报告开发期间保留，合并前按 AGENTS 沉淀长期结论并归档或移除。用户已明确授权独立连续实施与 PR，无需再次批准子步骤。

## 设计与实施计划

产品依据：本轮用户确认的 B1 规则及 PRODUCT_DECISIONS 的 M2-01～27。工程选择：沿用 Python/SQLite/JSON，无新增依赖。

1. 先编写真实离线路径的失败测试：技术/非技术/冲突/短 JD/非招聘/解析异常、证据定位。
2. 新增 `screening/`，通过 foundation 的 InputRecord、规范序列化、快照表、文件锁和原子输出复用基础能力。B1 运行、成员、范围、规则、判断独立保存，不向 A 的 tasks/attempts/facts/heads 写入。
3. 验证完整输入/范围内容/规则版本的复用键、观察独立保存、历史不可变、增量缺项保留、各事务与输出中断恢复；用既有 A 库检验双向运行与重放。
4. 运行 A 回归与阻断网络的后端非集成回归，写入实际数量和限制；补产品决策、索引、README、资产与测试说明。
5. 完整分支审查，修复阻塞问题后推送独立分支并创建面向 master 的 PR；不合并、不启动 B2。

检查重点：坏行与合法成员混合时不漏记；同一身份重复输入不可覆盖；标题和职责冲突；否定/引用等未可靠理解的表达；发布失败后不重复生成已提交判断。

## 具体代码范围

| 文件 | 职责 |
|---|---|
| `backend/app/job_analysis/screening/rules.py` | 严格范围/判断结构、可解释活动规则、原文字段字符偏移、规则及范围 manifest |
| `screening/inputs.py` | JSON 数组/JSONL 分单元错误审计，复用 A InputRecord/完整指纹/禁止凭据字段校验 |
| `screening/store.py` | 继承 A 文件锁及 SQLite 身份保护，只增加 b1_* 表并共享不可变 snapshots |
| `screening/runner.py` | 冻结数据集成员、增量复用、独立判断尝试、恢复、审计、重放，复用 A 原子 publish |
| `screening/__main__.py` | 显式 run/resume/replay CLI、输出/状态/输入隔离检查与退出码 |
| `screening/software-related.offline.json` | 显式、带版本的软件相关技术活动离线试验范围 |
| `backend/tests/test_job_analysis/test_screening.py` | 60 项合成实际执行路径回归，真实临时 SQLite 与子进程硬退出 |

新增包入口 `screening/__init__.py`；无新增第三方依赖。foundation 的 inputs/models/store/runner/aggregate 及旧业务代码均未修改。正式 DDL、配置密钥、exchange、M1/M3/M4/M5 不变。

文档：产品主文档追加 M2-28～31，决策索引追加 D67～D70；更新 M2 README、根 README、资产与状态，并记录 [开发陷阱](../superpowers/traps/2026-10-15-m2-b1-scope-and-input-audit.md)。核对 GitHub PR #4 状态 MERGED 与 merge commit d10fce2，修正资产清单仍写“待合并”的过时实现状态，不改历史决策原文。

## 判断规则与边界

- 有效性为 valid/invalid/undetermined；范围为 in_scope/out_of_scope/needs_review。无效 JD 的范围为空；解析/执行失败为独立 execution_status，validity=not_evaluated，不伪装范围外。
- 正向技术证据需要开发/测试/数据/运维动作及其工作对象，标题只作为协同/冲突线索；不依赖技能计数、标题白名单或单个工具词。只有一个技能的开发实习 JD 可纳入，行政报表使用 Excel 可依据行政活动排除。
- 标题/职责冲突、正反活动并存、已识别否定、历史/教程/公司背景及产品归属语境保留 needs_review。无可靠活动也复核；不把未知文本默认排除。
- 无内容判定复用 M1 `is_valid_jd` 作为信号，并综合独立 duties/requirements；M1 原始字段/状态不改写。没有实质岗位内容的可识别元信息/占位与明确非招聘材料单独记 invalid。未知剩余文字不自动确认为真实招聘。
- 范围样例仅定义四个工作活动证据组，允许显式缩小集合，不输出职业分类/主辅岗位/级别，不把样例当最终目录。复杂 NLP 未在本轮建设。

## 输入、结果、审计格式与复用

完整运行示例和范围 JSON 结构见 [M2 README](../../backend/app/job_analysis/README.md)。run 必须显式指定 --input、--dataset、--state、--output、--scope，可加 --rules-version；resume/replay 明确指定 --run、--state、--output。解析/筛选失败有审计文件且退出 2；无效/排除/复核属于正常判断，退出 0。

- 合法 JD 沿用 A 的 id/source/job_title/raw_text 必填项、可选文本职责/条件和完整其他 JSON 字段。数据集+原始 ID 是身份，正文/标题/职责/条件等完整 payload SHA-256 是内容键，观察时间不进指纹。
- 每次运行冻结完整 B1 数据集最后可解析 heads，加上当次失败单元。结果的 input_position 指当次输入位置，缺席旧成员为空；input_snapshot 仍指其真实来源 run/hash/position。失败单元没有 JD 快照时保留文件摘要、位置、可可靠读取的 ID 和安全错误，不编造身份。
- JSONL 坏行不阻断后续合法成员，重复身份作为单独错误；行号用物理行号，忽略空行。整文件容器损坏、无记录或根类型错误，只能记 position=0 的一个失败输入单元，不能声称知道内部 JD 条数。任意失败单元都令整文件原始字节不落盘；合法 JD payload 仍完整保存，源文件不改动。
- b1_versions 保存完整范围与规则清单及摘要，decision 按 snapshot_id + version_id 查复用；配置内容或标签、规则修订变化都产生新判断，输入变化产生新 snapshot。观察另存 b1_observations。同文不同身份各自保留，不去重/下架。
- 结果保留 namespace/jd_id/snapshot_id/fingerprint、source/source_detail、规则与范围版本、decision_id/decided_at、三层状态、reason_codes/explanation、review_reasons/execution_error 和 evidence(field/start/end/quote/signal)。字符定位为原字段左闭右开 Python 字符偏移，提交前逐字核查。
- 审计顶层 member_total、两组状态计数、失败/原因数量针对“冻结数据集成员+当次输入失败单元”；另有 current_input 子审计，与 input_total 对账。两组状态各自加总均等于适用 member_total；无效与错误在 scope_counts.not_applicable，undetermined 属 needs_review。输入数不冒充独立职位数。
- 不可变报告按 run_id 保存 SQLite 与原子 JSON 文件；恢复原运行不受新输入影响。失败筛选可在新 run 重试，旧报告和旧失败不改写。规则实现依赖不一致时拒绝 resume，但旧报告仍可 replay。
- formal_statistics_eligible 固定 false，analysis_status 为 not_executed_by_b1；无技能事实、正式需求率或独立职位数量。

## 与阶段 A 的兼容

复用 A 的 SQLite application_id、user_version=1、锁与快照保护。B1 只增加 b1_versions/runs/heads/observations/members/decisions/reports，不写 A runs/tasks/attempts/facts/observations/heads/aggregates。首次筛选必须显式输入 B1 数据，不自动读取 A heads；后续使用同一 B1 状态路径才能跨运行累积数据集。

实际兼容测试先创建有成功事实及聚合的 A 库，再用 B1 连续筛选与更新规则，最后用原 AnalysisStore 打开、重放 A 聚合并再次 A execute：原 attempt_id 复用、A 事实数量不变、user_version 仍为 1，A 业务结果一致。另完整运行 A 99 项回归（包含原恢复/重放）。旧 StateDB 的拒绝策略沿用 A，未执行迁移。

B1 判断事务提交与报告发布分开。覆盖 after_prepare/after_start/after_screen/before_commit/after_commit/after_report/after_stage_output/after_output 八处真实 os._exit(71)，恢复后所有成员在场、无 running 尝试、成功判断每个成员仅一份；发布失败恢复不重新筛选。终态、版本与报告的 UPDATE/DELETE/REPLACE 保护有真实 SQLite 断言。

## 本轮实际测试结果

环境：Windows / Python 3.14.5，复用已安装 requirements 的 Python 环境；工作树没有复制原 .env。以下命令工作目录为 backend；独立工作树用已有 Python 绝对路径代替 .venv，语义相同。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_screening.py -q --tb=short
# 60 passed，0 failed / 0 skipped
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_foundation_inputs.py tests/test_job_analysis/test_foundation_validation.py tests/test_job_analysis/test_foundation_runner.py tests/test_job_analysis/test_foundation_cli.py -q --tb=short
# 99 passed，0 failed / 0 skipped
```

完整后端非集成回归：合成配置及网络阻断，只允许 Windows Python 内部 socketpair 自连接；非“not integration”以外的整套服务测试不能直接运行。

```powershell
$b1TestCode = @'
import os, socket, sys, pytest
os.environ.update(MYSQL_URL="sqlite:///:memory:", NEO4J_URI="bolt://127.0.0.1:1",
    NEO4J_USER="offline", NEO4J_PASSWORD="offline", REDIS_URL="redis://127.0.0.1:1/0",
    OPENAI_API_KEY="offline-test", OPENAI_BASE_URL="http://127.0.0.1:1",
    LLM_API_KEY="", DS_API_KEY="", LLM_BASE_URL="http://127.0.0.1:1", DS_BASE_URL="http://127.0.0.1:1",
    GITHUB_TOKEN="", JD_DATA_PACK="__offline_no_data_pack__")
original_connect = socket.socket.connect
denied = []
def offline_connect(sock, address):
    caller = sys._getframe(1).f_code
    if caller.co_filename == socket.__file__ and caller.co_name == "_fallback_socketpair":
        return original_connect(sock, address)
    denied.append(str(address))
    raise RuntimeError("offline regression: service/network connection prohibited")
socket.socket.connect = offline_connect
socket.socket.connect_ex = offline_connect
result = pytest.main(["-m", "not integration", "-q", "-rs", "--tb=short"])
print("Blocked external/service attempts:", len(denied))
raise SystemExit(result or bool(denied))
'@
$b1TestCode | .\.venv\Scripts\python.exe -X utf8 -
```

最终实际结果：**500 passed / 2 skipped / 23 deselected / 0 failed**，190 项既有依赖弃用警告；**Blocked external/service attempts: 0**。两项 skipped 为 test_m2_return_package.py:15/:26，原因是私有 input 原回包未随干净检出提供；23 项真实服务 integration 测试未运行。修复审查问题前的一次完整回归为 496 passed，本报告采用修复后新增四项回归的 500，不沿用 PR #4 的 440。

所有新增 fixture 均在 finally 关闭/删除临时目录并断言不存在；子进程终止后核对无 running、成功判断不重复。未进行真实 MySQL/Neo4j 集成测试，未写入生产库，因而没有生产库夹具残留查询或“生产数据计数不变”的声称。原工作区唯一未提交资产文档 SHA-256 开发前后均为 F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B，未带入提交。

## 开发与内部检查

- 首批 36 项实际执行路径测试因缺 B1 功能失败，完成最小实现后全部通过。
- 增补语境/来源/硬退出/输出异常/凭据/证据校验，发现教程语境和旧成员来源引用两项失败，修复后 56 passed。
- 按 requesting-code-review 做一次只读子代理检查，合成探针发现三项 Important：直接否定、公司产品属性误作职责、截断 JSONL 凭据字节落盘。增加四项回归，实际 4 failed 后修复至 60 passed；没有未处理的 Critical/Important，也没有提出后延期的 Minor。
- 上述是 Codex 内部检查，不能替代用户要求的交付后 ChatGPT 独立审查；没有声称已获 ChatGPT 最终验收。

## 风险、后续依赖与交付

规则只能保守覆盖已定义的动作/对象及语境，对未识别的主体、跨句否定、引用、双重否定和新表达仍有误判风险；对不在已定义活动表达中的技术 JD，可能过多保留 needs_review。当前样例不能证明真实准确率。范围外不意味着岗位无效；规则复核也不替代正式语义基准。

B2 后续需要在独立授权下处理技能五态、未知候选及独立标注评测；B3 才裁决完整职业目录/主辅/级别；B4 才涉及真实模型、预算与外发。B1 没有启动上述工作，未给人工复核建设 UI/改写 API，也没有将筛选接入旧生产管道。

交付分支：`codex/m2-stage-b1-scope-screening`，面向 master；提交及 PR 链接在交付后补录。独立审查通过并经用户授权后再由 ChatGPT 合并；本轮不合并、不删除工作树/分支。长期规则与使用说明已沉淀正式文档，临时报告合并前按 AGENTS 处理。
