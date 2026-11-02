# P1 单条中文 JD 理解

独立于旧 B1/B2、MySQL、Neo4j、岗位分类与前端的异步入口：

```python
from app.job_analysis.understanding import analyze

result = await analyze(namespace, input_row, input_version, processor)
analysis = result["analysis"]
```

`analyze` 默认先做一次完整中文理解；若发现 explicit 关系、结构化程度/条件、已存原料约束冲突或未解析限定词，再最多做一次只读的定向语义审计。低风险输入保持一次调用。结果以 `primary_run`、`pipeline` 和独立阶段 run 保留两次实际请求、用量及失败状态；不能把审计自报当作人工确认。

`input_row` 是 P0 `InputRecord.from_row` 接受的单条 JSON 对象，必须有 `id/source/job_title/raw_text`；可选 `duties/requirements/experience`。保留完整原输入与指纹，外发只取上述五个文本字段，不发送身份、来源 URL、人工标签、指纹、版本摘要或其他任意字段。调用者负责真实数据授权和敏感字段筛查。本实现不自动脱敏或改变偏移，不能直接对未经授权的快照批量外发。

处理器实现 `processor.Processor`：显式可序列化无凭据 `descriptor` 和 `async complete(messages) -> Completion`。随附配置示例使用 DeepSeek 官方 `model="deepseek-flash"`（2026-10-17 文档对应 `DeepSeek-V4.1-Flash-1017`），同时使用 Chat Completions、JSON Output、thinking 与 `reasoning_effort`；历史 Pro run 只作历史证据。替换供应商时须复核数据政策、参数、端点和真实底层模型映射，不能因兼容格式推定供应商相同。无默认代理、端点、自动重试或收费降级链，无 GPU/模型权重依赖；本地模型尚未尝试。

## 实际 CLI

从 `backend/` 执行。配置由 [示例](config.example.json) 复制到私有目录后核实填写；凭据另存私有文件，命令行只传路径，不传 Key 值。

```powershell
python -m app.job_analysis.understanding analyze <单条快照.json> --namespace <数据集> --input-version <冻结内容版本> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录>
python -m app.job_analysis.understanding analyze <单条快照.json> --namespace <数据集> --input-version <冻结内容版本> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录> --raw
python -m app.job_analysis.understanding read <私有run目录>
python -m app.job_analysis.understanding refine <已保存私有run目录> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录>
python -m app.job_analysis.understanding audit <已保存私有run目录> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录>
```

`analyze --raw` 只执行完整理解主阶段，用于诊断；默认 `analyze` 在本模块内启用最多一次风险定向审计。`audit` 只接受已有机器草稿并做字段级定向编辑，不新增职责、目标或对象；`refine` 是把旧草稿作为上下文的一次完整显式补充。三者都不是自动重试。

所有入口在收费请求前独占创建输出目录；已有目录拒绝，无论此前是否完整。不自动覆盖或重新请求。默认入口在主阶段完成后先保存 `primary/`，审计完成后保存 `audit/`，最后写顶层 manifest；异常退出留下 `pending.json`，不能据此认定结果可用。完成时 `read_run(path)` 核对摘要和 P0 契约再返回原结果。不同 run 互不覆盖，没有共享“当前结果”指针，迟到请求不能替换新 run。

`run.json` 含真实输入、完整提示/请求、模型内容、实际用量和版本依赖，**只保存在私有位置，不提交或作为公开日志上传**。stdout 仅输出安全汇总，既不回显模型/原文也不回显异常文本。退出码：0=可读执行结果（含部分/无识别），2=已保存的模型执行失败/截断等，1=本地配置、输入或读取拒绝。中止的请求可能仍在供应商侧计费，未返回用量不能填零费用。

`refine` 绑定同 namespace/JD/输入指纹/内容版本，发送原文、先前机器草稿及通用复核指令，不发送人工标签；新结果以 `lineage` 和配置/提示摘要关联旧结果，原 run 不改。程序调用可传 `await analyze(..., prior=read_run(path))`；身份/版本不同或没有机器草稿时拒绝。补充可能改善、失败或引入新误判，须单独评价，不能用模型自述批准新版本；失败后旧有效部分仍可独立读取。

## 证据、覆盖和下游读取

