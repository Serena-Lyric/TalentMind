# P0 离线评价准备与契约

长期口径、私有清单及权限见 [P0 规范](../../../../docs/superpowers/specs/M2-P0-baseline.md)。这是新增的可验证数据边界，不接入旧生产 API、不运行分析器/模型/数据库。

从 `backend/` 使用已有安装了项目依赖的 Python（主仓现有 `backend/.venv/Scripts/python.exe` 可用于独立 worktree）：

```powershell
python -m app.job_analysis.baseline analysis app/job_analysis/baseline/examples/analysis.json
python -m app.job_analysis.baseline bundle <私有根>/manifest.json --archive <主仓>/data/local/chinese-jd-archive.zip
python -m app.job_analysis.baseline bundle <私有根>/manifest.json --samples DEV-01 DEV-02 DEV-03 DEV-04 DEV-05 DEV-06 DEV-07 DEV-08
python -m pytest tests/test_job_analysis/test_baseline_contract.py tests/test_job_analysis/test_baseline_bundle.py -q
```

`analysis` 调用 `validate_analysis(data)`，检查结构、输入摘要、原文偏移、局部引用和知识性质一致性；`bundle` 调用 `audit_bundle(path, archive=None)`，检查列入清单的文件摘要、材料可用性及跨开发/留出集合的身份/规范化正文重复。加 `--archive` 再比对历史来源字节与选中 payload。不传 archive 时不宣称已核对原始存档。

仅允许访问开发材料时使用 `--samples`，**不加 `--archive`**；同时提供两者会在读取任何文件前拒绝。此模式只打开明确选中的 snapshot/annotation 文件，并核对人工标签中已提供的证据字段、代码点区间、引文和输入摘要；返回 `audit_scope` 与 `integrity_scope`，不表示全包文件完整性或跨开发/留出的泄漏检查已重跑。空选择、未知或重复ID直接拒绝，不回退全包。全包默认命令会打开所有成员，不适用于“禁止访问留出”的任务。

当前 DEV 人工标签读取位置仍为私有 `annotations/DEV-01.json`～`DEV-08.json`；统一 Markdown 仅为一致可读参考，五份过程稿、旧 `drafts/` 和初版 `comparison-cases.json` 不作为当前判定输入。`human_reviewed` 表示负责人本轮逐项签审自述已入记录，`reference_status=candidate` 独立表示参照成熟度，不授予正式岗位知识状态。关系备注中的 `none_recorded` 及成组范围不能当作明确关系边或展开成完整配对矩阵。

成功输出不含原文，`structurally_valid` 只表示结构检查；失败退出 1、输出固定安全错误码（如 bundle_artifact_missing、bundle_artifact_digest_mismatch），不回显可能含私有输入的 Pydantic 异常。CLI 只读，不修补文件、不寻找替代数据、不回写清单。私有包中列入 `files` 的文件受摘要保护，额外未列入文件不属于该冻结版本。

`Analysis.model_json_schema()` 可导出结构；模型只描述最低契约，不能自动验证自然语言语义、外部知识中概念确实存在、审批真实性或所有历史数据暴露。声明中的版本摘要须由实际输入/知识和分析器配置提供，不能用模型自述替代依赖校验。

`role-references.v1.json` 是两条有来源的 AI 整理候选，不是完整岗位目录。`examples/comparison-cases.json` 是供后续阶段实现使用的手工合成断言，本段不执行候选关联或演化算法；不得把它们当中文真实验收。

岗位判断当前契约为 `m2-semantic-0.2`：仅有未覆盖职责时保持 `unresolved`；`not_supported` 必须给出非空结构化冲突（`duty_id/boundary_locator/boundary_quote/reason`），绑定父判断的参照ID/版本和已校验的本地职责证据。程序不证明外部引文真实性或语义冲突成立。旧0.1自由文本冲突不自动升级。`RoleReference` 仅是本轮P0外部职业来源参照格式，不约束未来全部岗位候选必须有来源职业编码或AI起草标识。
