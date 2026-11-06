# 简历解析与学习路径修复计划

> **For agentic workers:** 使用 executing-plans 按任务执行，先回归失败再修复；最终独立代码审查。

**Goal:** 在当前主工作区补齐简历上传、解析、推荐及学习路径的可用性，并整合已有分支。

**Architecture:** 复用现有 Python 规则解析与 Vue/Pinia 内存态，不增加模型服务或数据库结构。岗位和简历技能按 canonical 比较，明确“文本命中”不代表掌握程度。

**Tech Stack:** FastAPI、pytest、Vue 3、TypeScript、现有 Node 测试工具。

**Spec:** 本次用户授权自主修复并尝试合并全部分支；产品边界仍依照 `docs/PRODUCT_DECISIONS.md`（软技能未提及不能推断缺乏）。

## 全局约束

- 只使用当前工作区，不创建 worktree；保护启动时已有的 M2 P5/P6 未提交修改，不夹带提交。
- 不迁移数据库，不调用真实模型，不上传真实简历；测试只用合成文本/内存文件和隔离临时数据。
- 保留兼容响应字段；不再随机美化匹配分，不把字段识别覆盖率称为准确率。
- 学习顺序仍是启发式，不假称已建立技能依赖图；软技能未提及列为待核实。
- 合并保留历史，不强推、不删除历史分支；每个分支必须检查祖先关系和冲突。

## Review Focus

1. 空简历技能、空岗位要求不会被误报为完成或阻止生成。
2. C++/C#、技能别名及必备/加分重叠不漏计或重复计数。
3. 无日期工作经历、学校不在旧名单、DOCX 表格不会崩溃或丢失/重复正文。
4. 上传失败、重复上传、路由切换、清空简历时旧响应不能覆盖新状态。
5. 格式/大小异常在查询岗位前拒绝，不把二进制当简历或泄露解析异常细节。

## Task 1: 简历输入、解析与推荐

**Files:** `backend/app/matching/{resume_parser,skill_extractor,matcher}.py`、`backend/app/routers/mvp.py`；测试 `backend/tests/test_resume_learning_repair.py`。

**Interfaces:** 保留 `parse_resume(text)`、`quick_match_weighted(...)`、`POST /resume/upload`；新增完整 education/work_experience 字段及可核对的字段覆盖率说明。

- [ ] 编写合成测试：无日期经历不崩溃；符号技能；普通学校/分行教育；表格按文档顺序只提取一次；未知格式/超限拒绝；分数确定且 aliases 一致。
- [ ] 执行上述测试，确认失败原因。
- [ ] 最小修复，运行 matching、resume_preview_parser 及新增测试后独立提交。

## Task 2: 学习路径与页面状态

**Files:** `backend/app/routers/learning.py`、`frontend/src/components/{LearningRoadmap,ResumeDiagnosis}.vue`、API 类型及相关测试。

**Interfaces:** 复用 `build_learning_path(...)`；添加待核实技能/数据不足状态，兼容旧字段；前端依赖更新后重新请求且仅接受最新响应。

- [ ] 先覆盖别名去重、空要求、软技能待核实、JSON 无效形态、阶段建议与异步迟到响应。
- [ ] 修复并验证后端定向测试、前端测试和 `npm run build`。
- [ ] 同步模块说明、资产状态、陷阱及产品索引，独立提交。

## Task 3: 审查、整合与同步

- [ ] 独立代码审查本次修改，修复重要问题并测试。
- [ ] 明确备份/暂存原有未提交文件，只在合并需要时 stash 指定路径；逐一合并未包含的分支并解决冲突。
- [ ] 在整合后的主线执行相关后端/前端测试和构建，检查私有文件边界、相对链接及 Git diff。
- [ ] 普通推送主线，恢复原有未提交修改，核对远端 master、本地 master、当前工作区 HEAD 一致，报告保留的未提交工作。
