# GitHub Fetcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `backend/app/collect/fetchers/github.py` 里的空骨架 `GithubTrendingFetcher` 实现为真实抓取——从 GitHub Trending 页面找热门仓库，拉取贡献者，再抓每个贡献者的 profile/repos 语言，产出 `RawTalent` 列表,接入已完成的双轨采集管道。

**Architecture:** 单文件内拆分三层职责（`github.py`）：HTML 解析层（`_fetch_trending_repos`,BeautifulSoup 解析 Trending 页）→ REST API 层（`_fetch_contributors`/`_fetch_user_profile`,调用 GitHub REST API,内部检测限流并以私有异常 `_GithubRateLimited` 向上传递信号）→ 编排层（`GithubTrendingFetcher.fetch()`,按语言遍历、去重、捕获限流异常做优雅降级、拼装 `RawTalent`）。`Fetcher` 抽象签名同步更新以反映 `RawTalent` 已是合法返回类型。

**Tech Stack:** Python 3.11, httpx(mock 测试), BeautifulSoup4, pytest, pydantic-settings

**依赖设计文档:** `docs/superpowers/specs/2026-07-29-github-fetcher-design.md`（已经用户审阅确认,第 2-3 节的数据流与决策是本计划的直接依据）

## Global Constraints

- Trending 语言列表固定：`["python", "java", "go", "javascript", "typescript"]`，硬编码在 `github.py` 顶部,不做成配置项
- 仓库抓取总数固定上限 `MAX_REPOS = 25`（跨语言去重后的总数）
- 每仓库贡献者固定上限 `MAX_CONTRIBUTORS_PER_REPO = 5`（全局按用户名去重）
- `experience_hint` 永远填 `""`（GitHub API 不提供结构化经历数据,不强行拼字段）
- 限流判定条件：HTTP 429，或 HTTP 403 且响应头 `X-RateLimit-Remaining` 等于字符串 `"0"`
- 命中限流时停止后续请求,把已获取的部分结果正常返回,不向 `Fetcher.fetch()` 的调用方抛异常
- 不做代理池/随机延迟/断点续爬/APScheduler 调度/人才实体消歧/Playwright——均在设计文档第 4 节明确排除
- 新增依赖版本精确锁定：`beautifulsoup4==4.12.3`
- `github_token` 为可选配置,未设置时默认空字符串,请求退化为不带 `Authorization` 头的匿名请求
- 测试策略：HTML 解析用 fixture 字符串驱动(不联网)；REST API 调用 mock httpx.Client；编排逻辑 mock 三个底层函数验证去重/限流降级；真实网络调用不进自动化测试

---

## 文件结构（本计划新增/修改）

```
backend/
  requirements.txt              # 修改：追加 beautifulsoup4==4.12.3
  .env.example                   # 修改：追加 GITHUB_TOKEN=
  app/
    config.py                    # 修改：Settings 新增 github_token: str = ""
    collect/
      fetchers/
        base.py                  # 修改：Fetcher.fetch() 签名 list[RawJD] -> list[RawJD] | list[RawTalent]
        github.py                 # 修改：从空骨架实现为真实抓取（本计划核心）
  tests/
    test_config.py                # 修改：追加 github_token 相关测试
    test_github_fetcher.py         # 新建：HTML解析 + REST API + 编排逻辑测试
```

---

## Task 1: `github_token` 配置项

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: 无（`Settings` 是纯 Pydantic 模型)
- Produces: `Settings.github_token: str`（默认 `""`）——供 Task 5 的 `GithubTrendingFetcher.__init__` 消费

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_config.py` 文件末尾追加：

```python
def test_settings_github_token_defaults_to_empty(monkeypatch):
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@h:3306/db")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.github_token == ""


def test_settings_github_token_reads_env(monkeypatch):
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@h:3306/db")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    get_settings.cache_clear()
    s = get_settings()
    assert s.github_token == "ghp_test123"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_config.py -v -k github_token`
Expected: FAIL，`pydantic_core._pydantic_core.ValidationError` 或 `AttributeError: 'Settings' object has no attribute 'github_token'`（视 Pydantic 报错方式，核心是 `github_token` 字段不存在）

- [ ] **Step 3: 在 Settings 中新增字段**

把 `backend/app/config.py` 中的：

```python
    openai_base_url: str = "https://api.openai.com/v1"
