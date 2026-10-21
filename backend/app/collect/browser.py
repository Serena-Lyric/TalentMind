"""Independent Edge preparation and visible-page access checks; no DB imports."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx

from app.collect.fetchers.cdp import CdpClient, CdpError, host_matches, validate_endpoint
from app.collect.fetchers.job_sites import SITES
from app.collect.fetchers.boss import BOSS_CARD_SELECTOR, BOSS_DESCRIPTION_SELECTORS

DEFAULT_PROFILE = Path(__file__).resolve().parents[3] / 'data/local/edge-boss-cdp-profile'
HOSTS = {'boss': 'zhipin.com', **{key: spec.host_hint for key, spec in SITES.items()}}
ENTRY_URLS = {'boss': 'https://www.zhipin.com/web/geek/jobs?city=101010100&query=Python',
              **{key: spec.search_url('Python', '530' if key == 'zhaopin' else '010', 1)
                 for key, spec in SITES.items()}}
_LOCK = threading.RLock()
_READY = {'public_accessible', 'authenticated_accessible', 'empty_results'}
_BLOCKED = {'verification_required', 'login_required', 'content_limited'}
_PREPARED_TARGETS: dict[tuple[str, str], tuple[str, str]] = {}


class AccessBlocked(CdpError):
    """A page access gate must stop collection, even with saved list cards."""


def _profile(value: str | None) -> Path:
    profile = Path(value).expanduser().resolve() if value else DEFAULT_PROFILE.resolve()
    local = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    for daily in (local / 'Microsoft/Edge/User Data', local / 'Google/Chrome/User Data'):
        if profile == daily.resolve() or profile.is_relative_to(daily.resolve()):
            raise ValueError('必须使用独立浏览器 profile，不能使用日常浏览器用户目录')
    return profile


def _windows_argv(command: str) -> list[str]:
    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = parse(command, ctypes.byref(count))
    if not argv:
        return []
    try:
        return [argv[i] for i in range(count.value)]
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free(argv)


def _edge_sessions() -> list[dict]:
    """Native Windows process/listener evidence, never cookie or account access."""
    if os.name != 'nt':
        raise CdpError('当前自动启动仅支持 Windows Edge')
    script = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$edgeListeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue)
Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" |
Where-Object { $_.CommandLine -like '*--remote-debugging-port*' -and $_.CommandLine -notmatch '--type=' } |
ForEach-Object {
  $edgePid = $_.ProcessId
  [pscustomobject]@{pid=$edgePid; command=$_.CommandLine; listeners=@(
    $edgeListeners | Where-Object { $_.OwningProcess -eq $edgePid } |
    Select-Object @{n='port';e={$_.LocalPort}}, @{n='address';e={$_.LocalAddress}}
  )}
} | ConvertTo-Json -Depth 4 -Compress
"""
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise CdpError('无法核实独立 Edge 进程及监听端口')
    rows = json.loads(result.stdout.lstrip('\ufeff') or '[]')
    sessions = []
    for row in ([rows] if isinstance(rows, dict) else rows):
        args = _windows_argv(row['command'])
        if any(arg.startswith('--type=') for arg in args):
            continue
        options = dict(arg.split('=', 1) for arg in args if arg.startswith('--') and '=' in arg)
        if '--user-data-dir' in options and '--remote-debugging-port' in options:
            sessions.append({'pid': row['pid'], 'profile': options['--user-data-dir'],
                             'port': int(options['--remote-debugging-port']), 'listeners': row['listeners']})
    return sessions


def _owned_endpoint(profile: Path, sessions: list[dict]) -> str | None:
    for session in sessions:
        if Path(session['profile']).resolve() != profile:
            continue
        port = session['port']
        if port == 0:
            try:
                port = int((profile / 'DevToolsActivePort').read_text(encoding='utf-8').splitlines()[0])
            except (OSError, ValueError, IndexError):
                continue
        listeners = [item for item in session.get('listeners', []) if item['port'] == port]
        if listeners and all(item['address'] in {'127.0.0.1', '::1'} for item in listeners):
            return f'http://127.0.0.1:{port}'
    return None


