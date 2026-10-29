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

## 逐例断言草案校验

```powershell
python -m app.job_analysis.baseline assertions <私有根>/case-assertions/v1-draft/cases/DEV-01.json --manifest <私有根>/manifest.json
```

`case_assertions.validate_case_assertions` 校验单条提案与既有人工记录的绑定，`audit_case_assertions` 先通过已登记DEV的限定审计再调用它。只允许清单中development且路径对应既有DEV-01～08的源；在打开样本前核实路径无重定向，不读取HOLD或ZIP，不生成预测、不评语义通过。记录绑定原清单/标注原字节SHA、输入指纹/内容版本、unit_id和原标注证据；主单位自带的引文不能被支持单位替换；A/D互斥分配全部适用D/R单位，B/C可引用它们但不重复增加分母。目标/关系/边界备注单独保留，不当作技能或关系边总数。

草案逐例条件保留 `pending_review`，旧入口拒绝自述已批准；负责人签审后用下述受控批准入口读取。等价拆并改写和作用域仍须业务审核，位置匹配不能批准核心性或新真值。源标注、输入、清单变化时拒绝旧提案，不能只改摘要冒充重审。派生目录的 `index.json` 另登记草案文件哈希，不改原清单或annotations，不是第二套真值。三组跨JD比较、覆盖矩阵、待裁决问题与最小补样建议同目录私有保存，安全摘要见既有P0交付报告。

岗位判断当前契约为 `m2-semantic-0.2`：仅有未覆盖职责时保持 `unresolved`；`not_supported` 必须给出非空结构化冲突（`duty_id/boundary_locator/boundary_quote/reason`），绑定父判断的参照ID/版本和已校验的本地职责证据。程序不证明外部引文真实性或语义冲突成立。旧0.1自由文本冲突不自动升级。`RoleReference` 仅是本轮P0外部职业来源参照格式，不约束未来全部岗位候选必须有来源职业编码或AI起草标识。


## 受控批准条件读取

```powershell
python -m app.job_analysis.baseline approved-assertions <私有根>/case-assertions/approved-v3/release.json --manifest <私有根>/versions/m2-p0-cn-v1.3-dev9-reviewed/manifest.json --approval <私有根>/case-assertions/owner-signoff-dev9-identity-bound-20261029.json
```

必须显式提供包外的受信负责人签审凭据，拒绝archive/samples范围覆盖。该命令只读，不生成批准、不打语义分。成功状态为structurally_valid且business_status=approved，仅表示已批准评价条件的文件/签审/输入绑定通过；semantics仍not_run。原草案的pending是被审内容的历史状态，原annotations仍是唯一人工标签。生产评价条件仅使用release的condition_files；附件中的讨论/裁决历史不能覆盖当前条件。候选材料不因此入评，test/candidate岗位知识不因此正式化。

创建函数（仅在已获该固定索引真实签审后调用）：`create_approved_assertions(index_path, manifest_path, approval_path, output_dir, version="p0-case-map-3-approved")`，位于approved_assertions.py。只创建新目录，复制已审原字节；任何既有目标目录都拒绝覆盖。复制中断可能留下无有效release的目录，须人工诊断，不能自动清理/复用或伪称成功。原v1仅覆盖DEV-01～08；九例版本在明确新签审/生成授权下扩展DEV-09，并验证包内原八例索引/条件字节与补样已签映射。原八例除source_manifest_sha256外不变，新补样断言投影/coverage/input版本必须与签稿一致，并按签审完整快照的SHA单独绑定namespace/jd_id（fingerprint不含id）。任意其他范围不接受；旧入口仍不放开DEV-09。当前版本/摘要以P0规范§3.3为准。

签审凭据是负责人确认的可审查记录，不是密码学签名或身份认证。读者须从受信渠道获取凭据并核对规范记录的发布SHA；不得自造凭据冒充业务批准。来源/单位/Unicode证据校验不证明自然语言正确或模型效果。
