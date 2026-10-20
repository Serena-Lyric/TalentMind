"""Controller and historical-loop compatibility; all services remain synthetic."""
from io import StringIO
from contextlib import closing
import os
import sqlite3
import threading

import pytest
from websockets.exceptions import WebSocketException

from app.collect import control, boss_collect_loop as boss_loop, cn_collect_loop as cn_loop
from app.collect.fetchers import cdp
from app.config import Settings


@pytest.fixture
def isolated_control(tmp_path,monkeypatch):
    from app import config
    settings=Settings(_env_file=None,mysql_url='mysql+pymysql://fixture:fixture@127.0.0.1:1/offline',
        neo4j_uri='bolt://127.0.0.1:1',neo4j_user='fixture',neo4j_password='fixture',
        redis_url='redis://127.0.0.1:1',openai_api_key='fixture',
        openai_base_url='http://127.0.0.1:1',github_token='')
    monkeypatch.setattr(config,'get_settings',lambda:settings)
    monkeypatch.setattr(control,'_STATE_DIR',tmp_path/'collection')
    monkeypatch.setattr(control,'_STATE_PATH',tmp_path/'collection/state.json')
    monkeypatch.setattr(control,'_PROCESS',None)
    monkeypatch.setattr(control,'_ensure_browser',lambda endpoint,profile,platform:{
        'endpoint':'http://127.0.0.1:19444','user_data_dir':str(tmp_path/'profile'),
        'platform_access':{platform:{'can_collect':True,'access_state':'public_accessible'}}})
    return tmp_path


def test_controller_preserves_historical_custom_template_and_once_limit(isolated_control,monkeypatch):
    launched=[]
    class Process:
        pid=77
        def __init__(self,args,**kw):launched.append((args,kw))
        def poll(self):return None
    class Thread:
        def __init__(self,*a,**kw):pass
        def start(self):pass
    monkeypatch.setattr(control.subprocess,'Popen',Process)
    monkeypatch.setattr(control.threading,'Thread',Thread)
    template='https://www.liepin.com/zhaopin/?city={city}&dq={city}&currentPage={page}&key={keyword}'
    assert control.update_config({'search_url_template':template})['search_url_template']==template
    control.start_task({'platform':'liepin','mode':'once','keywords':['Python'],
                        'cities':[{'name':'北京','code':'010'}],'pages':1,'max_jobs':5,'detail_limit':5})
    args,_=launched[0]
    assert args[args.index('--search-url-template')+1]==template
    assert '--once' in args and '--forever' not in args
    assert args[args.index('--cdp')+1]=='http://127.0.0.1:19444'
    assert args[args.index('--max-jobs')+1]=='5'


def test_worker_receives_resolved_parent_settings_instead_of_unresolved_env(isolated_control,monkeypatch):
    from app import config
    settings=Settings(_env_file=None,mysql_url='mysql+pymysql://fixture:fixture@127.0.0.1:9/offline_parent',
        neo4j_uri='bolt://127.0.0.1:1',neo4j_user='fixture',neo4j_password='fixture',
        redis_url='redis://127.0.0.1:1',openai_api_key='fixture')
    monkeypatch.setattr(config,'get_settings',lambda:settings)
    monkeypatch.setenv('MYSQL_URL','mysql+pymysql://fixture:fixture@127.0.0.1:1/stale_env')
    monkeypatch.delenv('PYTHONIOENCODING',raising=False)
    monkeypatch.delenv('PYTHONUTF8',raising=False)
    launched=[]
    class Process:
        pid=88
        def __init__(self,args,**kw):launched.append(kw)
        def poll(self):return None
    class Thread:
        def __init__(self,*a,**kw):pass
        def start(self):pass
    monkeypatch.setattr(control.subprocess,'Popen',Process)
    monkeypatch.setattr(control.threading,'Thread',Thread)
    control.start_task({'platform':'liepin','mode':'once'})
    assert launched[0]['env']['MYSQL_URL']==settings.mysql_url
    assert launched[0]['env']['PYTHONIOENCODING']=='utf-8'
    assert launched[0]['env']['PYTHONUTF8']=='1'


