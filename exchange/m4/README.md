# M4 交接 — 简历解析与岗位匹配

## 正式实现（2026-08-13 迁入，MVP）
- 代码：`backend/app/matching/`（skill_extractor / resume_parser / job_parser / matcher / file_parser / generate_test_data / canonical / main / resume_matcher_app）
- 技能归一：`canonical.py` 对齐 `backend/app/skills/skill_dict_seed.json`（D31）；matcher 输出技能为 canonical（小写）
- 文本解析入口：`ResumeParser`；匹配入口：`ResumeJobMatcher.match` / `quick_match`

## MVP API（A 集成层 routers/mvp.py）
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/resume/upload | FormData `file`（PDF/DOCX，依赖未装时失败）或表单 `content`（纯文本）；返回 `{profile, matchResult}`，matchResult 含 score/matched/missing/strengths/target_job |
| GET | /api/resume/target-jobs | 库内岗位列表 `{value,label,score}` |
| GET | /api/resume/skill-dimensions | 技能维度雷达（MVP 返回空结构） |

## 已知限制
- `extract_skills` 对"中文紧邻英文"（如 `熟悉Python`）提取失效（原型 `\b` 边界缺陷），待优化
- PDF/DOCX 解析依赖已安装（requirements.txt 含 pdfplumber/python-docx/mammoth，2026-08-15）；`backend/tests/fixtures/matching/samples/` 含 5 份合成 DOCX/PDF 样本（file_parser 实测可解析）
- 匹配为加权规则（编程语言 1.5x / 后端框架 1.3x / 数据库 1.2x），非 embedding
- 真实简历样例未入库（D36），测试用 fixtures 文本样例