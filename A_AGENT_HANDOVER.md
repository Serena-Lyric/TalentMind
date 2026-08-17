# A 角色开发路线与交接文档（给下一个接手 A 工作的 Agent）

> **前置**：先完成 `AGENT_START_HERE.md` 通用路线（逐文件阅读并给出要点证明），再读本文件。
> **角色**：A = M1 数据采集负责人 + 唯一集成者（决策 D2/D3/D4）。你接手的是"系统集成 + 回发闭环验收 + 继续 A 的未完成事项"。

## 一、A 专属必读（通用路线之外）

| 文件 | 作用 |
|---|---|
| `backend/app/integration/validate_exchange.py` | 交接文件 schema 校验器（回包第一关；change_type 枚举硬校验、版本头软提示） |
| `backend/app/integration/import_exchange.py` | M2 交接 → MySQL 导入（**全量重建语义**：M2 产出是权威岗位集合） |
| `backend/app/integration/import_graph.py` | graph.json → Neo4j（MERGE 幂等；换数据先清空） |
| `backend/app/routers/mvp.py` | 20 个统一 API（jobs/graph/resume/dashboard；中英文 title/name_en 已生效） |
| `backend/app/collect/` | M1 采集（import_csv 等；jd_pool 5000 cleaned 已就绪，2026-08-16 恢复） |
| `backend/.env` | 本地配置（MySQL/Neo4j/Redis/LLM 密钥，gitignore 保护，**禁止外传/入库**） |
| `frontend/前后端接口对接文档.md` | 20 接口基线文档 |
| `output/` | 回发包 v3（已生成并发送给四位队员；结构见 08-14 roundtrip 方案） |

## 二、当前状态（截至 2026-08-16，commit `42a12b1`）

- **数据闭环完成**：jd_pool 5000 cleaned（2026-08-16 恢复导入；原 5003 曾被集成测试误删，见 traps/2026-08-16-integration-test-wiped-jd-pool.md）；skill_dict 285；job_definition 22（M2 约束重跑）；job_skill 22；Neo4j Job 22 / Skill 75 / REQUIRES 191 / RELATED_TO 31；`exchange/m1/jd.json`（200 条，2026-08-16 重新导出）。
- **测试**：后端 198 全量通过；前端 `pnpm run build`（含 vue-tsc）通过。
- **服务**：后端 uvicorn :8000、前端 vite :5173（vite 已配 `/api` 代理到 8000）；MySQL/Neo4j/Redis 在 Docker。
- **中英文过渡已上线**：API `title/label` 中文 + `name_en` 英文 key（过渡方案；M2 回包 `job_name_zh` 后转正式）。
- **回发闭环进行中**：`output/` 四包 v3 已发送队员（M2/M3/M4/M5），队员二次开发窗口 8/16–19，A 验收 8/19–21（错峰：M2 8/19 → M3/M4 8/20 → M5 8/21）。
- **已扩容**：`job_change_log.change_type VARCHAR(32)`、`jd_pool.experience VARCHAR(255)`（DDL+DB 均已改；正式通知随全队会议）。

## 三、交接：你接手后必须做的事

### 1. 立即（等队员回包前）
- [ ] 全队会议：正式通知 change_type / experience 扩容（均已执行，补告知）+ 中英文统一规则 + 版本 v3 基线 + 错峰时间表（材料见 `笔记.md` 第十一节 + `output/` 各包问题/要求清单）。
- [x] 补填 `exchange/m1/quality_check.md` 抽样 10 条核对结论（2026-08-16 已由 AI 基于数据标注：10/10 通过，可人工复核）。
- [ ] 熟悉验收工具链：`validate_exchange.py`、`import_exchange.py`、`import_graph.py`、测试命令（`cd backend && .\.venv\Scripts\python.exe -m pytest -q`）。

