# Issue #20：M3 离线修复计划与验证记录

> 执行方式：本会话直接实施，先反例 RED，再最小修复 GREEN；最后独立审查。对应 writing-plans / executing-plans 工作流，阶段内连续执行。

**Goal:** 修复实体键碰撞、RELATED_TO 候选截断及历史状态覆盖。

**Architecture:** 仅修改完整图构建纯函数并提供只读快照诊断。已知技能只按词典 canonical 的精确名称（忽略大小写）识别，不自动采纳旧别名或输入 canonical_name 主张；未知名称原样区分并审计。实体键使用 UTF-8 百分号编码，可逆且不丢特殊字符；Job ID 保留历史规则，但碰撞拒绝而不覆盖。

**Tech Stack:** Python 标准库、pytest；复用现有环境，不增加依赖。

**Spec:** [Issue #20](https://github.com/Serena-Lyric/TalentMind/issues/20)。基线 origin/master `61608a1`。

## Global Constraints

- 不改 M2 事实、DDL、前端或已核验 exchange/m3/graph.json；不执行 rebuild/import 或连接生产服务。
- Jaccard >= 0.35；完整计算，无 TopK；结果确定排序。
- 状态只表示 legacy_required / legacy_bonus 历史投影，冲突 is_required/weight 为 null、待复核，保留每次原名与来源状态，不冒充 M2 五态。
- 保留原工作区未提交修改；独立分支推送并建 PR，不合并。

## Review Focus

- C++、C#、空白、百分号及版本名称不能误并；场景键同样审计。
- 多次声明、同名跨字段冲突及不同原文 canonical 主张都不能最后写入胜出。
- 至少 12 个岗位共享技能时不漏远端岗位对，阈值与去重正确。
- 重放、输入排列及 JSON/list 字段形式具有确定行为，原始对象不变。
- 离线入口不加载服务连接；现有快照只有投影，不能恢复丢失的原始技能证据。

## Tasks

- [x] 1. `backend/tests/test_m3_graph_integrity.py`：实体/候选/冲突/重放/原输入与快照不变反例；运行并记录 RED。
- [x] 2. `backend/app/integration/rebuild_m2_graph.py`：修复 `build_graph_data(rows, skill_rows)`，输出 nodes/edges/audit；移入服务导入到显式 rebuild 边界。运行定向 GREEN。
- [x] 3. `backend/app/graph/diagnose_snapshot.py`：只读输入快照，内存重建与比较，输出候选、碰撞、冲突和哈希；独立测试并核对修复前后。
- [x] 4. 阻网非集成回归、兼容说明、陷阱/资产维护与独立审查；提交推送 PR 的实际结果见交付补录。

## 工程选择与兼容边界

这是 Issue 已授权范围内的最小设计，非新增产品决策。旧名映射一对多时不能直接重命名：未来需从原始证据重建关系、更新所有消费方后在隔离实例验证并另获生产迁移许可。本轮只输出 `audit.entity_mappings` 和碰撞分组。附加来源信息用平行标量数组，兼容 Neo4j 属性值形态；冲突 null 不可被消费方 bool() 强制为加分，生产接入前须单独适配。场景保留现有每岗位最多 8 项投影，本轮不扩大该范围。

## 执行记录

- 已核对原目录在旧 M1 分支，有未提交端口修复；新工作区独立从最新 master 创建，未夹带这些修改。
- 预检：唯一直接生产调用为显式 `rebuild()`；历史 builder、API 和导入器不在本轮修改范围。当前 GraphEdgeModel 已接受 nullable bool/float，额外字段不要求修改冻结 DDL。
- 实施采用最小源码范围：一处完整图算法、一处标准库只读诊断入口；未修改历史 builder。原词典只用精确 canonical 名称，不擅自认定旧别名都经过严格审核；代价是未核实的同义名称暂时分开，不把分开存储当作语义已确认不同。

## RED → GREEN 证据

Python 复用原工作区 `backend/.venv/Scripts/python.exe`，cwd 为新工作区 backend；不复制真实 .env，不安装依赖。

| 轮次 | 命令/反例 | 结果 |
|---|---|---|
| 算法首轮 | `python -m pytest tests/test_m3_graph_integrity.py -q --tb=short` | 配齐合成服务设置后 14 failed / 4 passed：实体碰撞、12 岗位漏边、冲突覆盖、计数/映射/重放失败；初次缺 OPENAI_API_KEY 为收集配置错误，不算有效 RED。 |
| 算法实现 | 上述文件 + `tests/test_graph.py` | 26 passed。 |
| 诊断首轮 | `python -m pytest tests/test_m3_snapshot_diagnostic.py -q --tb=short` | 新入口缺失，6 failed；实现后修正测试把 str 传给 Path 签名的夹具错误。 |
| 来源补充 | 原始空项索引、明细 bool 分歧 | 2 failed / 18 passed → 定向合计 34 passed。 |
| 独立审查修复 | 原始两级明细位置；逐岗位旧别名映射 | 2 failed / 20 passed → 最终定向 36 passed。 |

最终定向命令：

```powershell
python -m pytest tests/test_m3_graph_integrity.py tests/test_m3_snapshot_diagnostic.py tests/test_graph.py -q --tb=short
```

其中新增 28 项，既有图谱 8 项。输入对象未修改；同输入重放及岗位行换序一致。来源明细换序会改变真实位置和旧算法的历史投影审计，但不改变新技能身份或选择更强/最后状态。

## 独立内部审查

按 requesting-code-review 技能派遣独立只读 reviewer，未写文件或访问服务。另以 100 组确定性随机数据和全岗位对 Jaccard oracle 核对，关系集合与岗位换序一致；无 Critical，提出两项 Important，均已补有效 RED 并修复：

1. 保留 `skill_rows` 行与 skills 原字段两级索引，关系和平行来源数组直接指回输入；audit 保存同一位置，排序不再丢失证据位置。
2. 新旧映射按岗位复现旧 aliases 最后写入投影，仅用于审计。例 cpp→c++ 的实际旧 ID 为 skill:c，新 ID 为 skill:cpp；相同原名在不同岗位的不同旧目标分别保留，不再仅 slug(raw) 冒充旧键。

无延期 Minor。此为开发自检与内部审查，不替代交付后 ChatGPT 定向复审；未自行合并。

## 已核验快照只读比较

输入 SHA-256：`6565d56dbc5a267eb90144f078c54f3d0c761c9a98ca29a18b4dc9c6cdde38e2`，与基线及原工作区文件一致。

| 口径 | 候选对（至少一个共享技能） | 达标 RELATED_TO | 节点 / 边 |
|---|---:|---:|---:|
| 已存历史快照 | 非完整候选，未据此补造计数 | 7 | 7845 / 11412 |
| 同一旧技能 ID 集合，全岗位对穷举 | 46807 | 41 | 仍只读原快照 |
| 修复身份后的内存投影 | 46682 | 36 | 7864 / 11455 |

旧口径漏 34 对，无额外错误已存对。新投影相对已存快照新增 30 对、移除 1 对；相对旧 ID 全量结果新增 1 对、移除 6 对。由特殊字符/名称保留区分后技能集合变化导致，不可将 41 当新身份语义的固定验收值。

- 旧技能键可识别一对多 16 组，含 skill:c → c / c++ / c#；部分名称可能同义，未核实前保留区分并审计。
- 9 岗位存在 11 条 required/bonus 历史冲突边。新投影 REQUIRES=8880、APPLIES_TO=2539、RELATED_TO=36；岗位 717、技能 4690、场景 2457。
- 新旧节点 ID 唯一、无悬空端点、同类型关系键无重复；独立全岗位对 oracle 校验候选和达标集合完整。
- 快照重建只使用岗位节点的技能数组、已存行业边；缺失原技能明细，已经覆盖的行业名称也无法恢复。因此场景真实碰撞数未知，合成反例验证场景键修复；不声称从快照还原了原始数据库或 M2 新事实。
- `python -m app.graph.diagnose_snapshot ../exchange/m3/graph.json` 输出完整映射、碰撞与关系差异到 stdout，无写文件或服务操作。

## 全量验证与交付

完整非集成回归使用合成 MYSQL/Neo4j/Redis/模型地址与临时 sitecustomize，在父/子进程审计钩子中阻断服务/外网 connect、sendto 与 DNS；仅允许标准库 socket.socketpair 自身代码对 loopback 的内部事件循环通信。临时 pytest 基目录与 guard 放在 TemporaryDirectory，finally 自动删除。

首轮夹具误拦 Windows asyncio 内部 socketpair：6 failed / 1152 passed / 2 skipped / 23 deselected；失败为 `test_translate_structure_preserved`、`test_translate_job_skills` 及 middleware 的 `test_health`、`test_bizerror_handled`、`test_unhandled_exception_wrapped`、`test_unhandled_exception_logs_error`。仅修正测试隔离器后重跑，不修改这些业务代码。

最终 `python -m pytest -m "not integration" -q --tb=short --basetemp <专属临时目录>`：**1160 passed / 2 skipped / 23 deselected / 190 既有依赖警告，64.39s**。86 个父/子 Python 进程加载阻网钩子；服务/外网/DNS 尝试 0；标准库内部 socketpair 6 次；专属临时目录退出后不存在（TEMP_AREA_REMOVED=True）。定向检查额外证明纯构建与真实诊断入口均无需导入 sqlalchemy/neo4j/app.db/app.config。

`git diff --check` 通过。没有运行生产/隔离数据库集成测试，没有数据库夹具写入，因此不声称查询过生产夹具计数或逐行业务一致性。前端无变化，未运行前端构建。新旧 ID、nullable 冲突字段与审计还需消费方适配，禁止把本轮离线结果直接导入正式图。

交付实现提交：`098ef6424b83fa7fa79c60a02cefba4d87258987`，已推送 `codex/m3-issue-20`。[PR #21](https://github.com/Serena-Lyric/TalentMind/pull/21) 已创建并附到本聊天，目标 master；实查 OPEN / MERGEABLE、mergedAt=null、autoMergeRequest=null，无远端 CI 结果。保留工作区与分支供 ChatGPT 定向复审，未合并、未删除临时分支。此后仅补录交付文档；受保护的 exchange、M2、DDL、frontend 相对基线 diff 为空。
