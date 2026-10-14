# 岗位数据使用说明(新一代 / 现有)

> M2 模块 · 2026-09-01 生成(中英同岗位已合并版)

## 文件说明

| 文件 | 内容 |
|---|---|
| `新一代岗位_定义.json` | **344 个新一代岗位**(萌芽/兴起中),字段:job_name 中文名、name_en 英文 canonical、core_duties 核心职责、required_skills 必备技能、bonus_skills 加分技能、scenarios 典型行业应用场景、source 数据源、evolution 演化阶段、first_seen/collected_at 时间、source_jd_count |
| `现有岗位_定义.json` | **375 个现有岗位**(成熟/衰退),字段同上 |
| `新一代/现有岗位_技能.json` | 技能详情:每条技能带 evidence(JD 原文逐字引用)、verification(双模型验证)、canonical_name(英文 canonical) |
| `现有岗位_能力更新日志.json` | **243 条变化记录**:技能新增/场景/职责/演化阶段/新增岗位,每条带 reason、source 数据源、created_at 检测时间、source_jd_time 证据数据时间 |
| `岗位分类清单.md` | 719 个岗位分类依据表,最后一栏留空供人工复核(category_review=merged_cn_en 的是中英合并组) |

## 分类口径(市场成熟度)

- **新一代** = evolution.stage ∈ {emerging, growth}:萌芽/尚未标准化/兴起中的岗位
- **现有** = evolution.stage ∈ {mature, declining}:市场已标准化的成熟岗位(如 Java 开发工程师)

## 中英同岗位合并

同名岗位(中文名译英文 canonical 后归一化匹配)已合并为一条,如:
数据分析师 ↔ Data Analyst(JD 数 7,来源 boss+linkedin)、后端工程师 ↔ Backend Engineer(11 条 JD、4 平台)。
合并规则:技能并集、来源并集、JD 数相加、演化阶段取更成熟侧。

## 接口调用(页面取数)

```bash
cd jd-filter-package
uvicorn api:app --host 0.0.0.0 --port 8000
```

| 端点 | 返回 |
|---|---|
| `GET /api/jobs?category=新一代` | 岗位定义列表(category 可省略=全部) |
| `GET /api/jobs/{job_id}` | 单岗位详情 |
| `GET /api/skills/{job_id}` | 技能详情(含证据) |
| `GET /api/changes?since=2026-09-01` | 变化日志(按时间过滤) |
| `GET /api/categories` | 分类汇总 |

## 队友新数据接入(增量更新)

```bash
cd jd-filter-package
python scripts/incremental_update.py <新全量快照.sql>
```

自动:只处理新增/变化 JD → 中英同岗位合并 → 新增岗位自动分类 → 变化日志
(带双重时间 + 证据)→ 接口数据实时更新。

## 数据来源

- 英文池:LinkedIn 5000 + Hacker News 1796 筛选(M2交付包 470 岗)
- 中文池:BOSS 直聘 / 前程无忧 / 猎聘(boss 379 + zhaopin 365 + liepin 256 抽样)
- 时间演化测试集:`时间演化测试集/` 子目录,150 岗位 × 3 版本,演示赛题②动态更新