def _launch_edge(profile: Path) -> int:
    candidates = [Path(os.environ.get(key, '')) / 'Microsoft/Edge/Application/msedge.exe'
                  for key in ('ProgramFiles(x86)', 'ProgramFiles')]
    executable = next((path for path in candidates if path.is_file()), None)
    if executable is None:
        raise CdpError('未找到 Microsoft Edge')
    profile.mkdir(parents=True, exist_ok=True)
    # Dynamic port avoids fixed-port collisions and excluded Windows port ranges.
    process = subprocess.Popen([str(executable), '--remote-debugging-port=0',
        '--remote-debugging-address=127.0.0.1', f'--user-data-dir={profile}',
        '--no-first-run', '--no-default-browser-check', '--new-window', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    return process.pid


def _page_targets(endpoint: str) -> list[dict]:
    validate_endpoint(endpoint)
    response = httpx.get(endpoint + '/json/list', timeout=3, trust_env=False)
    response.raise_for_status()
    value = response.json()
    return [t for t in value if isinstance(t, dict) and t.get('type') == 'page'] if isinstance(value, list) else []


def _create_page(endpoint: str, url: str) -> dict:
    response = httpx.put(endpoint + '/json/new?' + quote(url, safe=''), timeout=3, trust_env=False)
    response.raise_for_status()
    return response.json()


def classify_page(page: dict, platform: str) -> dict:
    """Absence of a login marker is never evidence of authentication."""
    url = str(page.get('url') or '')
    body = str(page.get('text') or '')
    gate = str(page.get('gate_text') or '')
    path = urlsplit(url).path.lower()
    host = urlsplit(url).hostname or ''
    query = dict(parse_qsl(urlsplit(url).query))
    cards, details = int(page.get('cards') or 0), int(page.get('details') or 0)
    state, reason = 'page_error', 'no_access_evidence'
    challenge = ('安全验证', '访问验证', '异常访问', '访问过于频繁', '操作过于频繁', '拖动滑块', '完成验证', '人机验证')
    standalone = [line.strip() for line in body.splitlines() if line.strip()]
    # Job prose can mention verification/error handling; only a gate or standalone prompt proves blocking.
    challenge_prompt = any(re.fullmatch(r'(?:请|请先)?(?:完成|进行)?(?:安全验证|访问验证|人机验证)[！!。\s]*', line)
                           or line in {'异常访问', '访问过于频繁', '操作过于频繁', '拖动滑块完成验证'} for line in standalone)
    if not host_matches(url, HOSTS[platform]):
        reason = 'unexpected_domain'
    elif (page.get('challenge_visible') is True
          or any(word in path for word in ('captcha', 'verify', 'security', 'challenge'))
          or '_security_check' in query
          or any(word in gate for word in challenge) or challenge_prompt
          or ('验证码' in gate and not any(word in gate for word in ('获取验证码', '发送验证码')))):
        state, reason = 'verification_required', 'manual_verification_or_access_limit'
    elif (page.get('login_visible') is True
          or any(word in path for word in ('/login', '/signin')) or host.startswith(('passport.', 'login.'))
          or any(word in gate for word in ('扫码登录', '手机号登录', '密码登录', '登录/注册', '请登录', '请先登录'))
          or any(re.fullmatch(r'(?:请先登录|登录后查看(?:完整)?(?:职位|详情|内容)?)[！!。\s]*', line) for line in standalone)):
        state, reason = 'login_required', 'manual_login_gate'
    elif page.get('content_limited') is True:
        state, reason = 'content_limited', 'guest_content_limited'
    elif any(line in {'页面加载失败', '页面不存在', '网络异常', '服务异常', '访问出错'} for line in standalone):
        reason = 'visible_page_error'
    elif page.get('ready_state') not in {'interactive', 'complete'}:
        state, reason = 'loading', 'document_loading'
    elif cards or details:
        state = 'authenticated_accessible' if page.get('authenticated') is True else 'public_accessible'
        reason = 'visible_job_content'
    elif any(word in body for word in ('暂无搜索结果', '暂无相关职位', '没有找到相关职位', '未找到相关职位')):
        state, reason = 'empty_results', 'explicit_empty_results'
    parts = urlsplit(url)
    return {'access_state': state, 'can_collect': state in _READY,
            'authentication': 'authenticated' if page.get('authenticated') is True else 'unknown',
            'content_limited': bool(page.get('content_limited')),
            'reason': reason, 'url': urlunsplit((parts.scheme, parts.netloc, parts.path, '', '')),
            'search_url': _search_target(url),
            'evidence': {'visible_cards': cards, 'visible_details': details}}


def _snapshot_js(platform: str) -> str:
    cards = BOSS_CARD_SELECTOR if platform == 'boss' else ','.join(SITES[platform].card_selectors)
    details = ','.join(BOSS_DESCRIPTION_SELECTORS) if platform == 'boss' else ','.join(SITES[platform].description_selectors)
    return r"""(() => {
      const visible = n => { const r=n.getBoundingClientRect(), s=getComputedStyle(n);
        return r.width>0 && r.height>0 && s.display!=='none' && s.visibility!=='hidden'; };
      const nodes = s => [...document.querySelectorAll(s)].filter(visible);
      const nonempty = s => nodes(s).filter(n => (n.innerText||'').trim().length>10).length;
      const gates = nodes('[role="dialog"], .sign-form, .login-dialog, .login-modal, .verify-wrap, .geetest_panel');
      const frames = nodes('iframe').map(n=>n.src||'');
      return {url:location.href, ready_state:document.readyState,
        text:(document.body?.innerText||'').slice(0,18000),
        gate_text:gates.map(n=>n.innerText||'').join('\n').slice(0,6000),
        challenge_visible:frames.some(src=>/captcha|verify|security-check|challenge/i.test(src)) || nodes('.geetest_panel').length>0,
        login_visible:frames.some(src=>/\/login|passport\./i.test(src)),
        content_limited:nodes('.job-detail-login-gate, .job-list-login-gate, .job-description__content--guest-clamp').length>0,
        authenticated:nodes('a,button').some(n=>/^(退出登录|退出账号|注销登录)$/.test((n.innerText||'').trim())) ||
          nodes('.user-nav .nav-figure').some(n=>/1[0-9]{2}[*＊]{3,}[0-9]{2,4}/.test(n.innerText||'')),
        cards:nonempty(CARDS), details:nonempty(DETAILS)};
    })()""".replace('CARDS', json.dumps(cards)).replace('DETAILS', json.dumps(details))


def inspect_page(client: CdpClient, platform: str) -> dict:
    page = client.evaluate(_snapshot_js(platform))
    if not isinstance(page, dict):
        raise CdpError('页面状态未返回有效对象')
    return classify_page(page, platform)


def wait_access(client: CdpClient, platform: str, timeout: float = 10) -> dict:
    deadline = time.monotonic() + max(timeout, 0)
    while True:
        state = inspect_page(client, platform)
        if state['can_collect']:
            return state
        if (state['access_state'] not in {'loading', 'page_error'}
                or state['reason'] not in {'document_loading', 'no_access_evidence'}
                or time.monotonic() >= deadline):
            raise AccessBlocked(f"{platform}: {state['access_state']} ({state['reason']})")
        time.sleep(.5)


def _unavailable(state='cdp_unavailable', reason='no_owned_edge') -> dict:
    return {'access_state': state, 'can_collect': False, 'authentication': 'unknown', 'reason': reason}


def _search_target(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query)
             if key in {'city', 'query', 'page', 'jl', 'kw', 'key', 'dq', 'dqs', 'currentPage'}]
    return urlunsplit((parts.scheme, parts.hostname or '', parts.path, urlencode(query), ''))


def _same_search_target(observed: str, target: str) -> bool:
    actual, expected = urlsplit(observed), urlsplit(target)
    actual_query = dict(parse_qsl(actual.query))
    if '_security_check' in actual_query:
        return False
    return (actual.scheme == expected.scheme and actual.hostname == expected.hostname
            and actual.path.rstrip('/') == expected.path.rstrip('/')
            and set(parse_qsl(expected.query)) <= set(parse_qsl(actual.query)))


def _inspect_targets(endpoint: str, targets: list[dict], platform: str, target_id=None,
                     target_url: str | None = None) -> dict:
    pages = [page for page in targets if host_matches(str(page.get('url', '')), HOSTS[platform])]
    if target_id:
        pages = [page for page in pages if page.get('id') == target_id]
        if not pages:
            return {**_unavailable('page_missing', 'target_page_missing'), 'target_id': target_id}
    best = _unavailable('page_missing', 'target_page_missing')
    priority = {'page_missing': 0, 'page_error': 1, 'loading': 2, 'login_required': 3,
                'empty_results': 4, 'public_accessible': 5, 'authenticated_accessible': 6}
    for page in pages:
        client = None
        try:
            client = CdpClient.connect_first_page(endpoint, HOSTS[platform], target_id=page.get('id'))
            state = {**inspect_page(client, platform), 'target_id': page.get('id')}
        except (CdpError, OSError, TimeoutError):
            state = {**_unavailable('page_error', 'inspection_failed'), 'target_id': page.get('id')}
        finally:
            if client:
                client.close()
        # Never bypass a manual access gate by choosing another same-platform tab.
        if state['access_state'] in _BLOCKED:
            return state
        if target_id and page.get('id') != target_id:
            continue
        if target_url and not _same_search_target(state.get('search_url', ''), target_url):
            state.update(access_state='page_error', can_collect=False, reason='target_page_redirected')
        if priority.get(state['access_state'], 0) > priority.get(best['access_state'], 0):
            best = state
    return best


def status(endpoint='http://127.0.0.1:9333', user_data_dir=None, platform=None,
           target_url: str | None = None, target_id: str | None = None) -> dict:
    if endpoint != 'auto':
        validate_endpoint(endpoint)
    profile = _profile(user_data_dir)
    result = {'endpoint': endpoint, 'reachable': False, 'platform_pages': dict.fromkeys(HOSTS, 0),
              'platform_access': {key: _unavailable() for key in HOSTS}, 'page_targets': []}
    try:
        actual = _owned_endpoint(profile, _edge_sessions())
        if actual:
            result['endpoint'] = actual
            targets = _page_targets(actual)
            result['reachable'] = True
            result['page_targets'] = [{'url': t.get('url', ''), 'title': t.get('title', ''), 'type': 'page'} for t in targets]
            for key, host in HOSTS.items():
                pages = [t for t in targets if host_matches(str(t.get('url', '')), host)]
                result['platform_pages'][key] = len(pages)
                result['platform_access'][key] = _unavailable('page_missing', 'target_page_missing')
                if pages:
                    bound_id = target_id if key == platform else None
                    bound_url = target_url if key == platform else None
                    if key == platform and bound_id is None:
                        prepared_url, prepared_id = _PREPARED_TARGETS.get((str(profile), key), ('', ''))
                        bound_id = prepared_id or None
                        bound_url = bound_url or prepared_url or None
                    if key == platform and bound_url and bound_id is None:
                        matching = [page for page in pages if _same_search_target(str(page.get('url', '')), bound_url)]
                        if len(matching) == 1:
                            bound_id = matching[0].get('id')
                        elif len(pages) == 1:
                            bound_id = pages[0].get('id')
                    result['platform_access'][key] = _inspect_targets(
                        actual, pages, key, target_id=bound_id, target_url=bound_url)
    except (CdpError, OSError, ValueError, subprocess.SubprocessError, httpx.HTTPError):
        result['error'] = '无法核实受控 Edge 或读取 CDP 状态'
    result['boss_page_count'] = result['platform_pages']['boss']
    result['platform_login_required'] = {key: value['access_state'] == 'login_required'
                                         for key, value in result['platform_access'].items()}
    result['login_required'] = result['platform_login_required']['boss']
    return result


def prepare(platform='boss', endpoint='http://127.0.0.1:9333', user_data_dir=None,
            timeout=20.0, wait_for_login=0.0, url=None) -> dict:
    if platform not in HOSTS:
        raise ValueError('platform 必须为 boss、zhaopin 或 liepin')
    if timeout < 0 or wait_for_login < 0:
        raise ValueError('浏览器等待时间不能为负数')
    if endpoint != 'auto':
        validate_endpoint(endpoint)
    profile = _profile(user_data_dir)
    target = url or ENTRY_URLS[platform]
    if (not host_matches(target, HOSTS[platform]) or urlsplit(target).scheme != 'https'
            or urlsplit(target).username is not None or urlsplit(target).password is not None):
        raise ValueError('目标 URL 必须属于指定平台')
    deadline = time.monotonic() + timeout
    base = {'endpoint': endpoint, 'user_data_dir': str(profile), 'platform': platform,
            'timed_out': False, 'target_url': _search_target(target)}
    try:
        with _LOCK:
            sessions = _edge_sessions()
            if not any(Path(s['profile']).resolve() == profile for s in sessions):
                _launch_edge(profile)
            while True:
                actual = _owned_endpoint(profile, _edge_sessions())
                if actual:
                    try:
                        targets = _page_targets(actual)
                        break
                    except (httpx.HTTPError, ValueError):
                        pass
                if time.monotonic() >= deadline:
                    return {**base, **_unavailable('starting', 'edge_start_timeout'), 'timed_out': True}
                time.sleep(.5)
            base['endpoint'] = actual
            target_id = None
            matches = [t for t in targets if host_matches(str(t.get('url', '')), HOSTS[platform])]
            if url:
                previous_url, previous_id = _PREPARED_TARGETS.get((str(profile), platform), ('', ''))
                pinned = [t for t in matches if previous_url == target and t.get('id') == previous_id]
                existing = _inspect_targets(
                    actual, pinned or matches, platform,
                    target_id=previous_id if pinned else None)
                if existing['access_state'] in _BLOCKED:
                    return {**base, **existing}
                matches = pinned or [t for t in matches if _same_search_target(str(t.get('url', '')), target)]
            if not matches:
                created = _create_page(actual, target) or {}
                # Default preparation follows manual login into a new same-platform tab.
                target_id = created.get('id') if url else None
            elif url:
                target_id = matches[0].get('id')
            if url:
                if not target_id:
                    return {**base, **_unavailable('page_missing', 'target_page_missing')}
                _PREPARED_TARGETS[(str(profile), platform)] = (target, target_id)
        login_deadline = None
        while True:
            try:
                state = _inspect_targets(actual, _page_targets(actual), platform, target_id, target if url else None)
            except (CdpError, OSError, TimeoutError, httpx.HTTPError):
                state = _unavailable('loading', 'page_not_ready')
            if state['can_collect'] or state['access_state'] in {'verification_required', 'content_limited'}:
                return {**base, **state}
            if state['access_state'] == 'login_required':
                if not wait_for_login:
                    return {**base, **state}
                if login_deadline is None:
                    print(f'[{platform}] 请在独立 Edge 中人工登录；仅等待恢复准备状态，不启动采集', flush=True)
                    login_deadline = time.monotonic() + wait_for_login
            end = login_deadline if login_deadline is not None else deadline
            if time.monotonic() >= end:
                return {**base, **state, 'timed_out': True}
            time.sleep(.5)
    except (CdpError, OSError, ValueError, subprocess.SubprocessError, httpx.HTTPError):
        return {**base, **_unavailable(reason='edge_or_cdp_error')}


def ensure_ready(platform: str, endpoint: str, user_data_dir: str | None, **kwargs) -> dict:
    state = prepare(platform, endpoint, user_data_dir, **kwargs)
    if not state['can_collect']:
        raise CdpError(f"{platform}: {state['access_state']} ({state['reason']})")
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description='仅准备独立 Edge 和检查页面访问，不采集、不连接数据库')
    parser.add_argument('--platform', choices=HOSTS, default='boss')
    parser.add_argument('--cdp', default='auto')
    parser.add_argument('--user-data-dir')
    parser.add_argument('--browser-timeout', type=float, default=20)
    parser.add_argument('--login-timeout', type=float, default=0)
    args = parser.parse_args()
    result = prepare(args.platform, args.cdp, args.user_data_dir, args.browser_timeout, args.login_timeout)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['can_collect'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