```

替换为：

```python
    openai_base_url: str = "https://api.openai.com/v1"
    github_token: str = ""
```

- [ ] **Step 4: 在 .env.example 追加说明行**

在 `backend/.env.example` 文件末尾追加：

```
GITHUB_TOKEN=
```

- [ ] **Step 5: 运行验证通过**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: PASS（3 passed：既有 `test_settings_reads_env` + 本任务新增 2 个）

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/.env.example backend/tests/test_config.py
git commit -m "feat(A): add optional github_token setting"
```

---

## Task 2: `Fetcher` 抽象签名更新

**Files:**
- Modify: `backend/app/collect/fetchers/base.py`

**Interfaces:**
- Consumes: `RawJD`、`RawTalent`（`schema.py`，均已存在）
- Produces: `Fetcher.fetch() -> list[RawJD] | list[RawTalent]`——供 Task 5 的 `GithubTrendingFetcher` 声明返回 `list[RawTalent]` 时类型一致

这是纯类型标注变更，不影响运行时行为（Python 不在运行时强制检查返回类型标注），因此本任务用现有测试套件的全量回归作为验证手段，不新增测试文件。

- [ ] **Step 1: 修改 base.py**

用以下内容完整替换 `backend/app/collect/fetchers/base.py`：

```python
from abc import ABC, abstractmethod
from app.collect.schema import RawJD, RawTalent


class Fetcher(ABC):
    """采集器抽象。实现类负责代理池/随机延迟/断点续爬。"""
    @abstractmethod
    def fetch(self) -> list[RawJD] | list[RawTalent]:
        ...
```

- [ ] **Step 2: 运行全量回归确认未破坏现有代码**

Run: `cd backend && pytest -v -m "not integration"`
Expected: 全部 PASS（既有测试数量不变。当前代码库中唯一实现 `Fetcher` 的类是 `GithubTrendingFetcher` 本身,`fetchers/dataset.py` 是独立的加载函数,不实现 `Fetcher` 接口,因此本次签名收紧不影响任何其他代码）

- [ ] **Step 3: Commit**

```bash
git add backend/app/collect/fetchers/base.py
git commit -m "feat(A): widen Fetcher.fetch() return type to include RawTalent"
```

---

## Task 3: HTML 解析层 `_fetch_trending_repos` + `beautifulsoup4` 依赖

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/collect/fetchers/github.py`（从空骨架整体替换）
- Test: `backend/tests/test_github_fetcher.py`（新建）

**Interfaces:**
- Consumes: `httpx.Client`（调用方传入或默认构造）
- Produces: `_fetch_trending_repos(client: httpx.Client, language: str) -> list[tuple[str, str]]`——供 Task 5 的 `GithubTrendingFetcher.fetch()` 编排逻辑消费；也导出模块级常量 `LANGUAGES: list[str]`、`MAX_REPOS: int`、`MAX_CONTRIBUTORS_PER_REPO: int` 供 Task 4/5 使用

- [ ] **Step 1: 追加依赖**

在 `backend/requirements.txt` 文件末尾追加一行：

```
beautifulsoup4==4.12.3
```

安装依赖：

Run: `cd backend && pip install beautifulsoup4==4.12.3`
Expected: 安装成功,无报错

- [ ] **Step 2: 写失败测试**

```python
# backend/tests/test_github_fetcher.py
from unittest.mock import MagicMock
from app.collect.fetchers.github import _fetch_trending_repos

TRENDING_HTML_FIXTURE = """
<html><body>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/octocat/Hello-World">
      <span class="text-normal">octocat /</span>
      Hello-World
    </a>
  </h2>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/torvalds/linux">
      <span class="text-normal">torvalds /</span>
      linux
    </a>
  </h2>
</article>
</body></html>
"""


def test_fetch_trending_repos_parses_owner_and_repo():
    client = MagicMock()
    client.get.return_value = MagicMock(status_code=200, text=TRENDING_HTML_FIXTURE)
    repos = _fetch_trending_repos(client, "python")
    assert repos == [("octocat", "Hello-World"), ("torvalds", "linux")]


def test_fetch_trending_repos_returns_empty_on_non_200():
    client = MagicMock()
    client.get.return_value = MagicMock(status_code=500, text="")
    repos = _fetch_trending_repos(client, "python")
    assert repos == []


