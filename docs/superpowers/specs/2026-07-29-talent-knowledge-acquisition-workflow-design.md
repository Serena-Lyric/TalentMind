# 人才知识数据获取工作流设计（Talent Knowledge Acquisition Workflow）

- **日期**: 2026-07-29
- **定位**: 数据获取模块（原 Plan A）的版本更新设计，替代 `docs/superpowers/plans/2026-07-20-planA-data-collection.md` 的整体设计思路
- **关联**: 契合 `2026-07-20-talentmind-系统架构-design-v2.md`（全队冻结契约），是其中"数据采集"部分的深化，不推翻 v2 已冻结的表（`jd_pool`/`signal`/`skill_dict`/`job_skill`/`emerging_job`/`resume`），仅新增人才侧原始数据契约
- **讨论来源**: 基于一次外部研讨会式对话整理（原始链接内容已完整转录并经用户确认），本文档是该讨论的结构化落地
- **设计侧重点**: 五人协作、各自实现算法细节，本设计只锁**接口与数据契约**，不规定具体清洗/去重/采集算法的实现方式

## 1. 背景与项目定位

项目是一个五人分工的多源异构数据驱动岗位与能力图谱系统（新一代信息技术方向），`2026-07-20-talentmind-系统架构-design-v2.md` 是项目启动时的全队冻结契约，其他成员据此各自开发模块。本设计者负责的是其中"数据采集"部分，即原 Plan A。

Plan A 最初是为了快速解锁下游（C/D/E）而设计的占位实现，只覆盖了岗位数据（JD）的采集与入库（`jd_pool` 表 + CSV 导入管道，已完成实现）。本次研讨重新审视了"自动化人才数据获取工作流"的设计目标，确定需要将其升级为更完整的**人才知识数据获取工作流**，并用这份设计替代原 Plan A 的整体思路（不是推翻已完成代码，而是在其基础上扩展）。

五人小组的实际协作方式是各自独立开发、代码风格和实现细节不强求一致，后期合并到一台设备整合。因此本设计的核心价值不在于规定"怎么爬、怎么清洗"，而在于钉死**模块边界与数据契约**——谁产出什么形状的数据、新数据源如何接入、原始数据表结构是什么——确保合并时接口对得上。

## 2. 任务边界（重新定义）

**本模块负责范围**：

```
数据源 → 自动获取 → 原始数据存储 → 清洗 → 标准化 → 质量检测 → 数据库
```

止步于**原始数据入库完成**。不负责：

- ❌ 数据分析
- ❌ 能力图谱算法（角色 D）
- ❌ 大模型抽取（角色 C，消费本模块产出的 `jd_pool`/`talent_raw`）
- ❌ RAG / 推荐系统
- ❌ 结构化简历解析（角色 E 的 `resume` 表，消费用户上传的单份简历，与本模块产出的批量原始人才数据不是同一层）

需要考虑下游兼容性：字段设计不能只满足当前入库，需便于后续技能抽取、能力图谱构建等环节消费。

## 3. 时间约束的重新解读

初期讨论一度把"一个月"理解为项目规模上限（倾向选现成数据集、降低工程复杂度），后修正为：**一个月是流水线上线周期，不是数据量指标**。

核心结论：

- 数据量不是核心指标，**自动化流程本身具备持续更新能力**才是核心指标
- 各数据获取类型（岗位/人才/技能）分模块同步推进，而非串行排队
- 公开数据集的定位是**冷启动（Cold Start）**——降低初期数据不足的影响，不是最终方案；系统本质仍是可持续运行的动态自动化获取平台

| 指标 | 重要性 |
|---|---|
| 是否支持自动化采集 | ★★★★★ |
| 是否支持多数据源扩展 | ★★★★★ |
| 是否有统一数据处理流程 | ★★★★★ |
| 是否可以持续更新 | ★★★★★ |
| 当前数据规模 | ★★★ |

## 4. 核心设计决策记录（Q1-Q8）

