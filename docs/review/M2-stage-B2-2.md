# M2 B2 第二轮：技能治理与离线评测

日期：2026-10-16；基线 `63c897b`（PR #6 已合并）。开发分支 `codex/m2-stage-b2-2-skill-governance`。本报告在开发中持续补充，Codex 自检不替代 ChatGPT 独立审查；不自动合并，不启动 B3/B4。

## 设计与执行计划

**Goal**：不改写 A/B1/B2 第一轮事实与历史，提供有证据、可版本化重算的名称/分类/候选治理，以及可扩充的离线评测基础。

**Architecture**：新增 `backend/app/job_analysis/governance/`，消费已有 B2 run 和不可变 snapshots。词典只读，使用显式审定关系覆盖层，保留未审别名及冲突审计；独立 b22_* 表追加治理结果。旧 B2 body 原样引用，版本、关系、分类与候选结果均另存。复用标准库、现有 Pydantic、SQLite 锁与原子发布，不引入服务或依赖。

**Spec**：本轮用户任务书及 PRODUCT_DECISIONS M2-37～40。规则只覆盖有限明确格式，无法可靠判断保留复核。候选等级表示提取上下文依据，不是经过校准的可信概率。

**Global constraints**：285 条 seed、共享 normalizer、A/B1/旧 B2、正式 DDL/交接/生产接口均不修改；未知候选自动准入始终关闭。无真实 LLM/API/生产库；只用合成输入、临时 SQLite、隔离输出。无市场需求率、B3/B4/M3/M4 扩展。

**Review focus**：版本后缀被吞；canonical/alias 覆盖顺序；行业/证书伪技能；同职位多来源伪验证；标注缺失/分母为零/定位正确却事实错误。每项在对应测试中覆盖。

### Task 1：名称治理与审计

- 文件：`governance/catalog.py`、`policy.v1.json`；`tests/test_job_analysis/test_governance.py`。
- 接口：`Catalog(seed=None, policy=None).resolve(raw)`、`.audit`、`.manifest()`；同义/related_to/narrower_than/version_of 只按显式关系解释，版本身份独立。
- [x] 先写同义/相关/版本/重复键与顺序冲突测试，观察 RED。
- [x] 实现只读覆盖层、未审别名保留与审计，运行 GREEN。

### Task 2：分类、候选与持久化

- 文件：`governance/extract.py`、`models.py`、`store.py`、`runner.py`、`__main__.py`。
- 接口：`analyze(record, original_semantics, catalog)`；`execute(store, b2_run, catalog=None, revision='v1', output=None)`；`replay(store, run_id)`；候选审查与准入验证为离线可审计接口，无正式词典写入能力。
- [x] 先写四类、非技能、假技能、未知候选/重复来源/无准入权限、A/B1/B2 共库与历史回放测试，观察 RED。
- [x] 实现逐次原词/版本/位置、原陈述引用、有限非技能事实、分级候选、追加持久化和 CLI，运行 GREEN。
- [x] 核验旧事实与输入完全不变，版本变化只追加；失败与部分结果不提升完整性。

### Task 3：离线评测基础

- 文件：`governance/evaluation.py`，`tests/fixtures/governance/`，`tests/test_job_analysis/test_governance_evaluation.py`。
- 接口：`load_benchmark(path)`；`evaluate(benchmark, predictions)`，提取器输出、参考标注与程序证据检查分开。
- [x] 先写字面预期的计数、遗漏/误提取、五态混淆/必备误判、组合/成员、分类泄漏、候选误准入、零分母/缺标注及未审核真实语料拒绝测试，观察 RED。
- [x] 实现严格读取器、指标和差异列表；合成参考仅作程序自检，未获人类复核前不称人工真值或语义质量结果。运行 GREEN。

### Task 4：交付

- [x] 运行 A/B1/B2 第一轮兼容及全量阻网非集成回归；记录实际通过/失败/跳过/排除及清理。
- [x] 更新产品主文档、决策索引、M2 README、资产与陷阱；检查完整 diff。
- [x] 全分支内部检查，定向修复有失败回归；独立提交、推送及创建面向 master 的 PR，保留外部独立审查门禁。

## 执行记录

