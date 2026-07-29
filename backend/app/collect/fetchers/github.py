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