### 2. 队员回包验收（4 关门禁，见 08-14 roundtrip 方案 Step 5）
1. **schema 校验**：`validate_exchange`（字段/类型/枚举/关联/版本头）；
2. **diff 检查**：A 修改文件未被回滚（M2 `stage3_extract.py` 约束、M4 `matcher.py` canonical 化、前端 request/vite 配置等，见各包 README「A 修改文件清单」）；
3. **单测/集成**：队员测试结果 + A 机复验（198 基线 + 模块新增）；
4. **导入 + 前端冒烟**：import_exchange/import_graph → MySQL/Neo4j → `/api` → 前端页面。

验收通过 → 更新 `资产与状态.md` / 决策跟踪 → 进入下一里程碑；不通过 → 新问题清单随下一轮回发。

### 3. 队员回包后的跟进
- [ ] **M2 回包后重生成数据快照**（`output/` 各包 `依赖数据快照/快照说明.md`：snapshot_version+1）同步给 M3/M4/M5；
- [ ] 用新产出重跑 M3 builder（`exchange/m2` → graph.json）→ 清空重导 Neo4j；
- [ ] 若 M2 增加 `job_name_zh`：API/图谱切换到正式中文字段（当前为过渡映射）；
- [ ] 重跑 `validate_exchange` 确认关联警告（当前 job_skill↔job_definition 3/22）清零。

### 4. 未完成事项（P1 / 收尾）
- [ ] 阶段 7 清理：`input/` 下原交付目录（`jd-filter-package/`、`图谱模块/`、`岗位能力图谱-前端源码/`、`人岗匹配/`，2026-08-16 确认已归档于此）（**`input/人岗匹配/岗位测试用例/*.pdf/docx` 真实简历删除前先列清单与用户确认**，D36）；
- [ ] 部署说明与演示材料（P3）；
- [ ] P1 项（见 `笔记.md` 第七节）：M2 is_emerging 复核与 100 JD 测试集；M4 pathfinder 已列 P0（队员）；M5 空列/趋势/Learning；M3 Skill–Skill；resume 落库。

## 四、操作手册（A 常用命令）

```powershell
# 启动基础设施
docker compose up -d

# 启动后端 / 前端（两个终端）
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
cd frontend; pnpm dev

# 全量测试
cd backend; .\.venv\Scripts\python.exe -m pytest -q

# 交接校验（回包第一关）
cd backend; .\.venv\Scripts\python.exe -m app.integration.validate_exchange  # 或调用 validate_m2()/validate_m3()

# M2 交接 → MySQL（全量重建）
cd backend; .\.venv\Scripts\python.exe -c "from app.integration.import_exchange import import_all; print(import_all())"

# graph.json → Neo4j（换数据先清空再导）
cd backend; .\.venv\Scripts\python.exe -c "from app.integration.import_graph import import_graph; print(import_graph())"

# 重建图谱（基于 exchange/m2 产出）
cd backend; .\.venv\Scripts\python.exe -c "from app.graph import builder as b; b.DATA_SOURCE_PRIORITY=['m2']; print(b.build_graph())"

# M2 管道重跑（需 backend/.env 配 LLM_API_KEY）
cd backend; .\.venv\Scripts\python.exe -m app.job_analysis.main <输入SQL/JSON路径>

# 前端构建（含 vue-tsc 类型检查）
cd frontend; pnpm run build
```

## 五、红线（不可违反）

1. **禁止 `git add -A`**：`input/` 含真实简历、`output/` 含打包物、`backend/.env` 含密钥、`data/local/` 含 421MB SQL；只 add 明确文件。
2. **`笔记.md` 不提交**（用户要求）；`output/`、`input/` 不入库。
3. **契约变更先通知**：改/删字段须全队通知（D32/D33/P4 已执行，通知随会议）；加字段自由但须同步 `validate_exchange` 与文档。
4. **不臆测**：不确定先查资产清单/决策跟踪/笔记；仍不确定问用户。
5. **测试门禁**：任何集成改动后必须 `pytest` 全量通过（198 基线）+ 前端 `pnpm run build`。
6. **测试数据清理（D37）**：集成测试写库数据必须按测试夹具特征精确清理（finally/teardown），禁止按 source 宽泛删除；跑完测试后查询 DB 验证无残留、生产数据未被误删。