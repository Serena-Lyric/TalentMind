"""Own a worker's entire process tree, including Windows venv redirectors.

The root is suspended until its live process handle belongs to a named Job
Object. Descendants inherit it, and another backend can reopen it by name;
termination never trusts a recycled PID. Closing the last handle also stops the tree.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import signal
import subprocess
import threading
import time
import uuid

_JOB_NAME_PREFIX = 'Local\\TalentMind.Collection.'


def _valid_job_name(name):
    if not isinstance(name, str) or not name.startswith(_JOB_NAME_PREFIX):
        return False
    token = name[len(_JOB_NAME_PREFIX):]
    return len(token) == 32 and all(char in '0123456789abcdefABCDEF' for char in token)


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
    def __init__(self, name=None):
        self.lock = threading.RLock()
        self.name = name or f'{_JOB_NAME_PREFIX}{uuid.uuid4().hex}'
        if not _valid_job_name(self.name):
            raise ValueError('无效的采集 Job Object 名称')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self._configure_kernel()
        ctypes.set_last_error(0)
        self.handle = self.kernel.CreateJobObjectW(None, self.name)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            self.close()
            raise RuntimeError('采集 Job Object 名称已被占用')
        limits = _ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def _configure_kernel(self):
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            'OpenJobObjectW': ([wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
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
        for function_name, (args, result) in signatures.items():
            function = getattr(self.kernel, function_name)
            function.argtypes, function.restype = args, result

    @classmethod
    def open(cls, name):
        job = cls.__new__(cls)
        job.lock = threading.RLock()
        job.name = name
        job.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        job._configure_kernel()
        job.handle = job.kernel.OpenJobObjectW(0x0004 | 0x0008, False, name)
        if not job.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return job

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


def spawn(args, *, job_name=None, **kwargs):
    if os.name != 'nt':
        return subprocess.Popen(args, start_new_session=True, **kwargs)
    job = _WindowsJob(job_name)
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
        if job is None or not job.handle:
            raise RuntimeError('采集任务缺少可验证的进程树归属，拒绝按旧 PID 停止')
        with job.lock:
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


def open_job(name):
    if os.name != 'nt':
        return None
    if not _valid_job_name(name):
        raise ValueError('无效的采集 Job Object 名称')
    return _WindowsJob.open(name)


def job_has_processes(name):
    try:
        job = open_job(name)
    except OSError as exc:
        if getattr(exc, 'winerror', None) == 2:
            return False
        raise
    if job is None:
        return False
    try:
        return job.active_processes() > 0
    finally:
        job.close()
