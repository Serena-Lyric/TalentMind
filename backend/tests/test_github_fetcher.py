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