def test_quality_counts_and_gate_reason_survive_controller_history(isolated_control):
    state=control._default_state()
    state['current_task']=control._empty_task('synthetic',state['config'])
    control._save_state(state)
    payload={'platform':'liepin','listed':3,'details':2,'new':1,'skipped':0,
        'detail_attempted':2,'detail_obtained':1,'complete':1,'inserted':1,'updated':0,
        'rejected':0,'failed':1,'unattempted':1,'stop_reason':'verification_required'}
    line='liepin 第 1 轮完成: '+repr(payload)
    control._parse_log_line('synthetic',line)
    task=control._load_state()['current_task']
    assert task['complete']==1 and task['detail_attempted']==2 and task['failed']==1
    assert task['status']=='error' and task['errors']==1 and task['last_error']=='verification_required'
    log=isolated_control/'liepin_collect_loop.out.log'
    log.write_text(line,encoding='utf-8')
    summary=control._summarize_log(log)
    assert summary['status']=='error' and summary['complete']==1 and summary['failed']==1
    assert summary['last_error']=='verification_required'


@pytest.mark.parametrize('platform',['boss','liepin'])
@pytest.mark.parametrize('reason',['verification_required','login_required','page_error'])
def test_historical_loops_stop_typed_access_gates_without_sleep(platform,reason):
    def fetch(*a,**kw):raise cdp.CdpError(reason)
    def sleep(seconds):pytest.fail('Access block must not fall through to another round')
    args=dict(cdp_endpoint='http://127.0.0.1:9333',user_data_dir=None,
              rounds=0,fetcher=fetch,sleeper=sleep)
    if platform=='boss':result=boss_loop.run_loop([boss_loop.QueryTarget('Python','北京','101010100')],**args)
    else:result=cn_loop.run_loop('liepin',[cn_loop.QueryTarget('Python','北京','010')],**args)
    assert result==2


@pytest.mark.parametrize('platform',['boss','liepin'])
def test_once_business_error_is_not_reported_as_success(platform):
    def fetch(*a,**kw):raise RuntimeError('synthetic persistence failure')
    def sleep(seconds):pytest.fail('Once must never sleep for another round')
    args=dict(cdp_endpoint='http://127.0.0.1:9333',user_data_dir=None,rounds=1,fetcher=fetch,sleeper=sleep)
    if platform=='boss':result=boss_loop.run_loop([boss_loop.QueryTarget('Python','北京','101010100')],**args)
    else:result=cn_loop.run_loop('liepin',[cn_loop.QueryTarget('Python','北京','010')],**args)
    assert result!=0


def test_websocket_close_is_a_typed_cdp_failure_for_legacy_loops(monkeypatch):
    class Socket:
        def send(self,value):pass
        def recv(self,**kwargs):raise WebSocketException('synthetic closed')
        def close(self):pass
    monkeypatch.setattr(cdp,'connect',lambda *a,**kw:Socket())
    client=cdp.CdpClient('ws://127.0.0.1:9333/devtools/page/synthetic')
    try:
        with pytest.raises(cdp.CdpError):client.call('Runtime.evaluate',{'expression':'document.readyState'})
    finally:client.close()


