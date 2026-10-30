"""Exercise real httpx transport and local CLI, never call a paid model from tests."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys

import httpx
import pytest


def config():
    return dict(provider="synthetic", endpoint="https://example.invalid/chat/completions",
                model="fixture", model_revision="declared-1", account_region="test",
                policy_checked_on="2026-10-29", policy_note="synthetic only",
                timeout_seconds=2.0, max_tokens=8000, thinking="disabled", reasoning_effort="max")


def test_transport_uses_explicit_endpoint_and_retains_finish_and_usage():
    from app.job_analysis.understanding.cloud import CloudProcessor, CloudConfig

    def handle(request):
        assert str(request.url) == "https://example.invalid/chat/completions"
        assert request.headers["authorization"] == "Bearer synthetic-test-value"
        body = json.loads(request.content)
        assert body["model"] == "fixture"
        assert body["thinking"] == {"type": "disabled"}
        assert body["reasoning_effort"] == "max"
        return httpx.Response(200, json=dict(model="fixture-reply", id="synthetic-response",
                 choices=[dict(finish_reason="length", message=dict(content='{"claims": []}'))],
                 usage=dict(prompt_tokens=10, completion_tokens=20, total_tokens=30,
                            prompt_cache_hit_tokens=3)))

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            processor = CloudProcessor(CloudConfig.model_validate(config()), "synthetic-test-value", client)
            return await processor.complete([dict(role="user", content="synthetic")])

    result = asyncio.run(call())
    assert result.finish_reason == "length"
    assert result.metadata["usage"]["completion_tokens"] == 20
    assert result.metadata["returned_model"] == "fixture-reply"


@pytest.mark.parametrize("kind,want", [("timeout", "timeout"), ("http", "http_error"),
                                          ("bad", "invalid_response"), ("refusal", "refused")])
def test_provider_errors_are_safe_and_do_not_retry(kind, want):
    from app.job_analysis.understanding.cloud import CloudProcessor, CloudConfig
    attempts = []

    def handle(request):
        attempts.append(request)
        if kind == "timeout":
            raise httpx.ReadTimeout("sensitive test value, must not escape")
        if kind == "http":
            return httpx.Response(429, text="sensitive provider body")
        if kind == "bad":
            return httpx.Response(200, json={"unexpected": "private"})
        return httpx.Response(200, json=dict(choices=[dict(finish_reason="content_filter",
                                                          message=dict(content=None))]))

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await CloudProcessor(CloudConfig.model_validate(config()), "test-only", client).complete([])

    result = asyncio.run(call())
    assert result.status == want
    assert len(attempts) == 1
    assert "sensitive" not in str(result)


def test_explicit_https_endpoint_rejects_embedded_credentials_or_query():
    from app.job_analysis.understanding.cloud import CloudConfig
    for endpoint in ("http://example.invalid", "https://user:pw@example.invalid/x",
                     "https://example.invalid/x?token=private"):
        with pytest.raises(ValueError):
            CloudConfig.model_validate({**config(), "endpoint": endpoint})


def test_run_reader_detects_corruption_and_never_overwrites_existing(tmp_path):
    from app.job_analysis.understanding.storage import save_run, read_run
    from test_understanding import run, draft
    value = run(draft())
    path = tmp_path / "run-one"
    save_run(path, value)
    assert read_run(path)["analysis"]["jd_id"] == "one"
    with pytest.raises(FileExistsError):
        save_run(path, value)
    (path / "run.json").write_text('{}', encoding="utf-8")
    with pytest.raises(ValueError):
        read_run(path)


def test_read_cli_returns_only_safe_summary_and_detects_corruption(tmp_path):
    from app.job_analysis.understanding.storage import save_run
    from test_understanding import run, draft
    value = run(draft())
    path = tmp_path / "run-one"
    save_run(path, value)
    command = [sys.executable, "-m", "app.job_analysis.understanding", "read", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, cwd=Path(__file__).parents[2])
    assert result.returncode == 0
    summary = json.loads(result.stdout)
    assert summary["claims"] == 2
    assert "Redis" not in result.stdout
    (path / "run.json").write_text('{}', encoding="utf-8")
    result = subprocess.run(command, capture_output=True, text=True, cwd=Path(__file__).parents[2])
    assert result.returncode == 1
    assert not result.stderr


@pytest.mark.parametrize("manifest", [[], None, "bad", {}])
def test_corrupt_manifest_shape_has_safe_cli_failure(tmp_path, manifest):
    path = tmp_path / "bad-run"
    path.mkdir()
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "run.json").write_text("{}", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "app.job_analysis.understanding", "read", str(path)],
                            capture_output=True, text=True, cwd=Path(__file__).parents[2])
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "rejected"
    assert not result.stderr


def test_private_run_cannot_be_written_to_repository_public_paths():
    from app.job_analysis.understanding.storage import save_run
    from test_understanding import run, draft
    import shutil
    from uuid import uuid4
    root = Path(__file__).resolve().parents[3]
    path = root / "frontend" / ("__p1_fixture_" + uuid4().hex)
    try:
        with pytest.raises(ValueError):
            save_run(path, run(draft()))
    finally:
        assert path.resolve().parent == (root / "frontend").resolve()
        if path.exists():
            shutil.rmtree(path)
    assert not path.exists()
