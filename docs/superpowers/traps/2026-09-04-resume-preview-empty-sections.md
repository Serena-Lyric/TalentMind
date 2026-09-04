# 陷阱：简历预览页 项目经历/竞赛与荣誉/自我评价 空内容与错误占位（2026-09-04）

## 症状
- 简历预览（ResumeDemo）三个区块异常：`项目经历`、`竞赛与荣誉`恒为空标题无内容；`自我评价`显示错误的占位句「工作年限：…；最近公司：…」（非真实自我评价，应届/无公司时显示「—」）。
- 解析出的项目名对「项目名 2022.03-至今」写法取不到（name 为空），`项目经历`即便有数据也显示空标题。

## 根因
1. `frontend/src/views/ResumeDemo.vue` 预览适配层把 `projects/honors` 硬编码为空数组、`selfEvaluation` 用拼装占位句兜底，而后端 `/resume/upload` 的 profile **从不返回** 项目/荣誉/自我评价字段。
2. `resume_parser.py` 只解析 education/work/project，不提取「竞赛与荣誉」「自我评价」；`_find_section` 结束标题表也不含这两类，导致其后的行被并入前一段（项目描述里混入荣誉行）。
3. `_extract_project_experience` 对「项目名 + 时间段在行尾」的格式只取时间后的文本为项目名（为空），未取行首项目名。
4. **Word 模板简历正文常放在表格中**，`mvp._extract_file_text` 的 .docx 分支只读 `doc.paragraphs`，表格内容（项目/荣誉/自我评价）整体漏掉——这是“简历里有信息但提取不到”的直接原因之一。

## 修复
- `resume_parser.py`：新增 `honors/self_evaluation` 提取（新增 honor/self 关键字、`_find_section` 结束标题表补充两类标题、parse 返回字段）；修正项目名提取（行尾时间段时取行首为项目名）。
- `backend/app/routers/mvp.py`：profile 返回 `projects/honors/self_evaluation`（由解析器字段组装）。
- `frontend/src/views/ResumeDemo.vue`：预览改绑后端真实字段；`selfEvaluation` 去掉错误兜底文案；三个区块无真实内容时整节隐藏；技术栈为空时不显示冒号占位。
- `backend/app/routers/mvp.py`：.docx 提取改为“段落 + 表格单元格”两路拼接，模板简历正文不再漏读。
- 测试：`backend/tests/test_resume_preview_parser.py`（4 条：项目名前置/后置、荣誉、自我评价、项目段在荣誉处截断）；全链路冒烟 profile 字段齐全；前端 `pnpm run build` 通过。

## 教训
- 前端"预览/展示"与后端解析字段必须同契约：不要用占位文案假装有数据，也不要渲染永远为空的结构化区块；无真实内容应隐藏整节。
- 解析器分段结束标题表要覆盖业务上可能出现的全部章节（竞赛/荣誉/自我评价），否则会污染相邻段落。