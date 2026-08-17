# M1 采集模块（backend/app/collect/）

> 多源数据采集（D39/D40）：岗位 JD + 信号数据 → MySQL 原始层（jd_pool / signal / talent_raw）。
> 合规红线：只抓公开数据、遵守 robots.txt、不绕过登录/验证码、不伪造 source（D17/D38）。

## 一、数据源与产出

| 来源 | 类型 | 产出表 | 实现 | 状态 |
|---|---|---|---|---|
| LinkedIn postings.csv（本地数据集） | 岗位 JD | jd_pool（source=linkedin） | `fetchers/dataset.py` + `import_csv.py` | ✅ 5000 行 |
| HN "Who is hiring"（Algolia 公开 API） | 技术岗 JD | jd_pool（source=hn） | `fetchers/hn_hiring.py` + `fetch_hn_jobs.py` | ✅ 239 行（2026-08） |
| GitHub Trending（公开页面） | 信号 | signal（source=github） | `fetchers/trending.py` | ✅ 语言热度 |
| 技术博客 RSS（InfoQ/掘金；OSCHINA 403 待换源） | 信号 | signal（source=blog） | `fetchers/blog_rss.py` | ✅ 技能提及 |
| GitHub Trending 贡献者 → 人才线索 | 人才 | talent_raw（source=github） | `fetchers/github.py`（保留） | 按需 |
| 中文招聘平台（Boss/拉勾/猎聘/智联） | 岗位 JD | — | — | ⛔ robots 禁止/反爬，**不抓**（D40） |

## 二、常用命令（均在 `backend/` 下，需 venv）

```powershell
# 全部采集（信号 + HN 岗位）——推荐入口
.\.venv\Scripts\python.exe -m app.collect.fetch_all

# 单独采集信号（GitHub Trending + 博客 RSS）
.\.venv\Scripts\python.exe -m app.collect.fetch_signals --sources github,blog

# 单独采集 HN 岗位
.\.venv\Scripts\python.exe -m app.collect.fetch_hn_jobs --limit 50

# LinkedIn CSV 导入（本地数据集）
.\.venv\Scripts\python.exe -m app.collect.import_csv --csv ..\docs\originalfile\archive\postings.csv --limit 5000
```

## 三、幂等与增量

- `fetch_signals` / `fetch_hn_jobs`：**当日同 source 先清后写**，重复执行不产生重复行（按 `DATE(crawled_at)` / `DATE(captured_at)`）；
- 时间序列：每日跑一次 `fetch_all` → signal/jd_pool 形成多日快照，供 M2 evolution 趋势使用；
- LinkedIn CSV 导入为**追加**模式，扩量前需确认去重策略（dup_group）。

## 四、字段语义（D38/D39）

- `jd_pool.source`：来源平台（linkedin / hn；中文平台接入后扩展），仅记录平台（D17）；
- `jd_pool.source_detail`：来源细节（posting_domain / HN item URL / 数据集标识）；
- `signal.source`：github / blog / …（D39 新增列）；
- 技能匹配严格限定 `backend/app/skills/skill_dict_seed.json`（285 canonical + aliases），不自由命名（反幻觉）。

## 五、测试

- `backend/tests/test_signal_fetchers.py`、`test_hn_hiring.py`：纯函数单测（mock，不联网不写库）；
- `test_collect_integration.py` / `test_talent_pipeline_integration.py`：管道集成（D37 精确清理）；
- 全量：`cd backend; .\.venv\Scripts\python.exe -m pytest -q`（205+ 基线）。

## 六、设计参考（crawl4ai 评估，2026-08-17）

- 评估结论：**不引入 crawl4ai 依赖**（当前数据源均静态/API/XML，无需 JS 渲染；其 stealth 反检测不改变合规红线；引入需 Playwright/Chromium 重型依赖）；
- 可借鉴设计：内容清洗策略（fit-markdown 噪声过滤 → 已由 cleaner `_strip_noise`/`_fix_fused_prefix`/`_extract_duties` 覆盖）；缓存与幂等（已由当日先清后写覆盖）；
- 若未来出现"robots 允许但需 JS 渲染"的合规源，再评估 Playwright 直连（无需 crawl4ai）。