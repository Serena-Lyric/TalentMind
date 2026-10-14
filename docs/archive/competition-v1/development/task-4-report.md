# Task 4 Report: REST API 层 `_fetch_contributors` / `_fetch_user_profile` + 限流信号

## Status: DONE (contradiction found and fixed per coordinator decision; committed)

## What I implemented

Followed the brief's exact code for:
- `_GithubRateLimited` exception class
- `_is_rate_limited(resp)` — 429 always true; 403 true only if `X-RateLimit-Remaining` header equals string `"0"`
- `_auth_headers(token)` — empty dict for empty token, else `{"Authorization": f"token {token}"}`
- `_fetch_contributors(client, owner, repo, token)` — calls contributors API, raises `_GithubRateLimited` on rate limit, returns `[]` on other non-200, else truncates logins to `MAX_CONTRIBUTORS_PER_REPO`
- `_fetch_user_profile(client, username, token)` — calls users API then users/repos API, raises `_GithubRateLimited` on rate limit from either call

All inserted at the exact locations specified: exception/helpers after `MAX_CONTRIBUTORS_PER_REPO = 5`, the two fetch functions after `_fetch_trending_repos` and before `GithubTrendingFetcher`.

`GithubTrendingFetcher.fetch()` is untouched — still returns `[]`.

## TDD Evidence

### RED

Command:
```
cd backend && PYTHONPATH=. python -m pytest tests/test_github_fetcher.py -v -k "RateLimited or AuthHeaders or FetchContributors or FetchUserProfile"
```

Result: collection error as expected —
```
ImportError: cannot import name '_is_rate_limited' from 'app.collect.fetchers.github'
```
This matches the brief's Step 2 expectation exactly.

### GREEN attempt (blocked)

Command:
```
cd backend && PYTHONPATH=. python -m pytest tests/test_github_fetcher.py -v
```

Result: 17 passed, 1 failed —

```
FAILED tests/test_github_fetcher.py::TestFetchUserProfile::test_returns_bio_and_languages
AssertionError: assert ['A web app', 'A CLI tool', 'No language repo'] == ['A web app', 'A CLI tool']
```

## Blocker: contradiction between brief's test and brief's implementation

The brief's own test `test_returns_bio_and_languages` (brief lines 83-96) feeds `_fetch_user_profile` a repos response containing:
```python
{"description": "No language repo", "language": None},
```
and asserts:
```python
assert result["repo_descriptions"] == ["A web app", "A CLI tool"]
```
i.e. this item's description must be EXCLUDED from `repo_descriptions` because its `language` is `None`.

But the brief's own implementation code (brief lines 180-189) is:
```python
for item in repos_resp.json():
    desc = item.get("description")
    if desc:
        repo_descriptions.append(desc)
    lang = item.get("language")
    if lang:
        languages.append(lang)
```
This appends to `repo_descriptions` based solely on `desc` being truthy, independent of `language`. For the "No language repo" item, `desc` is truthy, so it gets appended regardless of `language` being `None`. Running this code against the brief's test produces `repo_descriptions == ["A web app", "A CLI tool", "No language repo"]`, which fails the assertion.

I transcribed both the test and the implementation verbatim from the brief (verified twice by re-reading brief lines 82-119 and 151-196). This is not a transcription error on my part — the two blocks in the brief are mutually inconsistent as written.

Two possible resolutions, and I don't want to silently pick one since it changes behavior:
1. **Fix the implementation** to only append `desc` when both `desc` and `lang` are truthy (matches the test, but changes the semantics from "collect all non-empty descriptions" to "collect descriptions only for repos that also have a language set" — a behavior change beyond what the brief's own implementation snippet specifies).
2. **Fix the test** to expect `["A web app", "A CLI tool", "No language repo"]` (matches the implementation as literally given, but that means editing the brief's "exact test code" which I was told to write verbatim).

I'm stopping here rather than guessing, per the task's explicit escalation instruction ("STOP and escalate if the brief's code doesn't work as described").

## Files changed (uncommitted)

- `backend/app/collect/fetchers/github.py` — added `_GithubRateLimited`, `_is_rate_limited`, `_auth_headers`, `_fetch_contributors`, `_fetch_user_profile` (exact brief code, unmodified)
- `backend/tests/test_github_fetcher.py` — appended `TestIsRateLimited`, `TestAuthHeaders`, `TestFetchContributors`, `TestFetchUserProfile` (exact brief code, unmodified)

No commit created — tests are not fully green.

## Self-review

- `_is_rate_limited` 403-vs-other-403 logic verified correct via passing tests `test_403_with_zero_remaining_is_rate_limited` and `test_403_with_nonzero_remaining_is_not_rate_limited`.
- `_fetch_contributors` tests exercise: truncation/success path, rate-limit-raises path, non-200-non-ratelimit-returns-empty path, and auth-header-forwarding — all pass.
- `_fetch_user_profile` tests exercise: success path (currently failing due to the contradiction above), rate-limit-from-profile-call path, rate-limit-from-repos-call path, and missing-bio path — 3 of 4 pass.
- `GithubTrendingFetcher.fetch()` confirmed unmodified, still `return []`.

## Resolution (coordinator decision: fix the implementation, not the test)

The coordinator confirmed this was a genuine bug in the plan (also fixed in `docs/superpowers/plans/2026-07-29-github-fetcher-implementation.md`) and decided to fix `_fetch_user_profile`'s implementation rather than the test. Applied this change in `backend/app/collect/fetchers/github.py`:

Before:
```python
    repo_descriptions: list[str] = []
    languages: list[str] = []
    if repos_resp.status_code == 200:
        for item in repos_resp.json():
            desc = item.get("description")
            if desc:
                repo_descriptions.append(desc)
            lang = item.get("language")
            if lang:
                languages.append(lang)
```

After:
```python
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
```

`repo_descriptions` now only includes a repo's description when that repo also has a non-null `language`. `languages` collection logic is unchanged.

### Re-test after fix

Command:
```
cd backend && PYTHONPATH=. python -m pytest tests/test_github_fetcher.py -v
```
Result: **18 passed** (4 from Task 3 + 14 from Task 4), including `TestFetchUserProfile::test_returns_bio_and_languages` now passing.

### Full backend regression

Command:
```
cd backend && PYTHONPATH=. python -m pytest -v -m "not integration"
```
Result: **85 passed, 10 deselected** — no regressions across the whole non-integration suite.

(Did not run the `-m integration` suite since this task doesn't touch DB/docker-compose-dependent code; Task 3's report already established that baseline.)

## Commit

`f5db310 feat(A): add github contributors and user profile api calls with rate-limit signaling`
(staged `backend/app/collect/fetchers/github.py` and `backend/tests/test_github_fetcher.py` only)

## Concerns

None remaining. The brief's contradiction was resolved per explicit coordinator/human decision (fix implementation, not test), all 18 tests in the target file pass, and the full non-integration suite (85 tests) shows no regressions.