- 模型草稿使用逐字 `field/quote/occurrence`；程序决定 Python Unicode 代码点 `[start,end)`、namespace、JD身份和输入指纹。重复引文无 occurrence 时拒绝该项，不默选第一处；换行、空白和兼容字形不自动规范化。模型误把内容章节名当作缺失/空字段时，仅在引文于 `raw_text` 逐字唯一出现才改绑实际字段，记录 `grounding_adjustments`；已有字段不符、多处出现、非首 occurrence 不能这样修正。Locator Schema 固定列五个公开文本字段，用户消息只发送真实非空字段；字段存在与否仍由定位校验决定。JS 消费端须另转 UTF-16。正文/字段副本只在语义结构完全相同时合并，保留全部来源并重映射关系；近义重复仍需语义审核。
- 每个 claim/relation 单独校验，坏项不抹除其他有效项，被影响维度降为 partial；同 ID 多次出现一并拒绝，防止关系端点歧义。程序验证引文存在和结构，不证明自然语言语义正确。所有输出保持 `machine_unreviewed`，不得写回人工参照。
- 定向审计不能扩大既有引文来“证明”限定词归属。`degree/condition` 必须给出 target、qualifier 和局部谓词/共享修饰/明确承接证明；要求组合的每个成员都必须落入可核验的限定范围。字段不同仅允许唯一完整字段副本映射；兼容字形查找须能映射回实际代码点，不能接受半个兼容展开或部分 ASCII 实体。
- 审计修订项的嵌套 `requirement.reason` 可省略；程序只在缺少该字段时把同一修订项的外层 `reason` 写入，拒绝不同理由被静默混用。该兼容不放松 claim、引文、组合或限定词证明。
- 字段级保留只在既有准确引文内扩充 scope；这不证明限定词语义上属于当前能力。非能力对象移除不适用的已知技能类别并审计。正向 required/preferred 的程度改写若不是连续原文，保留完整 text/evidence/state，将 degree/polarity 设 null 并记录未解析、降覆盖；不能把它读成“无程度要求”。审计不得静默擦除已有有效 degree。否定程度与无证据条件不做删除式救回，仍拒收，避免抹掉限定或扩大否定。
- “期望/更看重”软性章节中的 required 会按来源位置降为 preferred，范围在下一招聘/申请/联系方式等程序标题处结束。同一软性任选能力与可运行产出共享同句时，产出会成为能力 requirement 的精确 condition，避免拆成两个看似独立的 preferred。
- 关系强度由程序核验的源角色决定：同一活动或共享上下文只有同时给出可核查的 `means/work` 局部活动锚点时才可为 `inferred`；缺少锚点时，新端点不生成关系，既有端点最多保留有界 `unknown`。只有同句/有明确承接的“使用/利用/基于/借助某手段完成某项局部工作”且有正向前提、局部谓词和工作对象对齐时才可 `explicit`。同名动作、共同对象、简单共现和跨逗号的新增谓语不得升级；真实直接用途也不得被一律降为 unknown。审计必须处置全部既有关系端点；遗漏任一端点会把 relations 降为 partial，不能把“模型未返回”当成确认删除。
- `analysis` 原样遵守 `m2-semantic-0.2`。P1 五维 coverage 可以 complete，但 `classification=not_run`，因此 aggregate `outcome=partial` 正常；`execution.status=ok` 也不表示人工验收通过。知识对齐留原成员、unknown 映射；正式岗位知识、P2/P3 尚未执行。
- `execution.status` 单独区分 ok、partial、failed、not_run、no_recognized_results、empty、truncated、invalid_json、invalid_structure、timeout、http_error、network_error、invalid_response、refused、processor_error。没有完整识别结果与未提及、关系未知、未执行/失败不是同一概念。
- 截断不补 JSON 括号。`length` 返回即使恰好有完整 JSON，也仅保留可校验事实并降覆盖；坏 JSON 只存原始内容供私有诊断，不声称从中完成分析。根结构不合法也不以局部键绕过检查。
- 五态、程度极性、条件、组合及开放性、能力/经验与任职对象保存在 requirement；职责条件须在 duty 文本/证据保留。类别允许未知。不因技术使用升级必备，不展开组合成员为独立必备，不生成能力×职责矩阵。未知词原样保留。
- 版本绑定实际源码/契约/输入/提示/处理器配置摘要、Python、pydantic/httpx 版本；源码摘要在模块载入时固定，长驻 worker 不会被后续磁盘编辑改标版本。`reasoning_effort=low/high/max` 显式配置并传给供应商，缺省 high；实际生效仍依供应商能力。记录 API 返回的模型名/系统指纹与文档宣称版本，供应商别名不是固定模型权重，不能保证跨日可复现。
- DeepSeek 磁盘上下文缓存自动启用，不发送伪造的 `prompt_cache_key`。主理解与审计各自把公共 system instruction、固定 JSON Schema、字段顺序和 canonical 序列化放在共享前缀，JD 文本和机器草稿只放在后续 user 内容；两种请求形态分开统计。响应原样保留可用 `prompt_cache_hit_tokens`/`prompt_cache_miss_tokens`；缺失时标 unknown，不填零。缓存是 best-effort，完整前缀单元命中不保证，不能为命中删掉语义上下文。

## 验证与审查

```powershell
python -m pytest tests/test_job_analysis/test_understanding.py tests/test_job_analysis/test_understanding_io.py tests/test_job_analysis/test_understanding_audit.py tests/test_job_analysis/test_understanding_pipeline.py tests/test_job_analysis/test_understanding_policies.py -q
```

这些合成/模拟测试只证明工程行为；真实效果须按已批准 P0 DEV 的全部适用单位与 A/B/C/D 条件对照，不能用本测试或模型自报完整替代。阶段报告、当前审核及限制统一从 [总进度表](../../../../docs/superpowers/plans/2026-10-28-m2-core-delivery-plan.md#3-分段地图与当前进度) 进入。HOLD 不用于开发。
