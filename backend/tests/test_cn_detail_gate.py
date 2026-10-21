"""Real CN orchestration against synthetic CDP and isolated temporary SQLite."""
from datetime import datetime
import json
import shutil
import subprocess

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from websockets.exceptions import WebSocketException

from app.collect import fetch_cn_jobs as cn
from app.collect.fetchers.job_sites import SITES, build_detail_extract_js, normalize_job
from app.collect.cleaner import clean


def card(n):
    return {'url':f'https://www.liepin.com/job/synthetic-{n}', 'title':f'Python合成岗位{n}', 'tags':['Python']}


def detail(n, **kw):
    return {'url':card(n)['url'], 'title':card(n)['title'],
            'description':'岗位职责：\n负责 Python 服务开发\n任职要求：\n熟悉 SQL 和 Docker', **kw}


@pytest.fixture
def offline(monkeypatch,tmp_path):
    from app.db import mysql
    path=tmp_path/'cn-detail.sqlite3'
    engine=create_engine('sqlite:///'+str(path))
    @event.listens_for(engine,'before_cursor_execute',retval=True)
    def dates(conn,cursor,stmt,params,ctx,many):
        return stmt,tuple(x.isoformat() if isinstance(x,datetime) else x for x in params)
    with engine.begin() as db:
        db.exec_driver_sql('CREATE TABLE jd_pool (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, source_detail TEXT, job_title TEXT, raw_text TEXT, duties TEXT, experience TEXT, quality FLOAT, dup_group TEXT, crawled_at DATETIME, status TEXT)')
    def provider():
        with Session(engine) as db:yield db
    monkeypatch.setattr(mysql,'get_db',provider)
    monkeypatch.setattr(cn.browser,'ensure_ready',lambda *a,**kw:{'endpoint':'http://127.0.0.1:9333','target_id':'same'})
    monkeypatch.setattr(cn.browser,'wait_access',lambda *a,**kw:{'can_collect':True,'content_limited':False})
    monkeypatch.setattr(cn.time,'sleep',lambda _:None)
    cards=[card(1)]
    details={card(1)['url']:detail(1)}
    monkeypatch.setattr(cn,'fetch_search_page',lambda *a,**kw:list(cards))
    class Client:
        url=''
        def navigate(self,url,**kw):self.url=url
        def evaluate(self,script):
            value=details[self.url]
            if isinstance(value,Exception):raise value
            return value
        def close(self):pass
    monkeypatch.setattr(cn.CdpClient,'connect_first_page',lambda *a,**kw:Client())
    def rows():
        with engine.connect() as db:return list(db.exec_driver_sql('SELECT * FROM jd_pool').mappings())
    def run(**kw):
        return cn.run_fetch('liepin',['Python'],[('北京','010')],cdp_endpoint='http://127.0.0.1:9333',pages=1,max_jobs=5,delay=0,settle=0,**kw)
    try:yield cards,details,rows,run
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)
        assert not path.exists()


@pytest.mark.parametrize('bad', [None,{},detail(1,description=''),detail(1,description='暂无描述'),
                               detail(1,url=card(2)['url']),detail(1,title='另一个合成岗位'),
                               detail(1,description_truncated=True)])
def test_failed_empty_or_mismatched_detail_never_persists_list_card(offline,bad):
    _,details,rows,run=offline
    details[card(1)['url']]=bad
    stats=run()
    assert rows()==[]
    assert stats['detail_attempted']==1 and stats['complete']==0 and stats['rejected']==1


def test_only_attempted_valid_details_persist_and_duplicate_counts_are_precise(offline):
    cards,details,rows,run=offline
    cards.extend([card(2),card(3)])
    details.update({card(2)['url']:detail(2),card(3)['url']:detail(3)})
    first=run(detail_limit=2)
    assert len(rows())==2
    assert (first['listed'],first['detail_attempted'],first['detail_obtained'],first['complete'],first['inserted'],first['unattempted'])==(3,2,2,2,2,1)
    second=run(detail_limit=2)
    assert len(rows())==2
    assert second['inserted']==0 and second['updated']==0 and second['skipped']==2


