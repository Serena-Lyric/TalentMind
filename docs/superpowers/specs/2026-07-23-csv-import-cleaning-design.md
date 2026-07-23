# CSV 公开数据集导入与中洗管道设计

- **日期**: 2026-07-23
- **关联计划**: Plan A — 数据采集（`docs/superpowers/plans/2026-07-20-planA-data-collection.md`）
- **定位**: Plan A Task 1 + Task 3 的扩展实现设计，不改变 planA 任务结构
- **决策依据**: 种子数据快速解锁下游（Q2-A），中洗深度（B），全量导入

## 1. 背景与约束

### 1.1 数据源

LinkedIn 公开数据集，位于 `docs/originalfile/archive/`：

```
archive/
  postings.csv              ← 3,383,602 行，30 列，核心 JD 表
  companies/
    companies.csv            ← 公司信息
    company_industries.csv   ← 公司-行业关联
    company_specialities.csv ← 公司专长
    employee_counts.csv      ← 员工规模
  jobs/
    benefits.csv             ← 福利信息
    job_industries.csv       ← 岗位-行业关联
    job_skills.csv           ← 岗位-技能关联（skill_abr 外键）
    salaries.csv             ← 薪资明细
  mappings/
    industries.csv           ← industry_id → industry_name
    skills.csv               ← skill_abr → skill_name（36 条映射）
```

### 1.2 postings.csv 关键字段质量（前 500 行抽样）

| 字段 | 填充率 | 质量 |
|------|--------|------|
| `title` | 100% | ✅ 干净，直接映射 `job_title` |
| `description` | 100% | ❌ 信息杂烩：JD正文 + 薪资行 + 福利行 + 工时行 + 经验行 + 地点行 |
| `formatted_experience_level` | 7.4% | ❌ 几乎全空，不可作为 `experience` 主来源 |
| `skills_desc` | 2.0% | ❌ 几乎全空，技能在 `jobs/job_skills.csv` 中 |
| `formatted_work_type` | 100% | ✅ Full-time / Part-time 等 |
| `location` | 100% | ✅ "City, ST" 格式 |

### 1.3 description 典型杂烩结构

```
"Job descriptionA leading real estate firm...          ← JD 正文（"Job description" 无空格粘连）
Pay: $18-20/hour                                        ← 薪资行
Expected hours: 35 – 45 per week                        ← 工时行
Benefits:Paid time offSchedule:8 hour shift...           ← 福利行（无分隔符粘连）
Experience:Marketing: 1 year (Preferred)                 ← 经验行
Work Location: In person"                                ← 地点行
```

### 1.4 协作约束

- A 的 MySQL 为主库，只存阶段 2 真实爬取数据，**不存公开数据集**
- C 的 MySQL 需要种子数据做开发，通过 `jd_pool` 表消费
- C 不写文件读取逻辑，代码连 MySQL 不变
- 合并日：C 代码连 A 的 MySQL，A 库有真实数据
- **CSV 导入代码进 git；原始 CSV 文件不入 git（太大），通过 U 盘/网盘传输**

## 2. 数据流设计

```
postings.csv (338万行)
  + jobs/job_skills.csv
  + mappings/skills.csv
         │
         ▼
  load_csv()           ─── csv.DictReader 逐行读取
         │                  对 description 中的多行字段自动处理
         │                  产出 RawJD（扩展 raw_skills 可选字段）
         │
         ▼
  clean()              ─── 中洗：信息分离
         │                  ├── 剥离薪资/福利/工时/地点等杂讯行
         │                  ├── 去除粘连前缀（"Job description"）
         │                  ├── 识别并提取职责段落 → duties
         │                  ├── 提取经验 → experience（列优先，正则回退）
         │                  └── 剩余正文 → raw_text
         │
         ▼
  enrich_skills()      ─── join job_skills.csv + mappings/skills.csv
         │                  将技能名追加到 raw_text 尾部
         │                  （不新增 jd_pool 列，避免改契约）
         │
         ▼
  dedup / quality      ─── planA Task 2，与设计完全一致
         │
         ▼
  save_rows()          ─── planA Task 4，批量 INSERT jd_pool
         │                  status = 'cleaned'
         ▼
      jd_pool
```

