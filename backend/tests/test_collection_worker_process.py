"""Native venv wrapper/child lifecycle using sleep only; no services or collection."""
import ctypes
import os
import subprocess
import sys
import time

import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows venv wrapper regression')
@pytest.mark.parametrize('method', ['stop', 'close'])
def test_venv_sleep_wrapper_and_real_child_both_stop_before_return(method):
    from app.collect import worker_process
    process = worker_process.spawn([sys.executable, '-u', '-c',
        'import os,time; print(os.getpid(),flush=True); time.sleep(60)'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    child_handle = None
    try:
        child_pid = int(process.stdout.readline().strip())
        assert child_pid != process.pid  # Reproduce the installed venv wrapper.
        child_handle = kernel.OpenProcess(0x100000, False, child_pid)
        assert child_handle
        assert kernel.WaitForSingleObject(child_handle, 0) == 258
        if method == 'stop':
            worker_process.stop(process, timeout=5)
            assert process._collection_job.active_processes() == 0
        else:
            worker_process.close(process)
            process.wait(timeout=5)
        assert process.poll() is not None
        assert kernel.WaitForSingleObject(child_handle, 5000) == 0
    finally:
        worker_process.close(process)
        process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
        if child_handle:
            kernel.CloseHandle(child_handle)


@pytest.mark.skipif(os.name != 'nt', reason='Windows job/controller regression')
def test_stop_api_waits_for_tree_exit_and_watcher_archive(tmp_path, monkeypatch):
    from app.collect import control, worker_process
    monkeypatch.setattr(control, '_STATE_DIR', tmp_path)
    monkeypatch.setattr(control, '_STATE_PATH', tmp_path / 'state.json')
    monkeypatch.setattr(control, '_PROCESS', None)
    monkeypatch.setattr(control, '_STARTING_RUN', None)
    monkeypatch.setattr(control, '_ensure_browser', lambda *a: {
        'endpoint': 'http://127.0.0.1:1', 'user_data_dir': str(tmp_path),
        'platform_access': {'boss': {'can_collect': True, 'access_state': 'public_accessible'}}})
    monkeypatch.setattr(control, '_worker_environment', os.environ.copy)
    pid_file = tmp_path / 'synthetic-pid'
    script = f'import os,time; from pathlib import Path; Path({str(pid_file)!r}).write_text(str(os.getpid())); print("sleep worker ready",flush=True); time.sleep(60)'
    workers = []
    def spawn(args, **kwargs):
        process = worker_process.spawn([sys.executable, '-u', '-c', script], **kwargs)
        workers.append(process)
        return process
    monkeypatch.setattr(control, '_spawn_process', spawn)
    process = None
    try:
        run = control.start_task({})
        control._START_THREAD.join(2)
        process = workers[0]
        deadline = time.monotonic() + 3
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert int(pid_file.read_text()) != process.pid
        result = control.stop_task(run['run_id'])
        assert result['stopped'] is True
        assert process.poll() is not None
        state = control._load_state()
        assert state['current_task']['status'] == 'stopped'
        assert state['history'][0]['run_id'] == run['run_id']
        assert state['history'][0]['stop_reason'] == 'user_stopped'
        assert state['history'][0]['pid'] is None
        assert control._PROCESS is None
        assert process._collection_job.handle is None
    finally:
        if process is not None:
            worker_process.close(process)
            process.wait(timeout=5)
        pid_file.unlink(missing_ok=True)
