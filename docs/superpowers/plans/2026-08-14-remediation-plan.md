# 系统修正方案（2026-08-14 v2，整合 input 原版对比 + 中英文统一，待全队确认）

- **状态**：草案 v2。A 与全队确认后生效；裁决项见第十节。
- **日期**：2026-08-14
- **新增依据**：`input/`（队员提交的四个模块原版）与整合版（`backend/app/`、`frontend/`）的代码与产出对比；其他 Agent 的修正建议（字段偏差 17 项已在笔记第八节，本方案合并其可执行项）。
- **定位**：解决「新旧设计并存、模块实现偏差（含原版自带缺陷）、模块内部/联调 bug、中英文数据分裂」四类问题。

## 一、根因诊断（v1 保留 + 本次新增）

1. **权威基线漂移**：新旧两版设计差异未全部裁决（v1 已列 R1–R8）。
2. **契约无校验门禁**：交接文件无机读 schema，字段漂移在联调前发现不了（v1 已列）。
3. **联调是“迁就式”而非“契约驱动”**（v1 已列）。
4. **【新增】中英文分裂是 M2 原版 `translate.py` 自带的设计缺陷**，不是整合时引入：
   - 原版 `translate_job_skills` 把 `job_skill.json` 的 **job_name 和技能名全部翻译成中文**；
   - 原版 `job_definition.json` 是英文 job_name + 英文软技能（如 `communication skills`），而 `job_skill.json` 是中文 job_name + 中文技能（如 `沟通能力`）→ **两套技能词表**，实测原版 8 条与整合版 22 条均为 **0/N 关联**；
   - 翻译技能名会破坏 `skill_dict.canonical` 全局唯一性（`communication` vs `沟通` 是两个节点），直接危害图谱与匹配。
5. **【新增】M5 原版 Learning 页靠 mock 数据**（`src/mock/learning-data.js` 的 `jobLearningPaths`），整合时删 mock 但后端 pathfinder 未实现 → 页面变空态。
6. **【新增】M3 的 RELATED_TO = Job–Job 相似度来自原版实现**（`SIMILAR_THRESHOLD=0.25`），非整合改动 → 需裁决确认而非“纠正”。
7. **【新增】input/ 目录含真实简历且未被 gitignore** → 一旦 `git add -A` 会把真实简历提交（违反 D36），必须先加忽略保护。

## 二、整合版已做的正确修改（保留，不回退）

| 项 | 说明 |
|---|---|
| M2 stage3 skill_dict 约束（D31） | 候选限定 seed，未命中进 unknown_skills —— 反幻觉核心，保留 |
| M3 数据源 m2 优先 + 技能归一 | 从“只读 mock”改为“M2 产出优先、mock 回退”，保留 |
| M4 matcher canonical 化（D31） | 输出技能归一 seed，保留 |
| 目录统一小写 `exchange/m1~m5`（D26） | 原版大写 `M2` 已改小写，保留 |
| 前端 mock 删除 + 全真实 API（阶段 6） | 方向正确，保留；但 Learning/ResumeDemo 需补真实数据源（见 B4/B10） |
| 统一响应 code=0、vue-tsc 接入 build（2026-08-14 已修） | 保留 |

## 三、中英文统一方案（本次核心，建议直接采纳）

### 3.1 原则：一份数据、两层展示；技能词表全局唯一

1. **契约 key 用英文 job_name**（现状 DB/Neo4j/API 已是英文，不改）：
   - `job_definition.json` 每条增加 **`job_name_zh`**（中文展示名），把 `job_definition_zh.json` 的内容并入主文件（不再单独交付 zh 文件）；
   - `job_skill.json` 的 `job_name` **必须等于 `job_definition.job_name`（英文 key）**，中文名只作为展示字段。
2. **技能 canonical 全局唯一、禁止翻译**：
   - 规则固定为：**技术类技能用英文 canonical（python、kubernetes），软技能/通用能力用中文 canonical（沟通、团队协作、问题解决）**——与 `skill_dict_seed.json` 现状一致；
   - `translate.py` 的 `translate_job_skills` **删除“翻译技能名”逻辑**，只允许翻译 job_name、core_duties、scenarios、reason/evidence 等展示文本；
   - 校验器强制：`job_skill[].skills[].name` 与 `job_definition[].required_skills/bonus_skills` 全部 ∈ skill_dict canonical 集合，且 job_skill.job_name ⊆ job_definition.job_name。
3. **API/图谱展示**：
   - `/api/jobs` 列表与详情：`title` 返回中文（`job_name_zh`），新增 `name_en` 作为 key 字段；
   - `/api/graph/data` Job 节点：`id` 保持英文 key，`label` 返回中文（Neo4j 节点属性加 `name_zh`，由 import_graph 写入）；
   - 前端默认显示中文岗位名 + 中文软技能 + 英文技术技能（符合行业习惯，无需前端翻译表）。
4. **短期过渡**（不等 M2 重跑）：A 集成层可用 `job_definition_zh.json` 建立 `job_name → job_name_zh` 映射表，先让 API 出中文；长期以 3.1 的字段落地为准。

