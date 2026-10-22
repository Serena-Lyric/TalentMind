# M1 分平台修复 Implementation Plan

> **For agentic workers:** 使用 executing-plans 在当前会话连续实施；每阶段先补失败回归，再修复、验证、独立复核。

**Goal:** 先修复智联的详情绑定、错误报告和中断保存，再单独处理 BOSS 的普通浏览器桥接。

**Architecture:** 复用现有控制器、平台适配器、事件和增量保存管线。控制器向智联 worker 传递已准备的目标身份；缺失标题只作内容与身份分账，不降低身份门槛；合格详情逐条持久化。

**Tech Stack:** Python、FastAPI、SQLAlchemy、既有 CDP、Vue、pytest。

**Spec:** 当前会话用户确认的排查结论；`docs/PRODUCT_DECISIONS.md` §2；根 `AGENTS.md`。

## Global Constraints

- 保留未提交头像修改，不夹带到采集器提交；不合并或覆盖 PR49，不执行 DDL。
- 离线回归只用合成 CDP、临时 SQLite；禁止接入正式数据库或招聘平台。
- 真实功能验证只通过控制链路：单平台、单关键词、单城市、1 页、最多 2 条，页面间隔 15–30 秒；遇验证立即停止。
- 不进行批量、持续采集，不读取凭据，不绕过登录/验证码/反爬；BOSS 单独验收，不反复 CDP 探测。

## Review Focus

- 两次相同旧面板不能作为目标更新后的稳定证据。
- 列表标题迟到可等待；始终缺失时明确拒绝身份，不用详情反填后宣称绑定成功。
- 数据库失败须输出具体失败事件、结束统计，并停止后续详情访问。
- 已确认的详情必须在访问下一条或进入间隔前完成保存，停止任务不丢先前已提交记录。
- 子进程必须使用父进程绑定的目标；缺失或转移时失败关闭，不能换同域标签。

## Task 1: 智联面板与列表稳定性

- [x] 在 `backend/tests/test_cn_detail_gate.py` 和 `test_collection_identity.py` 补慢面板、空标题与列表延迟渲染失败回归。
- [x] 在 `fetch_cn_jobs.py` 等待“内容变化后两次稳定”，对空标题列表做有界重读；在 `identity.py` 区分正文资格与 `missing_list_title`。
- [x] 运行对应定向测试，保留原身份、截断和错岗拒绝回归。

## Task 2: 智联逐条保存与故障分账

- [x] 在 `test_cn_detail_gate.py` 补“下一条开始前可查询已保存行”和“写库失败输出 failure/finished”回归。
- [x] 复用原 pipeline/saver，逐条提交合格详情；数据库失败立即结束，不执行真实迁移。
- [x] 核对重复/跳过、pending 不计 complete、断线保留前项；临时 SQLite 在 finally 删除并验证。

## Task 3: 控制器目标绑定

- [x] 在 `test_collection_product.py`、`test_browser_runtime.py` 补父→子目标传递与缺失目标失败关闭回归。
- [x] 在 `control.py`、`fetch_cn_jobs.py`、`browser.py` 保留智联的目标 ID/URL；启动 worker 不重新挑选其他标签。
- [x] 运行 CN、浏览器、控制器、子进程相关离线回归；核对控制链路上限与原 BOSS 行为。

## Task 4: 分阶段交付与 BOSS

- [ ] 记录智联修复陷阱、资产状态和阶段报告，独立复核并形成独立提交/PR；不自行合并 master。
- [ ] 核对数据库与浏览器当前条件，条件未满足时只报告阻塞，不以离线通过冒充真实通过。
- [ ] 随后单独评估 PR49 的桥接契约、扩展和回环代理，按实际依赖移植并离线验证；真实 BOSS 输入需用户在普通浏览器中人工操作。

## 实施记录

- 2026-10-22：用户已授权按平台逐步修复；先智联，BOSS 后续。分支 `codex/m1-platform-repair-20261022`，基线 `ce9e068`；头像修改保持未提交。
- 第一阶段：267项离线通过，审查P2已补两项失败回归修复并复核；数据库23306未监听，真实入库验收待环境及独立DDL门禁满足。
