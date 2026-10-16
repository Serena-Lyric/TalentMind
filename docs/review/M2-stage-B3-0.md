# M2 B3-0 执行报告（Issue #8）

日期：2026-10-16（Asia/Singapore）。临时审查报告，合并前按 AGENTS 归档长期结论并移除；本轮不合并。

## 范围与基线

- Issue [#8](https://github.com/Serena-Lyric/TalentMind/issues/8)，从远端最新 master `93508b035f140a2180d8e6f52666627e707d3857`（PR #7）建立独立工作树与 `codex/m2-stage-b3-0-role-foundation`。
- 实现提交：`1802a95`（严格四维/证据）、`1f76348`（持久化/复用/重放/CLI）；后续文档与验证收尾以本 PR commit 列表为准。
- 原工作区 `D:\Application\ClaudeCode\repository\TalentMind` 保持原 M1 分支；未提交资产文档不带入。核对其 SHA-256 仍为 `F640E0380932F5651BCAE1472E7327A7F8F482AE6C92B68A067FDE40053B571B`。
- 实施依据是 Issue 明确边界与现有 M2-07～11、25～40；没有改 PRODUCT_DECISIONS 或替产品增加新原则。工程拆分见 [计划与执行记录](../superpowers/plans/2026-10-16-m2-b3-0-role-foundation.md)。

## 已实现

| 项目 | 实际能力与限制 |
|---|---|
| 四维 | 独立 family / 主 canonical_job / 多 technology_tracks / seniority；known/unknown/unresolved，仅保存显式断言，不从标题/技能自动分类 |
| 主辅及材料 | 主岗位与辅助角色有来源关联，单角色/混合/疑似多职位分开保存；不拆分、不产出职位数量 |
| 原文证据 | namespace/jd_id/完整指纹、字段、Python字符偏移逐字核对；标题与职责分别保留，冲突维度必须 unresolved；位置正确不代表语义正确 |
| 目录 | 显式严格空配置/合成示例配置，版本化合法值接口；无正式职业目录，不固化前端/后端等业务词表 |
| 持久化 | A SQLite追加四张b30表与共享不可变快照；完整输入源字节、解析后的完整标注/目录、版本、每轮观察与不完整成员可核对 |
| 复用 | 精确输入快照+标注摘要+目录/规则/实际源码版本；观察变化独立保存，其他依赖变化追加结果 |
| 历史与恢复 | UPDATE/DELETE/REPLACE保护，整轮事务，无长期running；提交前重跑，提交后历史replay恢复发布，不加载新分类规则 |
| 旧层隔离 | 不写旧A/B1/B2运行/事实/heads/观察；A增加默认recover=true的兼容开关，B3显式false；旧StateDB拒绝迁移 |
| 正式资格 | 所有已知值仍pending_review，classification_complete=false、semantic_validation=not_performed、formal_statistics_eligible=false；不输出需求率或真实准确率 |

严格畸形输入整轮拒绝（CLI退出2），不静默跳过坏标注；合法来源缺标注仍not_annotated/body=null保存。unknown/unresolved标注完整保留。进程退出0仅代表保存/发布流程成功。

## 验证证据

- 首组29 failed（包尚不存在）→29 passed；持久化新组16 failed→45 passed；CLI与完整源字节一致性追加组RED→GREEN，最终B3 **49 passed**。
- A/B1/B2/B3定向 **421 passed**（42.12s）。含旧A/B1/B2及治理运行共库前后全部旧表逐行对比，另验证A遗留running不被B3打开修改。
- 完整离线非集成 **762 passed / 2 skipped / 23 deselected / 0 failed**（37.57s），190项既有依赖弃用警告，Blocked external/service attempts: **0**。
- 最终交付树复跑同一命令仍为 **762 passed / 2 skipped / 23 deselected / 0 failed**（46.12s），190项既有警告、外部连接0；没有代码新增后未验收的改动。全部新增Markdown本地链接存在，无替换损坏字符，暂存diff检查通过；远端master仍为`93508b0`。
- 两项skipped：`test_m2_return_package.py:15/:26`，私有原M2回包不在检出中。23项真实服务integration按授权边界排除；没有运行MySQL/Neo4j/Redis集成。
- 真实子进程`os._exit(73)`在after_result、before_commit、after_commit、after_stage_output、after_output五处硬退出。提交前新结果/报告为0，提交后完整报告可重放；暂存发布文件按同artifact恢复，旧不同内容产物拒绝覆盖。
- 另外验证缺标注保存、多个方向/主辅/多职位待审、标题职责冲突、跨JD/指纹/伪造位置/类型拒绝、目录/标注/输入/规则/实现变化失效、历史REPLACE保护、事务异常、发布失败、CLI重复键拒绝、旧库拒绝。
- 仓库合成空目录示例经实际CLI run→replay：SQLite reports/results=1/1，原报告与重放完全一致；finally删除专属临时目录，核对remaining=false。
- 测试area fixture均finally清理并断言路径不存在；开发期一次legacy测试连接未关闭导致teardown错误，修正为contextlib.closing后已通过。其遗留4个测试专属文件已精确逐文件删除、空目录移除，核对remaining=false。递归删除命令曾被自动审批策略阻断，未绕过权限或操作其他路径。
- 没有接触生产库，因此不声称生产行数/夹具查询已执行；本轮写入只在临时SQLite，文件已清理。来源/事务边界教训见 [陷阱记录](../superpowers/traps/2026-10-16-m2-b3-source-and-transaction.md)。

### 可复现命令

工作目录backend；无工作树venv时使用已安装requirements的Python绝对路径。局部命令：

```powershell
python -m pytest tests/test_job_analysis/test_role_classification.py -q --tb=short
```

完整回归沿用前阶段已审查的合成配置及socket阻断方式，所有端点均为隔离内存库或不可用合成地址：

```powershell
$b30Regression = @'
import os, socket, sys, pytest
os.environ.update(MYSQL_URL="sqlite:///:memory:", NEO4J_URI="bolt://127.0.0.1:1", NEO4J_USER="offline", NEO4J_PASSWORD="offline", REDIS_URL="redis://127.0.0.1:1/0", OPENAI_API_KEY="offline-test", OPENAI_BASE_URL="http://127.0.0.1:1", LLM_API_KEY="", DS_API_KEY="", LLM_BASE_URL="http://127.0.0.1:1", DS_BASE_URL="http://127.0.0.1:1", GITHUB_TOKEN="", JD_DATA_PACK="__offline_no_data_pack__")
original_connect = socket.socket.connect
denied = []
def offline_connect(sock, address):
    caller = sys._getframe(1).f_code
    if caller.co_filename == socket.__file__ and caller.co_name == "_fallback_socketpair":
        return original_connect(sock, address)
    denied.append(str(address))
    raise RuntimeError("offline regression: service/network connection prohibited")
socket.socket.connect = socket.socket.connect_ex = offline_connect
result = pytest.main(["-m", "not integration", "-q", "-rs", "--tb=short"])
print("Blocked external/service attempts:", len(denied))
raise SystemExit(result or bool(denied))
'@
$b30Regression | python -X utf8 -
```

仅本地asyncio的socketpair初始化获得例外，服务/外部连接均拒绝。B3单元测试另有autouse socket阻断；硬退出子进程只运行本地显式输入/SQLite路径。测试命令不使用生产.env。

## 内部审查与交付状态

首个独立审查代理因模型额度未执行，没有审查结论；改用可用模型独立只读审查后，对 `93508b0..1f76348` 完整diff未发现可复现Critical/Important/Minor缺陷，结论为补齐交付文档后可提PR。审查代理独立重跑B3 **49 passed**（2.35s），未重跑421/762项。不把内部审查等同用户/ChatGPT的集中验收。

审查提出两项非阻断覆盖建议，本轮未额外扩测：B3 CLI专门覆盖标注/目录位于输出目录下的拒绝路径（实现已检查）；显式覆盖疑似多职位附主辅断言、方向集合未决含部分已知项的组合。后者已在README说明输入断言共存仍须待审，不能当作已确认混合岗位或完整分类。审查确认这些组合完整保留未决状态，不构成当前实现缺陷。

[PR #9](https://github.com/Serena-Lyric/TalentMind/pull/9) 已创建并附到当前聊天，目标master，head为`codex/m2-stage-b3-0-role-foundation`；创建后实查state=OPEN、mergedAt=null、autoMergeRequest=null，statusCheckRollup为空（没有远端CI结果可引用）。本地验证与内部审查证据如上，后续由用户/ChatGPT集中审查；不删除分支或工作树、不自行合并。

## 待产品确认与未验证项

- 正式职业大类与标准岗位目录、技术方向/级别映射及版本发布流程。
- 主辅岗位判定、成熟复合职业边界、一份材料含多个职位的拆分/复核规则。
- 职位关联/去重、独立数量与正式需求率、统计降级阈值、语义审核和真实效果验收。
- 本轮只有表达/结构与来源位置验证；没有真实JD标注或模型分类评测，也没有生产迁移、前端、B4/M3/M4、付费API、采集或真实数据清理。
- 整轮SQLite事务适合当前轻量离线标注；未验证断电、磁盘损坏、网络盘或跨机并发能力。
