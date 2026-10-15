# job_analysis

## 阶段 B1：JD 有效性与分析范围的离线筛选

入口 `python -m app.job_analysis.screening` 与 A/旧管道分离，不调用模型或服务，不写技能事实。所有路径必须显式提供；可以使用已有阶段 A SQLite（只增 B1 表、共享不可变 snapshots），也可用新的独立库。旧 StateDB 仍拒绝打开，不迁移。

先在 Git 忽略的 `data/local/m2-b1/input.json` 准备合成数据：

```json
[
  {"id":1,"source":"synthetic","job_title":"开发实习生","raw_text":"负责开发软件，只要求 Python。","crawled_at":"2026-10-15"},
  {"id":2,"source":"synthetic","job_title":"行政助理","raw_text":"负责整理行政报表，使用 Excel。"},
  {"id":3,"source":"synthetic","job_title":"助理","raw_text":"具体工作待定。"}
]
```

从仓库根进入 backend：

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.job_analysis.screening run --input ../data/local/m2-b1/input.json --dataset synthetic-b1 --state ../data/local/m2-b1/state.sqlite3 --output ../data/local/m2-b1/results --scope app/job_analysis/screening/software-related.offline.json
# 使用 stdout 的 run_id：
.\.venv\Scripts\python.exe -m app.job_analysis.screening resume --run <run_id> --state ../data/local/m2-b1/state.sqlite3 --output ../data/local/m2-b1/results
.\.venv\Scripts\python.exe -m app.job_analysis.screening replay --run <run_id> --state ../data/local/m2-b1/state.sqlite3 --output ../data/local/m2-b1/replay
```

无本地 venv 的独立工作树，可指定已安装 requirements 的 Python 绝对路径。状态/输出仅允许仓库内的 `data/local/` 或仓库外独立目录。输出目录允许包含状态库（同层或子目录），发布器只写 `<run_id>.json`；禁止把状态文件本身或其子路径当成输出目录。输入/范围文件必须位于输出目录之外，不以“目录隔离”暗示状态库也必须在目录外。配置/路径/存储错误返回 2；输入或筛选失败仍发布有错误的审计并返回 2；成功筛选运行（包括无效/范围外/待复核）返回 0。若未获得 stdout，可只读查询 `b1_runs` 的 `id,status,error`，再 resume。已完成的失败尝试通过新 run 重试；resume/replay 不改写旧判断或旧审计。

范围配置为严格 JSON 对象：`scope_id/version/mode/description/activities`；mode 仅 `offline_experiment`。样例包含 software_development、software_testing、data、it_operations 四种工作活动。它们是规则证据组，不生成职业大类、标准岗位、方向或级别。可显式缩小 activities；未识别配置拒绝执行。更改配置的任意内容（即使 version 标签相同）也会产生新版本键。代码/语境规则变化应升级内部 RULESET；`--rules-version v2` 可另行标记试验修订。当前实现 `conservative-activity-v2` 对“我司/本团队开发的产品”和向客户演示/介绍产品语境保守复核，不能将产品属性直接归给岗位。新 run 不复用 v1 判断，旧报告仍可 replay；旧运行 resume 要求原实现依赖一致，不自动改写历史。

**分层判断**：validity 为 valid / invalid / undetermined；已完成判断的有效或待判断 JD 分别使用范围三态。无效 JD 的 scope_status 为 null；解析/执行错误的 validity 为 not_evaluated、scope_status 为 null。规则需要技术工作动作与对象关系，不能靠标题或 Python/Excel 单词纳入；明确非技术工作可排除。短文本无长度限制，无技能数量或实习限制。标题与正文冲突、混合活动、已识别否定/历史/教程/公司介绍语境、信息不足均保留复核。复用 M1 `is_valid_jd` 作为无实质内容信号；未知剩余文字不自动确认为有效招聘，M1 输入字段与状态原样保留，不回写。

**输入**：沿用 A 的 JSON 数组/JSONL、InputRecord 必填字段及完整指纹；B1 对坏行/缺字段/重复身份逐条保留 input_failed，不使后续合法行消失。JSONL position 为物理行号，空白行不算输入；整个容器损坏、空文件/空数组或根类型不符记 position=0 的一个失败单元，无法推测损坏容器内的记录数。解析失败无不可变 JD 快照时，用源文件 SHA-256、原始身份（能可靠获取时）和位置引用；任一输入单元失败时均不保存整文件原始字节，合法成员仍保存完整快照。禁止凭据字段的行只保存安全原因与位置。输入文件本身始终只读。

**输出**：每个 run_id 一份不可覆盖的 JSON，含 members 和 audit。每条保存数据集/JD/snapshot/fingerprint、来源、有效性/范围/执行、原因与说明、原文 field/start/end/quote（Python 字符偏移、左闭右开）、版本、决策 ID/时间及真实来源文件运行引用。源文件字节、完整快照、观察值与完整配置保存在 SQLite；只改观察时间复用原决定，另存观察。

audit 的顶层 validity_counts、scope_counts、reason_counts、input_failed、screening_failed 针对**冻结的 B1 数据集最后可解析成员 + 本次输入失败单元**；member_total 等于两组状态计数各自之和。current_input 使用同一口径仅核对本次输入，member_total 等于 input_total。not_applicable 包含无效和未执行判断；needs_review 包含有效性待判断，不与失败混算。增量缺席的旧成员继续纳入数据集审计，保留原输入文件引用；无法解析的更新不抹掉此前可解析快照，本次失败仍单独可见。范围/规则变化重判整个已登记 B1 数据集，历史决定保留。首次 B1 使用共享 A 库时，必须显式输入需要纳入 B1 的 JD；不从 A heads 隐式扩展范围。

B1 独立表为 b1_versions/runs/heads/observations/members/decisions/reports；A 的 application_id/user_version=1 和既有表结构不变。只复用 snapshots；不写 A 的任务、尝试、事实、观察、heads 或聚合。A 原有执行与重放可继续运行。结果事务提交后再原子发布文件；未提交判断中断后重做，已提交判断不重复；输出失败可 resume。单进程文件锁及终态/版本/报告历史保护复用 A 的安全机制。输出固定 `formal_statistics_eligible=false`，`analysis_status=not_executed_by_b1`，不生成技能统计或独立职位计数。

### B1 测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_screening.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_foundation_inputs.py tests/test_job_analysis/test_foundation_validation.py tests/test_job_analysis/test_foundation_runner.py tests/test_job_analysis/test_foundation_cli.py tests/test_job_analysis/test_screening.py -q
```