## 3. 字段映射表

| jd_pool 列 | 来源 | 提取策略 | 空值处理 |
|------------|------|---------|---------|
| `source` | 硬编码 | `"dataset"` | 永不为空 |
| `job_title` | CSV `title` | `.strip()` | 为空时跳过该行 |
| `raw_text` | CSV `description` | 剥离杂讯行后的纯 JD 正文 | 空则留空 |
| `duties` | CSV `description` | 正则匹配职责段标题，截取至下一标题或末尾 | 未识别则留空 |
| `experience` | CSV `formatted_experience_level` → description 回退 | 列有值直接用；空时正则提取 `Experience:` 行 | 均无则留空 |
| `quality` | 管道计算 | `quality_score(row, group_size)`，不变 | 0.0 |
| `dup_group` | 管道计算 | `text_signature(raw_text)`，不变 | 空文本特殊处理 |
| `crawled_at` | 导入时间 | `datetime.utcnow()` | 永不为空 |
| `status` | 硬编码 | `"cleaned"` | 永不为空 |

## 4. 中洗 clean() 详细设计

### 4.1 杂讯剥离模式（从 raw_text 中移除的行）

```python
NOISE_LINE_PATTERNS = [
    # 薪资
    r"^(Pay|Salary|Compensation|Wage)\s*:",
    r"^\$[\d,.\s]+(.+?(hour|year|month|week|annum))",
    # 工时
    r"^(Expected\s+)?[Hh]ours?\s*:",
    # 福利
    r"^(Benefits?|Perks)\s*:",
    # 排班
    r"^Schedule\s*:",
    # 地点（description 内重复）
    r"^(Work\s+)?[Ll]ocation\s*:",
    # 工作类型
    r"^Job\s+[Tt]ype\s*:",
    # 薪资范围（数字格式）
    r"^\$[\d,.]+\s*[-–to]+\s*\$?[\d,.]+",
    # 纯 URL
    r"^https?://\S+",
]
```

### 4.2 粘连前缀修复

```python
FUSED_PREFIXES = [
    "Job description",       # "Job descriptionA leading..." → "A leading..."
    "Job Description",
    "Job Summary",
    "Job summary",
    "About the job",
    "About this job",
]
```

匹配规则：行首出现上述前缀且后接非空白字符（即粘连），删除前缀部分。

### 4.3 职责段落识别

```python
DUTY_HEADER_PATTERNS = [
    r"(?i)(?:^|\n)(?:Key\s+)?Responsibilities?(?:\s*:|\s*\n)",   # Responsibilities: / Key Responsibilities:
    r"(?i)(?:^|\n)Essential\s+Functions?(?:\s*:|\s*\n)",           # Essential Functions:
    r"(?i)(?:^|\n)(?:Primary\s+)?[Dd]uties?(?:\s*:|\s*\n)",        # Job Duties: / Duties:
    r"(?i)(?:^|\n)What\s+[Yy]ou'?ll\s+[Dd]o(?:\s*:|\s*\n)",       # What You'll Do:
    r"(?i)(?:^|\n)(?:The\s+)?Role\s*:?\s*\n",                      # Role:
]
```

提取逻辑：找到第一个匹配的职责标题 → 从标题后开始截取 → 直到下一个全大写/标题行或文本末尾 → 结果 = `duties`。

### 4.4 经验提取

两阶段回退：
1. 优先：`formatted_experience_level` 列非空 → 直接使用
2. 回退：正则匹配 description 中 `Experience:` 行

```python
EXPERIENCE_LINE_PATTERN = r"(?i)Experience\s*:\s*(.+?)(?:\n|$)"
```