def test_real_controller_child_once_pipeline_and_watcher_history(isolated_control,monkeypatch):
    area=isolated_control
    database=area/'worker.sqlite3'
    hook=area/'hook';hook.mkdir()
    child_guard=r'''
import os,sys
def record(event):
    path=os.environ.get('M3_OFFLINE_AUDIT')
    if path:
        with open(path,'a',encoding='utf-8') as stream:stream.write(str(os.getpid())+' '+event+'\n')
record('loaded')
def deny_network(event,args):
    if event=='subprocess.Popen':
        record('blocked:'+event)
        raise RuntimeError('Synthetic worker cannot start native helpers or browsers')
    if event in {'socket.connect','socket.connect_ex','socket.bind','socket.sendto','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr'}:
        record('blocked:'+event)
        raise RuntimeError('Synthetic controller worker prohibits network and database services')
sys.addaudithook(deny_network)
'''
    child_setup=r'''
from datetime import datetime
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from app.collect import fetch_cn_jobs as cn
from app.db import mysql
engine=create_engine('sqlite:///'+os.environ['M1_SYNTHETIC_DB'])
@event.listens_for(engine,'before_cursor_execute',retval=True)
def parameters(conn,cursor,sql,params,ctx,many):
    return sql,tuple(x.isoformat() if isinstance(x,datetime) else x for x in params)
with engine.begin() as db:
    db.exec_driver_sql('CREATE TABLE jd_pool (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, source_detail TEXT, job_title TEXT, raw_text TEXT, duties TEXT, experience TEXT, quality FLOAT, dup_group TEXT, crawled_at DATETIME, status TEXT)')
def provider():
    with Session(engine) as db:yield db
mysql.get_db=provider
cn.browser.ensure_ready=lambda *a,**kw:{'endpoint':'http://127.0.0.1:19444','target_id':'synthetic'}
cn.browser.wait_access=lambda *a,**kw:{'can_collect':True,'content_limited':False}
cn.fetch_search_page=lambda *a,**kw:[{'url':'https://www.liepin.com/job/synthetic-1','title':'Synthetic Python role'}]
class Client:
    def navigate(self,*a,**kw):pass
    def evaluate(self,script):
        return {'url':'https://www.liepin.com/job/synthetic-1','title':'Synthetic Python role',
                'description':'Responsibilities:\nBuild Python services\nRequirements:\nKnow SQL'}
    def close(self):pass
cn.CdpClient.connect_first_page=lambda *a,**kw:Client()
'''
    (hook/'sitecustomize.py').write_text(child_guard+'\n'+child_setup,encoding='utf-8')
    monkeypatch.setenv('PYTHONPATH',str(hook)+os.pathsep+os.environ.get('PYTHONPATH',''))
    monkeypatch.setenv('M1_SYNTHETIC_DB',str(database))
    threads=[]
    processes=[]
    original_popen=control.subprocess.Popen
    def spawn(*args,**kwargs):
        process=original_popen(*args,**kwargs);processes.append(process);return process
    monkeypatch.setattr(control.subprocess,'Popen',spawn)
    original_thread=threading.Thread
    def track(*args,**kwargs):
        result=original_thread(*args,**kwargs);threads.append(result);return result
    monkeypatch.setattr(control.threading,'Thread',track)
    process=None
    try:
        launched=control.start_task({'platform':'liepin','mode':'once','keywords':['Python'],
            'cities':[{'name':'Synthetic','code':'010'}],'pages':1,'max_jobs':5,'detail_limit':5,
            'page_delay_min':0,'page_delay_max':0,'settle_min':0,'settle_max':0})
        process=processes[0]
        assert process.wait(timeout=15)==0
        threads[0].join(timeout=10)
        assert not threads[0].is_alive()
        state=control._load_state()
        task=state['current_task']
        assert task['run_id']==launched['run_id'] and task['status']=='completed'
        assert task['complete']==1 and task['inserted']==1 and task['detail_attempted']==1
        assert task['quality_metrics_available'] is True
        assert state['history'][0]['complete']==1 and state['history'][0]['mode']=='once'
        with closing(sqlite3.connect(database)) as db:
            rows=db.execute('SELECT source,raw_text,duties FROM jd_pool').fetchall()
        assert len(rows)==1 and rows[0][0]=='liepin'
        assert 'Build Python services\nRequirements:' in rows[0][1]
        assert 'Build Python services' in rows[0][2] and 'Know SQL' not in rows[0][2]
    finally:
        if process is not None and process.poll() is None:
            process.terminate();process.wait(timeout=5)
        for thread in threads:thread.join(timeout=5)
        database.unlink(missing_ok=True)
        assert not database.exists()


def test_watcher_retains_explicit_gate_error_even_if_worker_exits_zero(isolated_control):
    state=control._default_state()
    state['current_task']=control._empty_task('synthetic',state['config'])
    control._save_state(state)
    class Worker:
        stdout=StringIO("liepin 第 1 轮完成: {'listed': 0, 'details': 0, 'new': 0, 'stop_reason': 'verification_required'}\n")
        def wait(self):return 0
    control._watch_process('synthetic',Worker())
    history=control._load_state()['history'][0]
    assert history['status']=='error' and history['last_error']=='verification_required'


def test_real_cdp_close_reaches_loop_stop_instead_of_generic_retry(monkeypatch):
    class Socket:
        def send(self,value):pass
        def recv(self,**kwargs):raise WebSocketException('synthetic closed')
        def close(self):pass
    monkeypatch.setattr(cdp,'connect',lambda *a,**kw:Socket())
    def fetch(*a,**kw):
        client=cdp.CdpClient('ws://127.0.0.1:9333/devtools/page/synthetic')
        try:client.call('Runtime.evaluate')
        finally:client.close()
    result=cn_loop.run_loop('liepin',[cn_loop.QueryTarget('Python','北京','010')],
        cdp_endpoint='http://127.0.0.1:9333',user_data_dir=None,rounds=0,fetcher=fetch,
        sleeper=lambda _:pytest.fail('CDP close must not trigger another round'))
    assert result==2
