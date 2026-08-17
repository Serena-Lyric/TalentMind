# 多源数据采集计划（2026-08-17）

- **状态**：已启动（P0 实施中）
- **依据**：原始 PDF 需求"多源异构数据获取"（Boss直聘/智联招聘/猎聘/牛客/拉勾/GitHub Trending/技术博客/开源社区）+ "多源异构数据清洗与交叉验证机制，解决JD滞后、噪声、抄袭问题"（创新点）；M2 数据支撑缺口诊断（技术岗占比低、单源、无时序/信号）
- **配套**：决策跟踪 D39；`backend/app/contracts/ddl.sql`（signal 加 source 列）

## 一、目标

1. 补齐"多源"：岗位数据（中文平台）+ 信号数据（GitHub/技术博客/社区）来自多个来源；
2. 支撑 M2：signal 表有数据 → is_emerging/evolution 的"信号判断"可用；多批次采集 → 时间序列；
3. 支撑"多源交叉验证质量分"：跨平台同岗位比对 → quality 从"组内重复度"升级为"跨平台一致度"；
4. 全部合规：只抓公开数据、遵守 robots、不绕过登录、限速。

## 二、数据源矩阵

| 来源 | 类别 | 产出表 | 优先级 | 合规/风险 | 状态 |
|---|---|---|---|---|---|
| GitHub Trending 页面 | 技术热度 | signal | P0 | 公开页面；限速 | **已启动（本轮）** |
| GitHub API（search/topics） | 技术热度 | signal | P0 | 需 token（.env 未配，先不做 API，页面优先） | 待启动 |
| 技术博客 RSS（InfoQ/OSCHINA/掘金等） | 技术趋势 | signal | P0 | RSS 公开；源可用性需验证 | **已启动（本轮）** |
| 拉勾 | 中文岗位 | jd_pool | P1 | 反爬中等；评估公开搜索页 | 待评估 |
| Boss直聘 | 中文岗位 | jd_pool | P1 | 反爬强；评估 | 待评估 |
| 智联招聘 / 猎聘 / 牛客 | 中文岗位 | jd_pool | P1 | 反爬强；评估 | 待评估 |
| 开源社区（Gitee 等） | 技术热度 | signal | P2 | 公开 API | 待定 |

## 三、架构（复用现有 collect 框架）

```
fetchers/  (base.py 抽象)
├─ trending.py    GitHub Trending 页面 → 语言/主题热度 → signal
├─ blog_rss.py    技术博客 RSS → 技能/主题提及 → signal
└─ github.py      已有（人才信号 → talent_raw，保留）
pipeline / repository：
└─ save_signals()  signal 表写入（signal 新增 source 列，D39）
CLI：python -m app.collect.fetch_signals --sources github,blog [--limit N]
```

- signal 表字段：`skill_or_job`（技能/主题/语言）、`signal_type`（tech_trend）、`metric`（mention_count/repo_count/rank）、`value`（FLOAT）、`captured_at`、**`source`**（github/blog/…，D39 新增列）
- 技能匹配：复用 `backend/app/skills/skill_dict_seed.json`（285 canonical + aliases），RSS 文本按 canonical/alias 匹配计数 → 直接对齐 M2/M3 技能词表（不自由命名）
- 去重：同一来源同一天同一 key 只保留一条（INSERT 前按 skill_or_job+source+metric+日期去重）

## 四、分阶段执行

### P0（2026-08-17 当周）：信号数据源
- [x] DDL：`signal` 表新增 `source VARCHAR(32)`；DB ALTER
- [x] `fetchers/trending.py`：解析 GitHub Trending（python/java/go/javascript/typescript/rust，since=daily）→ 语言 repo_count（**新版页面已无 topic 标签**，主题 mention_count 自然为空）
- [x] `fetchers/blog_rss.py`：RSS 源列表（InfoQ/掘金可用；OSCHINA 403 待换源）→ 标题+描述按 skill_dict 匹配计数
- [x] `repository.save_signals` + CLI `fetch_signals.py`
- [x] 单测（mock 响应，无网络）；跑通一次 → signal 入库（github 6 + blog 16，2026-08-17）
- [x] 文档同步（决策 D39、资产状态、笔记、README）

**P0 结果（2026-08-17）**：signal 表 22 条 = github（6 语言 repo_count）+ blog（16 技能 mention_count，中文正常 UTF-8）。`python -m app.collect.fetch_signals` 可重复执行（当日同 source 先清后写，幂等）。

### P1（下周，8/18-22）：中文平台岗位
- 评估拉勾/Boss 公开搜索页反爬强度 → 选 1 个先落地（搜索词=新一代信息技术关键词）
- fetcher：搜索页 → RawJD（source=boss/zhilian/liepin/lagou/nowcoder）→ 现有 pipeline（clean/dedup/quality）→ jd_pool
- source_detail 记页面 URL/账号；遵守 robots/限速 1 请求/2s
- 产出：jd_pool 中英文混合多源

### P2（后续）：交叉验证质量分
- 跨平台同岗位（title 归一 + 技能 Jaccard）比对 → quality 融合多平台一致度
- 多批次时间序列 → evolution 趋势真实化

## 五、验证门禁

1. signal 表行数 > 0，且 source ∈ {github, blog}；
2. 样例：skill_or_job 属于 skill_dict canonical 或合理语言/主题；
3. 198 测试通过（新增 signal fetcher 单测）；
4. D37：任何测试不残留。

## 六、风险

| 风险 | 对策 |
|---|---|
| GitHub 无 token 限流（API 60 次/h） | P0 用 Trending 页面（无需 token）；API 后续再配 token |
| RSS 源失效/改版 | 源列表可配置，失败跳过并打印告警 |
| 中文平台反爬 | P1 先做可行性评估；只抓公开页、限速、不绕登录 |
| 技能匹配噪声 | 仅匹配 skill_dict canonical/alias（严格词表，反幻觉） |
| 数据量/成本 | signal 为轻量计数，无 LLM 成本 |

## 七、不在范围

- 不采集需登录/付费/验证码的私有数据；
- 不伪造 source（D17/D38 语义不变）；
- 不重写现有 github.py 人才采集（保留）；
- 真实简历不涉及。