### 3.2 改动清单

| # | 位置 | 改动 |
|---|---|---|
| L1 | M2 `translate.py` | 删除 translate_job_skills 的技能名翻译；job_skill 保留英文 key job_name（不翻译） |
| L2 | M2 `export.py` / pipeline | job_definition.json 输出 `job_name_zh` 字段（zh 文件并入）；job_skill.json 的 job_name 用英文 key |
| L3 | M2 `models.py` | MergedJobDefinition 增加 `job_name_zh: str = ""`；MergedJobSkillDetail 的 job_name 语义注明为英文 key |
| L4 | A `validate_exchange.py`（阶段 2 新增） | 强制 job_name 关联 + 技能 canonical 唯一性 |
| L5 | A `import_exchange.py` | job_skill 导入 job_name 用英文 key（与 job_definition 对齐后重导） |
| L6 | A `import_graph.py` | Job 节点写入 `name_zh` 属性 |
| L7 | A `routers/mvp.py` | jobs/graph 返回中文 title/label + name_en |
| L8 | M5 前端 | 展示用 title/label（中文），不再自行处理语言 |

## 四、缺陷修复清单（看板，v1 + 其他 Agent 建议合并）

### P0（数据闭环 / 竞赛硬指标 / 中英文统一）
| # | 模块 | 缺陷 | 验收 |
|---|---|---|---|
| B1 | M2 | job_skill 与 job_definition 关联（L1–L3） | validate_exchange 关联校验通过 |
| B2 | 契约/A | change_type 扩容 VARCHAR(32)（通知后执行） | 插入 scenarios_removed/evolution_changed 成功 |
| B3 | A | import 白名单化 + validate_exchange（阶段 2） | 非空 change_log 样例集成测试 |
| B4 | M4 | pathfinder：missing→level/tip + 差距路径（不编造数字 DR-2） | Learning 页接真实数据 |
| B5 | M1 | jd_pool ≥100 + jd.json + quality_check + 接口自述 | M2 可用 jd.json 重跑 |
| B6 | M2/M4 | ≥100 JD / ≥30 简历标注测试集 + 准确率报告（≥90%） | 报告入库 |
| B7 | A/M2 | 中英文统一落地（L4–L8） | API/图谱全中文岗位名，技能词表唯一 |

### P1（展示 / 增强，不阻塞闭环）
| # | 模块 | 缺陷 |
|---|---|---|
| B8 | M5 | 前端隐藏/降级空字段列（公司/城市/薪资/赛道显示 “—”）；Dashboard 趋势/雷达真数据 |
| B9 | M4 | 中文紧邻英文抽取（`熟悉Python`）；resume 上传落库 |
| B10 | M3 | industry 展示映射（前端映射，不建图谱节点）；Skill–Skill RELATED_TO（P1） |
| B11 | M2 | is_emerging 人工复核流程（manual_review 回灌）；evolution 中文展示映射 |
| B12 | M5 | Learning 数据源（接 B4）；ResumeDemo 数据源 |

## 五、阶段路线（对齐第 3–4 周）

- **第 1–2 天**：阶段 1 全队会（裁决 R1–R8 + 中英文统一方案 3.1）；A 落地 .gitignore 保护 input/、阶段 2 契约机读化（schema + validate_exchange + 接口自述模板）。
- **第 3–5 天**：P0 修复 B1（M2 关联 + 中英文字段）、B2/B3（契约 + 导入白名单）、B5（M1 数据）。
- **第 6–8 天**：B4（M4 pathfinder）、B6（测试集/准确率）。
- **第 9–12 天**：B7（中英文 API/图谱落地）、端到端验收（100 JD → M2 → M3 → Neo4j → 20 API → 六页）、部署说明/演示视频。
- **并行 P1**：B8–B12 按人力穿插。

## 六、联调验收门禁（A 持续）

- 每次交付 4 关：**schema 校验 → 模块单测 → 集成测试（含非空样例）→ 前端冒烟**。
- 端到端录屏脚本；`笔记.md` 第八节偏差表升级为缺陷看板（状态列）。

## 七、协作机制固化

1. 契约变更流程：决策跟踪登记（P 列）→ 用户通知全队 → 变更 DDL/文档 → 同步 validate_exchange。
2. 交接 README 模板（版本头：schema_version / contract_version / generated_at / module）；每模块交付后 A 导入验证并回执。
3. `input/` 仅作对比参考，**不入库**（.gitignore 已保护真实简历）。

## 八、待确认事项（用户/全队拍板）

1. R1–R8 裁决建议（R2 保留 Job–Job、R3 job_skill 同 key、R8 pathfinder 列 P0）。
2. 中英文统一方案 3.1（英文 key + job_name_zh 展示；技能 canonical 技术英文/软技能中文，禁止翻译技能名）。
3. industry 前端映射降级是否接受。
4. 本方案转正并同步决策跟踪 / 笔记 / 资产状态。