- 原工作区 `codex/m1-stage-02` 的未提交资产记录保留；本轮使用独立管理工作树，未夹带其修改。
- 已核验 `origin/master=63c897baf067ff8986aac820f709197530920f93`、PR #6 MERGED。四项产品决策编号核对后追加 M2-37～40、索引 D76～79，无重号。
- 工程裁定：消费现有 B2 run，而不在新入口隐式重跑 B2；历史语义完整保留。名称治理可以纠正覆盖层的映射，但不据此修改原五态、程度、组合或有效状态。
- 工程裁定：只按明确能力动词/技能列表格式提取开放词候选；不能解释的其余片段继续保留未解析证据。无概率阈值，无独立来源验证结论。
- 工程裁定：Codex 编写的合成参考只能充当评测程序的测试预期，不能冒充人类已复核标注。真实效果报告必须具备合法来源和人类审核声明。


### 实际验证（内部检查前）

- 环境：Windows、Python 3.14.5，复用原仓库已安装依赖的绝对路径 Python；独立工作树无 .env、无真实输入/服务配置。
- 首批治理 RED：33 failed（包未实现）；实现后 33 passed。评测首批 15 failed、预测投影 1 failed；实现后新增反例/CLI 共 5 failed / 53 passed，修复后新模块 **58 passed**。
- A/B1/B2 与首批新模块合跑 **319 passed**（当时新模块49项），A/B1/B2原有270项全部执行；其后完整非集成回归包含新增58项。
- 完整合成配置与 socket 阻断非集成回归：**669 passed / 2 skipped / 23 deselected / 0 failed**，190 项既有依赖弃用警告，Blocked external/service attempts: **0**（24.55s）。两项 skipped 为 test_m2_return_package.py:15/:26，缺 Git 忽略的私有原回包；23 项真实服务 integration 按授权边界排除。未运行生产 MySQL/Neo4j/Redis 或收费模型。
- 期间一次从仓库根误调用 pytest 导致16项 app import失败，改为文档规定的 backend 工作目录后恢复；不是功能缺陷，未修改测试绕过。一次全量日志目录路径错误导致命令未启动，修正后才产生上述有效测试记录。
- 兼容测试逐字段比对 A/B1/B2 所有既有表，legacy_required 仍 unreviewed、user_version=1；旧 b2-1 报告、原五态/程度/对象/组合/effective/证据逐字段不变。治理历史 UPDATE/DELETE 保护与复用、策略变化追加、事务失败回滚、发布失败后 replay、具名审核事件和真实CLI均经过测试。
- 所有自动测试复用 finally 清理的临时目录fixture，关闭 SQLite 后删除并断言目录不存在；无生产写入，所以不存在生产测试残留核查，也不声称查询过生产计数。额外14样例导出为纯合成 smoke，后续清理记录另附。

### 合成程序自检结果与边界

14条参考由Codex手写，标注状态 pending_human_review、method=synthetic_test_oracle；不是人类真值或真实JD语料。以下仅记录程序计数/差异，不能称招聘语义准确率或作为质量验收。

| 项目 | 实际计数 |
|---|---|
| 原B2→治理 | 14份overlay、0上游失败、1个待复核候选 |
| 名称+版本+位置一一对应 | 参考14、预测14、配对14；漏提/误提0 |
| 组合 | 参考2、预测2、关系/组状态/成员配对2；成员有效状态4/4对应 |
| 五态 | required参考6：原B2保持required4、uncertain2；其余 mentioned5、preferred1、not_required1、uncertain1对应 |
| 四类 | technical_skill11、professional_skill1、engineering_practice1、soft_skill1对应；后三类仅各1例，不能据此评价泛化 |
| 非技能 | 4份有限词面事实对应（年限、学历、行业经验、证书），约束状态均待复核 |
| 候选 | 1参考/1预测/1配对，正式准入0；空分母用例在独立指标测试覆盖 |
| 程序证据定位 | 21/21原文位置可核对，包含组合；不意味着语义正确 |

两处差异是 Vue 3 要求与三年以上 Java 开发经验：旧B2的受限语法保留uncertain，治理不修改其状态或要求对象。benchmark中required只是待人类审核的程序参考。正式效果、独立标注和质量阈值未完成；没有把合成自检结果称市场语义质量。

候选例：`必须掌握 UnlistedLang` → raw_name=UnlistedLang、tier=strong_context、candidate_type=possible_skill、governance_status=pending_review、category=null、independent_validation=not_established、formal_admitted=false；`技术栈：OtherRuntime`与`熟悉 cv`为disputed，后者保留baseline_matches=[opencv]及别名复核原因。所有候选含原字段区间/身份/完整上下文及版本；复核通过也不能调用正式词典写入。

Ruling：非技能暂只做带完整上下文的有限词面结构化，constraint_state=needs_review——避免否定或条件片段被解释成无条件岗位要求；代价是消费者不能据此直接作任职资格判定。裸专业领域词进入review_mentions。

