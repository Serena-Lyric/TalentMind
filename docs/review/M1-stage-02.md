# M1 第二阶段开发与文档核查

日期：2026-10-15。交付目标：`Serena-Lyric/TalentMind` 的临时开发分支，面向 `master` 审查；未经验收不合并、不清理分支或报告。

## 执行计划与边界

- [x] 阶段一：复核 `codex/m1-jd-validity` 工作树中的 v2，运行五份离线测试，核对八个误判案例；独立提交。
- [x] 阶段二：先增加中断离线测试，完成 BOSS 中断保护；智联/猎聘列遗留；独立提交。
- [ ] 阶段三：还原单字符损坏，核对主要 README、入口与资产说明；可确认的修正，无法确认的列待核查；独立提交。
- [ ] 交付：非集成回归、自检 diff 和公开信息边界、推送分支与 PR，补充提交 SHA 和限制。

复用 Python、SQLAlchemy、现有适配器与公共管道；不新增 AI、依赖、队列或数据库字段。不运行真实采集、数据库迁移、真实数据清理或演示库集成测试。当前需求已授权连续执行，计划不设置子阶段审批。

重点验证：列表读到后浏览器退出；下一页失败；详情过程中失败；列表保存后详情仍可补全；详情失败的空卡片不入库。智联的 DOM 卡片依赖当前页面，不能直接照搬 BOSS 的详情导航。

## 阶段一

- 接手分支：`codex/m1-jd-validity`，HEAD `fd17b32`；v2 尚未提交。既有修改先逐文件备份到 Git 私有目录并保存 SHA-256。
- 已审查 `is_valid_jd()`、三平台归一化与 `run_pipeline()`：过滤在清洗后、去重评分/写库前；八个验收案例在三平台均有回归，短职责与混合内容保留。没有增加广告规则。
- 命令（`backend/`）：`.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_cleaner.py tests/test_boss_fetcher.py tests/test_cn_job_fetchers.py tests/test_collect_repo.py -q`。
- 结果：**147 passed**。先前探测命令误引用不存在的 `test_dedup.py`，未执行测试；以上正确命令已完整通过。
- 仅提交相关 v2 代码、测试与说明；`资产与状态.md` 原有 Docker 清理记录保持本地未提交，不夹带。

## 阶段二

- BOSS 改为每页有效列表、每条成功详情分别提交。公共管道增加可替换岗位写入器，保持原过滤和评分；repository 精确查重、补全、提交及回滚。
- 列表不会阻挡同轮详情；跨轮只补可识别的纯列表行。未知历史文本和已有描述不覆盖，稳定 URL、原采集时间及 cross_source 保留；不改表、不删数据。
- `test_boss_interruption.py` 新增 11 项测试；合成输入、临时 SQLite，真实 SQL、独立连接检查提交，fixture finally 删除数据库并断言不存在。未访问正式 MySQL，没有生产库测试残留或清理操作。
- RED：初版 3 failed / 2 passed，复现下一页、详情连接前未提交及详情补全缺失；历史未知文本保护另有 1 failed / 9 passed，补严格元信息识别后通过。
- 局部命令：阶段一五份测试加 `tests/test_boss_interruption.py`，**158 passed**。
- 非集成命令：`.\.venv\Scripts\python.exe -m pytest -m "not integration" -q`，**340 passed / 23 deselected**；190 条现有 Neo4j/Starlette/FastAPI 弃用警告。SQLite 旧日期适配警告已在测试绑定层消除。
- 智联/猎聘：已研究整轮缓冲与写入路径。DOM 身份卡片需要当前页激活，直接套用 BOSS 导航会读错详情；本轮按授权优先交付 BOSS，另外两平台保持原实现，中断保护未完成。
- 限制：未执行真实网页冒烟或 MySQL 集成；现有 DDL 无唯一键，并发采集仍不保证幂等，要求同平台串行。浏览器退出时内存中的未补全卡片可以丢弃，无队列/断点恢复。

## 阶段三

进行中。

## 提交、遗留与下一阶段

完成后补充。历史数据库数字不当作本轮查询结果，历史通过数不当作本轮测试结果。
