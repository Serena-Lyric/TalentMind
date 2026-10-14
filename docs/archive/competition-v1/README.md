# 竞赛 V1 资料归档

2026-10-14 从本机原始交付及第一轮备份审查、去重后补入。原 `input/`、`output/`、`docs/submit/`、`docs/originalfile/`、`.superpowers/` 和笔记均保持原位置，没有整体强制入库；来源与导出方式见 [source-index.json](source-index.json)。

## 内容

| 目录 | 保存内容 |
|---|---|
| `design/` | 参赛 V1 产品设计、技术设计、测试方案与报告的 Word 正文导出 |
| `materials/` | 08-31 参赛准备、实现、测试和部署历史文档 |
| `development/` | 早期开发进度、8 份阶段报告、团队笔记 |
| `interfaces/` | 原始前后端接口与采集接口草案，个人姓名替换为合成示例 |
| `handover/` | M2 原版使用说明、M4 原型说明、09-04 会话交接 |
| `demo/` | 历史演讲稿及分镜表 |
| `data/` | 100 条 JD 的初版中文标注、两个岗位图谱示例、450 个时间演化版本 |
| `generators/` | M2 原版时间演化数据生成脚本，仅作历史源码保存 |
| `runtime/` | 第一轮核验时实际安装的 Python 包版本，不含配置值 |

## 使用边界

这些是**历史资料**，不是当前契约或操作手册。当前规范仍以 `backend/app/contracts/ddl.sql`、`docs/superpowers/决策跟踪.md`、正式源码和 [V1恢复手册](../../V1恢复手册.md) 为准。原文的相对路径、Mock 开关、`code=200`、旧图谱计数、旧阈值及旧测试结果均保留历史含义，不应照搬回正式系统。

`development/task-7-report.md` 曾记录宽泛 `DELETE WHERE source='dataset'` 清理；该方式后来造成数据事故并已废止，见 [D37 陷阱](../../superpowers/traps/2026-08-16-integration-test-wiped-jd-pool.md)。历史部署说明、测试方案和演示脚本也含覆盖或写库操作；本轮只归档，不执行。

Word 正文导出未携带作者、自定义属性和缩略图，表格转为段落。原始 DOCX 留在私有备份。设计文档的 RAG 等扩展描述、旧报告的准确率/覆盖率声明及演讲稿分数均不是本轮重新验证的性能结论；缺少独立评估记录的指标不得据此宣称已经验证。

## 测试数据口径

- `100-jd-annotated.json` 为 08-31 大模型初版标注，不是完成人工复核的金标准；原始 100 条抽样数据已在 `exchange/m2/100-jd-test-cases.json`，这里不再复制。
- `time-evolution-emerging.json` 为 85 类岗位、255 个版本；`time-evolution-existing.json` 为 65 类岗位、195 个版本，合计 **150 类 / 450 个版本**。
- 版本 3 来自原交付的真实 JD；版本 1/2 通过回拨时间、删减技能及证据句构造，属于**合成回溯演示**，不是 450 条独立的真实历史观测。
- `expected_skills` 来自原管道提取结果，不代表独立人工真值；本轮只核对 JSON 结构、规模、敏感信息及来源，不重跑 LLM 准确率评估。
- 这些小型数据经过内容审查，未携带真实简历、联系方式、实际密钥或浏览器登录态。大型原始 CSV/SQL/JSONL 仍只保留私有副本。

## 生成脚本

`generators/make_evolution_testset.py` 是未改动的 M2 原版脚本，依赖原模块的 `config.DATA_DIR`、`state.db` 与 `exchange/M2_final`。它不属于正式后端运行代码；需要原交付环境才能执行，会写输出目录。本轮未执行，也未据其声称输出可逐字确定性再生成（导出时间戳、同分排序等有环境依赖），因此已交付测试数据保留在 GitHub。

通用精简备份核验和恢复工具为根目录 `scripts/backup_assets.py`。只使用 Python 标准库；默认只核验，`--restore-to` 只接受不存在的新目标目录。