def test_fetch_trending_repos_skips_malformed_links():
    html = """
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/onlyowner">onlyowner</a>
      </h2>
    </article>
    """
    client = MagicMock()
    client.get.return_value = MagicMock(status_code=200, text=html)
    repos = _fetch_trending_repos(client, "python")
    assert repos == []


def test_fetch_trending_repos_requests_correct_language_url():
    client = MagicMock()
    client.get.return_value = MagicMock(status_code=200, text="<html></html>")
    _fetch_trending_repos(client, "java")
    client.get.assert_called_once_with("https://github.com/trending/java", params={"since": "daily"})
```

- [ ] **Step 3: 运行验证失败**

Run: `cd backend && pytest tests/test_github_fetcher.py -v`
Expected: FAIL，`ImportError: cannot import name '_fetch_trending_repos' from 'app.collect.fetchers.github'`

- [ ] **Step 4: 用以下完整内容替换 `backend/app/collect/fetchers/github.py`**

```python
import httpx
from bs4 import BeautifulSoup
from app.collect.fetchers.base import Fetcher
from app.collect.schema import RawTalent

LANGUAGES = ["python", "java", "go", "javascript", "typescript"]
MAX_REPOS = 25
MAX_CONTRIBUTORS_PER_REPO = 5


def _fetch_trending_repos(client: httpx.Client, language: str) -> list[tuple[str, str]]:
    """解析 GitHub Trending 页面（指定语言），返回 [(owner, repo), ...]。"""
    resp = client.get(f"https://github.com/trending/{language}", params={"since": "daily"})
    if resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    repos: list[tuple[str, str]] = []
    for article in soup.select("article.Box-row"):
        link = article.select_one("h2.h3.lh-condensed a")
        if not link or not link.get("href"):
            continue
        href = link["href"].strip("/")
        parts = href.split("/")
        if len(parts) == 2:
            repos.append((parts[0], parts[1]))
    return repos


class GithubTrendingFetcher(Fetcher):
    """GitHub Trending 采集(反爬弱,优先)。真实实现按需补充解析逻辑。"""
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=10)

    def fetch(self) -> list[RawTalent]:
        return []
```

- [ ] **Step 5: 运行验证通过**

Run: `cd backend && pytest tests/test_github_fetcher.py -v`
Expected: PASS（4 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/app/collect/fetchers/github.py backend/tests/test_github_fetcher.py
git commit -m "feat(A): parse github trending page into repo list"
```

---

## Task 4: REST API 层 `_fetch_contributors` / `_fetch_user_profile` + 限流信号

**Files:**
- Modify: `backend/app/collect/fetchers/github.py`
- Modify: `backend/tests/test_github_fetcher.py`

**Interfaces:**
- Consumes: `httpx.Client`、`Settings.github_token`（Task 1）
- Produces:
  - `_GithubRateLimited`（模块级私有异常类，无字段，仅作信号）——供 Task 5 的 `GithubTrendingFetcher.fetch()` 捕获
  - `_is_rate_limited(resp: httpx.Response) -> bool`——纯函数,判定响应是否为限流响应
  - `_auth_headers(token: str) -> dict[str, str]`——纯函数,`token` 为空时返回 `{}`,非空时返回 `{"Authorization": f"token {token}"}`
  - `_fetch_contributors(client: httpx.Client, owner: str, repo: str, token: str) -> list[str]`——返回贡献者用户名列表(已按 `MAX_CONTRIBUTORS_PER_REPO` 截断)；命中限流时抛 `_GithubRateLimited`
  - `_fetch_user_profile(client: httpx.Client, username: str, token: str) -> dict`——返回 `{"bio": str, "repo_descriptions": list[str], "languages": list[str]}`；命中限流时抛 `_GithubRateLimited`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_github_fetcher.py` 文件末尾追加：

```python
import pytest
from app.collect.fetchers.github import (
    _is_rate_limited, _auth_headers, _fetch_contributors, _fetch_user_profile,
    _GithubRateLimited, MAX_CONTRIBUTORS_PER_REPO,
)


class TestIsRateLimited:
    def test_429_is_rate_limited(self):
        resp = MagicMock(status_code=429, headers={})
        assert _is_rate_limited(resp) is True

    def test_403_with_zero_remaining_is_rate_limited(self):
        resp = MagicMock(status_code=403, headers={"X-RateLimit-Remaining": "0"})
        assert _is_rate_limited(resp) is True

    def test_403_with_nonzero_remaining_is_not_rate_limited(self):
        resp = MagicMock(status_code=403, headers={"X-RateLimit-Remaining": "5"})
        assert _is_rate_limited(resp) is False

    def test_200_is_not_rate_limited(self):
        resp = MagicMock(status_code=200, headers={})
        assert _is_rate_limited(resp) is False


