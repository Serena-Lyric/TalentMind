"""Offline browser runtime contracts; fake only OS/CDP/time boundaries."""
import importlib
import sys
import builtins
import json
import shutil
import subprocess

import pytest


def runtime():
    return importlib.import_module('app.collect.browser')


def snapshot(**kw):
    return {**dict(url='https://www.liepin.com/zhaopin/', ready_state='complete',
                   cards=0, details=0, text='', gate_text='', authenticated=False), **kw}


@pytest.mark.parametrize('changes,state,can_collect', [
    ({}, 'page_error', False),
    ({'ready_state': 'loading'}, 'loading', False),
    ({'cards': 3, 'text': '登录 注册 Python'}, 'public_accessible', True),
    ({'details': 1}, 'public_accessible', True),
    ({'cards': 2, 'authenticated': True}, 'authenticated_accessible', True),
    ({'text': '登录后查看职位'}, 'login_required', False),
    ({'cards': 2, 'gate_text': '请完成安全验证'}, 'verification_required', False),
    ({'text': '暂无搜索结果'}, 'empty_results', True),
    ({'url': 'https://passport.liepin.com/login'}, 'login_required', False),
    ({'url': 'https://www.liepin.com/security-check'}, 'verification_required', False),
    ({'url': 'https://liepin.com.evil.test/', 'cards': 3}, 'page_error', False),
    ({'text': '访问过于频繁', 'cards': 2}, 'verification_required', False),
    ({'text': '页面加载失败', 'cards': 2}, 'page_error', False),
])
def test_page_state_requires_positive_evidence(changes, state, can_collect):
    page = snapshot()
    page.update(changes)
    result = runtime().classify_page(page, 'liepin')
    assert result['access_state'] == state
    assert result['can_collect'] is can_collect
    if state == 'public_accessible':
        assert result['authentication'] == 'unknown'


@pytest.fixture
def browser_env(monkeypatch, tmp_path):
    b = runtime()
    profile = tmp_path / 'private-profile'
    sessions = []
    targets = []
    launches = []
    snapshots = [snapshot(cards=3)]
    now = [0.0]
    monkeypatch.setattr(b, '_edge_sessions', lambda: sessions)
    monkeypatch.setattr(b, '_page_targets', lambda endpoint: list(targets))
    def launch(user_data_dir):
        launches.append(user_data_dir)
        user_data_dir.mkdir(parents=True, exist_ok=True)
        (user_data_dir / 'DevToolsActivePort').write_text('19444\n/devtools/browser/synthetic\n')
        sessions.append({'pid': 123, 'profile': str(user_data_dir), 'port': 0,
                         'listeners': [{'port': 19444, 'address': '127.0.0.1'}]})
        return 123
    monkeypatch.setattr(b, '_launch_edge', launch)
    class Client:
        def evaluate(self, script):
            return snapshots.pop(0) if len(snapshots) > 1 else snapshots[0]
        def close(self): pass
    monkeypatch.setattr(b.CdpClient, 'connect_first_page', lambda *a, **kw: Client())
    def create(endpoint, url):
        target={'id': 'target', 'type': 'page', 'url': url, 'webSocketDebuggerUrl': 'ws://127.0.0.1:19444/devtools/page/target'}
        targets.append(target)
        return target
    monkeypatch.setattr(b, '_create_page', create)
    monkeypatch.setattr(b.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(b.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + max(seconds, .1)))
    return b, profile, sessions, targets, launches, snapshots


def test_first_prepare_launches_dynamic_edge_and_repeated_prepare_reuses(browser_env):
    b, profile, _, targets, launches, _ = browser_env
    for _ in range(2):
        result = b.prepare('liepin', user_data_dir=str(profile), timeout=2)
        assert result['access_state'] == 'public_accessible'
        assert result['endpoint'] == 'http://127.0.0.1:19444'
    assert len(launches) == 1
    assert len(targets) == 1


def test_prepare_waits_for_manual_login_and_returns_ready_without_collecting(browser_env):
    b, profile, _, _, _, pages = browser_env
    pages[:] = [snapshot(text='请先登录'), snapshot(cards=2, authenticated=True)]
    result = b.prepare('liepin', user_data_dir=str(profile), timeout=2, wait_for_login=3)
    assert result['access_state'] == 'authenticated_accessible'


def test_verification_blocks_immediately_without_polling_through(browser_env):
    b, profile, _, _, _, pages = browser_env
    pages[:] = [snapshot(gate_text='验证码 安全验证'), snapshot(cards=2)]
    result = b.prepare('liepin', user_data_dir=str(profile), timeout=2, wait_for_login=30)
    assert result['access_state'] == 'verification_required'
    assert len(pages) == 1