### 可复现回归命令

工作目录为 backend，无本地 venv 时将命令中的 Python 替换为已安装 requirements 的绝对路径。以下配置均为合成/不可用地址。

```powershell
$b22Regression = @'
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
socket.socket.connect = offline_connect
socket.socket.connect_ex = offline_connect
result = pytest.main(["-m", "not integration", "-q", "-rs", "--tb=short"])
print("Blocked external/service attempts:", len(denied))
raise SystemExit(result or bool(denied))
'@
$b22Regression | .\.venv\Scripts\python.exe -X utf8 -
```

额外合成 smoke 生成的 5 个已知文件已逐文件删除、空目录逐层移除；核对 Synthetic smoke files remaining: 0。递归清理命令曾被自动审批阻断，随后限定文件名集合和路径/非 junction 断言，采用逐文件清理完成；无真实数据或其他目录参与。自动化用例仍由 finally fixture teardown 清理。原工作区未提交资产文档 SHA-256 仍为 `F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B`，未带入本轮。


### 唯一一次完整内部只读检查与定向修复

requesting-code-review 技能要求的无上下文 reviewer 实际阅读新增代码/策略/测试/参考及文档，并复跑58项；仅离线合成探针，临时SQLite在finally删除。该检查不是ChatGPT独立审查。报告Critical=0、Important=4、Minor=1：版本后缀截断、长数词尾部匹配、类别缺标注污染分母、旧DevOps粗类误归；Minor为直接存储审查事件绕过空白归因检查。

五项均以独立失败回归复现：**18 failed / 58 deselected**；第一轮修复后76 passed。补充同根因的`Vue >=3`和`Vue 3.5 - 4.0`：**2 failed / 5 passed / 52 deselected**，完整保留后治理与评测最终**78 passed**。

- 未支持rc/beta/+/>=或范围整体保留原词与version_review、canonical=null，不生成较短已知版本；只对受支持完整数字版本映射。原B2证据和语义不改写。
- 年限匹配加数词/小数/范围左边界，不从十一/二十/100/3.5/3-5尾部提取数字；未支持原文仍保留未解析，不无限增加数词解析规则。
- 参考技能category缺字段拒绝；显式null作为待复核，排除该事实的分类分母并记pending_reference_review，不把正确预测当作分类误判。预测缺类别仍可报告未分类。
- 旧DevOps类别不再批量映射technical_skill；Scrum/Agile/Kanban按明确实践条目归engineering_practice，其他未审项可分类待复核。
- 将非空人名/依据/证据引用检查统一进Review模型，所有入口一致；直接record_review也不能写入空白归因。此项虽被列Minor，但影响审查依据的可靠性，作为本轮信任边界一起修复。移除一处本轮留下的无用import。

Reviewer考虑但排除：开放中文/复杂句/英文完整语法、通用版本解释、真实模型/生产/质量阈值均在明确边界外；领域review_mentions、非技能needs_review、无独立来源验证、保留组合与原状态均符合任务。相同输入以不同样本ID重复标注目前不做采样去重，指标只描述所给样本，不能把样本数解释为独立职位/独立证据。本轮不新增独立职位关联算法。


### 最终验证与提交范围

修复后按上文相同合成配置和socket阻断命令运行完整非集成回归：**689 passed / 2 skipped / 23 deselected / 0 failed**，190项既有依赖警告，26.24s；Blocked external/service attempts: **0**。新增治理/评测78项全部包含，原A/B1/B2第一轮270项全部执行。跳过/排除原因不变，无真实语料效果或生产库核验结论。

正式seed/normalizer、foundation/screening/semantics源码与测试、DDL、旧管道及exchange对63c897b的diff为空；无真实数据、凭据或产出库纳入提交。新增资产、M2/根README、产品与索引、文档地图、陷阱和本报告为明确暂存范围。Markdown本地链接及git diff --check已通过；原工作区未提交资产文件哈希保持原值。工作树保留供PR定向修改，不合并、不删除分支，不启动B3/B4。


### GitHub交付