class TestAuthHeaders:
    def test_empty_token_returns_empty_headers(self):
        assert _auth_headers("") == {}

    def test_nonempty_token_returns_authorization_header(self):
        assert _auth_headers("ghp_abc") == {"Authorization": "token ghp_abc"}


class TestFetchContributors:
    def test_returns_usernames_truncated_to_max(self):
        client = MagicMock()
        body = [{"login": f"user{i}"} for i in range(10)]
        client.get.return_value = MagicMock(status_code=200, headers={}, json=lambda: body)
        result = _fetch_contributors(client, "octocat", "Hello-World", "")
        assert result == [f"user{i}" for i in range(MAX_CONTRIBUTORS_PER_REPO)]

    def test_raises_on_rate_limit(self):
        client = MagicMock()
        client.get.return_value = MagicMock(status_code=429, headers={})
        with pytest.raises(_GithubRateLimited):
            _fetch_contributors(client, "octocat", "Hello-World", "")

    def test_returns_empty_on_non_200_non_ratelimit(self):
        client = MagicMock()
        client.get.return_value = MagicMock(status_code=404, headers={})
        result = _fetch_contributors(client, "octocat", "Hello-World", "")
        assert result == []

    def test_sends_auth_header_when_token_present(self):
        client = MagicMock()
        client.get.return_value = MagicMock(status_code=200, headers={}, json=lambda: [])
        _fetch_contributors(client, "octocat", "Hello-World", "ghp_abc")
        _, kwargs = client.get.call_args
        assert kwargs["headers"] == {"Authorization": "token ghp_abc"}


class TestFetchUserProfile:
    def test_returns_bio_and_languages(self):
        client = MagicMock()
        profile_resp = MagicMock(status_code=200, headers={}, json=lambda: {"bio": "Pythonista"})
        repos_resp = MagicMock(status_code=200, headers={}, json=lambda: [
            {"description": "A web app", "language": "Python"},
            {"description": None, "language": "Python"},
            {"description": "A CLI tool", "language": "Go"},
            {"description": "No language repo", "language": None},
        ])
        client.get.side_effect = [profile_resp, repos_resp]
        result = _fetch_user_profile(client, "octocat", "")
        assert result["bio"] == "Pythonista"
        assert result["repo_descriptions"] == ["A web app", "A CLI tool"]
        assert set(result["languages"]) == {"Python", "Go"}

    def test_raises_on_rate_limit_from_profile_call(self):
        client = MagicMock()
        client.get.return_value = MagicMock(status_code=403, headers={"X-RateLimit-Remaining": "0"})
        with pytest.raises(_GithubRateLimited):
            _fetch_user_profile(client, "octocat", "")

    def test_raises_on_rate_limit_from_repos_call(self):
        client = MagicMock()
        profile_resp = MagicMock(status_code=200, headers={}, json=lambda: {"bio": "x"})
        repos_resp = MagicMock(status_code=429, headers={})
        client.get.side_effect = [profile_resp, repos_resp]
        with pytest.raises(_GithubRateLimited):
            _fetch_user_profile(client, "octocat", "")

    def test_handles_missing_bio(self):
        client = MagicMock()
        profile_resp = MagicMock(status_code=200, headers={}, json=lambda: {"bio": None})
        repos_resp = MagicMock(status_code=200, headers={}, json=lambda: [])
        client.get.side_effect = [profile_resp, repos_resp]
        result = _fetch_user_profile(client, "octocat", "")
        assert result["bio"] == ""
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_github_fetcher.py -v -k "RateLimited or AuthHeaders or FetchContributors or FetchUserProfile"`
Expected: FAIL，`ImportError: cannot import name '_is_rate_limited' from 'app.collect.fetchers.github'`

- [ ] **Step 3: 在 `github.py` 中追加实现**

在 `backend/app/collect/fetchers/github.py` 里,`MAX_CONTRIBUTORS_PER_REPO = 5` 这一行之后、`_fetch_trending_repos` 函数之前，插入：

```python
class _GithubRateLimited(Exception):
    """GitHub API 限流信号,内部使用,不向 Fetcher.fetch() 的调用方传播。"""