def test_run_events_map_exact_rows_and_never_replace_current_body_with_history(offline, monkeypatch, tmp_path):
    from app.collect import control
    _, details, rows, run = offline
    monkeypatch.setattr(control, '_STATE_DIR', tmp_path / 'events')
    monkeypatch.setattr(control, '_STATE_PATH', tmp_path / 'events/state.json')
    def capture(run_id):
        return lambda value: control._parse_log_line(run_id, 'TM_EVENT ' + json.dumps(value, ensure_ascii=False, default=str))
    run(on_event=capture('first'))
    inserted = control.get_results('first')[0]
    assert inserted['outcome'] == 'inserted'
    assert inserted['jd_pool_id'] == rows()[0]['id']
    assert inserted['quality'] is not None
    details[card(1)['url']] = detail(1, description='负责本轮新的 Python 服务开发')
    run(on_event=capture('second'))
    skipped = control.get_results('second')[0]
    assert skipped['outcome'] == 'skipped'
    assert skipped['jd_pool_id'] == inserted['jd_pool_id']
    assert skipped['raw_text'] == '负责本轮新的 Python 服务开发'
    assert skipped['crawled_at'] is not None
    assert '本轮新的' not in rows()[0]['raw_text']


def test_limited_guest_detail_blocks_platform_and_is_not_inserted(offline,monkeypatch):
    _,_,rows,run=offline
    monkeypatch.setattr(cn.browser,'wait_access',lambda *a,**kw:{'can_collect':True,'content_limited':True})
    stats=run()
    assert rows()==[] and stats['complete']==0
    assert stats['failed']==1 and stats['stop_reason']


def test_verification_after_good_detail_preserves_only_that_detail(offline,monkeypatch):
    cards,details,rows,run=offline
    cards.append(card(2));details[card(2)['url']]=detail(2)
    checks=[0]
    def access(*a,**kw):
        checks[0]+=1
        if checks[0]==2:raise cn.browser.AccessBlocked('verification_required')
        return {'can_collect':True,'content_limited':False}
    monkeypatch.setattr(cn.browser,'wait_access',access)
    stats=run()
    assert len(rows())==1 and stats['inserted']==1 and stats['failed']==1 and stats['stop_reason']


def test_websocket_closure_preserves_prior_good_detail_and_final_stats(offline):
    cards,details,rows,run=offline
    cards.append(card(2));details[card(2)['url']]=WebSocketException('synthetic closed')
    stats=run()
    assert len(rows())==1 and stats['inserted']==1 and stats['failed']==1
    assert stats['detail_attempted']==2 and stats['complete']==1 and stats['stop_reason']


def test_dom_same_title_without_stable_panel_binding_is_not_complete():
    job={**card(1),'_dom':True,'url':'dom://zhaopin/synthetic','company':'甲合成公司'}
    got=detail(1,company='乙合成公司')
    assert cn.detail_rejection(SITES['zhaopin'],job,got) is not None


def test_normalization_preserves_actual_paragraphs_and_duties_boundary():
    row=clean(normalize_job(SITES['liepin'],card(1),detail(1)))
    assert '\n负责 Python 服务开发\n' in row['raw_text']
    assert '负责 Python 服务开发' in row['duties']
    assert '熟悉 SQL' not in row['duties']


@pytest.mark.parametrize('has_body',[True,False])
def test_real_detail_script_preserves_lines_and_never_reads_recommendation_metadata(has_body):
    node=shutil.which('node')
    if not node:pytest.skip('Node required for actual extraction JavaScript')
    script=r'''
const vm=require('node:vm');let input='';process.stdin.on('data',d=>input+=d);process.stdin.on('end',()=>{
 const p=JSON.parse(input), make=t=>({innerText:t,querySelectorAll:()=>[],getBoundingClientRect:()=>({width:100,height:100})});
 const header={querySelectorAll:s=>s==='.job-title'?[make('Python合成岗位1')]:[]};
 const document={querySelector:s=>s==='.job-apply-container'?header:null,
  querySelectorAll:s=>s==='.job-intro-container'&&p.has_body?[make(p.body)]:s==='.job-description'?[make('另一岗位负责 Java 开发')]:s==='.company-name'?[make('错误的推荐公司')]:s==='.job-title'?[make('Python合成岗位1')]:[]};
 process.stdout.write(JSON.stringify(vm.runInNewContext(p.script,{document,location:{href:'https://www.liepin.com/job/synthetic-1'},getComputedStyle:()=>({display:'block',visibility:'visible'})})));
});'''
    body=detail(1)['description']
    done=subprocess.run([node,'-e',script],input=json.dumps({'script':build_detail_extract_js(SITES['liepin']),'body':body,'has_body':has_body}),text=True,capture_output=True,encoding='utf-8',check=True)
    got=json.loads(done.stdout)
    assert got['description']==(body if has_body else '')
    assert got['company']==''


