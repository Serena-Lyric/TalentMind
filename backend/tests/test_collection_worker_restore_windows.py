"""Windows restore tests exercise a real venv wrapper and child process."""
import ctypes
import json
import os
import subprocess
import sys

import pytest


def _sleep_wrapper_script():
    return ("import subprocess,sys,time; child=subprocess.Popen([sys.executable,'-u','-c',"
            "'import os,time; print(os.getpid(),flush=True); time.sleep(60)'],"
            "stdout=subprocess.PIPE,text=True); print(child.stdout.readline().strip(),flush=True); time.sleep(60)")


@pytest.fixture
def live_worker_tree(tmp_path, monkeypatch):
    from app.collect import worker_process
    from app.collect.runtime import lease, scheduler

    state_root = tmp_path / 'runtime'
    monkeypatch.setattr(scheduler, '_STATE_ROOT', state_root)
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', state_root / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_LEASES', {})
    process = None
    child_handle = None
    kernel = None
    held = None
    try:
        process = worker_process.spawn([sys.executable, '-u', '-c', _sleep_wrapper_script()],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        child_pid = int(process.stdout.readline().strip())
        assert child_pid != process.pid

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        child_handle = kernel.OpenProcess(0x100000, False, child_pid)
        assert child_handle
        assert kernel.WaitForSingleObject(child_handle, 0) == 258

        held = lease.acquire('boss', 'scheduler:test', 'runtime', root=state_root)
        scheduler._PROCESSES['boss'] = process
        scheduler._bind_worker_lease('boss', process, held)
        scheduler._LEASES['boss'] = held
        scheduler._write_scheduler({
            'started_at': 1000,
            'config': {},
            'pids': scheduler._process_payload(),
        })
        yield process, child_handle, kernel, held, state_root
    finally:
        if process is not None:
            try:
                worker_process.stop(process, timeout=5)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
            worker_process.close(process)
            process.wait(timeout=5)
            if process.stdout:
                process.stdout.close()
        if child_handle and kernel:
            kernel.CloseHandle(child_handle)
        if held is not None:
            held.release()


@pytest.mark.skipif(os.name != 'nt', reason='Windows named job restore regression')
def test_restored_scheduler_stops_real_child_before_releasing_writer(live_worker_tree):
    from app.collect.runtime import lease, scheduler

    process, child_handle, kernel, _, state_root = live_worker_tree
    record = scheduler._read_scheduler()['pids']['boss']
    assert record.get('job_name')
    assert lease.status('boss', root=state_root)['job_name'] == record['job_name']

    # The wrapper can exit while its child remains in the named Job Object.
    process.terminate()
    process.wait(timeout=5)
    assert kernel.WaitForSingleObject(child_handle, 0) == 258
    assert lease.release_if_dead('boss', root=state_root) is False
    assert lease.status('boss', root=state_root)['owner'].startswith('worker:')

    scheduler._PROCESSES.clear()
    scheduler._PROCESS_META.clear()
    scheduler._LEASES.clear()
    scheduler._restore_processes()
    restored = scheduler._PROCESSES['boss']
    assert restored is not process
    assert restored._collection_job is not None

    scheduler.stop()

    assert kernel.WaitForSingleObject(child_handle, 5000) == 0
    assert lease.status('boss', root=state_root) is None


@pytest.mark.skipif(os.name != 'nt', reason='Windows fail-closed restore regression')
def test_restored_scheduler_fails_closed_without_process_tree_handle(live_worker_tree):
    from app.collect.runtime import lease, scheduler

    _, child_handle, kernel, _, state_root = live_worker_tree
    persisted = scheduler._read_scheduler()['pids']['boss']
    persisted.pop('job_name', None)
    scheduler._write_scheduler({'started_at': 1000, 'config': {}, 'pids': {'boss': persisted}})
    owner_path = lease.lock_path('boss', root=state_root) / 'owner.json'
    owner_record = json.loads(owner_path.read_text(encoding='utf-8'))
    owner_record.pop('job_name', None)
    owner_path.write_text(json.dumps(owner_record), encoding='utf-8')
    scheduler._PROCESSES.clear()
    scheduler._PROCESS_META.clear()
    scheduler._LEASES.clear()
    scheduler._restore_processes()

    with pytest.raises(RuntimeError, match='termination_unknown'):
        scheduler.stop()

    assert kernel.WaitForSingleObject(child_handle, 0) == 258
    assert lease.status('boss', root=state_root) is not None