def _is_rate_limited(resp: httpx.Response) -> bool:
    if resp.status_code == 429:
        return True
    if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
        return True
    return False


def _auth_headers(token: str) -> dict[str, str]:
    if not token:
        return {}
    return {"Authorization": f"token {token}"}
```

然后在 `_fetch_trending_repos` 函数之后、`GithubTrendingFetcher` 类之前，插入：

```python
def _fetch_contributors(client: httpx.Client, owner: str, repo: str, token: str) -> list[str]:
    """调用 contributors API，返回用户名列表(截断到 MAX_CONTRIBUTORS_PER_REPO)。"""
    resp = client.get(
        f"https://api.github.com/repos/{owner}/{repo}/contributors",
        headers=_auth_headers(token),
    )
    if _is_rate_limited(resp):
        raise _GithubRateLimited()
    if resp.status_code != 200:
        return []
    body = resp.json()
    return [item["login"] for item in body[:MAX_CONTRIBUTORS_PER_REPO]]


def _fetch_user_profile(client: httpx.Client, username: str, token: str) -> dict:
    """调用 users API + users/repos API，返回 bio/仓库描述/语言列表。"""
    headers = _auth_headers(token)

    profile_resp = client.get(f"https://api.github.com/users/{username}", headers=headers)
    if _is_rate_limited(profile_resp):
        raise _GithubRateLimited()
    bio = ""
    if profile_resp.status_code == 200:
        bio = profile_resp.json().get("bio") or ""

    repos_resp = client.get(f"https://api.github.com/users/{username}/repos", headers=headers)
    if _is_rate_limited(repos_resp):
        raise _GithubRateLimited()
    repo_descriptions: list[str] = []
    languages: list[str] = []
    if repos_resp.status_code == 200:
        for item in repos_resp.json():
            desc = item.get("description")
            lang = item.get("language")
            if desc and lang:
                repo_descriptions.append(desc)
            if lang:
                languages.append(lang)

    return {
        "bio": bio,
        "repo_descriptions": repo_descriptions,
        "languages": list(dict.fromkeys(languages)),
    }
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_github_fetcher.py -v`
Expected: PASS（全部通过，包括 Task 3 的 4 个测试 + 本任务新增的 14 个测试）

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/fetchers/github.py backend/tests/test_github_fetcher.py
git commit -m "feat(A): add github contributors and user profile api calls with rate-limit signaling"
```

---

## Task 5: 编排层 `GithubTrendingFetcher.fetch()`

**Files:**
- Modify: `backend/app/collect/fetchers/github.py`
- Modify: `backend/tests/test_github_fetcher.py`

**Interfaces:**
- Consumes: `_fetch_trending_repos`（Task 3）、`_fetch_contributors`/`_fetch_user_profile`/`_GithubRateLimited`（Task 4）、`LANGUAGES`/`MAX_REPOS`（Task 3）、`Settings.github_token`（Task 1，惰性读取）
- Produces: `GithubTrendingFetcher.fetch() -> list[RawTalent]`——真实可运行的最终交付物；`GithubTrendingFetcher.__init__(self, client=None, token=None)`——`token=None` 时惰性从 `get_settings().github_token` 读取

编排顺序（无早停的语言遍历,统一在收集完所有语言的仓库后再截断到 `MAX_REPOS`,保证跨语言去重结果确定）：

1. 遍历 `LANGUAGES`,调用 `_fetch_trending_repos`,按 `(owner, repo)` 去重累积,最终截断到 `MAX_REPOS`
2. 遍历上述仓库列表,调用 `_fetch_contributors`,按用户名全局去重累积；命中 `_GithubRateLimited` 时停止后续仓库的抓取,保留已收集到的用户名
3. 遍历上述用户名列表,调用 `_fetch_user_profile`,拼装 `RawTalent`；命中 `_GithubRateLimited` 时停止后续用户的抓取,保留已生成的 `RawTalent` 列表
4. 返回最终 `RawTalent` 列表(可能因限流而不完整,但不抛异常)

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_github_fetcher.py` 文件末尾追加：

```python
from unittest.mock import patch
from app.collect.fetchers.github import GithubTrendingFetcher
import app.collect.fetchers.github as github_module


