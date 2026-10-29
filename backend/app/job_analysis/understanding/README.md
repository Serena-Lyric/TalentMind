# P1 单条中文 JD 理解

独立于旧 B1/B2、MySQL、Neo4j、岗位分类与前端的异步入口：

```python
from app.job_analysis.understanding import analyze

result = await analyze(namespace, input_row, input_version, processor)
analysis = result["analysis"]
```

`input_row` 是 P0 `InputRecord.from_row` 接受的单条 JSON 对象，必须有 `id/source/job_title/raw_text`；可选 `duties/requirements/experience`。保留完整原输入与指纹，外发只取上述五个文本字段，不发送身份、来源 URL、人工标签或其他任意字段。调用者负责真实数据授权和敏感字段筛查。本实现不自动脱敏或改变偏移，不能直接对未经授权的快照批量外发。

处理器实现 `processor.Processor`：显式可序列化无凭据 `descriptor` 和 `async complete(messages) -> Completion`。当前 `CloudProcessor` 使用 DeepSeek 的 Chat Completions/JSON Output/thinking 参数；替换供应商时须复核数据政策、参数、端点和真实底层模型映射，不能因兼容格式推定供应商相同。无默认代理、端点、自动重试或收费降级链，无 GPU/模型权重依赖；本地模型尚未尝试。

## 实际 CLI

从 `backend/` 执行。配置由 [示例](config.example.json) 复制到私有目录后核实填写；凭据另存私有文件，命令行只传路径，不传 Key 值。

```powershell
python -m app.job_analysis.understanding analyze <单条快照.json> --namespace <数据集> --input-version <冻结内容版本> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录>
python -m app.job_analysis.understanding read <私有run目录>
python -m app.job_analysis.understanding refine <已保存私有run目录> --config <私有配置.json> --key-file <私有凭据.txt> --output <全新私有run目录>
```

`analyze` 在收费请求前独占创建输出目录；已有目录拒绝，无论此前是否完整。不自动覆盖或重新请求。异常退出留下 `pending.json`，不能据此认定结果可用；完成时最后写入 `manifest.json`，`read_run(path)` 核对摘要和 P0 契约再返回原结果。不同 run 互不覆盖，没有共享“当前结果”指针，迟到请求不能替换新 run。`pending.json` 是启动痕迹，完成以有效 manifest 为准。

`run.json` 含真实输入、完整提示/请求、模型内容、实际用量和版本依赖，**只保存在私有位置，不提交或作为公开日志上传**。stdout 仅输出安全汇总，既不回显模型/原文也不回显异常文本。退出码：0=可读执行结果（含部分/无识别），2=已保存的模型执行失败/截断等，1=本地配置、输入或读取拒绝。中止的请求可能仍在供应商侧计费，未返回用量不能填零费用。

`refine` 是发现具体语义风险后的显式一次补充，不是自动重试或默认每条双调用。它绑定同 namespace/JD/输入指纹/内容版本，发送原文、先前机器草稿及通用复核指令，不发送人工标签；新结果以 `lineage` 和配置/提示摘要关联旧结果，原 run 不改。程序调用可传 `await analyze(..., prior=read_run(path))`；身份/版本不同或没有机器草稿时拒绝。补充可能改善、失败或引入新误判，须单独评价，不能用模型自述批准新版本；失败后旧有效部分仍可独立读取。

## 证据、覆盖和下游读取

- 模型草稿使用逐字 `field/quote/occurrence`；程序决定 Python Unicode 代码点 `[start,end)`、namespace、JD身份和输入指纹。重复引文无 occurrence 时拒绝该项，不默选第一处；换行、空白和兼容字形不自动规范化。模型误把内容章节名当作缺失/空字段时，仅在引文于 `raw_text` 逐字唯一出现才改绑实际字段，记录 `grounding_adjustments`；已有字段不符、多处出现、非首 occurrence 不能这样修正。动态 Schema 只列真实非空字段。JS 消费端须另转 UTF-16。正文/字段副本只在语义结构完全相同时合并，保留全部来源并重映射关系；近义重复仍需语义审核。
- 每个 claim/relation 单独校验，坏项不抹除其他有效项，被影响维度降为 partial；同 ID 多次出现一并拒绝，防止关系端点歧义。程序验证引文存在和结构，不证明自然语言语义正确。所有输出保持 `machine_unreviewed`，不得写回人工参照。
- `analysis` 原样遵守 `m2-semantic-0.2`。P1 五维 coverage 可以 complete，但 `classification=not_run`，因此 aggregate `outcome=partial` 正常；`execution.status=ok` 也不表示人工验收通过。知识对齐留原成员、unknown 映射；正式岗位知识、P2/P3 尚未执行。
- `execution.status` 单独区分 ok、partial、failed、not_run、no_recognized_results、empty、truncated、invalid_json、invalid_structure、timeout、http_error、network_error、invalid_response、refused、processor_error。没有完整识别结果与未提及、关系未知、未执行/失败不是同一概念。
- 截断不补 JSON 括号。`length` 返回即使恰好有完整 JSON，也仅保留可校验事实并降覆盖；坏 JSON 只存原始内容供私有诊断，不声称从中完成分析。根结构不合法也不以局部键绕过检查。
- 五态、程度极性、条件、组合及开放性、能力/经验与任职对象保存在 requirement；职责条件须在 duty 文本/证据保留。类别允许未知。不因技术使用升级必备，不展开组合成员为独立必备，不生成能力×职责矩阵。未知词原样保留。
- 版本绑定实际源码/契约/输入/提示/处理器配置摘要、Python、pydantic/httpx 版本；源码摘要在模块载入时固定，长驻 worker 不会被后续磁盘编辑改标版本。`reasoning_effort=low/high/max` 显式配置并传给供应商，缺省 high；实际生效仍依供应商能力。记录 API 返回的模型名/系统指纹与文档宣称版本，供应商别名不是固定模型权重，不能保证跨日可复现。

## 验证与审查

```powershell
python -m pytest tests/test_job_analysis/test_understanding.py tests/test_job_analysis/test_understanding_io.py -q
```

这些合成/模拟测试只证明工程行为；真实效果须按已批准 P0 DEV 的全部适用单位与 A/B/C/D 条件对照，不能用本测试或模型自报完整替代。阶段报告、当前审核及限制统一从 [总进度表](../../../../docs/superpowers/plans/2026-10-28-m2-core-delivery-plan.md#3-分段地图与当前进度) 进入。HOLD 不用于开发。