以下是研讨会式讨论中确认的关键决策，供后续设计和实现参考，避免反复讨论或方向漂移：

| 问题 | 结论 |
|---|---|
| Q1 系统驱动方向 | **人才驱动**：人才数据 → 人才画像 → 与岗位能力图谱比对 → 差距分析（而非岗位驱动） |
| Q2 人才对象范围 | **通用模型 + 技术人才增强**：数据库模型保持通用（不限行业），采集策略对技术人才（GitHub/开源）做特化增强，对高校学生小幅优化，同时兼容通用职业人才 |
| Q3 人才数据来源模式 | **混合模式**：公开数据集初始化冷启动 + 动态采集持续增强，不追求"真实身份认证"，也不是纯样本库 |
| Q4 人才最小描述单位 | **实体档案 + 能力事件结合**：原始数据 → Entity/Event 层 → Talent Profile 层三层结构（不是只存静态档案，也不是只存事件流） |
| Q5 自动化程度目标 | **自动发现/采集能力 + 可扩展 Connector 架构**：系统可周期性运行采集；新数据源接入只增加新 Connector，不改核心系统 |
| Q6 数据获取粒度 | **双中心模型**：同时维护 Talent Entity 和 Skill/Job Knowledge Entity，形成"人才拥有技能、技能满足岗位需求"的匹配闭环 |
| Q7 技能体系构建方式 | **混合方式**：基础 Skill Taxonomy 打底 + 数据驱动动态发现新技能，合并进统一 Skill Knowledge Base |
| Q8 采集模块组织方式 | **双层结构（方案 C）**：Fetcher 统一拿数据，Pipeline 按数据类型分流处理（详见第 6 节） |

已不再是"简历自动获取方案"，升级为：**面向人才能力分析的异构数据自动获取与知识库构建工作流**。

## 5. 双中心数据模型

系统采集的不是单一对象，而是两类可关联的数据：

```
              Talent Data Ecosystem

        Talent Entity        Knowledge Entity

             人才                 能力/岗位

              │                    │
              │ possesses          │ requires
              ▼                    ▼

             Skill  ──────────── Job
```

**理由**：仅采集人才数据能回答"这个人会什么"，但无法回答"这个能力是否匹配某岗位"（缺少外部标准）；仅采集岗位/技能数据能回答"岗位需要什么"，但不知道"谁具备这些能力"。双中心才能形成人才能力 → 技能匹配 → 岗位匹配 → 差距分析的闭环，对应竞赛核心功能（简历解析 + 岗位匹配 + 差距分析）。

**数据分类**：

- **Talent Sources**（人才侧）：简历数据集/文件、GitHub/Gitee、公开个人资料、开源贡献
- **Knowledge Sources**（知识侧）：招聘岗位数据、技能词典、技术文档、行业数据

人才数据模型采用三层结构：

```
多源数据（简历/GitHub/岗位/数据集/文件/API）
    ↓
Raw Data Layer（原始数据层，保留来源/获取时间/原始文本，不急于判断代表什么）
    ↓
Entity / Event Layer（实体与事件层，统一表达不同来源的数据）
    ↓
Talent Profile Layer（人才画像层，供业务模块调用的最终结果）
```

**本模块只负责 Raw Data Layer 的产出**（获取 → 清洗 → 落库），Entity/Event 抽取和 Talent Profile 生成属于下游（角色 C 的技能抽取/角色 D 的图谱构建）职责范围。

## 6. 采集模块组织方式（Q8 最终方案）

### 6.1 决策过程

讨论过三个方案：

- **方案 A（数据源驱动）**：每个数据源一个 Collector，独立产出到对应表。改动最小，但 Talent 侧和 Knowledge 侧的清洗/去重逻辑会在每个 Collector 里重复，接口约束力最弱，多人协作时最容易走样。
- **方案 B（数据类型驱动）**：先定义 `TalentCollector`/`KnowledgeCollector`，数据源作为插件接入。边界最清晰，但需要拆现有的单一 pipeline，对已完成的 CSV 导入代码改动最大。
- **方案 C（双层结构，已采纳）**：`Fetcher` 统一拿数据（不关心去哪张表），`Pipeline` 按数据类型分流处理。是现有代码的自然延伸，新数据源接入只需实现一个 `Fetcher` 子类。

