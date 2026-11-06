# PR #71 工程可靠性与统一交付

日期：2026-11-07（Asia/Singapore）。起始远端与本地均为 `7f3c4a87f613dad7ca71a16bfdd9aa4230ffca8f`，分支 `codex/resume-learning-unification`，起始工作区干净；它在用户提供的 `2087309` 之上仅多文档收尾提交。最终固定 head、实际回归输出和 CI 链接以 [PR #71](https://github.com/Serena-Lyric/TalentMind/pull/71) 的最终证据评论为准。本文件是交付范围与复核清单，不用旧测试数字宣称当前版本通过。

执行期间，其他会话已合并 #71，生成 `2526f4ef52a4b0b527e5915a5184016f9975571c`，并将本地切换为 master。主代理重新核对该提交与起始 head 的文件树完全相同，全部本轮未提交修改仍在；随后从该 master 建立 `codex/pr71-engineering-reliability` 承载后续 PR，在 #71 保留入口链接。本轮未执行任何合并。

## 执行范围与归属

- A：`mvp.py`、`db/neo4j.py`、`main.py` 和后端定向测试。上传同步工作单元、CSV 全文件预校验/往返、INSERT 返回 ID、应用级 driver 生命周期。
- B：`Jobs.vue` 和岗位页面测试。详情/保存与编辑版本隔离，筛选/分页去重复请求，列表/统计独立成败；新详情与旧列表冲突时保留草稿并阻止静默丢技能。
- C：`Dashboard.vue`、`Analytics.vue`、`JobEvolution.vue` 和面板测试。当前岗位绑定、真实刷新、独立错误/空态及卸载保护。
- 复用 C：遗留 `matching/file_parser.py` 三处确定缺陷及定向测试，保持文件版解析策略。
- 主代理：前端构建入口/CI、上传契约与既有卸载保护回归、文档、交叉审查协调、统一提交及固定 head 验证。

同一工作区按文件独占；仅主代理操作暂存、提交、推送，不合并 master。每组先定向测试，再由未参与该部分实施的代理交叉审查；发现问题交原负责人处理。最终统一提交后执行后端全仓非 integration、前端完整测试/类型检查/构建及跨模块验收，推送后追踪同一 head CI。

## 首轮定向回归与交叉审查（6905ca5）

- 后端在 `backend` 执行 `.venv/Scripts/python.exe -m pytest tests/test_mvp_reliability.py tests/test_neo4j_lifecycle.py tests/test_resume_learning_repair.py tests/test_upload_contract.py tests/test_file_parser_reliability.py -q`：**77 passed**、735 条依赖弃用警告、退出 0。全部服务显式指向端口 1；受限沙箱的 asyncio socketpair 挂起尝试已终止，不计业务通过/失败。
- 前端在 `frontend` 执行 `node --experimental-strip-types --test tests/jobs.test.ts tests/pagePanels.test.ts tests/resumeLearning.test.ts`：**36 passed**、退出 0；本地 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` 退出 0。锁文件安装 `pnpm install --frozen-lockfile` 成功，退出 0，未改锁文件。
- A 审查 B/C 页面，确认并复现“陈旧列表先编辑→新详情新增技能→保存时误删”的 P1；B 增加冲突保护及失败回归，A 复核通过。B 审查旧 parser、配置与上传测试，无新增阻断项。
- C 审查 A 后端，复现后行嵌套非有限 JSON、FLOAT 溢出、TEXT 字节超限、DATETIME 存储边界导致首行先写的问题；A 补 11 项先失败回归与 3 项合法边界测试。C 独立同步探针核对六类拒收均零写入、合法边界通过，无遗留阻断项。
- 合成 HTTP SQLite 验收覆盖创建 ID 对应真实行、岗位技能更新、CSV 导出再导入和错误后行零新增。finally 精确删除唯一 `job_name` 夹具并断言计数 0，旁置哨兵计数仍 1；再精确清理哨兵后总计 0，释放独立内存引擎。

上述是提交前定向证据，不代替最终固定 head 的统一回归与 GitHub CI；最终数字和链接在 PR 证据评论发布，避免报告自身改动使验证 SHA 漂移。

## PR #72 独立复审后的定向收口

[独立复审](https://github.com/Serena-Lyric/TalentMind/pull/72#pullrequestreview-5805340536) 对 `6905ca5` 确认既有核心工程修复与五项 CI，另发现两项缺口；后续仅修以下范围，最新固定 head/统一验证以 [PR #72](https://github.com/Serena-Lyric/TalentMind/pull/72) 的复审证据为准，不复用首轮数字。

- R1（P1）：关闭重开同一岗位会允许并发 PUT，旧服务端写入可覆盖较新的已保存技能。前端负责岗位级在途写顺序、新会话基线核对与草稿保护，回归同时断言实际持久状态和页面保存状态。
- R2（P2）：导入全文件预校验已保证字段错误零写入，但固定 HTTP 错误丢失记录/字段定位。后端补安全的记录序号、白名单字段名及文件级错误区分，禁止回显原始记录；不改变校验范围或逐行事务。

前后端仍按原文件归属独占修改，主代理统一提交和验证，在原两条 review thread 回复修复证据，保留 ChatGPT 独立复审与合并授权流程。

修复已落实在 `Jobs.vue` 与 `mvp.py`，对应测试各新增 8 / 25 项。R1 以岗位 ID 保存跨弹窗在途 Promise，重开等待旧写结束再 GET，保持草稿、冲突保护和不同岗位并发；R2 只返回安全记录序号及模型字段名，文件级错误单独提示，未改变准入与事务。未参与实施的代理只读交叉审查四个源码/测试文件，未发现新增阻断项。主代理提交前复跑后端 `test_mvp_reliability.py test_upload_contract.py test_resume_learning_repair.py`：**92 passed**，前端 `jobs.test.ts pagePanels.test.ts resumeLearning.test.ts`：**44 passed**，均退出 0；类型检查通过。最终固定 head 的全仓/构建/CI 证据另在 #72 更新。

## 验证与安全边界

- 前端固定 Node `24.15.0`、pnpm `11.5.1`，锁文件安装；`build/start/build:open` 均经过类型检查，`serve` 为已有静态构建的本地预览。
- 后端全仓显式 `-m "not integration"`；服务配置固定到 `127.0.0.1:1`，禁用真实模型与 integration 开关。仅合成夹具、内存 SQLite 与 Mock，不连正式 MySQL/Neo4j/Redis，不迁移或删除真实数据。
- 跨模块覆盖上传→推荐→学习路径、岗位技能保存、CSV 往返、图谱 session/driver；M2 当前入口/恢复/历史读回随非 integration 套件与必要定向命令核对。
- 上传按网页 PDF/DOCX/TXT、10MB、DOCX 解压 40MB 契约回归；旧 DOC 继续转换提示。遗留文件版 parser 三修不作为网页链路改进证据。
- 测试实际命令、退出码、skipped/deselected 原因和最终 head 在 PR 评论统一发布；Windows asyncio/socketpair 在受限沙箱卡住时，隔离配置下正常本机执行，不能把卡住的试跑计为通过。

## 保留的限制与未决

- 不改匹配/学习路径/M2 权重、排序、阈值或演化语义。
- CSV 先完成全文件解析与字段校验，再沿用现有逐行提交；后行校验失败时零写入，但写库中途故障仍可能保留此前成功行。不新增去重、覆盖或合并规则。
- 导入日期接受 `YYYY-MM-DD` 或 `YYYY-MM-DD[ T]HH:mm:ss[.微秒]`，规范为 SQL 无时区日期时间并检查 DATETIME 范围；拒绝含时区、紧凑或周日期格式，不自行定义时区换算。导出字段可直接导回。
- 看板 UI 传 `day/week/month`，前端 API 注释写 `month/quarter/year`，后端虽接收 `range`，查询未使用它过滤；本轮只保留并记录此冲突，不定义自然周或滚动天数。
- 本轮非真实浏览器端到端、非真实数据库集成、非 OCR/复杂排版或真实简历准确率验收。Mock 图表证明脚本生命周期，不能替代浏览器绘制效果。
- M2 P2-2/P6 真实中文同组、完整岗位归属与演化准确率继续按 [#63](https://github.com/Serena-Lyric/TalentMind/issues/63)、[#67](https://github.com/Serena-Lyric/TalentMind/issues/67)、[#69](https://github.com/Serena-Lyric/TalentMind/issues/69) 跟踪；工程整合和 CI 通过不代表这些语义验收完成。ChatGPT 对固定 head 独立复审后再按用户授权合并。
