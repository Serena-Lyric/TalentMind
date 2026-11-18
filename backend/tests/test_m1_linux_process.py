"""Linux process-group and /proc ownership contracts; synthetic files only."""
import errno
import json
import signal
from types import SimpleNamespace

import pytest

from app.collect import worker_process
from app.collect.runtime import lease, scheduler

_SIGKILL = getattr(signal, 'SIGKILL', 9)


def proc_stat(pid=100, *, comm='python', state='S', starttime=4242):
    tail = [state, '1', '1', '1', '0', '-1', '4194560', '0', '0', '0', '0', '0', '0', '0',
            '0', '20', '0', '1', '0', str(starttime)]
    return f'{pid} ({comm}) ' + ' '.join(tail) + '\n'


def write_proc(root, pid, *, state='S', starttime=4242):
    entry = root / str(pid)
    entry.mkdir(parents=True, exist_ok=True)
    (entry / 'stat').write_text(proc_stat(pid, state=state, starttime=starttime), encoding='utf-8')


def write_owner(tmp_path, **overrides):
    path = lease.lock_path('boss', root=tmp_path)
    path.mkdir(parents=True, exist_ok=True)
    record = {'platform': 'boss', 'owner': 'worker:700:test', 'kind': 'runtime',
              'pid': 700, 'created_at': 5, 'pgid': 700}
    record.update(overrides)
    (path / 'owner.json').write_text(json.dumps(record), encoding='utf-8')
    return record


def ticking_clock():
    ticks = [0.0]
    return (lambda: ticks[0]), (lambda seconds: ticks.__setitem__(0, ticks[0] + seconds))


def group_probe(*, dies_on=()):
    state = {'alive': True, 'signals': []}

    def killpg(pgid, sig):
        state['signals'].append((pgid, sig))
        if sig == 0:
            if not state['alive']:
                raise ProcessLookupError
        elif sig in dies_on:
            state['alive'] = False

    return state, killpg


class ServiceProcess:
    def __init__(self, pgid=700):
        self._collection_pgid = pgid
        self.waited = False

    def wait(self, timeout=None):
        self.waited = True
        return 0


@pytest.fixture
def fake_proc(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, '_PLATFORM', 'linux')
    monkeypatch.setattr(scheduler, '_PROC_ROOT', tmp_path)
    return tmp_path


def test_parse_proc_stat_handles_spaces_and_parens_in_comm():
    assert scheduler.parse_proc_stat(proc_stat(comm='talent mind (worker)')) == ('S', 4242)


@pytest.mark.parametrize('text', [
    '',
    'garbage',
    '42 (python) S 1 2 3',
    '42 (python) S ' + ' '.join(['1'] * 18) + ' nope',
])
def test_parse_proc_stat_rejects_malformed_records(text):
    assert scheduler.parse_proc_stat(text) is None


def test_linux_pid_alive_requires_matching_starttime(fake_proc):
    write_proc(fake_proc, 100, starttime=4242)
    assert scheduler._pid_alive(100, 4242) is True
    assert scheduler._pid_alive(100, 9999) is False
    assert scheduler._pid_alive(100, None) is False


@pytest.mark.parametrize('state', ['Z', 'X', 'x'])
def test_linux_pid_alive_rejects_zombie_and_dead_states(fake_proc, state):
    write_proc(fake_proc, 100, state=state)
    assert scheduler._pid_alive(100, 4242) is False


def test_linux_pid_alive_is_false_when_proc_entry_is_missing(fake_proc):
    assert scheduler._pid_alive(101, 4242) is False


def test_linux_creation_time_reads_proc_starttime(fake_proc):
    write_proc(fake_proc, 100, starttime=777)
    assert scheduler._process_creation_time(100) == 777
    assert scheduler._process_creation_time(101) is None


def test_non_linux_posix_pid_check_falls_back_to_signal_zero(monkeypatch):
    monkeypatch.setattr(scheduler, '_PLATFORM', 'darwin')
    fake_os = SimpleNamespace(name='posix', kill=lambda pid, sig: None)
    monkeypatch.setattr(scheduler, 'os', fake_os)
    assert scheduler._pid_alive(123456) is True

    def missing(pid, sig):
        raise ProcessLookupError

    fake_os.kill = missing
    assert scheduler._pid_alive(123456) is False


def test_group_alive_maps_process_lookup_error_to_false():
    def killpg(pgid, sig):
        assert (pgid, sig) == (55, 0)
        raise ProcessLookupError

    assert worker_process.group_alive(55, killpg=killpg) is False


def test_group_alive_maps_permission_error_to_true():
    def killpg(pgid, sig):
        raise PermissionError

    assert worker_process.group_alive(55, killpg=killpg) is True