**采纳方案 C**：完全兼容现有代码（`Fetcher` 抽象、`cleaner.py`/`dedup.py`/`repository.py` 均不推翻），且"新增数据源只需实现一个 `Fetcher.fetch()`"这条规则最简单、最难被其他成员误用，符合五人各自独立开发、后期合并代码的协作场景。

### 6.2 分层结构

```
Fetcher（已存在的抽象，签名不变）
    ↓ fetch() -> list[RawJD | RawTalent]
Pipeline（单一入口，按返回元素类型路由，不新增平行入口）
    ├── RawJD      → 现有 clean/dedup/quality/save_rows（jd_pool，不变）
    └── RawTalent  → 新增 clean_talent/dedup(复用)/quality(复用)/save_talent_rows（talent_raw，新增）
```

`Fetcher.fetch()` 返回的类型本身就是路由依据，不需要额外的 `kind` 字符串字段。

## 7. 字段级契约

### 7.1 `RawTalent`（新增，与现有 `RawJD` 并列，不改动 `RawJD`）

```python
@dataclass
class RawTalent:
    source: str                          # 数据源标识：github / resume_dataset / resume_file ...
    raw_text: str                        # 简历正文 / GitHub profile 描述等原始文本
    identity_hint: str = ""              # 姓名/用户名等弱标识，仅供后续实体消歧参考，不代表已确认身份
    skills_hint: list[str] | None = None  # 数据源自带的技能线索（未归一，如 GitHub 语言列表）
    experience_hint: str = ""            # 经历/项目文本线索
```

字段命名对齐现有 `RawJD` 风格（`source`/`raw_text`/`experience`）。`identity_hint` 明确标注"弱标识"——人才实体消歧（同一人多来源合并判断）不在本模块职责内，这里只留线索给下游。

### 7.2 `talent_raw` 表（新增，与 `jd_pool` 同批写入 `ddl.sql` 并冻结）

```sql
CREATE TABLE IF NOT EXISTS talent_raw (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source VARCHAR(32), identity_hint VARCHAR(128), raw_text TEXT,
  skills_hint JSON, experience_hint TEXT,
  quality FLOAT DEFAULT 0, dup_group VARCHAR(64),
  crawled_at DATETIME, status VARCHAR(16) DEFAULT 'raw',
  INDEX idx_status (status), INDEX idx_source (source)
);
```

字段结构与 `jd_pool` 一一对应（`quality`/`dup_group`/`crawled_at`/`status` 语义一致），使 `dedup.py` 中的通用函数（`text_signature`/`quality_score`）可直接复用，无需为人才侧另写一套去重/质量逻辑。

### 7.3 函数签名契约

```python
# talent_cleaner.py（新文件，与 cleaner.py 并列，职责分离）
def clean_talent(raw: RawTalent) -> dict:
    """人才侧清洗：不做 JD 式的职责段落提取（岗位专用逻辑不适用于简历/GitHub 文本），
    只做通用文本规整。具体清洗规则由实现者决定，本设计只锁签名与输出行结构。"""
    ...
    # 返回字段需覆盖：source, identity_hint, raw_text, skills_hint, experience_hint,
    #                crawled_at, status（对齐 talent_raw 表结构）
```

```python
# repository.py 追加（不改动现有 save_rows）
def save_talent_rows(db, rows: list[dict]) -> int:
    """结构对齐 save_rows，写 talent_raw 表。"""
```

