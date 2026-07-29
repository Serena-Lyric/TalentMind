# GitHub Fetcher 实现设计

- **日期**: 2026-07-29
- **定位**: 落地 `2026-07-29-talent-knowledge-acquisition-workflow-design.md` 第 10 节未决问题 3——将 `backend/app/collect/fetchers/github.py` 从空骨架实现为真实抓取，产出 `RawTalent`
- **前置依赖**: Task 1-5（`RawTalent`/`talent_cleaner.py`/`talent_raw` 表/pipeline 路由）已全部完成并验证通过，本设计是这条双轨管道的第一个真实数据源

## 1. 背景

`talent_raw` 链路目前只有集成测试手写的 `RawTalent` 样例数据流过，没有任何真实 `Fetcher` 产出过数据。`fetchers/github.py` 里的 `GithubTrendingFetcher` 是最早 Plan A 留下的骨架：

```python
class GithubTrendingFetcher(Fetcher):
    def fetch(self) -> list[RawJD]:
        return []
```

设计文档把 GitHub 明确归为 **Talent Sources**（人才侧数据源），本设计要让它真正产出 `RawTalent`，让双轨管道的人才侧第一次跑通真实数据。

## 2. 数据流

```
GitHub Trending 页面（按技术语言列表遍历：Python/Java/Go/JavaScript/TypeScript）
    ↓ BeautifulSoup 解析 HTML
仓库列表 [(owner, repo), ...]（固定上限 N=25 个，跨语言去重）
    ↓ REST API: GET /repos/{owner}/{repo}/contributors
Contributor 用户名列表（每仓库固定上限 M=5 个，全局去重）
    ↓ REST API: GET /users/{username} + GET /users/{username}/repos
RawTalent(
    source="github",
    raw_text=bio + 该用户公开仓库描述拼接,
    identity_hint=username,
    skills_hint=该用户仓库语言去重列表,
    experience_hint="",
)
```

## 3. 关键设计决策

### 3.1 抓取入口：GitHub Trending 页面（已确认）

不用 GitHub Search API 主动搜索用户，而是从 Trending 榜单反向拿到活跃仓库、再拿贡献者。理由：Trending 直接对应"当前热门技术项目"，产出的人才样本天然带有"活跃于热门技术方向"的信号，比盲目搜索更贴近设计文档里"技术人才增强"的定位。

### 3.2 人才提取策略：拉取 contributors 列表（已确认）

不只取仓库 owner（owner 可能是组织账号、且同一热门仓库只产出一人），改为对每个仓库调用 `GET /repos/{owner}/{repo}/contributors`，取前 M 个贡献者。能拿到的人才样本数量更多，但每个仓库多消耗一次 API 调用。

### 3.3 认证：需要 GitHub Token（已确认）

未认证请求限额 60 次/小时，Trending（跨 5 个语言）+ 每仓库 contributors + 每贡献者 profile+repos 的请求量会迅速超限。新增可选配置项：

```python
# backend/app/config.py 新增字段
github_token: str = ""  # 可选，未配置时退化为匿名请求
```

```
# backend/.env.example 追加一行
GITHUB_TOKEN=
```

未配置 `github_token` 时,请求头不带 `Authorization`，退化为匿名请求（限额 60/小时，仍可运行，只是抓得少）。

### 3.4 抓取规模：固定上限（已确认）

- Trending 语言列表：`["python", "java", "go", "javascript", "typescript"]`（硬编码在 `github.py` 顶部常量，不做成配置项——这是抓取范围的业务决策，不是运行环境差异，YAGNI）
- 每语言 Trending 页取前若干仓库，全部语言汇总后跨语言去重，总数固定上限 `MAX_REPOS = 25`
- 每仓库取前 `MAX_CONTRIBUTORS_PER_REPO = 5` 个贡献者，全局按用户名去重

### 3.5 字段映射：profile + repos 语言（已确认）

`RawTalent` 四个字段的来源：

| 字段 | 来源 | 说明 |
|---|---|---|
| `source` | 硬编码 | `"github"` |
| `raw_text` | `GET /users/{username}` 的 `bio` 字段 + 该用户 `GET /users/{username}/repos` 返回的仓库 `description` 拼接 | bio 可能为 `null`，拼接时跳过空值 |
| `identity_hint` | `GET /users/{username}` 的 `login` 字段 | 即 GitHub 用户名，弱标识，不做身份确认 |
| `skills_hint` | 该用户所有公开仓库的 `language` 字段去重列表 | 排除 `null`（无主语言的仓库） |
| `experience_hint` | 固定为 `""` | GitHub API 不提供结构化工作经历，强行拼字段没有意义 |

### 3.6 限额用尽处理：优雅降级（已确认）

请求命中限流响应（HTTP 403 且响应头 `X-RateLimit-Remaining: 0`，或 HTTP 429）时，停止后续请求，把已经拿到的部分结果正常通过 `fetch()` 返回，不抛异常。这与现有骨架"拿不到就返回空列表"的宽容风格一致，也符合 `Fetcher` 抽象没有定义任何异常契约的现状。

### 3.7 代码组织：方案 B——单文件内拆分职责（已确认）

不新建文件，在 `github.py` 内部拆两个职责清晰的部分：

