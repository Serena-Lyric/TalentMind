# M2 B2 第一轮：技能要求语义识别

日期：2026-10-16；基线 master `e40d40b`（PR #5）。用户已授权独立完成开发、离线测试、文档与 PR，不合并、不清理分支、不启动 B2 第二轮/B3/B4。

## 设计与执行计划

**目标**：单条 JD 的五态、基本组合、程度与冲突可以一起保存、复用、恢复、重放。
**架构**：Python 标准库 + 现有 Pydantic/SQLite。新增 `semantics/`，遵循 A 的 Analyzer 接口，复用 InputRecord、快照、文件锁、原子发布。独立 `b2_*` 表保存结构化结果，不修改 A/B1 任务或事实，不将 legacy 标签升级。产品依据为本次用户任务及 PRODUCT_DECISIONS M2-01～14、25～31。

工程选择（不是新增产品裁决）：

- 原文陈述是最小单位，保存字段、字符位置、章节/相邻上下文、适用对象、条件、程度、规则原因。组合以 any_of/all_of 陈述保存；候选成员不派生为独立 required。
- 冲突只在同技能、同程度、同条件、同对象的独立陈述间判定；mentioned 不构成冲突。没有修订规则，不按位置或强弱覆盖。
- 仅精确支持的简单语法生成确定状态。复杂/多对象/嵌套/否定范围不清时保存 uncertain 与原因；未知或未解析片段令 coverage=incomplete。coverage=complete 只指本轮已知别名与受限语法，不授予正式统计资格。
- 词典只读，别名匹配采取最长不重叠及 ASCII 边界；未知表达只记未解析证据，不建设候选治理。
- 版本包括规则/结构/验证源码内容摘要、实际词典摘要和显式修订。新版本追加结果；旧结果无需当前规则即可重放，resume 需要原依赖。

检查重点：否定或工作使用误升 required；任选成员误升 required；不同程度误判冲突；重复引文定位/跨 JD 证据；中断时重复提交或历史污染。

1. [x] 在 `tests/test_job_analysis/test_semantics.py` 先写合成反例及执行断言，运行观察失败。
2. [x] `semantics/models.py` 定义严格结构、证据与冲突解析；`rules.py` 实现 `SkillSemanticAnalyzer.analyze(InputRecord)`；`validation.py` 核对证据位置、成员、结构与规则判断，不把引文匹配当语义真值。
3. [x] `semantics/store.py` 与 `runner.py` 提供 execute/resume/replay，完整输入/观察分离、独立增量 heads、每 JD 原子提交、报告不可变；`__main__.py` 显式 CLI。
4. [x] 验证版本变化、旧历史、A/B1 共库、失败与零结果、真实进程中断及发布失败；执行阻断网络的后端非集成回归。
5. [ ] 产品决策追加五项、决策索引、M2 README、资产记录；记录限制与实测结果，完整分支检查、独立提交、推送并建 PR（文档及检查已完成，提交交付待下节补录）。

接口依赖核对：rules 产生严格语义文档 → validation 验证 → runner 将终态与完整 body 原子写入 b2_attempts → report/replay 引用不可变快照与版本。A/B1 只共享 snapshots，其他表互不写入。

## 执行记录

### 结构与边界

完整输入保存在 A snapshots，B2 仅追加七张 b2_* 表。Document 保存陈述及逐次技能词/程度/上下文/跨字段 scope_evidence；effective 按技能、程度、对象、条件解析，冲突标记与全体陈述引用独立。组合不展开成独立 required。结构版本 b2-1，实际源码/词典/别名摘要进入依赖；不修改 A FactClaim/validator/runner，也不重解释 legacy 标签。具体结构、输入/CLI、状态、规则示例与限制见 [M2 README](../../backend/app/job_analysis/README.md)。

Ruling：采用独立 B2 Document + b2_* 兼容扩展，不扩展 A 的旧枚举——避免旧客户端/旧聚合误读新五态及组合。代价是 B2 需独立 runner，不能将 Document 直接传给 A validate_response。

Ruling：仅复用 completed/partial 的完全相同依赖结果；partial 仍不完整——规则是确定性的，同依赖反复运行不会补齐未支持语法。代价是补齐能力必须改变规则/结构依赖，再追加新判断。

### 实际测试证据