def test_timeout_can_recover_on_next_prepare_without_second_launch(browser_env):
    b, profile, _, _, launches, pages = browser_env
    pages[:] = [snapshot(ready_state='loading')]
    result = b.prepare('liepin', user_data_dir=str(profile), timeout=1)
    assert result['access_state'] == 'loading'
    assert result['timed_out'] is True
    pages[:] = [snapshot(cards=1)]
    assert b.prepare('liepin', user_data_dir=str(profile), timeout=1)['can_collect']
    assert len(launches) == 1


def test_stale_active_port_cannot_adopt_unrelated_session(browser_env):
    b, profile, sessions, targets, launches, _ = browser_env
    profile.mkdir()
    (profile / 'DevToolsActivePort').write_text('19444\n/devtools/browser/old\n')
    sessions.append({'pid': 999, 'profile': str(profile.parent / 'daily'), 'port': 19444})
    targets.append({'type': 'page', 'url': 'https://www.liepin.com/'})
    assert b.prepare('liepin', user_data_dir=str(profile), timeout=1)['can_collect']
    assert len(launches) == 1


def test_no_target_page_is_not_login_or_authenticated(browser_env):
    b, profile, _, _, _, _ = browser_env
    result = b.status(user_data_dir=str(profile))
    assert result['reachable'] is False
    assert result['platform_access']['boss']['can_collect'] is False
    assert result['platform_access']['boss']['access_state'] == 'cdp_unavailable'


@pytest.mark.parametrize('module,args', [
    ('app.collect.fetch_boss_jobs', ['--prepare-only']),
    ('app.collect.fetch_cn_jobs', ['--platform','liepin','--prepare-only']),
])
def test_cli_prepare_only_does_not_call_fetch_or_import_database(monkeypatch, module, args):
    mod = importlib.import_module(module)
    def forbidden(*a, **kw): pytest.fail('prepare-only called collection')
    monkeypatch.setattr(mod, 'run_fetch', forbidden)
    # Intercept the shared browser boundary; CLI still runs its real argument parsing.
    monkeypatch.setattr(runtime(), 'prepare', lambda *a, **kw: {'access_state':'login_required','can_collect':False})
    monkeypatch.setattr(sys, 'argv', [module, *args])
    assert mod.main() == 2


def test_real_prepare_path_never_imports_database(browser_env, monkeypatch):
    b, profile, _, _, _, _ = browser_env
    original = builtins.__import__
    def no_db(name, *args, **kwargs):
        if name == 'app.db' or name.startswith('app.db.'):
            pytest.fail('Browser preparation imported database layer')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', no_db)
    assert b.prepare('liepin', user_data_dir=str(profile), timeout=1)['can_collect']


@pytest.mark.parametrize('platform,url', [('boss','https://www.zhipin.com/web/geek/jobs'),
                                          ('zhaopin','https://www.zhaopin.com/jobs'),
                                          ('liepin','https://www.liepin.com/zhaopin/')])
def test_all_platforms_allow_visible_public_content_without_login(platform, url):
    result = runtime().classify_page(snapshot(url=url, cards=1, text='登录 注册'), platform)
    assert result['access_state'] == 'public_accessible'
    assert result['can_collect']


def test_dynamic_file_without_matching_live_listener_is_never_trusted(browser_env):
    b, profile, sessions, _, _, _ = browser_env
    profile.mkdir()
    (profile/'DevToolsActivePort').write_text('19444\n/devtools/browser/stale\n')
    sessions.append({'pid':1, 'profile':str(profile), 'port':0,
                     'listeners':[{'port':19445,'address':'127.0.0.1'}]})
    result = b.prepare('liepin', user_data_dir=str(profile), timeout=1)
    assert result['access_state'] == 'starting'
    assert not result['can_collect']


def test_non_loopback_listener_cannot_be_reused(browser_env):
    b, profile, sessions, _, _, _ = browser_env
    sessions.append({'pid':1,'profile':str(profile),'port':19444,
                     'listeners':[{'port':19444,'address':'0.0.0.0'}]})
    assert not b.prepare('liepin', user_data_dir=str(profile), timeout=1)['can_collect']


def test_target_missing_opens_own_tab_without_navigating_other_platform(browser_env):
    b, profile, _, targets, _, _ = browser_env
    targets.append({'type':'page','url':'https://www.zhipin.com/web/geek/jobs'})
    assert b.prepare('liepin', user_data_dir=str(profile), timeout=1)['can_collect']
    assert len(targets) == 2
    assert targets[0]['url'] == 'https://www.zhipin.com/web/geek/jobs'


