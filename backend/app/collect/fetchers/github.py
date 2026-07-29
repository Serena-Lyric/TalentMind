import httpx
from bs4 import BeautifulSoup
from app.collect.fetchers.base import Fetcher
from app.collect.schema import RawTalent

LANGUAGES = ["python", "java", "go", "javascript", "typescript"]
MAX_REPOS = 25
MAX_CONTRIBUTORS_PER_REPO = 5


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