```python
# HTML 解析部分（Trending 页面 → 仓库列表）
def _fetch_trending_repos(client: httpx.Client, language: str) -> list[tuple[str, str]]:
    """解析 GitHub Trending 页面（指定语言），返回 [(owner, repo), ...]"""

# REST API 调用部分（仓库/用户 → 结构化数据）
def _fetch_contributors(client: httpx.Client, owner: str, repo: str, token: str) -> list[str]:
    """调用 contributors API，返回用户名列表"""

def _fetch_user_profile(client: httpx.Client, username: str, token: str) -> dict:
    """调用 users API + users/repos API，返回 {"bio", "repo_descriptions", "languages"}"""

class GithubTrendingFetcher(Fetcher):
    def fetch(self) -> list[RawTalent]:
        """编排：按语言遍历 Trending → 去重仓库 → 抓 contributors → 抓 profile → 拼成 RawTalent"""
```

`GithubTrendingFetcher.fetch()` 只负责编排调用顺序和错误降级，不直接写 HTML 解析或 API 调用细节。这符合 CLAUDE.md「函数/组件保持单一职责」的要求——网页解析（会因 GitHub 改版而失败）和 REST API 调用（会因限流而失败）是两种完全不同的失败模式，拆开后各自可以独立测试、独立替换。

### 3.8 HTML 解析方式：引入 BeautifulSoup（已确认）

新增依赖 `beautifulsoup4==4.12.3`（与 `2026-07-20-planA-data-collection.md` 原文档中记录的版本一致，该依赖此前从未真正写入 `requirements.txt`，本次补上）。理由：GitHub Trending 页面结构变化时，正则表达式会静默失败（拿到空列表但不报错），而 BeautifulSoup 按 CSS 选择器/DOM 结构解析更稳定，且现有 `cleaner.py` 的正则方案是针对"清洗已抽取的纯文本"设计的，不适合"从结构化 HTML 中定位特定元素"这个不同的任务。

### 3.9 `Fetcher` 抽象签名更新

`base.py` 当前签名：

```python
class Fetcher(ABC):
    @abstractmethod
    def fetch(self) -> list[RawJD]:
        ...
```

更新为：

```python
from app.collect.schema import RawJD, RawTalent

class Fetcher(ABC):
    @abstractmethod
    def fetch(self) -> list[RawJD] | list[RawTalent]:
        ...
```

这不是行为变更，只是让类型标注追上设计文档 Q8 已经确认的事实——`Fetcher.fetch()` 的返回类型本身就是 pipeline 的路由依据，`RawTalent` 早已存在（Task 1），只是这个抽象签名此前一直没跟上。`github.py` 里 `GithubTrendingFetcher.fetch()` 的类型标注同步从 `list[RawJD]` 改为 `list[RawTalent]`。

## 4. 不做的事（保持范围聚焦）

- **不做代理池/随机延迟/断点续爬**——这些是 `2026-07-20-talentmind-系统架构-design-v2.md` 中"真实爬取"阶段的特性（角色 A 职责的一部分），本设计的目标只是把骨架变成一次调用能拿到真实数据的最小实现，不是生产级反爬对抗
- **不做调度（APScheduler）**——本设计只保证 `fetch()` 单次调用产出真实数据；定时触发属于设计文档第 10 节未决问题 1，是独立主题
- **不做人才实体消歧**——`identity_hint` 只是 GitHub 用户名字符串，不做任何身份判断或跨来源合并，交给下游 Entity/Event 层（设计文档第 10 节未决问题 2 已明确排除在本模块职责外）
- **不引入 Playwright**——Trending 页面是服务端渲染的静态 HTML，不需要浏览器自动化；`requirements.txt` 中虽然 Plan A 早期文档提过 `playwright`，但本设计的抓取目标不需要它

## 5. 测试策略

- **HTML 解析函数（`_fetch_trending_repos`）**：用真实 GitHub Trending 页面的 HTML 片段样例（截取自本设计撰写时的实际页面结构，硬编码为测试 fixture 字符串）驱动单测,不依赖网络
- **API 调用函数（`_fetch_contributors`/`_fetch_user_profile`）**：mock `httpx.Client`，构造模拟 JSON 响应,覆盖正常返回和限流响应（403/429）两种场景
- **`GithubTrendingFetcher.fetch()` 编排逻辑**：mock 上述三个函数的返回值，验证编排顺序、去重逻辑、限额降级后的部分结果返回行为
- **真实网络调用**：不在自动化测试范围内，留给手动集成验证（需要真实 `GITHUB_TOKEN`）

## 6. 自审

- **无 TBD/占位**：抓取入口、人才提取策略、认证方式、抓取规模、字段映射、限额降级、代码组织、HTML 解析方式均已具体到实现层面的函数签名和常量值
- **一致性**：字段映射（3.5 节）与 `RawTalent` dataclass（`schema.py`，Task 1 已实现）字段一一对应；代码组织（3.7 节）与现有 `fetchers/` 目录"一个数据源一个文件"模式一致
- **范围检查**：仅覆盖 `github.py` 的真实实现与 `Fetcher` 抽象签名更新，不涉及调度、实体消歧、代理池——这些已被第 4 节明确排除并注明原因
- **歧义检查**：`experience_hint` 固定为空字符串的理由已说明（GitHub 不提供结构化经历数据）；限额降级的判定条件（403+`X-RateLimit-Remaining:0` 或 429）已明确,不是含糊的"检测到限流"
