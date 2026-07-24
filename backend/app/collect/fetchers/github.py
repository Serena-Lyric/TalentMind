import httpx
from app.collect.fetchers.base import Fetcher
from app.collect.schema import RawJD


class GithubTrendingFetcher(Fetcher):
    """GitHub Trending 采集(反爬弱,优先)。真实实现按需补充解析逻辑。"""
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=10)

    def fetch(self) -> list[RawJD]:
        return []