def test_new_edge_launch_uses_dynamic_loopback_and_independent_profile(browser_env, monkeypatch, tmp_path):
    b, profile, _, _, _, _ = browser_env
    # Exercise the real launcher separately from the fake used for lifecycle tests.
    import runpy
    launch = runpy.run_path(b.__file__)['_launch_edge']
    executable = tmp_path/'Microsoft/Edge/Application/msedge.exe'
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setenv('ProgramFiles(x86)',str(tmp_path))
    commands=[]
    monkeypatch.setattr(b.subprocess,'Popen', lambda args, **kwargs: commands.append(args) or type('P',(),{'pid':7})())
    assert launch(profile) == 7
    assert '--remote-debugging-port=0' in commands[0]
    assert '--remote-debugging-address=127.0.0.1' in commands[0]
    assert f'--user-data-dir={profile}' in commands[0]


def test_manual_login_timeout_recovers_without_restarting(browser_env):
    b, profile, _, _, launches, pages = browser_env
    pages[:] = [snapshot(text='请先登录')]
    result = b.prepare('liepin', user_data_dir=str(profile), timeout=1, wait_for_login=2)
    assert result['access_state'] == 'login_required' and result['timed_out']
    pages[:] = [snapshot(cards=2, authenticated=True)]
    assert b.prepare('liepin', user_data_dir=str(profile), timeout=1)['access_state']=='authenticated_accessible'
    assert len(launches)==1


def test_visible_verification_on_detail_stops_before_extraction(browser_env):
    b, _, _, _, _, pages = browser_env
    class Client:
        def evaluate(self, script): return snapshot(cards=3,gate_text='安全验证')
    with pytest.raises(b.AccessBlocked,match='verification_required'):
        b.wait_access(Client(),'liepin',timeout=1)


def test_boss_gate_prevents_database_open(monkeypatch):
    from app.collect import fetch_boss_jobs as boss
    def blocked(*a,**kw): raise runtime().AccessBlocked('synthetic gate')
    monkeypatch.setattr(runtime(),'ensure_ready',blocked)
    with pytest.raises(runtime().AccessBlocked):
        boss.run_fetch(['Python'],[('北京','101010100')])


def test_sms_login_code_is_login_not_challenge():
    result=runtime().classify_page(snapshot(gate_text='手机号登录 获取验证码 登录/注册'),'liepin')
    assert result['access_state']=='login_required'


def test_challenge_iframe_over_cards_blocks_access():
    result=runtime().classify_page(snapshot(cards=2,challenge_visible=True),'liepin')
    assert result['access_state']=='verification_required'


@pytest.mark.parametrize('text', ['负责安全验证系统开发', '处理服务异常与网络异常，开发验证服务'])
def test_job_description_words_do_not_masquerade_as_access_gate(text):
    assert runtime().classify_page(snapshot(details=1,text=text),'liepin')['can_collect']


def test_login_frame_over_existing_cards_blocks_access():
    result=runtime().classify_page(snapshot(cards=2,login_visible=True),'liepin')
    assert result['access_state']=='login_required'


def test_os_query_ignores_renderer_processes_and_uses_one_listener_inventory(monkeypatch):
    b=runtime()
    rows=[{'pid':1,'command':'msedge.exe --remote-debugging-port=0 --user-data-dir=C:/private',
           'listeners':[{'port':19444,'address':'127.0.0.1'}]},
          {'pid':2,'command':'msedge.exe --type=renderer --remote-debugging-port=0 --user-data-dir=C:/private','listeners':[]}]
    def run(args,**kwargs):
        return type('Done',(),{'returncode':0,'stdout':json.dumps(rows)})()
    monkeypatch.setattr(b.subprocess,'run',run)
    assert b._edge_sessions()==[{'pid':1,'profile':'C:/private','port':0,
                                'listeners':[{'port':19444,'address':'127.0.0.1'}]}]


def test_returned_ready_target_is_pinned_for_collection(browser_env):
    b,profile,_,targets,_,pages=browser_env
    targets.extend([{'id':'old','type':'page','url':'https://passport.liepin.com/login'},
                    {'id':'ready','type':'page','url':'https://www.liepin.com/zhaopin/'}])
    class Client:
        def __init__(self,target): self.target=target
        def evaluate(self,script):
            return snapshot(text='请先登录') if self.target=='old' else snapshot(cards=2)
        def close(self):pass
    b.CdpClient.connect_first_page=lambda *a,**kw: Client(kw.get('target_id','old'))
    state=b.prepare('liepin',user_data_dir=str(profile),timeout=1)
    assert state['can_collect'] and state['target_id']=='ready'


