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
