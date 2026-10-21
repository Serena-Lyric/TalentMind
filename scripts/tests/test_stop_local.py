"""Run the real PowerShell stop entry with isolated state and fake service boundaries."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_stop(status, fail=False):
    with tempfile.TemporaryDirectory(prefix='talentmind-stop-test-') as temporary:
        area = Path(temporary).resolve()
        (area / 'scripts').mkdir()
        runtime = area / 'data/local/local-runtime'
        runtime.mkdir(parents=True)
        script = area / 'scripts/stop-local.ps1'
        shutil.copyfile(ROOT / 'scripts/stop-local.ps1', script)
        stamp = '2026-01-01T00:00:00.0000000Z'
        entry = lambda pid: {'pid': pid, 'started': stamp}
        state = {'root': str(area), 'backend': {**entry(101), 'listener': entry(102)}, 'frontend': entry(103)}
        (runtime / 'services.json').write_text(json.dumps(state), encoding='utf-8')
        wrapper = area / 'check.ps1'
        source = r'''
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$global:tmStopEvents = [Collections.Generic.List[string]]::new()
$global:tmBatchDone = $false
function Get-Process { param($Id, $ErrorAction); return [pscustomobject]@{ Id=$Id; StartTime=[datetime]'2026-01-01T00:00:00Z' } }
function Stop-Process { param($Id, $ErrorAction); $global:tmStopEvents.Add("kill:$Id") }
function Invoke-RestMethod {
    param($Uri,$Method,$ContentType,$Body,$TimeoutSec)
    if ($Uri -match '/batches$') {
        $global:tmStopEvents.Add('batches')
        return @{code=0; data=@{items=@(@{batch_id='test-batch';status='__STATUS__';finished_at=$null})}}
    }
    if ($Uri -match '/batches/test-batch/stop$') {
        $global:tmStopEvents.Add('stop-batch')
        if (__FAIL__) { throw 'synthetic batch stop failure' }
        $global:tmBatchDone=$true
        return @{code=0;data=@{status='stopped'}}
    }
    if ($Uri -match '/batches/test-batch$') {
        $global:tmStopEvents.Add('batch-state')
        return @{code=0;data=@{status='stopped';finished_at='2026-01-01T00:00:01Z'}}
    }
    if ($Uri -match '/status$') {
        $global:tmStopEvents.Add('single-state')
        return @{code=0;data=@{status='completed';finished_at='2026-01-01T00:00:00Z'}}
    }
    throw "Unexpected request: $Uri"
}
try { & '__SCRIPT__' }
finally { [Console]::WriteLine('TRACE:' + (ConvertTo-Json -InputObject @($global:tmStopEvents) -Compress)) }
'''
        source = source.replace('__STATUS__', status).replace('__FAIL__', '$true' if fail else '$false')
        source = source.replace('__SCRIPT__', str(script).replace("'", "''"))
        wrapper.write_text(source, encoding='utf-8-sig')
        result = subprocess.run(['pwsh', '-NoProfile', '-File', str(wrapper)], capture_output=True,
                                encoding='utf-8', errors='replace', timeout=20)
        trace = next(line[6:] for line in result.stdout.splitlines() if line.startswith('TRACE:'))
        return result.returncode, json.loads(trace), result.stderr


@pytest.mark.parametrize('status', ['running', 'waiting_next_round', 'stopping'])
def test_stop_archives_active_batch_before_application_processes(status):
    code, trace, error = run_stop(status)
    assert code == 0, error
    assert trace.index('stop-batch') < trace.index('batch-state') < trace.index('kill:103')
    assert trace[-3:] == ['kill:103', 'kill:102', 'kill:101']


def test_stop_preserves_an_unstarted_batch_plan():
    code, trace, error = run_stop('queued')
    assert code == 0, error
    assert 'stop-batch' not in trace
    assert 'kill:103' in trace


def test_failed_batch_stop_preserves_backend_and_frontend():
    code, trace, _ = run_stop('waiting_next_round', fail=True)
    assert code != 0
    assert 'stop-batch' in trace
    assert not any(event.startswith('kill:') for event in trace)