def dom_snapshot(platform, elements):
    node=shutil.which('node')
    if not node:
        pytest.skip('Node is needed to execute synthetic DOM snapshot JavaScript')
    # Execute the real browser script with a minimal synthetic visible DOM and no network APIs.
    script=r'''
const vm=require('node:vm'); let input='';
process.stdin.on('data',d=>input+=d); process.stdin.on('end',()=>{
 const p=JSON.parse(input), all=p.elements.map(n=>({...n,innerText:n.text||'',
  getBoundingClientRect:()=>({width:n.hidden?0:200,height:100})}));
 const document={readyState:'complete',body:{innerText:all.filter(n=>!n.hidden).map(n=>n.text||'').join('\n')},
  querySelectorAll:s=>all.filter(n=>s.split(',').some(x=>n.selector===x.trim()))};
 const value=vm.runInNewContext(p.script,{document,location:{href:p.url},getComputedStyle:n=>({display:'block',visibility:'visible'})});
 process.stdout.write(JSON.stringify(value));
});'''
    result=subprocess.run([node,'-e',script],input=json.dumps({'script':runtime()._snapshot_js(platform),
        'elements':elements,'url':'https://www.zhipin.com/web/geek/jobs' if platform=='boss' else 'https://www.liepin.com/'}),
        capture_output=True,text=True,encoding='utf-8',check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize('selector,field', [('.job-card','cards'),('.job-list-box','cards'),
                                           ('.job-detail','details'),('.job-detail-section','details')])
def test_actual_boss_dom_script_accepts_existing_extractor_selectors(selector,field):
    page=dom_snapshot('boss',[{'selector':selector,'text':'负责 Python 后端服务开发与维护'}])
    assert page[field]==1
    assert runtime().classify_page(page,'boss')['can_collect']


@pytest.mark.parametrize('src,state', [('https://passport.liepin.com/login','login_required'),
                                      ('https://www.liepin.com/security-check','verification_required')])
def test_actual_dom_script_detects_visible_frame_covering_old_cards(src,state):
    page=dom_snapshot('liepin',[{'selector':'.job-card','text':'负责 Python 后端服务开发与维护'},
                              {'selector':'iframe','src':src}])
    assert runtime().classify_page(page,'liepin')['access_state']==state


def test_hidden_challenge_frame_does_not_block_visible_public_content():
    page=dom_snapshot('liepin',[{'selector':'.job-card','text':'负责 Python 后端服务开发与维护'},
                              {'selector':'iframe','src':'https://www.liepin.com/security-check','hidden':True}])
    assert runtime().classify_page(page,'liepin')['can_collect']


def test_actual_liepin_current_camelcase_cards_are_publicly_accessible():
    page=dom_snapshot('liepin',[{'selector':'.jobCardPcContainer','text':'负责 Python 后端服务开发与维护'}])
    assert runtime().classify_page(page,'liepin')['can_collect']


def test_guest_partial_detail_is_reported_separately_from_public_list_access():
    result=runtime().classify_page(snapshot(cards=3,details=1,content_limited=True),'liepin')
    assert result['can_collect'] and result['content_limited'] is True


def test_login_gate_after_old_error_uses_manual_login_deadline(browser_env,monkeypatch):
    b,profile,_,targets,_,_=browser_env
    targets.extend([{'id':'old','type':'page','url':'https://www.liepin.com/old'},
                    {'id':'login','type':'page','url':'https://passport.liepin.com/login'}])
    class Client:
        def __init__(self,target):self.target=target
        def evaluate(self,script):
            if self.target=='old':return snapshot()
            return snapshot(cards=1,authenticated=True) if b.time.monotonic()>=3 else snapshot(text='请先登录')
        def close(self):pass
    monkeypatch.setattr(b.CdpClient,'connect_first_page',lambda *a,**kw:Client(kw.get('target_id')))
    state=b.prepare('liepin',user_data_dir=str(profile),timeout=1,wait_for_login=5)
    assert state['access_state']=='authenticated_accessible' and state['target_id']=='login'


def test_new_ready_tab_is_found_after_initial_created_tab_stays_unknown(browser_env,monkeypatch):
    b,profile,_,targets,_,_=browser_env
    original=b._page_targets
    def target_list(endpoint):
        if b.time.monotonic()>=.5 and not any(t['id']=='new' for t in targets):
            targets.append({'id':'new','type':'page','url':'https://www.liepin.com/zhaopin/'})
        return original(endpoint)
    class Client:
        def __init__(self,target):self.target=target
        def evaluate(self,script):return snapshot(cards=2) if self.target=='new' else snapshot()
        def close(self):pass
    monkeypatch.setattr(b,'_page_targets',target_list)
    monkeypatch.setattr(b.CdpClient,'connect_first_page',lambda *a,**kw:Client(kw.get('target_id')))
    state=b.prepare('liepin',user_data_dir=str(profile),timeout=2)
    assert state['can_collect'] and state['target_id']=='new'
