"""Own a worker's entire process tree, including Windows venv redirectors.

The root is suspended until its live process handle belongs to a private Job
Object. Descendants inherit that job; termination never trusts a recycled PID.
Closing the job (including interpreter exit) also terminates remaining workers.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import signal
import subprocess
import threading
import time


class _BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
        ('flags', wintypes.DWORD), ('min_working', ctypes.c_size_t), ('max_working', ctypes.c_size_t),
        ('active_limit', wintypes.DWORD), ('affinity', ctypes.c_size_t),
        ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]


class _IoCounters(ctypes.Structure):
    _fields_ = [(key, ctypes.c_ulonglong) for key in
        ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', _BasicLimits), ('io', _IoCounters), ('process_memory', ctypes.c_size_t),
        ('job_memory', ctypes.c_size_t), ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [(key, ctypes.c_longlong) for key in ('user', 'kernel', 'period_user', 'period_kernel')] + [
        (key, wintypes.DWORD) for key in ('faults', 'total', 'active', 'terminated')]


class _ThreadEntry(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD), ('tid', wintypes.DWORD),
        ('pid', wintypes.DWORD), ('priority', wintypes.LONG), ('delta', wintypes.LONG), ('flags', wintypes.DWORD)]


class _WindowsJob:
    def __init__(self):
        self.lock = threading.RLock()
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            'SetInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            'AssignProcessToJobObject': ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            'TerminateJobObject': ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            'QueryInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
            'CreateToolhelp32Snapshot': ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            'Thread32First': ([wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)], wintypes.BOOL),
            'Thread32Next': ([wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)], wintypes.BOOL),
            'OpenThread': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            'ResumeThread': ([wintypes.HANDLE], wintypes.DWORD),
            'OpenProcess': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            'IsProcessInJob': ([wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL),
            'WaitForSingleObject': ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def attach_and_resume(self, process):
        # Popen holds the actual creation handle; no PID/name-based ownership guess.
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        snapshot = self.kernel.CreateToolhelp32Snapshot(4, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = _ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            found = self.kernel.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.pid == process.pid:
                    thread = self.kernel.OpenThread(2, False, entry.tid)
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if self.kernel.ResumeThread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                        return
                    finally:
                        self.kernel.CloseHandle(thread)
                found = self.kernel.Thread32Next(snapshot, ctypes.byref(entry))
            raise RuntimeError('无法恢复已归属的采集进程线程')
        finally:
            self.kernel.CloseHandle(snapshot)

    def active_processes(self):
        accounting = _Accounting()
        if not self.kernel.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return accounting.active

    def terminate(self):
        if not self.kernel.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def member_handles(self):
        capacity = 32
        while True:
            buffer = ctypes.create_string_buffer(8 + ctypes.sizeof(ctypes.c_size_t) * capacity)
            if self.kernel.QueryInformationJobObject(self.handle, 3, buffer, len(buffer), None):
                count = wintypes.DWORD.from_buffer(buffer, 4).value
                pids = (ctypes.c_size_t * count).from_buffer(buffer, 8)
                break
            if ctypes.get_last_error() != 234:
                raise ctypes.WinError(ctypes.get_last_error())
            capacity *= 2
        handles = []
        try:
            for pid in pids:
                handle = self.kernel.OpenProcess(0x100000 | 0x1000, False, pid)
                if not handle:
                    continue  # It may already have exited.
                owned = wintypes.BOOL()
                if not self.kernel.IsProcessInJob(handle, self.handle, ctypes.byref(owned)) or not owned:
                    self.kernel.CloseHandle(handle)
                    continue
                # Retain the verified handle, immune to PID reuse while waiting.
                handles.append(handle)
            return handles
        except BaseException:
            for handle in handles:
                self.kernel.CloseHandle(handle)
            raise

    def close(self):
        with self.lock:
            if self.handle:
                self.kernel.CloseHandle(self.handle)
                self.handle = None


def spawn(args, **kwargs):
    if os.name != 'nt':
        return subprocess.Popen(args, start_new_session=True, **kwargs)
    job = _WindowsJob()
    process = None
    try:
        process = subprocess.Popen(args, creationflags=0x4 | 0x08000000, **kwargs)
        process._collection_job = job
        job.attach_and_resume(process)
        return process
    except BaseException:
        job.close()
        if process is not None:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        raise


def stop(process, timeout=10):
    job = getattr(process, '_collection_job', None)
    if os.name == 'nt':
        if job is None:
            raise RuntimeError('采集任务缺少可验证的进程树归属，拒绝按旧 PID 停止')
        with job.lock:
            if job.handle:
                handles = job.member_handles()
                try:
                    job.terminate()
                    deadline = time.monotonic() + timeout
                    for handle in handles:
                        remaining = max(0, int((deadline - time.monotonic()) * 1000))
                        if job.kernel.WaitForSingleObject(handle, remaining) != 0:
                            raise TimeoutError('采集子进程句柄停止超时')
                    while job.active_processes():
                        if time.monotonic() >= deadline:
                            raise TimeoutError('采集子进程树停止超时')
                        time.sleep(0.05)
                finally:
                    for handle in handles:
                        job.kernel.CloseHandle(handle)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    process.wait(timeout=timeout)


def close(process):
    job = getattr(process, '_collection_job', None)
    if job:
        job.close()