def test_group_alive_propagates_unknown_oserror():
    def killpg(pgid, sig):
        raise OSError(errno.EINVAL, 'bad probe')

    with pytest.raises(OSError):
        worker_process.group_alive(55, killpg=killpg)


def test_group_alive_returns_true_when_probe_succeeds():
    calls = []
    assert worker_process.group_alive(
        55, killpg=lambda pgid, sig: calls.append((pgid, sig))) is True
    assert calls == [(55, 0)]


@pytest.mark.parametrize('pgid', [0, -1, '55', None])
def test_group_alive_rejects_unverifiable_group_ids(pgid):
    with pytest.raises(ValueError):
        worker_process.group_alive(pgid, killpg=lambda *_: None)


def test_stop_process_group_terminates_whole_group_with_sigterm():
    state, killpg = group_probe(dies_on=(worker_process._SIGTERM,))
    clock, sleeper = ticking_clock()
    process = ServiceProcess()
    worker_process.stop_process_group(process, timeout=3, killpg=killpg,
                                      clock=clock, sleeper=sleeper)
    assert state['signals'][0] == (700, worker_process._SIGTERM)
    assert state['signals'][-1] == (700, 0)
    assert process.waited


def test_stop_process_group_escalates_to_sigkill_after_timeout():
    state, killpg = group_probe(dies_on=(_SIGKILL,))
    clock, sleeper = ticking_clock()
    worker_process.stop_process_group(ServiceProcess(), timeout=1, killpg=killpg,
                                      clock=clock, sleeper=sleeper)
    signals = state['signals']
    assert signals[0] == (700, worker_process._SIGTERM)
    assert signals.count((700, _SIGKILL)) == 1
    assert signals[-1] == (700, 0)


def test_stop_process_group_fails_closed_when_group_survives_sigkill():
    _, killpg = group_probe()
    clock, sleeper = ticking_clock()
    with pytest.raises(TimeoutError, match='采集子进程树停止超时'):
        worker_process.stop_process_group(ServiceProcess(), timeout=0, killpg=killpg,
                                          clock=clock, sleeper=sleeper)


def test_stop_process_group_refuses_to_guess_a_pid():
    class BareProcess:
        pid = 700

        def wait(self, timeout=None):
            return 0

    with pytest.raises(RuntimeError, match='进程组'):
        worker_process.stop_process_group(BareProcess(), killpg=lambda *_: None)


def test_posix_spawn_uses_new_session_and_records_pgid(monkeypatch):
    class Proc:
        pid = 4321

    captured = {}

    def popen(args, **kwargs):
        captured['kwargs'] = kwargs
        return Proc()

    monkeypatch.setattr(worker_process, 'os', SimpleNamespace(name='posix'))
    monkeypatch.setattr(worker_process.subprocess, 'Popen', popen)
    process = worker_process.spawn(['python', '-c', 'pass'])
    assert captured['kwargs']['start_new_session'] is True
    assert process._collection_pgid == 4321


def test_posix_stop_delegates_to_process_group(monkeypatch):
    calls = []
    monkeypatch.setattr(worker_process, 'os', SimpleNamespace(name='posix'))
    monkeypatch.setattr(worker_process, 'stop_process_group',
                        lambda process, timeout=10: calls.append((process.pid, timeout)))
    worker_process.stop(SimpleNamespace(pid=700), timeout=7)
    assert calls == [(700, 7)]


def test_posix_close_is_a_noop():
    worker_process.close(object())


def test_pid_process_poll_tracks_process_group_after_leader_exit(monkeypatch):
    monkeypatch.setattr(scheduler, '_POSIX', True)
    monkeypatch.setattr(scheduler, '_pid_alive', lambda pid, created_at=None: False)
    process = scheduler._PidProcess(700, 4242, pgid=700)
    monkeypatch.setattr(worker_process, 'group_alive', lambda pgid: True)
    assert process.poll() is None
    monkeypatch.setattr(worker_process, 'group_alive', lambda pgid: False)
    assert process.poll() == 0


def test_pid_process_terminate_and_kill_use_group_stop(monkeypatch):
    monkeypatch.setattr(scheduler, '_POSIX', True)
    calls = []
    monkeypatch.setattr(worker_process, 'stop',
                        lambda process, timeout=10: calls.append((process.pid, timeout)))
    process = scheduler._PidProcess(700, 4242, pgid=700)
    process.terminate()
    process.kill()
    assert calls == [(700, 5), (700, 5)]


def test_restore_processes_passes_persisted_pgid(tmp_path, monkeypatch):
    state_root = tmp_path / 'runtime'
    monkeypatch.setattr(scheduler, '_STATE_ROOT', state_root)
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', state_root / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    process = SimpleNamespace(pid=700)
    captured = {}

    def fake_pid_process(platform, pid, created_at, job_name=None, pgid=None):
        captured.update(platform=platform, pid=pid, created_at=created_at, pgid=pgid)
        return process

    monkeypatch.setattr(scheduler, '_pid_process', fake_pid_process)
    scheduler._write_scheduler({'pids': {'boss': {'pid': 700, 'created_at': 4242, 'pgid': 700}}})
    scheduler._restore_processes()
    assert captured == {'platform': 'boss', 'pid': 700, 'created_at': 4242, 'pgid': 700}
    assert scheduler._PROCESS_META['boss']['pgid'] == 700


