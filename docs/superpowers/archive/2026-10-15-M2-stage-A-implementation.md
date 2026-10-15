# M2 第一阶段 A 实施与验证报告

> **历史实施归档，非生产发布授权。** 原报告在 [PR #4](https://github.com/Serena-Lyric/TalentMind/pull/4) 中经 ChatGPT 源码审查后归档；代码依据为阶段 A 提交 `aeb7a37`～`629a5494`，后续实现以 Git 历史及正式文档为准。本报告测试结果来自 Codex 的 Windows 本地执行，未由 ChatGPT 独立重跑，也无 GitHub CI 检查。

日期：2026-10-15。基线：`origin/master` 的 `29caa924`。本报告已于审查后从临时目录归档。

## 授权与实施计划

需求依据为本轮用户完整任务与 A-01～03；沿用 M2-01～24，不增加生产接入。
使用 Python 标准库 SQLite/JSON/SHA-256/文件原子替换、现有 Pydantic 与技能归一工具。
新路径 `backend/app/job_analysis/foundation/`；旧 StateDB、完整 LLM 管道及交接文件保持隔离。

- [x] 1. `inputs.py`、`store.py`：先写 JSON/JSONL 错误、身份与持久化测试，再实现快照、观察及独立库。拒绝旧库，不迁移。
- [x] 2. `models.py`：先写完整输入变化、时间独立、依赖缺失/变化测试，再实现确定序列化与独立版本摘要。
- [x] 3. `validation.py`：先写失败、跨 JD 引文、部分事实和零技能测试，再实现严格响应解析与逐字段原文定位。
- [x] 4. `runner.py`、`aggregate.py`：先写复用、force、关键事务中断和固定成员重放测试，再实现串行任务、原子提交与完整历史集合聚合。
- [x] 5. `__main__.py`、README、产品决策/索引/资产：先写离线 CLI、安全路径和输出中断测试，再实现显式路径入口，完成离线回归、独立审查与文档。PR 交付记录在本报告末尾补录。

每步遵循 RED→GREEN。验证命令使用仓库已有 Python 环境，测试只写临时目录并在 fixture teardown 清理。
重点审查：重复身份/JSON 键、非有限数字、旧库与路径别名、force 失败后的历史选择、提交后输出中断。

## 实施记录

初始工作区为 `codex/m1-stage-02`，用户唯一未提交文件是 `资产与状态.md`；本轮使用独立工作树，未携带该修改。
PR #3 已合并到基线；24 项矩阵、E01～E11、P0 风险与离线验收已核对。
工程选择：全字段保守指纹（仅身份与真实观察时间分离），不清洗/截断分析文本；原文字段直接作为分析文本，无虚构映射。

## 实际文件范围

| 文件（仓库相对路径） | 实际职责/变更 |
|---|---|
| `backend/app/job_analysis/foundation/__init__.py` | 新基础层边界，不引入旧配置/数据库/模型客户端 |
| `backend/app/job_analysis/foundation/inputs.py` | JSON/JSONL 严格适配、不可变输入、原始文件摘要、完整字段 SHA-256 |
| `backend/app/job_analysis/foundation/models.py` | Pydantic 分析器依赖/响应/证据/claim；分析版本清单 |
| `backend/app/job_analysis/foundation/store.py` | 独立 SQLite、单 owner 锁、快照/观察/尝试/事实/任务/聚合、不可变保护 |
| `backend/app/job_analysis/foundation/validation.py` | 单条身份/完整引文校验与语义未复核、未知候选表达 |
| `backend/app/job_analysis/foundation/runner.py` | 增量复用、force、恢复、单条事务提交、聚合与原子发布 |
| `backend/app/job_analysis/foundation/aggregate.py` | 固定成员 evidence inventory、业务 SHA、历史事实核对重放 |
| `backend/app/job_analysis/foundation/__main__.py` | run/resume/replay 显式离线路径，Python 字面演示分析器 |
| `backend/tests/test_job_analysis/test_foundation_inputs.py` | 输入/身份/指纹/持久化/旧库拒绝，fixture finally 清理 |
| `backend/tests/test_job_analysis/test_foundation_validation.py` | 分析依赖、解析/引文/部分/零技能/未知与二分兼容 |
| `backend/tests/test_job_analysis/test_foundation_runner.py` | 增量/版本/force/历史/事务/中断/锁/不可变规则 |
| `backend/tests/test_job_analysis/test_foundation_cli.py` | 真 CLI、八个阶段硬退出、发布错误、安全路径与 replay |
| `.gitignore` | SQLite/旁置锁/事务产物保护 |
| `README.md`、`backend/app/job_analysis/README.md`、`docs/README.md` | 阶段 A 导航、完整输入/状态/恢复/接入/测试说明 |
| `docs/PRODUCT_DECISIONS.md`、`docs/superpowers/决策跟踪.md` | 追加 M2-25～27（A-01～03）与 D64～66，不改 M2-01～24、D1～63 原行 |
| `docs/superpowers/资产与状态.md` | 新资产、真实验证范围和待审查状态 |
| `docs/superpowers/traps/2026-10-15-m2-facts-and-recovery.md` | 输入/事实/版本/发布恢复与 SQLite 边界教训 |
| `docs/superpowers/archive/2026-10-15-M2-stage-A-implementation.md` | 计划、实施台账与测试报告，已转历史归档 |

## 结构、复用与版本

新库九表：runs、snapshots、heads、observations、versions、attempts、facts、tasks、aggregates。runs 保留来源路径、文件原始字节/SHA、分析依赖 ID、聚合 revision、状态/时间/错误；其余表分开表达身份最新指向、历史输入、观察、尝试、事实与冻结成员。一个逻辑概念一个表的轻量实现，无队列/Redis/生产数据库扩展。

复用标准库 sqlite3 的连接/参数化事务、JSON、hashlib、现有 Pydantic，以及 `app.skills.normalizer.build_alias_map/normalize` 与现有 seed。旧 JdRecord 缺 source_detail/任意重要字段，旧 ExtractionResult 二分/未知项缺证据；StateDB 的 hash 去重与阶段状态、merge 的 OR、export 的覆盖行为不适合新语义，因此保留旧路径而使用最小独立适配，不复制采集或词典体系。不改旧模块调用者，M3～M5 仍读取原交接。

完整字段稳定序列化后 SHA-256；仅 id/namespace 身份与 crawled_at 观察分离。全部 payload 字段可见于分析器，不清洗、不截断；坐标对应不可变输入字段的 Python 字符索引。源文件字节另存，既保实际输入，又可核验原文件；同文不同身份保留，部分批次缺项不推下架。

分析版本摘要固定 revision、解析/清洗/校验修订、词典内容 SHA、分析器 extractor/prompt/model/configuration 必填修订。同次归一化使用同一词典快照。聚合独立固定 revision 和 inventory 规则标识。影响集无法精确判断时，针对当前数据集全部 heads 保守重分析；仅聚合 revision 变化不提取。版本、快照、事实、终态尝试和聚合不可改写；store recursive_triggers 阻断 REPLACE 隐式删除。密钥不进入配置清单，异常日志只保原因码。

## 状态、证据与统计资格

- 任务：无尝试 pending；running；completed；partial（coverage incomplete 或部分结构/证据不合法）；failed（调用失败/空响应/顶层解析失败）；retryable（进程中断前未提交）。API 成功后仍须严格解析和逐项校验。
- 事实：matched、missing_evidence、foreign_jd、quote_not_found、invalid_structure；匹配完整 quote，而非 50 字前缀。合法部分保留；未知名称/原证据/验证状态保留为 candidate。模型 verified 无效，semantic_status 始终 unreviewed；五态仅可承载，未实现识别，也未升级 legacy 二分。
- 资格：仅离线 evidence audit；completed included、partial/未完成 incomplete、failed excluded，逐成员原因固定。partial 的 matched_facts 可核对，整条不当完整样本。正式统计资格始终 false，原因 independent_positions_unresolved/requirement_semantics_unreviewed；无独立职位数/需求率。
- 合法零技能是指定分析器范围 coverage complete 且无 skill claim，与失败分开。内置 Python 规则的“零技能”只指未找到 Python 字面词，不能解释为 JD 没有其他技能。

## 恢复与重建

输入、观察、heads 与完整数据集任务清单同事务准备；单条先提交 running，再将事实和终态一次提交。未提交结果在重开库后 retryable；已提交尝试可复用。原运行任务范围及聚合 revision 固定，恢复不读取当前文件的新字段，也不污染较新 heads。force 在新 run 使用本次提供的输入，失败不会静默退回旧成功，但旧事实仍可追查/replay。

聚合从 tasks 的全部快照/尝试/事实重建，不是本轮新增项；固定成员包含 snapshot/attempt/fact ID、输入摘要、分析版本、纳入/排除/未完成原因。成员稳定排序；相同成员及聚合版本得到相同 aggregate_id 和 business_sha256。源文件摘要/观察属于运行元数据，不改变同一事实集合的业务结果。

聚合先入库，输出按 run_id 写独立 JSON；同目录暂存、flush/fsync、原子替换，最后标完成。失败记 publication_failed，恢复无需重复提取；暂存崩溃清理本 artifact 的暂存文件。不同内容已有文件拒绝覆盖。显式路径在仓库内只允许 data/local，拒绝覆盖 exchange、源码/文档/原始输入；旧状态文件拒绝迁移。单 owner 锁解析符号链接/junction，并拒绝硬链接；不承诺网络盘/跨机。

## 验证命令与实际结果

环境：Windows / Python 3.14.5 / SQLite 3.50.4 / Pydantic 2.12.0，复用现有 backend/.venv；全程合成数据和临时 SQLite。工作树不含个人 .env，不复制真实密钥。以下命令在仓库根进入 backend 后执行；若独立工作树无 venv，可指定已有同依赖 Python（本轮如此执行），不要求个人绝对路径。

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_foundation_inputs.py tests/test_job_analysis/test_foundation_validation.py tests/test_job_analysis/test_foundation_runner.py tests/test_job_analysis/test_foundation_cli.py -q
```

最终：**99 passed，0 failed**。初始各模块测试均先观察缺实现失败再 GREEN；独立审查后的三类保护及词典冻结测试共 8 项先失败，再修复全部通过。另补既有无表但有其他 application_id 的 SQLite 文件不能被接管的 RED→GREEN 测试，确保空外部库也不被修改。

完整非集成回归使用合成配置及连接阻断（仅允许 Python Windows 内部 socketpair 自连接），无需真实服务或模型：

```powershell
$m2TestCode = @'
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
$m2TestCode | .\.venv\Scripts\python.exe -
```

实际输出：`440 passed, 2 skipped, 23 deselected, 190 warnings`，**0 failed**，`Blocked external/service attempts: 0`。2 skipped 均为 `test_m2_return_package.py:15/:26`，私有 input 原回包未在干净检出提供；23 项真实服务 integration 测试未运行。190 项为 Neo4j/FastAPI/Starlette 既有弃用警告，不在本轮顺手升级依赖。

首次直接回归在收集阶段因干净检出无 Settings 配置产生 8 errors；加入合成配置后，最初一版过严网络 guard 拦住 Windows socketpair，产生 translate 两项 + middleware 四项失败（425 passed / 6 failed）。两次都未访问真实服务；修正**验证环境**只放行 socketpair 后，最终上述回归通过。未改旧业务代码来掩盖这些问题。

| 用户离线验收场景 | 实际测试 |
|---|---|
| 首次、同输入同版本、同文不同身份、增量缺项 | first_run_and_unchanged；store_persists；time_and_identity；CLI run |
| 标题/职责/条件/2000 字后/其他输入变化、历史证据 | every_analysis_input_change；updated_input_preserves_old_attempt |
| 观察独立、强制新输入、分析/聚合版本 | observation_change；versions_and_force；analyzer_dependency_changes |
| API 错误、空/坏 JSON、跨 JD 引文、部分/零技能 | failures_recorded；bad_response；missing_or_cross_jd；partial_valid_facts_and_zero |
| 每关键阶段中断与事务提交、发布错误 | interrupt_resume（7 阶段 KeyboardInterrupt）；abrupt_process_exit（8 阶段 os._exit）；ingest_transaction_rolls_back；failed_output_can_resume |
| 固定成员稳定重建、旧运行冻结 | same_members_reordered；new_incremental_batch_cannot_change_older_run；replay 及 CLI |
| 非法输入/格式/依赖、旧库拒绝、保护路径 | invalid_records；bad_format；version_requires；legacy_database_rejected；protected_repository_outputs |
| 不可变与单 owner 实际边界 | terminal_attempt/version；terminal追加；五表 REPLACE；concurrent_owner；hardlinked_state_alias |

所有新增测试共享 area fixture，在 finally 删除其专属临时目录并断言不存在；各连接通过上下文显式关闭。中断恢复后实际 SQL 查询：成功 attempts=2、facts=2、running=0；准备事务故障后 runs/snapshots/heads/observations 全为 0。未运行真实数据库集成，故没有生产数据库查询/清理结论；真实生产连接被禁止且未尝试。首轮测试曾因测试连接未 close 留下一个纯合成临时目录，修正 closing 后复跑通过，并在本轮收尾精确移除该目录。

CLI 端到端测试真实启动包入口，检查 run/replay 的 JSON 业务内容、摘要与成员复用；模拟输出仅用于正确性，不证明真实大模型识别质量。文件/文档检查另行执行 git diff --check、链接/历史行保留/忽略规则检查，不冒充业务测试。

## 独立审查与工程取舍

按 requesting-code-review 技能派发一次只读独立审查；3 Important、0 Critical/Minor：硬链接 owner 绕过、终态追加事实、REPLACE 绕过删除触发器。均有独立合成复现，接受并在本轮新增 RED→GREEN 回归，最终全套 GREEN；未再派二次审查，不把 Codex 自检视为 ChatGPT 验收。

工程取舍：按 st_nlink 拒绝硬链接库，保留旁置 OS 锁，避免在 SQLite 正文施加 Windows 强制字节锁；代价是硬链接形式的部署不支持。其余取舍是全字段保守失效、显式依赖修订、原文不转换、只作离线审计，均在授权边界内，代价分别为可能多分析、接入者须维护修订、暂不分段优化、不能发布正式统计。

审查暂不裁决且本轮保持的后续门禁：五态/招聘意图/模型效果；独立职位关联/需求率/时间可比性/阈值；未知自动准入；真实服务/正式迁移/生产规模；断电/文件损坏/远程盘/跨机；真实分析器实际参数与修订同步。上述并非已验证能力，不以演示代替；后续阶段分别补语义/分类、最小身份关联、正式聚合及经许可的生产接入。

## 完成程度与交付

阶段 A 的独立离线输入→版本化单条尝试→确定性引文事实→持久化/恢复→固定成员聚合/重放已实现并完成上述验证。生产旧链仍有历史评估中的缺陷，本轮通过新入口绕开；旧 CLI/SQL 解析/StateDB 及旧交接统计语义不宣称被修复。未改正式 DDL、API、M1 记录、MySQL/Neo4j 或 exchange/m2、m3 数据；未调用模型、采集、导入或 reset。

最终静态检查：21 文件范围准确；新增 12 个本地 Markdown 链接存在，围栏配对、git diff --cached --check 通过；M2-01～24 与 D1～63 原决策行保持，SQLite/旁置锁/运行 JSON 忽略规则生效。原工作区仍在 codex/m1-stage-02，仅原有资产状态文件有改动；收尾核对其 SHA-256 为 F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B，与本轮提交前记录一致。

实现提交：`aeb7a37`（21 文件）。分支 `codex/m2-stage-a` 已推送；[PR #4](https://github.com/Serena-Lyric/TalentMind/pull/4) 面向 master，已关联当前任务。提交时未合并；后续由 ChatGPT 审查并归档，合并仍须用户授权。本段为交付元数据补录，不改业务代码或测试。
