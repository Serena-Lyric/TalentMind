# 陷阱：cleaner experience 单行描述捕获整段致 DataError 1406（2026-08-16）

## 症状
- 从 postings.csv 导入 5000 行时，`INSERT INTO jd_pool` 报 `DataError (1406) Data too long for column 'experience'`，导入中断、零写入。
- 报错行的 `experience` 不是短经验值，而是整段 JD 描述（如 `1 to 3 years ... is an equal-opportunity employer and is ...`）。

## 根因
- `backend/app/collect/cleaner.py::_extract_experience` 的正则 `^Experience\s*:\s*(.+)$` 中 `.` 不匹配换行，但 postings.csv 大量描述是**单行无换行**，`Experience:` 出现在行中，`(.+)` 就把该行"Experience:"之后**整段文本**捕获为 experience。
- 此前该缺陷被 `repository.py` 的 `experience[:32]` 截断掩盖；D33（2026-08-15）扩容 VARCHAR(255) 并移除 `[:32]` 截断后，超长捕获直接撞列宽，成为显性故障。
- 文档曾写"真实数据最长约79字符"，仅对截断后的旧数据成立，对单行描述不成立。

## 修复
- `cleaner.py` 提取层把捕获限制为 `(.{0,255})`（与 `jd_pool.experience VARCHAR(255)` 契约一致），并在返回值再 `[:255]` 兜底；fallback（CSV `formatted_experience_level`）仍优先。
- 修复后重新导入 5000 行成功；`MAX(CHAR_LENGTH(experience))=255`（契约上限），`MAX(CHAR_LENGTH(job_title))=128`。
- 更新 ddl.sql experience 注释说明 cleaner 上限 255。

## 教训
- 列宽约束应在**提取层**保证，不能依赖持久层截断或运气；字段扩容时要同步复核上游提取逻辑是否会产生超长值。
- 正则 `(.+)$` 对"单行大文本 + 行内标题"会贪心捕获整行；需要长度上限或明确的段落边界。
- 文档中的"实测最长约 N 字符"要注明样本范围，避免扩容后仍按旧结论推断。