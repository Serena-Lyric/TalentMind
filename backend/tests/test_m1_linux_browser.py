"""Linux Edge discovery/launch contracts using synthetic /proc trees; no browser."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.collect import browser
from app.collect.fetchers.cdp import CdpError


def tcp_row(local_hex, port_hex, *, state='0A', inode=12345):
    return (f'   0: {local_hex}:{port_hex} 00000000:0000 {state} '
            f'00000000:00000000 00:00000000 00000000 0 0 {inode} 1 0000000000000000 100 0 0 10 0')


def write_listen_table(root, rows):
    net = root / 'net'
    net.mkdir(exist_ok=True)
    (net / 'tcp').write_text('\n'.join(rows) + '\n', encoding='utf-8')


def write_process(root, pid, args, inodes=(12345,)):
    entry = root / str(pid)
    entry.mkdir(parents=True, exist_ok=True)
    (entry / 'cmdline').write_bytes(b'\0'.join(arg.encode() for arg in args) + b'\0')
    fd = entry / 'fd'
    fd.mkdir(exist_ok=True)
    for index, inode in enumerate(inodes):
        (fd / str(index)).write_text(f'socket:[{inode}]', encoding='utf-8')
    return entry


def read_link(link):
    return Path(link).read_text(encoding='utf-8')


def test_linux_edge_sessions_requires_main_process_and_owned_listener(tmp_path, monkeypatch):
    monkeypatch.setattr(browser, '_readlink', read_link)
    write_listen_table(tmp_path, [tcp_row('0100007F', '4BF4', inode=12345)])
    write_process(tmp_path, 4321, ['/usr/bin/microsoft-edge', '--remote-debugging-port=0',
                                   '--user-data-dir=/tmp/private', '--no-sandbox'])
    write_process(tmp_path, 4322, ['/usr/bin/microsoft-edge', '--type=renderer',
                                   '--remote-debugging-port=0', '--user-data-dir=/tmp/private'])
    write_process(tmp_path, 4323, ['/usr/bin/microsoft-edge'])
    empty = tmp_path / '4324'
    empty.mkdir()
    (empty / 'cmdline').write_bytes(b'')

    assert browser.linux_edge_sessions(tmp_path) == [{
        'pid': 4321, 'profile': '/tmp/private', 'port': 0,
        'listeners': [{'port': 19444, 'address': '127.0.0.1'}],
    }]


def test_linux_edge_sessions_fails_closed_without_listen_table(tmp_path):
    write_process(tmp_path, 4321, ['/usr/bin/microsoft-edge', '--remote-debugging-port=0',
                                   '--user-data-dir=/tmp/private'])
    with pytest.raises(CdpError, match='监听'):
        browser.linux_edge_sessions(tmp_path)


def test_parse_proc_net_tcp_accepts_only_listen_rows_and_decodes_ipv6():
    text = '\n'.join([
        '  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode',
        tcp_row('0100007F', '4BF4', inode=11),
        tcp_row('00000000', '0050', state='01', inode=12),
        tcp_row('00000000000000000000000001000000', '1F90', inode=13),
        'garbage line',
    ])
    assert browser.parse_proc_net_tcp(text) == {11: ('127.0.0.1', 19444), 13: ('::1', 8080)}


def test_stale_devtools_active_port_is_not_owned_by_a_live_listener(tmp_path):
    profile = tmp_path / 'profile'
    profile.mkdir()
    (profile / 'DevToolsActivePort').write_text('19444\n/devtools/browser/stale\n', encoding='utf-8')
    stale = {'pid': 1, 'profile': str(profile), 'port': 0,
             'listeners': [{'port': 19445, 'address': '127.0.0.1'}]}
    assert browser._owned_endpoint(profile, [stale]) is None

    owned = {**stale, 'listeners': [{'port': 19444, 'address': '127.0.0.1'}]}
    assert browser._owned_endpoint(profile, [owned]) == 'http://127.0.0.1:19444'


@pytest.mark.parametrize('name', ['microsoft-edge', 'google-chrome', 'chromium'])
def test_linux_daily_profile_directories_are_rejected(name):
    daily = Path.home() / '.config' / name
    with pytest.raises(ValueError, match='独立浏览器'):
        browser._profile(str(daily))
    with pytest.raises(ValueError, match='独立浏览器'):
        browser._profile(str(daily / 'Default'))


def test_unrelated_private_profile_is_accepted(tmp_path):
    assert browser._profile(str(tmp_path / 'private-profile')) == (tmp_path / 'private-profile').resolve()


def test_edge_launch_argv_only_adds_container_flags_on_linux(tmp_path):
    executable = Path('/usr/bin/microsoft-edge')
    profile = tmp_path / 'profile'
    linux = browser.edge_launch_argv(executable, profile, 'about:blank', linux=True)
    windows = browser.edge_launch_argv(executable, profile, 'about:blank', linux=False)
    common = ['--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
              f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check',
              '--disable-extensions']
    assert linux[0] == str(executable)
    for flag in common:
        assert flag in linux
        assert flag in windows
    assert '--no-sandbox' in linux and '--disable-dev-shm-usage' in linux
    assert '--no-sandbox' not in windows and '--disable-dev-shm-usage' not in windows
    assert linux[-1] == 'about:blank'


def test_edge_sessions_dispatch_uses_linux_proc(monkeypatch):
    monkeypatch.setattr(browser, 'os', SimpleNamespace(name='posix'))
    monkeypatch.setattr(browser, '_PLATFORM', 'linux')
    monkeypatch.setattr(browser, 'linux_edge_sessions', lambda proc_root='/proc': [{'pid': 7}])
    assert browser._edge_sessions() == [{'pid': 7}]


def test_edge_sessions_dispatch_rejects_other_platforms(monkeypatch):
    monkeypatch.setattr(browser, 'os', SimpleNamespace(name='posix'))
    monkeypatch.setattr(browser, '_PLATFORM', 'darwin')
    with pytest.raises(CdpError, match='Windows/Linux'):
        browser._edge_sessions()


def test_linux_launch_keeps_worker_session_and_container_flags(tmp_path, monkeypatch):
    executable = tmp_path / 'microsoft-edge'
    executable.write_text('#!/bin/sh\n', encoding='utf-8')
    monkeypatch.setattr(browser, '_PLATFORM', 'linux')
    monkeypatch.setattr(browser.shutil, 'which',
                        lambda name: str(executable) if name == 'microsoft-edge' else None)
    captured = {}

    class Proc:
        pid = 4321

    def popen(argv, **kwargs):
        captured['argv'], captured['kwargs'] = argv, kwargs
        return Proc()

    monkeypatch.setattr(browser.subprocess, 'Popen', popen)
    profile = tmp_path / 'profile'
    assert browser._launch_edge(profile, 'about:blank') == 4321
    assert captured['argv'][0] == str(executable)
    assert '--no-sandbox' in captured['argv']
    assert 'creationflags' not in captured['kwargs']
    assert 'start_new_session' not in captured['kwargs']
    assert profile.is_dir()