Windows / Python 3.14.5，复用原仓库已安装 requirements 的 Python 绝对路径，工作树没有 .env。以下命令工作目录 backend（独立工作树用原环境绝对路径替代 `.venv`）。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_semantics.py -q --tb=short
# 首批：41 failed（缺 B2 包）；实现后 41 passed。
# 扩展后：2 failed / 66 passed（占位符碰撞、重复成员伪组合）；修复后 68 passed。
```

68 项包括：五态正反例、ANY/ALL、加分/使用/列表、同技能不同程度、正反顺序真实冲突、否定精通与基础并存、同义词及重复引文、跨 JD/错误位置/语义伪造拒绝、未知词零识别、执行失败、来源观察分离、完整 payload/实际源码/规则修订失效、历史重放/恢复、增量缺项、A/B1/B2 共库、历史 DELETE/REPLACE 保护、发布失败和真实 CLI。

八处真实子进程 `os._exit(71)`：after_prepare / after_start / after_analyze / before_commit / after_commit / after_report / after_stage_output / after_output。重开后逐条完成，running=0，completed=2（每成员一份），原子文件与 SQLite replay 完全一致，无遗留 staging 文件。临时目录 fixture 在 finally 删除并断言不存在。

共库测试先创建含 legacy_required 的 A 事实与聚合，再运行 B1 和 B2：A facts 原样、semantic_status=unreviewed；B1 decisions 逐字段不变；user_version=1；A/B1 旧报告可重放，随后再次 A/B1 执行复用原 attempt/decision。B2 不写 A/B1 heads/观察/运行表。

完整非集成回归使用与 A/B1 相同的合成配置及 socket 阻断方法（只放行 Windows Python 内部 socketpair），执行命令：

```powershell
$b2TestCode = @'
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
$b2TestCode | .\.venv\Scripts\python.exe -X utf8 -
```

实测 **587 passed / 2 skipped / 23 deselected / 0 failed**，190 项既有依赖弃用警告，Blocked external/service attempts: 0。两项 skipped 为 test_m2_return_package.py:15/:26，因私有 input 回包不随干净检出提供；23 项真实服务 integration 未执行。没有生产库写入/夹具，故不声称查询生产库计数或生产清理证明。

### 未支持或待后续

- 本轮只支持 README 列出的中文简单句式、已知别名及窄跨分句程度对比。复杂嵌套、范围、指代、多主体、一般条件解析、英文完整句法和任意编号/格式均未通用支持；原文和不确定原因保存，不强建逻辑树。
- 示例“如果参加数据项目，则需要掌握 Python”保留 unresolved target/condition、uncertain/incomplete；“必须掌握 (Java 或 Python) 和 SQL”不建嵌套关系；未知 UnlistedFixtureLang 只生成未解析 issue，无技能实体，不装作执行失败或完整样本。
- 真实语料准确率未知；规则重算验证只是语法符合性检查，不是独立语义评测。没有自设 95% 或其他质量门槛，未启动真实 JD 标注。
- B2 第二轮依赖：技能类别/别名治理、未知候选证据规范及严格准入策略须在另行授权后开发。无新本体/自动准入/正式词典写入；B3 职业目录、B4 模型及正式统计/匹配评分未启动。
- 原工作区未提交资产文档 SHA-256 仍为 F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B，未带入提交。

### 内部只读检查与单次修复

按 requesting-code-review 技能调用无历史上下文的只读 reviewer，完整阅读新增源码/测试/文档及纯合成探针；不是交付后 ChatGPT 独立审查。提出 4 项 Important：无冒号加分标题误继承 required、跨句对象/条件/否定限定未参与判断、未解析多技能程度错绑、未知冒号标题吞掉技能而错误 complete。程度问题此前由作者新增测试先复现；其余由 reviewer 探针复现。

新增 16 项回归中实测 **15 failed / 1 passed**（另有已有 68 项未选择），随后单次修复后完整 B2 **84 passed**。每项修复见 [陷阱记录](../superpowers/traps/2026-10-16-m2-b2-context-and-degree.md)。Ruling：已识别范围提示保守影响本 JD 全部技能并以 scope_evidence 保存，不强行判断限定只作用哪句——防止跨行/跨字段的无条件 required；代价是无关技能也可能过多保留 uncertain，需要后续可靠作用域解析才可放宽。

Reviewer 未列阻塞的事项及处理依据：英文/任意编号/开放词汇/嵌套继续保留已声明的未支持边界；ANY/ALL 不展开成员符合本轮要求；规则重算只是规则符合性，不能证明准确率；未建立完整运行环境锁文件，本轮用已安装 Python 3.14.5/既有 requirements 并报告环境，不宣称跨环境完全重现；B2 打开时沿用 A 独占锁恢复遗留 running，是既有恢复行为，不改已提交历史。A/B1 兼容及中断恢复已有实际回归，没有发现其他阻塞项。

**非阻塞延期 Minor**：含重复 canonical 的组合（例如“必须掌握 Java 和 Java 和 Python”）在 effective 中可能出现重复 group_ids；不会凭此把候选升级 required，也不丢原始证据。本轮保留并交审查者知悉，后续可仅对引用列表去重，不影响历史文档。

所有 Important 已有失败回归及修复后绿灯；最终完整离线回归与提交/PR 信息见交付记录。没有据此声称 ChatGPT 已验收。

### 最终回归与交付记录

按上面的完整合成配置/网络阻断命令再次执行，最终 **603 passed / 2 skipped / 23 deselected / 0 failed**，190 项既有依赖警告；**Blocked external/service attempts: 0**。新增 B2 为 **84 passed**，包含修复后全部语义、A/B1 兼容及真实恢复用例。跳过/排除原因同上；没有运行真实服务 integration、标注评测、模型或旧正式管道，没有生产写入。

暂存范围只含 B2 包、合成测试、M2/根 README、产品决策/索引、资产、两份陷阱和本临时报告。正式 DDL、foundation、screening、skills、旧 M2 源码、exchange 及本地原工作区均未修改。提交与 PR 创建后补记，不自动合并或删除分支。
