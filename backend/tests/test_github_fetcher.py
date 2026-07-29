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
