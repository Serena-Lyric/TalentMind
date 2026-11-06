# matching

M4 简历解析与岗位匹配正式目录（已迁入实现：resume_parser / matcher / skill_extractor / canonical 等，详见 `exchange/m4/README.md`）。`input/人岗匹配/` 原版目录按用户要求暂缓迁移（只读对照，不入库）。

上面的 `exchange/`、`input/` 均相对仓库根目录。正式 API 位于 `backend/app/routers/mvp.py`，支持可复制文字的 PDF、DOCX、UTF-8 TXT，最大 10MB；旧版 DOC 需先另存为 DOCX/PDF，扫描件需先转文字。上传内容不写 resume 表，也不发送模型服务。DOCX 按段落/表格顺序读取，合并单元格只提取一次。

匹配采用 canonical 技能加权规则，必备/加分重叠只计必备；`score/raw_score/display_score` 均为实际规则分，不再随机抬分。返回最多 3 个岗位。文本命中不代表能力水平、录用概率或实测准确率。`parseQuality` 是姓名、联系方式、教育、经历、技能五类字段的识别覆盖率（每类 20%），`parseQualityBasis=field_coverage`；不是解析准确率。完整解析经历位于 `profile.education_history/work_experience`，摘要保留最高学历与最近工作。

学习路径由 `backend/app/routers/learning.py` 按岗位要求、JD 证据和简历内存态生成。别名去重，必备优先；技术未命中项给出建议、练习与完成条件；未提及的软技能列入 `verification_skills`，不能推断缺乏能力。空要求返回 `overview.requirements_available=false`。兼容字段 `mastered_skills/completed/at_standard` 仅指文本命中，页面不解释为已掌握/可直接投递。基础→核心→专项→加分为启发式顺序，非技能依赖图；独立 pathfinder 尚未接入。

前端只在内存保存当前简历，刷新需重新上传；零识别技能也可生成路径。上传/切换岗位/清空时旧响应失效，失败可重试。中文英文相邻与符号技能有合成回归；复杂排版、否定语义、真实简历准确率仍未经专项验收。修复依据见 [陷阱记录](../../../docs/superpowers/traps/2026-11-07-resume-learning-evidence-and-state.md)。