def test_stable_panel_requires_update_then_two_identical_samples(monkeypatch):
    old = {'panel_title': '旧岗位', 'description': '旧正文', 'company': '旧公司',
           'panel_visible': True, 'target_active': False,
           'list_url': 'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1'}
    changed = {**old, 'panel_title': 'Python 工程师', 'description': '负责平台开发',
               'company': '甲公司', 'target_active': True}
    class Client:
        def __init__(self):
            self.values = iter([old, changed, changed])
        def evaluate(self, script):
            return next(self.values)
    monkeypatch.setattr(cn.time, 'sleep', lambda _: None)

    result = cn.await_stable_panel(
        Client(), SITES['zhaopin'], 0, old, timeout=1.0, interval=0.01
    )

    assert result['panel_changed'] is True
    assert result['stable_samples'] == 2
    assert result['target_active_before'] is False
    assert result['target_active_after'] is True


def test_dom_pending_detail_persists_without_increasing_complete(tmp_path, monkeypatch):
    from app.db import mysql
    path = tmp_path / 'zhaopin-pending.sqlite3'
    engine = create_engine('sqlite:///' + str(path))
    with engine.begin() as db:
        db.exec_driver_sql(
            'CREATE TABLE jd_pool (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, '
            'source_detail TEXT, job_title TEXT, raw_text TEXT, duties TEXT, experience TEXT, '
            'quality FLOAT, dup_group TEXT, crawled_at DATETIME, status TEXT)'
        )
    def provider():
        with Session(engine) as db:
            yield db
    monkeypatch.setattr(mysql, 'get_db', provider)
    monkeypatch.setattr(cn.browser, 'ensure_ready', lambda *a, **kw: {
        'endpoint': 'http://127.0.0.1:9333', 'target_id': 'same'
    })
    monkeypatch.setattr(cn.browser, 'wait_access', lambda *a, **kw: {
        'can_collect': True, 'content_limited': False
    })
    job = {
        'url': 'dom://zhaopin/provisional', 'title': 'Python 工程师',
        'company': '甲公司', 'salary': '20-30K', 'location': '上海',
        'tags': ['Python'], '_card_index': 0, '_dom': True,
        '_list_url': 'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1',
        '_observation_key': 'zhaopin:list-card-0',
    }
    detail_value = {
        'url': 'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1',
        'title': 'Python 工程师', 'company': '客户公司',
        'description': '负责 Python 平台开发\n熟悉 SQL 和 Docker',
        'description_truncated': False,
    }
    before = {
        'target_card_found': True, 'target_active': False, 'panel_visible': True,
        'panel_title': '旧岗位', 'description': '旧正文', 'company': '旧公司',
        'list_url': job['_list_url'],
    }
    changed = {
        'target_card_found': True, 'target_active': True, 'panel_visible': True,
        'panel_title': 'Python 工程师', 'description': detail_value['description'],
        'company': '客户公司', 'list_url': job['_list_url'],
    }
    class Client:
        def __init__(self):
            self.probes = iter([before, changed, changed])
        def evaluate(self, script):
            if 'card.click();' in script:
                return {'clicked': True}
            if 'description_truncated:' in script:
                return dict(detail_value)
            return next(self.probes)
        def close(self):
            pass
    monkeypatch.setattr(cn, 'fetch_search_page', lambda *a, **kw: [dict(job)])
    monkeypatch.setattr(cn.CdpClient, 'connect_first_page', lambda *a, **kw: Client())
    monkeypatch.setattr(cn.time, 'sleep', lambda _: None)
    events = []
    try:
        stats = cn.run_fetch(
            'zhaopin', ['Java'], [('上海', '538')],
            cdp_endpoint='http://127.0.0.1:9333', pages=1,
            detail_limit=1, max_jobs=1, delay=0, settle=0,
            on_event=events.append,
        )
        assert stats['detail_obtained'] == 1
        assert stats['content_eligible'] == 1
        assert stats['identity_pending'] == 1
        assert stats['identity_verified'] == 0
        assert stats['complete'] == 0
        assert stats['rejected'] == 0
        assert stats['inserted'] == 1
        persisted = next(e for e in events if e['event'] == 'persisted')['items'][0]
        assert persisted['identity_status'] == 'pending'
        assert persisted['content_eligible'] is True
        assert persisted['identity_evidence']['binding_policy'] == 'zhaopin-dom-panel-v1'
        assert persisted['source_detail'].startswith('dom://zhaopin/')
        assert len(persisted['source_detail'].split('/')[-1]) == 64
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)
        assert not path.exists()
