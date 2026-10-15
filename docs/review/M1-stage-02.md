# M1 第二阶段开发与文档核查

日期：2026-10-15。交付目标：`Serena-Lyric/TalentMind` 的临时开发分支，面向 `master` 审查；未经验收不合并、不清理分支或报告。

## 执行计划与边界

- [x] 阶段一：复核 `codex/m1-jd-validity` 工作树中的 v2，运行五份离线测试，核对八个误判案例；独立提交。
- [x] 阶段二：先增加中断离线测试，完成 BOSS 中断保护；智联/猎聘列遗留；独立提交。
- [x] 阶段三：还原单字符损坏，核对主要 README、入口与资产说明；可确认的修正，无法确认的列待核查；独立提交。
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

扫描全部 Git 跟踪 Markdown，六份存在相同的 717 字符逐行损坏：README、AGENT_START_HERE、AGENTS、CLAUDE、A_AGENT_HANDOVER、资产与状态。按原字符拼回两个引用段落，恢复两处被插入块打断的旧引用，没有猜造正文；重新扫描无同类长串。

| 不一致 | 依据与处理 |
|---|---|
| 09 月历史数字/通过数当作当前 | 六份入口明确历史日期；根 README/资产表分别列本轮只读文件计数和测试结果，不声称实查生产库。 |
| M2 交接仍写 719/719/243 | JSON 实际为 717/717/275，中文兼容快照 717；修正根 README、M2 README、exchange/m2 与资产表，保留原回包历史。 |
| M3 图谱仍写 7852/11423，builder 与交接混为一谈 | JSON 实际 7845/11412；旧 builder 仅 Job/Skill，当前交接还有 Industry/APPLIES_TO。修正说明并禁止直接覆盖，源码未改。 |
| 采集页进入自动启动 | Collection.vue 的 prepareOnEntry/mounted 调用已注释；修正当前说明，D54 原历史决策保留并追加实现核查。 |
| 后端命令漏 18000、前端启动缺失 | 对照 vite 配置、package.json、启动脚本，补 host/port、前端安装/启动和代理说明。 |
| “完整 M2 CLI 可运行”、自动读取 .env | main 使用绝对导入，config 仅 os.environ；明确 --help 不能证明完整运行，完整 CLI 待 M2 专项修复，不执行收费管道。 |
| M4 pathfinder 未交付被误写成学习路径不可用 | routers/learning.py 已有确定性分层缺口与建议；区分现有集成能力和待回包算法。 |
| 页面展示分当作真实匹配分/准确率 | mvp.py 的低分候选使用随机演示展示分，并保留 raw_score；Collection 的 LinkedIn/HN 有历史回退数值。修正文档，不改其他模块源码。 |
| 图谱导入描述为无损 MERGE | import_graph.py 实际先 DETACH DELETE；修正 integration README 与资产经验，仅限明确授权的隔离/恢复操作。 |
| docs 导航/Agent 指引过时 | 更新 D60、审查报告入口；笔记/output 明确仅本地，基础设计须服从后续决策；历史采集/导入清单不自动执行。 |

待核查：M2 完整 CLI 与收费管道的运行闭环；M3 统一重建当前图谱的正式流程；二进制 .doc 的兼容范围；独立人工真值下的准确率；当前数据库、采集进程及浏览器登录态。本轮不为确认这些问题启动真实服务/采集、收费调用或改动其他模块源码。

## 提交、遗留与下一阶段

| 阶段 | 提交 SHA | 内容 |
|---|---|---|
| 一 | `80c777d` | 收录已保全的 v2 判定、八个案例的三平台回归及说明 |
| 二 | `20e366f` | BOSS 逐页/逐条持久化、精确补全与 11 项离线中断测试 |
| 三 | `a0d602d` | 六份 Markdown 还原、主要文档与代码一致性修正、D60 工作方式 |

全部修改文件（目录以下为精确文件名；共享文件可能跨提交出现）：

- 根目录：`README.md`、`AGENT_START_HERE.md`、`AGENTS.md`、`CLAUDE.md`、`A_AGENT_HANDOVER.md`。
- `backend/app/collect/`：`cleaner.py`、`pipeline.py`、`repository.py`、`fetch_boss_jobs.py`、`README.md`；`backend/tests/`：`test_pipeline.py`、`test_boss_interruption.py`。
- 其他模块说明：`backend/app/job_analysis/README.md`、`backend/app/graph/README.md`、`backend/app/matching/README.md`、`backend/app/integration/README.md`、`frontend/README.md`；`exchange/m1/README.md` 至 `exchange/m4/README.md`。
- 文档：`docs/README.md`、本报告、`docs/superpowers/资产与状态.md`、`docs/superpowers/决策跟踪.md`；`docs/superpowers/traps/` 下 `2026-10-15-cn-jd-validity.md`、`2026-10-15-boss-interruption.md`、`2026-10-15-markdown-single-character.md`。

收尾验证：

- `frontend/` 执行 `pnpm run build`：类型检查与 Vite 构建成功，2619 modules；保留现有 >500 kB chunk 警告，不提交 dist。
- `backend/` 执行 `.\.venv\Scripts\python.exe -m app.job_analysis.main --help`：退出 0；离线 `importlib.util.find_spec` 核对顶层 `pipeline`、`db_state` 均不存在，完整 CLI 仍列待修复，未运行收费路径。
- 一次性只读文档扫描：全部 Git 跟踪 Markdown 的连续单字符块已消除；主要文档 9 个相对链接、12 个 Agent 路线入口、229 次明确仓库文件引用均可达。仅本地资料与历史路径保留对应语境。
- `git diff --check` 通过；28 个阶段修改文件无私有目录、数据库/日志/备份或 >1 MB 文件，新增行凭据模式扫描无命中。DDL 未改。原有无关 Docker 段逐字比对未变，未纳入提交。
- 局部与非集成测试结果如上；这些通过数来自本地依赖/可选资料环境，新的纯 Git 检出可能跳过依赖本地原回包的既有用例。没有运行 23 项数据库集成测试，也没有对正式库执行核查或清理。

独立只读审查发现 1 项 Important、无 Critical：有效列表技能会掩盖占位详情，使其写入后阻断下一轮补全。已增加“列表→占位/空/薪资详情→下一轮真实详情”3 项回归，先复现 **2 failed / 12 passed**；修复为详情正文单独复用已有判定，不扩规则。最终六份局部 **161 passed**，中断测试 **14 passed**，非集成 **343 passed / 23 deselected**（190 条既有弃用警告），没有未处理的阻塞发现。

审查边界与取舍：无唯一键的并发幂等留后续，不为此迁移表；真实网页/登录态与 MySQL 行为未验收，不启动真实采集或集成；智联/猎聘按用户许可明确遗留；M2–M5 仅核对文档与代码，不扩为功能验收。最终远端核验在收尾补记；不自动合并 master。历史数据库数字不当作本轮查询结果，历史通过数不当作本轮测试结果。

下一阶段优先：对智联/猎聘按当前页卡片逐条完成详情与提交，补中断测试；经审查后再决定是否处理 M2 CLI/M3 重建流程，以及演示评分与平台回退数值的产品口径。