```python
# pipeline.py 改动（run_pipeline 按类型分流，保持单一入口）
def run_pipeline(db, raws, job_skill_map=None, skill_map=None) -> dict:
    """raws 可混合 RawJD 与 RawTalent；按 isinstance 分流到两条处理链，
    JD 侧逻辑完全复用现状，Talent 侧调用 clean_talent + 复用 dedup/quality + save_talent_rows。
    返回统计需区分 jd_saved / talent_saved。"""
```

### 7.4 文件组织

```
backend/app/collect/
  schema.py            # RawJD（不变）+ RawTalent（新增）
  cleaner.py            # JD 专用清洗（不变）
  talent_cleaner.py      # 新增：clean_talent(raw: RawTalent) -> dict
  dedup.py               # 通用去重/质量分（不变，两侧共用）
  repository.py          # save_rows（不变）+ save_talent_rows（新增）
  pipeline.py            # run_pipeline 按类型分流（改）
  fetchers/
    base.py              # Fetcher 抽象（不变）
    github.py            # 现有骨架；GitHub 属于人才侧，未来产出 RawTalent
    dataset.py            # 现有 CSV 导入（不变，产出 RawJD）
  contracts/ddl.sql       # 追加 talent_raw 表定义，与 jd_pool 同批冻结
```

## 8. 与现有设计的关系

- **与 v2 架构契约的关系**：不改动 v2 已冻结的 6 张表（`jd_pool`/`signal`/`skill_dict`/`job_skill`/`emerging_job`/`resume`），`talent_raw` 是新增表，遵循 v2 契约冻结规则第 10 条"加字段/加表自由，改/删须全队通知"。
- **与原 Plan A 的关系**：本设计替代 Plan A 的整体范围定义（原 Plan A 仅覆盖 JD 采集），已完成的 JD 采集代码（`schema.py::RawJD`、`cleaner.py`、`dedup.py`、`repository.py::save_rows`、`fetchers/dataset.py` 的 CSV 导入）全部保留、不推翻，仅在其基础上并列扩展人才侧。
- **与角色 E（`resume` 表）的边界**：`talent_raw` 是自动化批量采集的人才原始线索（GitHub、公开简历数据集），`resume` 表是用户上传单份简历经结构化解析后的结果。两者数据来源、粒度、消费方式均不同，不重叠，需在后续 handoff 文档中向 E 明确说明，避免误读为可直接复用。

## 9. 自审

- **无 TBD/占位**：所有新增字段、函数签名、表结构均已具体化到字段级
- **一致性**：`talent_raw` 字段结构与 `jd_pool` 对齐；`RawTalent` 命名风格与 `RawJD` 对齐；Pipeline 路由方式与 Fetcher 抽象契约一致
- **范围检查**：本设计聚焦接口规范（数据契约、模块边界、扩展方式），不规定具体清洗/去重/采集算法实现，符合"五人协作、各自实现细节、统一接口"的项目实际情况
- **歧义检查**：`identity_hint` 明确排除身份确认含义；`talent_raw` 与 `resume` 表边界已在第 8 节明确区分

## 10. 未决问题（留待下一阶段设计）

以下问题在本轮讨论中已识别但未展开，建议作为下一阶段设计的起点：

1. **调度/自动化触发方式**：`talent_raw` 与 `jd_pool` 的定期采集如何调度（是否复用 Plan A 提及的 APScheduler，采集频率如何设定），本文档尚未涉及。
2. **人才实体消歧（Entity Resolution）**：同一人才可能来自多个来源（简历数据集 + GitHub），如何判断是否为同一人，本设计仅预留 `identity_hint` 字段，具体消歧逻辑不在本模块范围（属于下游 Entity/Event 层）。
3. **`github.py` 等现有 Fetcher 骨架的返回类型迁移**：现有 `fetchers/github.py` 骨架尚未实现真实抓取逻辑，迁移为产出 `RawTalent` 需在具体实现时处理，本设计只定契约方向。
4. **`skills_hint` 与 `skill_dict` 的对接细节**：技能线索如何在下游被归一到 `skill_dict.canonical`，属于角色 C 的职责，本设计仅保证字段可用、不做归一。