## 5. 技能补充设计

### 5.1 数据关系

```
postings.csv                jobs/job_skills.csv         mappings/skills.csv
┌──────────┐               ┌─────────┬───────────┐     ┌───────────┬────────────┐
│ job_id   │──────────────→│ job_id  │ skill_abr │────→│ skill_abr │ skill_name │
│ ...      │               └─────────┴───────────┘     └───────────┴────────────┘
└──────────┘
```

### 5.2 处理策略

- 在 pipeline 中增加 `enrich_skills()` 步骤
- 预先加载 `job_skills.csv` 和 `skills.csv` 到内存 dict（数据量小，36 个技能 × 百万级映射）
- 对每条 RawJD，通过 `job_id` 查找技能缩写 → 映射为技能名 → 追加到 `raw_text` 尾部：
  ```
  "\n\nSkills: Python, Project Management, Engineering, ..."
  ```
- 不新增 `jd_pool` 列（避免改契约），技能信息融入 `raw_text` 供下游抽取
- **`job_id` 仅用于 enrich_skills 阶段的 join，不写入 `jd_pool`**（jd_pool 无此列）。enrich 完成后 `job_id` 即丢弃

## 6. 代码变更清单（对 planA 的扩展）

### 6.1 修改 planA Task 1 设计

**schema.py** — RawJD 新增可选字段：

```python
@dataclass
class RawJD:
    source: str
    job_title: str
    raw_html: str              # 实际存 description 原文
    duties: str = ""
    experience: str = ""
    job_id: str = ""           # 新增：用于 join job_skills
    raw_skills: list[str] = None  # 新增：技能名列表
```

**cleaner.py** — 从中洗逻辑替换原"去 HTML"逻辑：
- `_strip_noise(text) -> str` — 剥离杂讯行 + 修复粘连前缀
- `_extract_duties(text) -> str` — 识别职责段落
- `_extract_experience(text, fallback) -> str` — 经验提取
- `clean(raw: RawJD) -> dict` — 与 planA 签名一致，内部调用上述函数

### 6.2 重写 planA Task 3 设计

**fetchers/dataset.py** — 改为 CSV 加载器：

```python
def load_csv_posting(path: str) -> list[RawJD]:
    """读 postings.csv，逐行产出 RawJD"""

def load_skill_map(skills_csv: str) -> dict[str, str]:
    """加载 skill_abr → skill_name 映射"""

def load_job_skills(job_skills_csv: str) -> dict[str, list[str]]:
    """加载 job_id → [skill_abr, ...] 映射"""
```

### 6.3 扩展 planA Task 5

**pipeline.py** — 流程中插入 `enrich_skills()`：

```python
def enrich_skills(rows: list[dict], job_skill_map: dict, skill_map: dict) -> list[dict]:
    """对每行追加技能文本到 raw_text"""

def run_pipeline(db, raws, job_skill_map=None, skill_map=None) -> dict:
    rows = [clean(r) for r in raws]
    if job_skill_map and skill_map:
        rows = enrich_skills(rows, job_skill_map, skill_map)
    rows = assign_dup_groups(rows)
    # ... 后续不变
```

### 6.4 微调部分

- Task 2（dedup.py）— 完全不变
- Task 4（repository.py）— `save_rows` 改为批量提交（1000 条/批），签名不变。原 planA 设计逐行 commit 在 338 万行场景下不可接受
- Task 6（集成测试）— 入参从 JSONL 变 CSV，其余不变

## 7. 文件结构（最终态）