只用合成 JD、临时 SQLite 和 finally 清理的临时目录；包含真实子进程硬退出、输出失败恢复和 A/B1 共库重放。本轮实际计数与完整非集成回归的合成环境/网络阻断命令见 [B1 实施报告](../../../docs/superpowers/archive/2026-10-15-M2-stage-B1-implementation.md)。合成回归不能证明真实岗位分类准确率；复杂否定、转述、跨句指代、多职位拆分和最终范围目录仍需后续人工/语义验证，B1 不承担 B2/B3/B4。

## 第一阶段 A：独立离线事实基础层

新入口为 `python -m app.job_analysis.foundation`，与下方旧管道隔离。新库跨运行持久化，不读取或升级旧 StateDB，不连接数据库服务或外部模型；要求显式输入/状态/输出。仓库内运行产物只允许位于 Git 忽略的 `data/local/`，也可使用仓库外的独立目录。

在仓库根准备一个**合成** `data/local/m2-a/input.json`：

```json
[{"id":1,"source":"synthetic","source_detail":"fixture-a","job_title":"Engineer","raw_text":"Use Python","duties":"Build services","experience":"3 years","crawled_at":"2026-10-15T08:00:00+08:00"}]
```

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.job_analysis.foundation run --input ../data/local/m2-a/input.json --dataset synthetic-a --state ../data/local/m2-a/state.sqlite3 --output ../data/local/m2-a/results
# 使用上一步 stdout 的 run_id 或 aggregate_id：
.\.venv\Scripts\python.exe -m app.job_analysis.foundation resume --run <run_id> --state ../data/local/m2-a/state.sqlite3 --output ../data/local/m2-a/results
.\.venv\Scripts\python.exe -m app.job_analysis.foundation replay --aggregate <aggregate_id> --state ../data/local/m2-a/state.sqlite3 --output ../data/local/m2-a/replay
```

`run` 可加 `--analysis-version v2`、`--aggregate-version v2` 或 `--force`。状态文件始终使用同一路径才能跨运行复用；不要删除状态模拟增量。`resume` 沿用原运行的完整输入范围和两个版本，依赖不符则拒绝。失败或 partial 任务可通过新 `run` 重试；已有成功事实保留，但最新强制尝试失败时不会静默退回旧成功。输出发布失败保留 `publication_failed`，恢复可直接复用已提交事实。

若进程在输出 stdout 前退出，可重复同一 `run` 命令（已提交事实仍复用），或只读查询本地库取得原 run_id，再执行 `resume`：`.\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('file:../data/local/m2-a/state.sqlite3?mode=ro',uri=True); print(c.execute('SELECT id,status,error FROM runs ORDER BY rowid DESC').fetchall()); c.close()"`。库的恢复状态在 `AnalysisStore` 重新打开时更新。