实现提交 `980c44f43ad36b9b318b521d8346f8f816ee1d9e` 已推送分支 `codex/m2-stage-b2-2-skill-governance`，创建并附加 [PR #7](https://github.com/Serena-Lyric/TalentMind/pull/7)，目标master。创建后实际核验OPEN、isDraft=false、mergeCommit=null、autoMergeRequest=null；本次后续仅补文档交付记录，源代码与已测试提交一致，无须重复业务回归。工作区与分支保留，未合并或启用自动合并、未启动B3/B4；等待ChatGPT独立审查，经用户明确授权后再合并。

## ChatGPT Review #5541830781 定向修复（2026-10-16）

已完整读取 [独立审查正文](https://github.com/Serena-Lyric/TalentMind/pull/7#pullrequestreview-5541830781)，审查 head=`1961261c90f4`，结论为1项Important：同行招聘标题后的未知能力词未进入候选池。用户授权在原PR定向修复、验证并推送，保持未合并，不启动B3/B4。

### 最小实现与历史边界

- 正式代码只改 `governance/extract.py`：复用 B2 标题及风险提示，区分章节标题与正文并调整匹配基准偏移，原文不清洗、不替换。支持任职要求/岗位要求/技能要求同行能力句、换行及列表；保留从标题到当前行的上下文。
- 未知冒号标题、公司介绍/福利等明确独立标题和职责等非招聘章节不提供开放词锚点，直到新明确招聘标题；章节按字段隔离。有限否定/条件前缀可定位词名，但候选 disputed + unresolved_requirement_context，不能当作正式五态判断；任意复杂句仍保留未解析。
- 正式seed/normalizer、A/B1/B2源码/表结构/语义历史、正式DDL/旧管道/交接/评测逻辑均未修改，自动准入仍关闭。原 B2 五态、程度、对象、组合/effective与全部证据逐字段保留。
- 在改代码前，以真实 B2→治理→SQLite 路径捕获两条重点样例的旧结果到 `tests/fixtures/governance/b22-inline-heading-history.json`（12,070字节），注明 origin_commit=1961261；candidates均为空，临时库在finally删除并断言不存在。它是实际历史夹具，不是人工真值。
- 回归将原捕获 manifest/body 装入受不可变保护的临时 b22_results，核对与原B2文档逐字段一致；新真实execute因源码摘要改变而追加不同version/result，旧零候选body不变，再次新版执行复用新result。未伪造旧语义输出或给旧结果补字段。

### RED→GREEN 与执行路径

工作目录 backend，Python 3.14.5，复用已安装依赖的绝对路径Python；全部输入为合成JD，临时SQLite/文件由finally fixture teardown清理。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_governance.py -q --tb=short -k heading
# RED: 14 failed / 5 passed / 59 deselected
# 两条重点样例均在 SELECT b22_results.body 后因 candidates=[] 失败。
# 首轮修复: 19 passed / 59 deselected
# 补充独立公司介绍/福利标题: 2 failed / 22 passed / 59 deselected
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_governance.py tests/test_job_analysis/test_governance_evaluation.py tests/test_job_analysis/test_semantics.py -q --tb=short
# GREEN: 194 passed（治理83 + 评测19 + 原B2 92）
```

新增24项参数展开用例覆盖同行/换行、空格与ASCII冒号/方括号标题、emoji前缀字符定位、列表、多行候选、公司/福利/教程/职责排除与标题重新建立、否定/条件原因、JS/cv别名及捕获旧历史。正例同时调用实际analyze和真实B2→治理runner→SQLite SELECT，核对原始字段/区间/身份/指纹、original_semantics不变、旧b2_attempts逐行不变、候选pending_review/formal_admitted=false、准入接口allowed=false及replay一致。

陷阱与长期限制见 [同行标题候选陷阱](../superpowers/traps/2026-10-16-m2-b22-inline-heading-candidates.md)。本次属于既有已支持句式的格式修复，不新增产品决策、词典准入、真实语料质量结论或后续阶段功能。


### 本次最终回归与交付边界

按本报告可复现命令的同一合成环境和socket阻断方式执行全量离线非集成回归：**713 passed / 2 skipped / 23 deselected / 0 failed**，190项既有依赖警告，36.15s；Blocked external/service attempts: **0**。其中治理/评测合计102项，原A/B1/B2第一轮270项均在全量执行中通过。2项跳过为缺私有回包的test_m2_return_package.py:15/:26；23项真实服务integration按边界排除。测试临时目录/SQLite由finally清理并断言不存在，历史捕获目录也已删除；未操作生产库，所以不声称生产数据残留查询或真实语料效果。

本次只改1份治理源码、定向测试、纯合成历史夹具及其说明、M2 README、资产记录、本报告和新陷阱。旧B2/词典/normalizer、A/B1、DDL/交接对审查head的diff为空。无需新增产品决策或执行迁移；未调用真实模型/外部收费API，不合并、不启动B3/B4，推送后等待ChatGPT定向复审。