class TestGithubTrendingFetcherOrchestration:
    def test_dedupes_repos_across_languages_and_caps_at_max(self):
        def fake_trending(client, language):
            return {"python": [("a", "r1"), ("b", "r2")], "java": [("a", "r1"), ("c", "r3")]}.get(language, [])

        with patch.object(github_module, "_fetch_trending_repos", side_effect=fake_trending), \
             patch.object(github_module, "_fetch_contributors", return_value=[]), \
             patch.object(github_module, "_fetch_user_profile", return_value={}):
            fetcher = GithubTrendingFetcher(client=MagicMock(), token="")
            fetcher.fetch()
            # 3 unique repos (a/r1, b/r2, c/r3) all under MAX_REPOS=25, so all requested for contributors
            assert github_module._fetch_contributors.call_count == 3

    def test_caps_total_repos_at_max_repos_constant(self):
        many_repos = [(f"owner{i}", f"repo{i}") for i in range(50)]

        with patch.object(github_module, "_fetch_trending_repos", side_effect=lambda c, lang: many_repos if lang == "python" else []), \
             patch.object(github_module, "_fetch_contributors", return_value=[]) as mock_contrib, \
             patch.object(github_module, "_fetch_user_profile", return_value={}):
            fetcher = GithubTrendingFetcher(client=MagicMock(), token="")
            fetcher.fetch()
            assert mock_contrib.call_count == github_module.MAX_REPOS

    def test_dedupes_usernames_across_repos(self):
        with patch.object(github_module, "_fetch_trending_repos", side_effect=lambda c, lang: [("a", "r1"), ("b", "r2")] if lang == "python" else []), \
             patch.object(github_module, "_fetch_contributors", side_effect=lambda c, o, r, t: ["alice", "bob"] if r == "r1" else ["bob", "carol"]), \
             patch.object(github_module, "_fetch_user_profile", return_value={"bio": "", "repo_descriptions": [], "languages": []}) as mock_profile:
            fetcher = GithubTrendingFetcher(client=MagicMock(), token="")
            fetcher.fetch()
            called_usernames = [call.args[1] for call in mock_profile.call_args_list]
            assert called_usernames == ["alice", "bob", "carol"]

    def test_stops_contributor_fetch_on_rate_limit_but_returns_partial_result(self):
        from app.collect.fetchers.github import _GithubRateLimited

        def fake_contributors(client, owner, repo, token):
            if repo == "r1":
                return ["alice"]
            raise _GithubRateLimited()

        with patch.object(github_module, "_fetch_trending_repos", side_effect=lambda c, lang: [("a", "r1"), ("b", "r2")] if lang == "python" else []), \
             patch.object(github_module, "_fetch_contributors", side_effect=fake_contributors), \
             patch.object(github_module, "_fetch_user_profile", return_value={"bio": "", "repo_descriptions": [], "languages": []}) as mock_profile:
            fetcher = GithubTrendingFetcher(client=MagicMock(), token="")
            result = fetcher.fetch()
            assert len(result) == 1
            mock_profile.assert_called_once()

    def test_stops_profile_fetch_on_rate_limit_but_returns_partial_result(self):
        from app.collect.fetchers.github import _GithubRateLimited

        def fake_profile(client, username, token):
            if username == "alice":
                return {"bio": "hi", "repo_descriptions": [], "languages": ["Python"]}
            raise _GithubRateLimited()

        with patch.object(github_module, "_fetch_trending_repos", side_effect=lambda c, lang: [("a", "r1")] if lang == "python" else []), \
             patch.object(github_module, "_fetch_contributors", return_value=["alice", "bob"]), \
             patch.object(github_module, "_fetch_user_profile", side_effect=fake_profile):
            fetcher = GithubTrendingFetcher(client=MagicMock(), token="")
            result = fetcher.fetch()
            assert len(result) == 1
            assert result[0].identity_hint == "alice"

    def test_produces_rawtalent_with_correct_fields(self):
        def fake_profile(client, username, token):
            return {"bio": "Pythonista", "repo_descriptions": ["A web app"], "languages": ["Python", "Go"]}

        with patch.object(github_module, "_fetch_trending_repos", side_effect=lambda c, lang: [("a", "r1")] if lang == "python" else []), \
             patch.object(github_module, "_fetch_contributors", return_value=["octocat"]), \
             patch.object(github_module, "_fetch_user_profile", side_effect=fake_profile):
            fetcher = GithubTrendingFetcher(client=MagicMock(), token="")
            result = fetcher.fetch()
            assert len(result) == 1
            talent = result[0]
            assert talent.source == "github"
            assert talent.identity_hint == "octocat"
            assert "Pythonista" in talent.raw_text
            assert "A web app" in talent.raw_text
            assert talent.skills_hint == ["Python", "Go"]
            assert talent.experience_hint == ""

    def test_returns_empty_list_when_no_repos_found(self):
        with patch.object(github_module, "_fetch_trending_repos", return_value=[]), \
             patch.object(github_module, "_fetch_contributors") as mock_contrib, \
             patch.object(github_module, "_fetch_user_profile") as mock_profile:
            fetcher = GithubTrendingFetcher(client=MagicMock(), token="")
            result = fetcher.fetch()
            assert result == []
            mock_contrib.assert_not_called()
            mock_profile.assert_not_called()