CLI 只运行内置 `LiteralDemoAnalyzer`：在完整正文中定位 Python 字面词，记录 `unclassified`，未匹配返回的是该演示范围的零结果。它不能识别真实要求、否定、其他技能或岗位分类，**不代表模型分析效果或完整技能覆盖**。输出携带 `offline-demo` 依赖标识，统计范围限定 `offline_evidence_audit`。

### 输入与精确复用

- 支持 UTF-8（可带 BOM）JSON 数组、逐行 JSON 对象的 JSONL；空列表、坏行、重复 JSON 键、重复身份、非有限数字、缺必填字段及其他文件格式明确报错。JSON 包装对象、CSV、SQL/mysqldump 不在新入口支持范围。
- 必填 `id`（非空字符串或整数）、`source/job_title/raw_text`（非空文本）；`duties/experience/requirements` 如出现须为文本。其他 JSON 字段保守保留并参与指纹，包括 `source_detail/quality/dup_group/cross_source`。不假设存在职位 URL。整数 ID 转成十进制字符串，故同一数据集内 `1` 与 `"1"` 是同一身份，不能同时出现；不同数据集分别保存。
- `id` 与数据集构成身份；`crawled_at` 独立存为来源观察值，不进入分析器 payload/内容指纹，不作为发布时间、不补时区或虚构缺失时间。每次载入保留观察及其来源运行；相同来源时间重复出现只是重复导入证据，不宣称新的真实观察。
- 剩余全部字段按 UTF-8、key 排序、紧凑 JSON、不允许 NaN 稳定序列化后 SHA-256。完整字段不截断；快照正文不可变，整份源文件原始字节与 SHA-256 另存于运行记录。不按正文 hash 或 dup_group 删除身份，增量文件缺项不判下架。
- 分析版本为显式 revision + 解析/清洗/证据校验修订、实际词典内容摘要、分析器 extractor/prompt/model/configuration 修订的摘要。必填依赖缺失直接拒绝；任何依赖变化保守使所选数据集全部当前输入重新处理。分析器代码、模型参数或提示词改变时接入者必须更新相应修订，第一阶段不自动分析代码依赖。
- 聚合版本独立保存 revision 与 `offline-evidence-inventory-v1` 规则标识；仅改聚合版本可复用完整单条事实。成功终态、输入/依赖/事实/聚合记录受不可改写触发器保护，不能给旧成功直接改版本号。

### 分层状态与证据

尝试状态为 `running/completed/partial/failed/retryable`；准备后尚无尝试即 pending。partial 包括声明尚未完成、事实结构损坏或引文未通过；failed 包括调用异常、空响应或顶层解析失败。合法 `coverage=complete,facts=[]` 与失败分开。失败日志只存安全原因码，不保存供应商异常文本、API 密钥或任意原始响应；合法 claim 和未知技能的原名/证据保留，非法结构项保留审计记录。

每条 claim 必须指定 `kind/name/requirement`，证据含 `namespace/jd_id/field/quote`。程序核对具体身份、完整引文及字段，保存 Python 字符索引半开区间 `[start,end)`；重复引文取首个位置。当前分析输入不清洗、不分段、不翻译，位置直接对应不可变输入字段，不能当作原始网页位置。`verified` 模型自述被忽略。

`evidence_status` 区分 `matched/missing_evidence/foreign_jd/quote_not_found/invalid_structure`。`matched` 仅证明原文对应，`semantic_status=unreviewed` 始终保留；可承载五态标签，但本阶段没有五态识别算法，兼容 `legacy_required/legacy_bonus` 也不升级为新语义。已知技能复用共享 normalizer；未知项 `governance=candidate`，不改词典。

聚合成员的资格只针对离线证据审计：completed → included，partial/未完成 → incomplete，failed → excluded，逐条保留原因。partial 中合法事实仍可在 matched_facts 核对，不让该 JD 冒充完整样本。所有正式统计资格均为 false，并注明独立职位未关联、语义未复核；没有技能需求率或独立职位数。

### 持久化、恢复与接入边界