```
backend/app/collect/
  __init__.py
  schema.py              ← RawJD 扩展 job_id + raw_skills
  cleaner.py             ← 中洗逻辑
  dedup.py               ← 不变（planA Task 2）
  fetchers/
    __init__.py
    base.py              ← Fetcher 抽象（不变）
    github.py            ← GitHub 采集骨架（不变）
    dataset.py           ← CSV 加载器（扩展 planA Task 3）
  repository.py          ← 不变（planA Task 4）
  pipeline.py            ← 流程中插入 enrich_skills
  import_csv.py          ← 新增：CLI 入口，供 C 使用

backend/tests/
  test_cleaner.py        ← 扩展：含真实 CSV 样本的测试
  test_dedup.py          ← 不变
  test_dataset_import.py ← 改写：CSV 替代 JSONL
  test_collect_repo.py   ← 不变
  test_pipeline.py       ← 扩展：验证技能补充
  test_collect_integration.py ← 不变（planA Task 6）
```

## 8. C 的交付物与操作

### 8.1 A → C 交付

| 交付物 | 方式 | 大小 |
|--------|------|------|
| Git 仓库（含 `app/collect/` 全部代码） | `git push` → C `git pull` | < 1MB |
| 原始 CSV 文件包 | U 盘 / 网盘 / 局域网共享 | 压缩后 ~30MB |

### 8.2 C 的操作步骤

```bash
# 1. 拿到 CSV 文件，放入本地 data/ 目录
mkdir -p data/archive
cp -r /path/to/archive/* data/archive/

# 2. 起 MySQL
docker-compose up -d --wait

# 3. 运行导入（全量 338 万行，预计 10-30 分钟）
cd backend
python -m app.collect.import_csv \
    --csv data/archive/postings.csv \
    --job-skills data/archive/jobs/job_skills.csv \
    --skills-map data/archive/mappings/skills.csv

# 4. 验证
docker exec -i $(docker-compose ps -q mysql) \
    mysql -uroot -ptalentmind talentmind \
    -e "SELECT COUNT(*) FROM jd_pool WHERE status='cleaned';"
# Expected: > 3,000,000
```

### 8.3 C 不需要做的事

- ❌ 不需要写文件读取代码
- ❌ 不需要修改任何 SQL / ORM 代码
- ❌ 不需要了解 CSV 格式细节
- ✅ 现有的 `SELECT * FROM jd_pool WHERE status='cleaned'` 直接可用

## 9. 性能考量（全量 338 万行）

| 阶段 | 预估耗时 | 内存峰值 | 备注 |
|------|---------|---------|------|
| `load_csv` | ~30s | ~50MB | csv.DictReader 是流式的 |
| `clean` | ~3-5min | ~100MB | 纯 CPU 正则，逐行处理 |
| `enrich_skills` | ~1min | ~200MB | job_skills 映射表需全量加载 |
| `dedup + quality` | ~2-3min | ~300MB | 需在内存中建签名索引 |
| `save_rows` | ~10-20min | ~50MB | 网络 IO 瓶颈，考虑 `executemany` 批量插入 |

优化措施：
- `save_rows` 使用 1000 条/批次的批量 INSERT
- 可选：全流程加 tqdm 进度条，避免"黑盒等待"感
- 可选：增加 `--limit N` 参数支持采样模式

## 10. 与 planA 任务结构的对应关系

```
planA Task 1  → 扩展 schema.py + cleaner.py（中洗逻辑）
planA Task 2  → 不变（dedup.py）
planA Task 3  → 扩展 fetchers/dataset.py（JSONL → CSV）
planA Task 4  → 不变（repository.py）
planA Task 5  → 扩展 pipeline.py（插入 enrich_skills）
planA Task 6  → 不变（集成测试）
        新增 → import_csv.py（CLI 入口）
```

本设计不创建新任务，不改变 Task 顺序，仅扩展实现细节。

## 11. 自审

- **无 TBD / TODO** — 所有模块具名、函数签名明确、正则模式具体
- **一致性** — 字段映射表与 DDL 契约一致；`status='cleaned'` 与下游 C 的查询一致
- **范围** — 仅覆盖 CSV 导入与清洗，不涉及阶段 2 真实爬虫、不涉及 signal 表
- **无歧义** — 清洗步骤有伪代码级别的正则模式；C 的操作步骤有具体命令