def test_process_payload_persists_posix_pgid(monkeypatch):
    monkeypatch.setattr(scheduler, '_POSIX', True)
    monkeypatch.setattr(scheduler, '_PROCESSES',
                        {'boss': SimpleNamespace(pid=700, _collection_pgid=700)})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_process_creation_time', lambda pid: 4242)
    assert scheduler._process_payload()['boss'] == {'pid': 700, 'created_at': 4242, 'pgid': 700}


def test_stop_process_fails_closed_when_posix_group_survives(monkeypatch):
    monkeypatch.setattr(scheduler, '_POSIX', True)
    monkeypatch.setattr(worker_process, 'stop', lambda process, timeout=10: None)
    monkeypatch.setattr(worker_process, 'close', lambda process: None)
    monkeypatch.setattr(worker_process, 'group_alive', lambda pgid: True)
    process = SimpleNamespace(pid=700, _collection_pgid=700, poll=lambda: 0)
    with pytest.raises(RuntimeError, match='collection_worker_termination_unknown'):
        scheduler._stop_process(process)


def test_stop_process_fails_closed_when_posix_group_stop_errors(monkeypatch):
    monkeypatch.setattr(scheduler, '_POSIX', True)

    def failing_stop(process, timeout=10):
        raise TimeoutError('采集子进程树停止超时')

    monkeypatch.setattr(worker_process, 'stop', failing_stop)
    process = SimpleNamespace(pid=700, _collection_pgid=700, poll=lambda: 0)
    with pytest.raises(RuntimeError, match='collection_worker_termination_unknown'):
        scheduler._stop_process(process)


def test_stop_process_accepts_verified_posix_group_exit(monkeypatch):
    monkeypatch.setattr(scheduler, '_POSIX', True)
    monkeypatch.setattr(worker_process, 'stop', lambda process, timeout=10: None)
    monkeypatch.setattr(worker_process, 'close', lambda process: None)
    monkeypatch.setattr(worker_process, 'group_alive', lambda pgid: False)
    scheduler._stop_process(SimpleNamespace(pid=700, _collection_pgid=700, poll=lambda: 0))


def test_rebind_persists_pgid(tmp_path, monkeypatch):
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: True)
    held = lease.acquire('boss', 'scheduler:test', 'runtime', root=tmp_path, pid=100, created_at=1)
    lease.rebind(held, 200, 2, owner='worker:200', pgid=200)
    assert held.pgid == 200
    assert lease.status('boss', root=tmp_path)['pgid'] == 200
    held.release()


def test_posix_worker_owner_uses_pgid_after_leaders_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(lease, '_POSIX', True)
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: False)
    record = write_owner(tmp_path)
    monkeypatch.setattr(worker_process, 'group_alive', lambda pgid: True)
    assert lease._owner_tree_alive(record) is True
    assert lease.status('boss', root=tmp_path) is not None

    monkeypatch.setattr(worker_process, 'group_alive', lambda pgid: False)
    assert lease._owner_tree_alive(record) is False
    assert lease.status('boss', root=tmp_path) is None
    assert lease.release_if_dead('boss', root=tmp_path) is True


@pytest.mark.parametrize('pgid', [None, 0, '700', -1])
def test_posix_worker_owner_without_valid_pgid_fails_closed(tmp_path, monkeypatch, pgid):
    monkeypatch.setattr(lease, '_POSIX', True)
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: False)
    record = write_owner(tmp_path, pgid=pgid)
    assert lease._owner_tree_alive(record) is None
    assert lease.release_if_dead('boss', root=tmp_path) is False
    with pytest.raises(lease.WriterStateError, match='tree_unknown'):
        lease.acquire('boss', 'new-owner', 'runtime', root=tmp_path, pid=100, created_at=2)
    assert lease.lock_path('boss', root=tmp_path).exists()


def test_posix_worker_owner_group_probe_error_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(lease, '_POSIX', True)
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: False)
    record = write_owner(tmp_path)

    def broken(pgid):
        raise OSError(errno.EIO, 'probe failed')

    monkeypatch.setattr(worker_process, 'group_alive', broken)
    assert lease._owner_tree_alive(record) is None


def test_posix_non_worker_owner_is_dead_after_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(lease, '_POSIX', True)
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: False)
    record = write_owner(tmp_path, owner='scheduler:1')
    assert lease._owner_tree_alive(record) is False
