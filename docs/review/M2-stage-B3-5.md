# M2 B3-5 实施报告

日期：2026-10-17（Asia/Singapore）。依据 [Issue #18](https://github.com/Serena-Lyric/TalentMind/issues/18)，从最新 master `26c51346e71462d3e53cd58f69ed8d8f5aecdff6` 开始；分支 `codex/m2-stage-b3-5-canonical-catalog`，独立工作树 `C:/Users/Serena Lyric/.codex/worktrees/m2-b3-5-canonical-catalog/TalentMind`。保留原工作树与用户未提交修改。

## 产品规则与交付边界

准确回填用户已确认 M2-52～60 / D91～99：跨大类同名不合并，自动化测试/SDET、DevOps/SRE、数据分析/BI/数据工程、ML/算法研发、安全研发/SecOps 按主要交付责任区分；数据分析技术准入不以单个工具判断。M2-60 首次目录收录由逐项用户确认职责、相邻边界、大类及真实审核记录决定，真实 JD 用于后续独立质量验证。一般原则确认不批准任何具体定义。

本 PR **正式标准岗位零条**；不合并，不启用自动合并，不启动 B4/M3/M4，不修改图谱/生产接口/DDL，不迁移/连接生产数据库、不读取私有 JD、原 .env 或调用真实模型。

## 实现与工程选择

- 新增独立 `backend/app/job_analysis/canonical_catalog/`，没有改旧 B3 源码、family 版本或存储；复用严格 JSON/摘要/锁/原子发布概念与基础实现，不复用 B3-2 accepted 作为目录准入。
- `candidates.v1.json` 八类 19 个非等量草案（2/2/5/2/2/2/2/2），有稳定独立 ID、拟议中文名、family、职责、交付成果、排除项、相邻候选区分、定义依据来源及待审别名。所有精确定义、名字与别名均 unconfirmed / ai_draft。产品原文只证明起草依据，不声称具体定义已经获用户确认。`release.empty.v1.json` 正式目录为空。
- 独立 c35_artifacts / c35_revisions。目录快照绑定候选全文 SHA、family 全文、规则 revision、实际依赖源码摘要及原始来源字节；具名审核绑定 snapshot/candidate/hash，拒绝/延期/接受分别追加，后续决定明确 supersedes 当前事件。不可改旧快照和审核，依赖变化不搬用旧批准。
- 独立 release manifest 逐项列候选摘要、当前接受事件、独立确认来源和版本；不允许用产品原则、候选依据、审核来源/事件及其原字节副本充当另一次确认，拒绝重复 ID、同类别名映射冲突、过期审核、矛盾未显式替代与跨模式授权。相同 release revision 不能绑定不同 manifest；明确前版时不得隐式删掉旧条目，新版全部重新逐项确认。
- 工具不认证人的身份。非合成输出始终为 awaiting_external_approval 的 release_proposal，formal_jobs=[]；现实用户逐项确认和受控 PR/显式目录变更才是授权门。synthetic_only 可在临时输出中模拟完整 candidate → review → admitted，结果位于 simulated_jobs，仍不写正式 release。该选择避免把填写姓名当成授权，不增加未确认的产品发布策略。
- 目录不执行自然语言分类，不制造 JD canonical_job、级别、技术方向、熟练度或 vacancy；不按工具拆职业，不用多个核心候选拼成成熟复合职业。职责交叉主次不清仍需人工判断；来源字节与结构通过不等于语义或身份真实。

## RED → GREEN

1. 候选契约/资产及产品记录首组 **26 failed**（缺模块/目录/新增规则）→ 26 passed。修正两条嵌入式来源引文为真实产品原文，并将空 release 的 approval_status 避开既有凭据字段过滤；没有放宽过滤。
2. 生命周期、审核、manifest、历史兼容与 CLI 首组 **39 failed**（缺 store/runner/CLI）→ 联合 **65 passed**。
3. 自查补测复制审核来源、release 命名版本不唯一和 review/manifest 二次读原文件 **4 failed / 39 passed**，再补一般原则不能当逐项审核来源 **1 failed**；只解析已保存字节、按原字节摘要排除来源复用、命名版本绑定后联合 **70 passed**。
4. 为将来逐项审核直接提供候选摘要映射，candidate_versions 用例 **1 failed / 2 passed** → 增加快照摘要映射；另外两项已有门禁回归确认新定义再审及禁止隐式丢条目。
5. 独立只读审查发现 Important：复制审核事件 JSON 本身仍能充当 release 确认。合成/非合成两项复现 **2 failed** → 排除全部本快照历史事件原输入、来源及完整记录副本摘要，专项最终 **74 passed（5.96s）**。详见 [陷阱](../superpowers/traps/2026-10-17-m2-b35-independent-release-source.md)。
6. 收尾发现 Windows CRLF 产品来源 hash 在 LF 检出无法匹配，新增干净 LF 检出用例 **1 failed** → 仅为产品文档增加 `.gitattributes` 的 `text eol=lf`、规范该文件并重新绑定来源 hash，专项 **75 passed（5.96s）**。曾误从仓库根运行该测试导致 app import 失败，按正式 backend 工作目录重跑后通过；没有为错误命令修改业务代码。完整回归随后再跑。

## 验证、恢复与清理

最终完整阻网非集成回归 **1132 passed / 2 skipped / 23 deselected / 190 warnings（71.01s）**，外部/服务连接尝试 **0**，pytest 和阻网包装均退出 0。两项 skipped 是 `test_m2_return_package.py` 缺少私有原回包，23 项真实服务 integration 按授权排除；190 项为既有 Neo4j/Starlette/FastAPI 弃用警告。此前首轮（独立审查修复前）为 1127 passed；独立审查修复及新增四项测试后 1131 passed（67.79s），最后补 LF 检出用例后完成上述最终回归。

使用原仓已安装 requirements 的 Python 3.14.5 解释器，只读复用运行时，cwd 为新工作树 backend。未复制原 .env/私有文件；完整测试在合成环境覆盖 MYSQL_URL=sqlite:///:memory:、Neo4j/Redis/OpenAI/LLM 端点 127.0.0.1:1、合成认证、LLM/DS/token 为空、JD_DATA_PACK 指向不存在的合成路径。

临时 sitecustomize 通过 PYTHONPATH 同时进入父/子测试进程，包装 socket.connect/connect_ex 并添加 sys.addaudithook 拦截底层 socket.connect；只豁免标准库 Windows `_fallback_socketpair` 的进程内初始化。每次被阻断的外部/服务连接跨进程追加专属日志，最终须为 0 行。执行命令：`python -X utf8 -m pytest -m "not integration" -q -rs --tb=short`。不使用模型/采集或收费 API。合成通过不能说明真实 JD 识别准确率。

所有新增测试使用 `area` fixture：临时目录 finally 自动精确删除，并断言不存在。实际子进程 `os._exit(71)` 覆盖 before_commit/after_commit/after_stage_output/after_output；提交前整轮回滚（含版本登记），提交后可在缺原输入时 replay，不重审当前定义。发布错误可从 c35_artifacts 找 ID 恢复，拒绝覆盖来源/输入/状态与已有不同内容。

实际混合 SQLite 测试先运行已有 A/B1/B2/B22/B30/B31/B32，再追加 B34 和新 c35；逐表核对旧行完全不变，保留 A running，user_version=1。恢复现有由旧 master 实际生成的 v1/v2 混合 fixture，原 B31/B32 审核与导出可 replay，追加 c35 后不改旧记录。families.v1/v2/v3、旧空 catalog、旧输入/报告版本、技能词典、exchange 和生产 DDL 源文件均不修改。

没有生产连接/写入，所以没有执行或声称执行生产夹具行数查询；临时 SQLite、文件与阻网 guard 清理单独核查。原工作树仍只有资产文档原修改，SHA-256 保持 `F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B`。

收尾核验 18 个变更文件的 UTF-8、Python AST/JSON 解析、153 个本地 Markdown 链接通过；`git diff --check` 通过。families.v1/v2/v3、DDL、技能词典按 Git checkout 过滤规则计算 blob，与基线完全一致（Windows 检出换行为 CRLF，不能拿工作树字节直接与 `git show` 的 LF 比较）。仅新增独立目录层、当前产品来源文件的 LF 规则及相应测试/文档；没有前端变更，不运行前端构建或生产服务测试。临时 guard、脚本、日志和 pycache 已逐文件精确清理，实查 guard_remaining=false；测试目录由 fixture finally 清理。

## 独立内部只读审查

按 requesting-code-review / executing-plans 技能派发 fresh reviewer，独立读取 Issue、计划、源码和测试，实际运行当时专项 **70 passed**。发现上述一项 Important，无 Critical、无 Minor；实现方按两模式 RED→GREEN 修复，并重跑全部专项。没有其他已知延期缺陷。未请求重复审查以替代回归；交付仍需 ChatGPT 集中复审。

审查没有认证真实用户身份、判定草案自然语言职业边界的现实正确性，或测量真实 JD 分类准确率；这些不由结构工具或合成例子证明。实现保留 ai_draft/unconfirmed、identity_verified=false、formal_jobs=[]；代价是后续仍须逐项用户审核和单独质量验证。

## 交付状态

实现提交 **`26deedc6f47d9a01d88d7094ba6de4dc311933e4`** 已普通推送；[PR #19](https://github.com/Serena-Lyric/TalentMind/pull/19) 已创建并附到本聊天，base=master、head=codex/m2-stage-b3-5-canonical-catalog。创建后实查 OPEN/MERGEABLE、mergedAt=null、autoMergeRequest=null；statusCheckRollup 为空，没有远端 CI 结果可引用。此后补录仅修改报告/计划/资产状态，不改受测实现或来源资产。本阶段保留独立分支/工作树，等待 ChatGPT 复审与用户再次明确授权；不自动合并、不抢先发布具体标准岗位。
