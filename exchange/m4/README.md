# M4 交接 — 简历解析与岗位匹配

## 正式实现（2026-08-13 迁入，MVP）
- 代码：`backend/app/matching/`（skill_extractor / resume_parser / file_parser / matcher.quick_match_weighted / requirements / canonical）
- 技能归一：`canonical.py` 对齐 `backend/app/skills/skill_dict_seed.json`（D31）；matcher 输出技能为 canonical（小写）
- 文本解析入口：`parse_resume` / `ResumeParser`；匹配入口：`routers/mvp.py` 与 `routers/learning.py` 调用 `quick_match_weighted`
- 旧 `resume_matcher_app.py`、`main.py`、`generate_test_data.py` 与 `job_parser.py` 已于 Issue #81 P5 退役，原实现保留在 Git 历史

## MVP API（A 集成层 routers/mvp.py）

上传 API 自动推荐最多三个岗位，返回 `recommendedJobs`，展示分与 `raw_score` 均为实际规则分。学习路径由 `backend/app/routers/learning.py` 提供，M4 独立 pathfinder 尚未接入。现行输入限制、字段含义和内存态边界见 [M4 使用说明](../../backend/app/matching/README.md)。
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/resume/upload | FormData `file`（PDF/DOCX，依赖未装时失败）或表单 `content`（纯文本）；返回 `{profile, matchResult}`，matchResult 含 score/matched/missing/strengths/target_job |
| GET | /api/resume/target-jobs | 库内岗位列表 `{value,label,score}` |
| GET | /api/resume/skill-dimensions | 技能维度雷达（MVP 返回空结构） |

## 已知限制
- 中文紧邻英文、C++/C# 符号边界已有合成回归；复杂语义与真实解析准确率仍待专项验证。
- PDF/DOCX 解析依赖已安装（requirements.txt 含 pdfplumber/python-docx/mammoth，2026-08-15）；P5 已删除旧 CLI 的 `backend/tests/fixtures/matching/` 生成样例，`file_parser` 保留内联合成回归。
- 匹配为加权规则（编程语言 1.5x / 后端框架 1.3x / 数据库 1.2x），非 embedding
- 真实简历样例未入库（D36），测试用 fixtures 文本样例
