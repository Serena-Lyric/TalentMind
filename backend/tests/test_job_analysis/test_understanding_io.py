"""Exercise real httpx transport and local CLI, never call a paid model from tests."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import shutil

import httpx
import pytest


@pytest.fixture(autouse=True)
def _remove_owned_file_fixtures(request):
    target=request.getfixturevalue('tmp_path') if 'tmp_path' in request.fixturenames else None
    base=request.getfixturevalue('tmp_path_factory').getbasetemp().resolve() if target is not None else None
    if target is not None:
        assert not any(target.iterdir())
    yield
    if target is not None and target.exists():
        resolved=target.resolve()
        assert resolved!=base and resolved.is_relative_to(base) and resolved==target.absolute()
        shutil.rmtree(resolved)
        assert not target.exists()


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


def test_flash_protocol_uses_thinking_json_output_and_cache_usage_fields():
    from app.job_analysis.understanding.cloud import CloudProcessor, CloudConfig

    def handle(request):
        body=json.loads(request.content)
        assert body["model"]=="deepseek-flash"
        assert body["thinking"]=={"type":"enabled"}
        assert body["reasoning_effort"]=="max"
        assert body["response_format"]=={"type":"json_object"}
        assert "prompt_cache_key" not in body
        return httpx.Response(200, json=dict(
            id="flash-synthetic",
            model="deepseek-flash",
            system_fingerprint="flash-fingerprint",
            choices=[dict(finish_reason="stop",message=dict(content='{"claims":[]}'))],
            usage=dict(prompt_tokens=10,completion_tokens=2,total_tokens=12,
                       prompt_cache_hit_tokens=4,prompt_cache_miss_tokens=6),
        ))

    settings={**config(),"provider":"DeepSeek official","model":"deepseek-flash",
              "thinking":"enabled","reasoning_effort":"max"}
    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await CloudProcessor(
                CloudConfig.model_validate(settings),"synthetic-test-value",client
            ).complete([dict(role="user",content="synthetic")])
    result=asyncio.run(call())
    assert result.metadata["returned_model"]=="deepseek-flash"
    assert result.metadata["usage"]["prompt_cache_hit_tokens"]==4
    assert result.metadata["usage"]["prompt_cache_miss_tokens"]==6


def test_shipped_config_example_selects_current_flash_alias_without_legacy_names():
    example=json.loads((Path(__file__).parents[2]/"app/job_analysis/understanding/config.example.json")
                       .read_text(encoding="utf-8"))
    assert example["model"]=="deepseek-flash"
    assert "V4.1-Flash-1017" in example["model_revision"]
    assert example["thinking"] in {"enabled","disabled"}
    assert example["reasoning_effort"] in {"low","high","max"}


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


def test_audit_cli_saves_raw_patch_effective_draft_and_real_request_without_overwriting_prior(tmp_path, monkeypatch, capsys):
    from app.job_analysis.understanding import __main__ as cli
    from app.job_analysis.understanding.processor import Completion
    from app.job_analysis.understanding.storage import save_run, read_run
    from test_understanding_audit import prior, patch_for, relation
    original = prior("使用 Redis 完成任务存储", "任务存储")
    patch = patch_for(original)
    patch["relations"] = [relation("instrumental_use", "Redis", "任务存储", "使用")]
    old, new = tmp_path / "previous", tmp_path / "audited"
    save_run(old, original)
    before = {p.name:p.read_bytes() for p in old.iterdir()}
    settings = tmp_path / "config.json"
    settings.write_text(json.dumps(config()), encoding="utf-8")
    credential = tmp_path / "credential.txt"
    credential.write_text("synthetic-test-only", encoding="utf-8")

    class Fixture:
        def __init__(self, settings, credential):
            self.descriptor = settings.model_dump()

        async def complete(self, messages):
            return Completion(content=json.dumps(patch), finish_reason="stop")

    monkeypatch.setattr(cli, "CloudProcessor", Fixture)
    monkeypatch.setattr(sys, "argv", ["understanding", "audit", str(old), "--config", str(settings),
                                     "--key-file", str(credential), "--output", str(new)])
    assert cli.main() == 0
    result = read_run(new)
    assert result["analysis"]["relations"][0]["basis"] == "explicit"
    assert json.loads(result["completion"]) == patch
    assert result["compiled_draft"]["claims"]
    assert result["request"][0]["content"].startswith("你是中文JD的定向语义复核器")
    assert before == {p.name:p.read_bytes() for p in old.iterdir()}
    output = capsys.readouterr().out
    assert "Redis" not in output and "synthetic-test-only" not in output


def test_default_cli_durably_saves_primary_before_audit_and_reports_both_call_usage(tmp_path,monkeypatch,capsys):
    from app.job_analysis.understanding import __main__ as cli
    from app.job_analysis.understanding.storage import read_run
    from test_understanding_audit import prior,patch_for,relation
    from test_understanding_pipeline import response
    old=prior('使用 Redis 完成任务存储','任务存储');raw=json.loads(old['completion'])
    raw['relations']=[dict(duty_id='d1',requirement_id='r1',basis='explicit',evidence=[{'field':'raw_text','quote':'任务存储','occurrence':None}],reason='需角色校验的关系')]
    patch=patch_for(old);patch['relations']=[relation('instrumental_use','Redis','任务存储','使用')]
    snapshot=tmp_path/'input.json';snapshot.write_text(json.dumps(old['analysis']['input_row']),encoding='utf-8')
    settings=tmp_path/'config.json';settings.write_text(json.dumps(config()),encoding='utf-8')
    key=tmp_path/'key.txt';key.write_text('synthetic-only',encoding='utf-8');out=tmp_path/'out';calls=[]
    class Service:
        def __init__(self,settings,key):self.descriptor=settings.model_dump()
        async def complete(self,messages):
            calls.append(messages)
            if len(calls)==2:
                assert (out/'primary/manifest.json').exists()
                assert not (out/'manifest.json').exists()
                return response(patch)
            return response(raw)
    monkeypatch.setattr(cli,'CloudProcessor',Service)
    monkeypatch.setattr(sys,'argv',['understanding','analyze',str(snapshot),'--namespace','synthetic','--input-version','v1','--config',str(settings),'--key-file',str(key),'--output',str(out)])
    assert cli.main()==0
    result=read_run(out)
    assert len(calls)==2
    assert read_run(out/'primary')['analysis']['relations']
    assert read_run(out/'audit')['analysis']['relations'][0]['basis']=='explicit'
    assert result['pipeline']['total_usage']['total_tokens']==24
    assert json.loads(capsys.readouterr().out)['processor_calls']==2
