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
    script = ("import subprocess,sys,time; child=subprocess.Popen([sys.executable,'-u','-c',"
              "'import os,time; print(os.getpid(),flush=True); time.sleep(60)'],"
              "stdout=subprocess.PIPE,text=True); print(child.stdout.readline().strip(),flush=True); time.sleep(60)")
    process = worker_process.spawn([sys.executable, '-u', '-c', script],
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
