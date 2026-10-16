# M2 B3-4 实施报告

日期：2026-10-17（Asia/Singapore）。依据 [Issue #16](https://github.com/Serena-Lyric/TalentMind/issues/16)，基线 `814c99168390f6d3ae476d814d9adddee36223df`；分支 `codex/m2-stage-b3-4-boundary-evidence`，独立工作树 `m2-b3-4-boundary-evidence/TalentMind`。原工作树及其修改保留。

## 范围与产品规则

只追加用户已确认 M2-48～51 / D87～90：研发与工程技术并重的硬件/IC 范围、宽泛岗位仅确定证据支持层级、完整共同交付支持复合候选、独立招聘目标证据与人数分离。正式名单/别名/映射、自动职位拆分与发布、统计细则仍未决定；不自行发布，不合并，不启动 B4，不接生产/真实 JD/模型。

## 实现

- 新增 families-v3，同八类 ID/标签；仅增量范围和三条封闭工程交付句式，v1/v2 文件原字节保全。工艺、封装、良率工程正例及普通操作/标题/宣传/销售/历史/培训反例；跨界、多核心、证据不足 unresolved。B1 范围筛选不自动变更。
- 新建 boundaries/b34 数据层，显式 source=synthetic、synthetic_only 输入。复用 B32 严格候选/源文校验，但只写 b34；不改变 B32 schema/报告。四类主张、复合未证实、family 与独立维度、完整源文分别保存。
- 多目标结构门禁要求独立标题、分段职责/要求、位置一致、分段互斥，编号可选；缺项/冲突/重叠只保留原主张与 unresolved。复合须不同领域的 core 组件与共同交付证据，重复引文/标题/技能/辅助不足；门禁满足仍待审。无已发布 vacancy、招聘人数或需求率。
- b34_versions/inputs/results/reports/reviews/exports 全部不可变；全轮事务提交后原子发布，真实硬退出验证四个阶段。完整源字节、提交、taxonomy/revision/规则/实际源码摘要绑定结果及审核版本；观察时间独立，历史与审核截面原样 replay。

### 工程选择与限制

采用独立层，沿用既有事务/重放模式以隔离旧 schema；无新依赖。程序只证明身份、字节、span 和结构一致，不能证明原文语义、人工署名身份或隐含冲突；错标的历史/否定/无关句仍需复核完整上下文，不把结构门禁通过当作真实招聘事实。自动句式不是开放自然语言分类器，也不是正式标准岗位名单。当前八类可用显式断言表达，技术方向和级别不因标准岗位未知而清空。

## RED → GREEN

1. v3 目录/工程职责首组 16 failed（缺 v3 配置及注册/规则）→ GREEN；与旧版本测试联合 55 passed。
2. 四类结构化证据首组 26 failed（缺独立模块；先修正一处测试候选 helper 的错误默认引文）→ 42 passed（含目录组）。
3. 生命周期首组 21 failed（缺 runner/store/CLI；修正测试中的无用旧类名导入和历史快照 ID 准备顺序）→ 新三组 63 passed。
4. 重复组件与共同交付复用组件引文补测 2 failed / 61 passed → 最小门禁修复后 B3 联合 337 passed。
5. 独立审查同名不同编号用例 1 failed / 1 passed → 修复；收尾 family/方向/级别断言缺署名用例 1 failed / 2 passed → 严格来源署名校验，最终完整回归见下文。

## 验证与清理

最终完整非集成阻网回归 **1057 passed / 2 skipped / 23 deselected / 190 warnings（64.22s）**，父进程及子进程外部/服务连接尝试 **0**，退出 0。两项 skip 为 `test_m2_return_package.py` 缺私有原回包，23 项真实服务 integration 按授权排除；190 项为既有 Neo4j/Starlette/FastAPI 弃用警告。此前首轮完整回归 1053 passed / 2 skipped / 23 deselected，随后新增署名、基线混合历史及真实 CLI 验证后重跑为上述最终结果。合成通过数不代表真实语义准确率。

验证使用已安装 requirements 的 Python 3.14.5（原仓 venv 解释器），工作目录为新工作树 backend，未加载原仓 `.env`。只读复用解释器，不复制密钥/私有数据。环境显式覆盖 MYSQL_URL=sqlite:///:memory:，Neo4j/Redis/OpenAI/LLM 端点为 127.0.0.1:1，合成认证，LLM/DS/GitHub token 为空，JD_DATA_PACK 为不存在的占位路径。临时 `sitecustomize.py` 经 PYTHONPATH 传播给全部测试子进程：包装 socket.connect/connect_ex，另用 sys.addaudithook 阻断底层 socket.connect；仅豁免 Python 标准库 Windows `_fallback_socketpair` 内部初始化。所有拒绝尝试跨进程记录到专属日志，最终 0 行。不是依赖测试作者单独记得 mock 网络。

可在相同合成环境运行 `python -m pytest -m "not integration" -q -rs --tb=short`；完整阻网包装的核心如下，须在启动 pytest 之前加载并通过 PYTHONPATH 传播给子进程：

```python
import os, socket, sys
original_connect = socket.socket.connect
def internal_pair():
    frame = sys._getframe(1)
    while frame:
        if frame.f_code.co_filename == socket.__file__ and frame.f_code.co_name == "_fallback_socketpair":
            return True
        frame = frame.f_back
    return False
def deny(address):
    with open(os.environ["B34_NETWORK_LOG"], "a", encoding="utf-8") as log:
        log.write(str(os.getpid()) + ": " + repr(address) + "\n")
    raise RuntimeError("offline regression: external/service connection prohibited")
def offline_connect(sock, address):
    if internal_pair():
        return original_connect(sock, address)
    deny(address)
def audit(event, args):
    if event == "socket.connect" and not internal_pair():
        deny(args[1])
socket.socket.connect = socket.socket.connect_ex = offline_connect
sys.addaudithook(audit)
```

测试 `area` fixture 在 finally 关闭/删除专属临时 SQLite 与文件并断言目录不存在；新增历史生成目录、阻网 guard 也已 finally 清理，临时 guard remaining=false。实际模块子进程执行 boundaries run→review→export-reviews→replay 原报告/导出，字节相同；四条合成样例分别覆盖宽泛、复合、多职位与竞争主张，只有多职位样例有两个待审分段，没有人数派生。生产服务未连接、没有生产写入，因此没有执行或声称执行生产行数/夹具查询。

历史混合夹具 `history.families-v1-v2.json` 来自 **git archive 814c991** 的基线源码实际离线运行：先导入现有旧 v1 历史，再执行 v2 B31/B32、追加审核/截面，导出原始行（BLOB 保留 UTF-8 字节表示）。不是用 v3 源码伪造旧 v2 报告。测试把旧 v1/v2 共库存回后追加 b34，逐行比对原历史并逐份 replay；另实际执行 A/B1/B2/B22/B30/B31/B32 共库、保留 A running 状态，旧表逐行不变。

v1/v2 Git blob 分别保持 `2d1c49c820ccea7a84c5c6137f71e574fbdf149e`、`a89efdeaab92e1092bede0ab4ef51e64a8f86231`，与基线相同。未改旧 exchange、词典、正式 DDL 或历史归档；本轮源码共用更改仅 proposals/models.py 和 rules.py，旧报告不重算。

## 独立内部审查与修复

按 requesting-code-review/executing-plans 技能分派 fresh reviewer 只读审查，独立运行当时 B3-4 三组 **79 passed**、旧 family/proposals/governance/storage **209 passed**。发现 1 项 Important：初版错误要求目标标题不同，遗漏同名而编号不同的独立招聘目标。新增回归 **1 failed / 1 passed** 后修复：同名必须有不同、各自在独立原文段内的编号，仍逐项检查职责/要求和互斥 spans；未把名称相同直接合并。见 [陷阱记录](../traps/2026-10-17-m2-b34-evidence-gates.md)。修复后专项 82 passed；收尾再补非空署名校验（1 failed→GREEN）、基线混合历史和真实模块入口，最终全部进入 1057 项回归。

审查没有判定显式自然语言主张的真实语义、正式目录/人数/发布，因其明确属于本轮未授权范围；对此工程裁决是保留原文与未审状态、准入/统计恒 false，代价是仍需人工复核，不能承诺真实效果。该审查优先代码，最终文档由主执行者单独核验；不替代交付后的 ChatGPT 集中复审。无其他已知延期缺陷。

最终源码专项复核 **86 passed（4.23s）**。文件 UTF-8/Python AST/JSON 解析及 135 个本地 Markdown 链接核验通过；`git diff --check` 通过。原工作树仍仅保留原资产文档修改，其 SHA-256 为 `F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B`。

## 交付状态

实现提交 `7bbe8a25d70fdfa70b4d47fe4a65050558dd38d3` 已推送；[PR #17](https://github.com/Serena-Lyric/TalentMind/pull/17) 已创建并附到当前聊天，base=master、head=codex/m2-stage-b3-4-boundary-evidence。实查 OPEN/MERGEABLE、mergedAt=null、autoMergeRequest=null，远端 statusCheckRollup 为空，无远端 CI 结果可引用。此后提交仅补录交付文档，不改实现。此段为提交交审时点记录；最终状态以 PR #17 为准。保留独立开发分支/工作树。

## ChatGPT 独立复审与归档（2026-10-17）

ChatGPT 对 [PR #17 Review #5550858572](https://github.com/Serena-Lyric/TalentMind/pull/17#pullrequestreview-5550858572) 进行了 GitHub 源码、测试路径、产品契约及实施报告独立静态复审，未发现新的 Critical/Important 合并阻塞项。复核了 v3 新增工程职责与 v1/v2 历史隔离、B34 宽泛/竞争/复合/多目标待审证据、同名不同编号目标边界、具名审核/版本绑定、不可变重放与故障恢复。Codex 的完整阻网非集成 1057 passed、2 skipped、23 deselected，父/子进程服务连接尝试 0 为实施方报告；ChatGPT 未在相同 Windows 环境独立重跑全部测试。无外部 CI 结果可作为独立验证。合成结构证据不代表真实自然语言语义准确率或已审核岗位归类。

用户已于复审后授权归档并合并 PR #17，实际合并状态以 GitHub 为准；不清理原开发分支/工作树。**随后 B3-5 的产品决定**：首次正式标准岗位目录采用“逐项人工确认职责定义、相邻岗位边界、归属大类和审核记录后收录”；真实 JD 样本作后续验证，不强制作为初次目录收录前置条件。该决定尚未由 B3-4 实现，不得理解为本次已发布正式标准岗位。