SQLite 包含 runs（源文件/版本/状态）、snapshots、heads、observations、versions、attempts、facts、tasks（冻结输入范围及复用选择）、aggregates（版本/完整成员/业务结果和摘要）。新库由 application_id/user_version 标识，旧库拒绝自动迁移。文件锁使用 Windows msvcrt / POSIX flock，仅支持单进程串行拥有；拒绝硬链接状态文件，符号链接/junction 先解析到实际路径，不适用于多机共享网络盘。store 连接开启 recursive_triggers，使 REPLACE 的隐式删除也受历史保护；终态尝试不能追加事实。

准备运行时原子保存快照、观察、当前身份指向与完整数据集任务范围；每次尝试先提交 running，事实与终态一次事务提交。进程退出后重新打开库将遗留 running 标为 retryable；已提交终态复用，未提交结果重做。恢复旧运行按原任务范围执行，后续输入变化不污染旧运行，也不会倒退最新 heads。聚合从完整任务范围构建，不只统计本轮新增项；成员按身份稳定排序，固定 attempt/fact ID 可逐条重放。

SQLite 先保存聚合，文件在同目录暂存、flush/fsync 后原子替换，最后才记运行完成。每个 run_id 独立 JSON，已有不同内容拒绝覆盖；恢复清理该 artifact 自有暂存文件。测试覆盖进程硬退出；断电、文件系统损坏、远程盘和跨机锁不在已验证范围。

可注入边界为 `models.Analyzer` 协议：提供完整 `AnalyzerSpec`，实现 `analyze(InputRecord) -> dict | str`，由 `runner.execute/resume` 编排、验证、落库和聚合。分析器拿到全部参与指纹的字段，观察时间在接口外独立保存；不得私自读取未纳入版本的外部依赖。后续按另行授权接入旧客户端即可复用此基础设施；旧 `ExtractionResult/StateDB/merge/export` 不足以表达完整证据和失败语义，本轮不直接复用这些行为，也不替换生产 API 或交接格式。

### 离线测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_job_analysis/test_foundation_inputs.py tests/test_job_analysis/test_foundation_validation.py tests/test_job_analysis/test_foundation_runner.py tests/test_job_analysis/test_foundation_cli.py -q
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
```

新增测试全部使用合成数据、可注入分析器、临时 SQLite 与临时文件；fixture finally 自动关闭/删除并断言目录不存在。包含真正子进程 `os._exit` 中断、事务回滚及发布失败恢复。不得去掉 integration 排除条件后指向演示库；真实数据库与模型效果验证需另获许可。详细本轮通过数、干净检出时的合成配置及网络阻断回归命令见 [历史实施报告](../../../docs/superpowers/archive/2026-10-15-M2-stage-A-implementation.md)（PR #4 审查存档）；原因与教训见 [恢复陷阱](../../../docs/superpowers/traps/2026-10-15-m2-facts-and-recovery.md)。

## 旧管道与既有交接

M2 岗位分析正式目录，已接入 2026-09-01 M2 回包管道源码兼容能力。主要流程为：数据解析/预筛 → 相关性与质量判断 → 技能提取与证据验证 → 合并 → 差异记录 → 交接导出。

- 交接数据：仓库根 `exchange/m2/`；2026-10-15 只读核对为 **717 条岗位定义、717 条按 `job_id` 合并的技能明细、275 条日志**。719/719/243 是 2026-09-01 原回包数字，09-05 演示基线已调整；不是本轮数据库实查。
- 帮助入口（在仓库根进入 backend）：`cd backend; .\.venv\Scripts\python.exe -m app.job_analysis.main --help`。这只验证帮助输出；`main.py` 完整执行路径仍使用 `from pipeline import ...` / `from db_state import ...` 等绝对导入，完整 CLI 不能据此宣称可运行，待 M2 专项修复。本轮未执行收费管道。
- 模块配置：LLM 密钥从环境变量读取（当前模块配置不自动加载本地 `.env`），禁止写入源码或回包；
- M2 输出的技能优先使用 `canonical_name`，无法进入 285 条词典的候选仍保留在证据 JSON 中，并在导入审计中记录，不静默删除；
- 旧的 `input/jd-filter-package/` 已被新回包替代并于 2026-08-30 删除，Git 工作树不再依赖该目录。

源码 `export._write_json()` 写带版本头的 `{items: [...]}` 包装；已核验交接文件为标准数组，集成加载器兼容两种格式。默认 `import_all()` 优先读本地原回包目录，可能覆盖演示基线；只在明确授权的隔离实例显式指定 `exchange/m2`，具体见根目录 `docs/V1恢复手册.md`。