class TestGithubTrendingFetcherTokenResolution:
    def test_get_token_uses_explicit_token_when_provided(self):
        fetcher = GithubTrendingFetcher(client=MagicMock(), token="explicit_token")
        assert fetcher._get_token() == "explicit_token"

    def test_get_token_reads_settings_when_not_provided(self, monkeypatch):
        fake_settings = MagicMock(github_token="from_settings_token")
        monkeypatch.setattr("app.config.get_settings", lambda: fake_settings)
        fetcher = GithubTrendingFetcher(client=MagicMock())
        assert fetcher._get_token() == "from_settings_token"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_github_fetcher.py -v -k Orchestration`
Expected: FAIL，`AttributeError: <module 'app.collect.fetchers.github'> does not have the attribute '_fetch_trending_repos'` 之类的 patch 目标缺失,或 `fetch()` 返回空列表导致断言失败(当前骨架 `fetch()` 恒返回 `[]`)

- [ ] **Step 3: 用以下完整内容替换 `GithubTrendingFetcher` 类**

把 `backend/app/collect/fetchers/github.py` 文件末尾的：

```python
class GithubTrendingFetcher(Fetcher):
    """GitHub Trending 采集(反爬弱,优先)。真实实现按需补充解析逻辑。"""
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=10)

    def fetch(self) -> list[RawTalent]:
        return []
```

替换为：

```python
class GithubTrendingFetcher(Fetcher):
    """GitHub Trending 采集：找热门仓库 → 贡献者 → profile/repos，产出 RawTalent。"""
    def __init__(self, client: httpx.Client | None = None, token: str | None = None):
        self.client = client or httpx.Client(timeout=10)
        self._token = token

    def _get_token(self) -> str:
        if self._token is not None:
            return self._token
        from app.config import get_settings
        return get_settings().github_token

    def fetch(self) -> list[RawTalent]:
        token = self._get_token()

        repos: list[tuple[str, str]] = []
        seen_repos: set[tuple[str, str]] = set()
        for language in LANGUAGES:
            for repo in _fetch_trending_repos(self.client, language):
                if repo not in seen_repos:
                    seen_repos.add(repo)
                    repos.append(repo)
        repos = repos[:MAX_REPOS]

        usernames: list[str] = []
        seen_usernames: set[str] = set()
        for owner, repo in repos:
            try:
                contributors = _fetch_contributors(self.client, owner, repo, token)
            except _GithubRateLimited:
                break
            for username in contributors:
                if username not in seen_usernames:
                    seen_usernames.add(username)
                    usernames.append(username)

        talents: list[RawTalent] = []
        for username in usernames:
            try:
                profile = _fetch_user_profile(self.client, username, token)
            except _GithubRateLimited:
                break
            raw_text_parts = [profile.get("bio", "")] + profile.get("repo_descriptions", [])
            raw_text = "\n".join(part for part in raw_text_parts if part)
            talents.append(RawTalent(
                source="github",
                raw_text=raw_text,
                identity_hint=username,
                skills_hint=profile.get("languages", []),
                experience_hint="",
            ))

        return talents
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_github_fetcher.py -v`
Expected: PASS（全部通过：Task 3 的 4 个 + Task 4 的 14 个 + 本任务的 9 个)

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/fetchers/github.py backend/tests/test_github_fetcher.py
git commit -m "feat(A): orchestrate github trending fetch into RawTalent with rate-limit graceful degradation"
```

---
<!--PLAN_CONTINUE_5-->




