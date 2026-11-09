"""Execute the real DOM scripts and collector against synthetic cards and SQLite."""
import json
from datetime import datetime
import shutil
import subprocess
import sys
import types

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.collect import fetch_cn_jobs as cn, frequency
from app.collect.fetchers.job_sites import SITES, build_search_extract_js


TITLE = '合成绑定回归 Python工程师'
BODY = '岗位职责：\n负责 Python 平台开发\n任职要求：\n熟悉 SQL 和 Docker'
URL = 'https://www.zhaopin.com/jobs?jl=530&kw=Python&page=1'

# Exact selector matching deliberately avoids the old tests' "includes(title)"
# stub, which returned a title even when the production selector was obsolete.
DOM_RUNNER = r'''
const vm = require('node:vm');
let input = '';
process.stdin.on('data', value => input += value);
process.stdin.on('end', () => {
  const p = JSON.parse(input), state = p.state;
  const node = (value, visible = true) => ({
    innerText: value, textContent: value,
    querySelectorAll: () => [],
    getBoundingClientRect: () => ({width: visible ? 100 : 0, height: 100}),
  });
  const cards = p.cards.map((data, index) => {
    const fields = {
      [data.title_selector]: node(data.title, !data.hidden_title),
      '.job-card__company-name': node(data.company),
      '.job-card__salary': node('20-30K'),
      '.job-location': node('北京'),
    };
    return {
      ...node([data.title, data.company, '20-30K', '北京'].join(' ')),
      querySelector: selector => fields[selector] || null,
      querySelectorAll: selector => fields[selector] ? [fields[selector]] : [],
      classList: {contains: cls => cls === 'job-card--active' && state.active === index},
      scrollIntoView: () => {},
      click: () => { state.active = index; state.panel = index; state.clicks++; },
    };
  });
  const active = p.cards[state.panel];
  const detail = state.clicks ? active : null;
  const panelFields = {
    '.job-detail-summary__title-text': node(detail ? (detail.detail_title || detail.title) : '旧岗位'),
    '.job-detail-summary__company-name': node(detail ? (detail.detail_company || detail.company) : '旧合成公司'),
    '.job-description__content': node(detail ? detail.body : '负责旧系统维护'),
  };
  const panel = {...node(''), querySelectorAll: selector => panelFields[selector] ? [panelFields[selector]] : []};
  const document = {
    querySelectorAll: selector => selector.startsWith('.job-card') ? cards : [],
    querySelector: selector => selector === '.job-detail-panel' ? panel : null,
  };
  const result = vm.runInNewContext(p.script, {
    document, location: {href: p.url},
    getComputedStyle: () => ({display: 'block', visibility: 'visible'}),
  });
  process.stdout.write(JSON.stringify({result, state}));
});
'''


class SyntheticBrowser:
    def __init__(self, cards):
        self.cards = cards
        self.state = {'active': -1, 'panel': -1, 'clicks': 0}
        self.url = URL
        self.before_evaluate = lambda script: None

    def evaluate(self, script):
        self.before_evaluate(script)
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is required to execute the production DOM scripts')
        result = subprocess.run(
            [node, '-e', DOM_RUNNER], input=json.dumps({
                'script': script, 'cards': self.cards, 'state': self.state, 'url': self.url,
            }), text=True, encoding='utf-8', capture_output=True, check=True,
        )
        value = json.loads(result.stdout)
        self.state = value['state']
        return value['result']

    def navigate(self, url, **kwargs):
        self.url = url

    def close(self):
        pass


def synthetic_card(**changes):
    return {
        'title': TITLE, 'company': '合成甲公司', 'body': BODY,
        'title_selector': '.job-card__title-clamp', **changes,
    }


@pytest.fixture
def isolated_collector(monkeypatch, tmp_path):
    engine = create_engine('sqlite://')
    assert engine.url.database in (None, '')
    @event.listens_for(engine, 'before_cursor_execute', retval=True)
    def dates(conn, cursor, statement, params, context, many):
        return statement, tuple(value.isoformat() if isinstance(value, datetime) else value for value in params)
    with engine.begin() as db:
        db.exec_driver_sql(
            'CREATE TABLE jd_pool (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, '
            'source_detail TEXT, job_title TEXT, raw_text TEXT, duties TEXT, experience TEXT, '
            'quality FLOAT, dup_group TEXT, crawled_at DATETIME, status TEXT, '
            'identity_status TEXT, content_eligible BOOLEAN, identity_evidence TEXT)'
        )
        db.execute(text('INSERT INTO jd_pool (job_title, source_detail) VALUES (:title, :url)'),
                   {'title': '隔离库保留哨兵', 'url': 'synthetic://sentinel'})
    mysql = types.ModuleType('app.db.mysql')
    def provider():
        with Session(engine) as db:
            yield db
    mysql.get_db = provider
    monkeypatch.setitem(sys.modules, 'app.db.mysql', mysql)
    import app.db
    monkeypatch.setattr(app.db, 'mysql', mysql, raising=False)
    now = [1000.0]
    monkeypatch.setattr(frequency, '_STATE_PATH', tmp_path / 'frequency.sqlite3')
    monkeypatch.setattr(frequency, '_clock', lambda: now[0])
    monkeypatch.setattr(cn.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(cn.time, 'sleep', lambda value: now.__setitem__(0, now[0] + value))
    monkeypatch.setattr(cn.browser, 'ensure_ready', lambda *a, **kw: {
        'endpoint': 'http://127.0.0.1:9333', 'target_id': 'synthetic',
    })
    monkeypatch.setattr(cn.browser, 'wait_access', lambda *a, **kw: {
        'can_collect': True, 'content_limited': False,
    })
    def run(browser):
        monkeypatch.setattr(cn.CdpClient, 'connect_first_page', lambda *a, **kw: browser)
        events = []
        stats = cn.run_fetch(
            'zhaopin', ['Python'], [('北京', '530')], cdp_endpoint='http://127.0.0.1:9333',
            max_jobs=2, detail_limit=2, delay=15, settle=5, on_event=events.append,
        )
        with engine.connect() as db:
            rows = list(db.execute(text('SELECT * FROM jd_pool WHERE job_title=:title'),
                                   {'title': TITLE}).mappings())
        return stats, events, rows
    try:
        yield run
    finally:
        with engine.begin() as db:
            db.execute(text('DELETE FROM jd_pool WHERE job_title=:title'), {'title': TITLE})
            assert db.execute(text('SELECT COUNT(*) FROM jd_pool WHERE job_title=:title'),
                              {'title': TITLE}).scalar_one() == 0
            assert db.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar_one() == 1
            assert db.execute(text('SELECT source_detail FROM jd_pool')).scalar_one() == 'synthetic://sentinel'
        engine.dispose()


def test_list_detail_identity_and_persistence_use_independent_list_title(isolated_collector):
    browser = SyntheticBrowser([synthetic_card()])
    stats, events, rows = isolated_collector(browser)
    assert stats['identity_pending'] == stats['inserted'] == 1
    assert stats['complete'] == stats['identity_verified'] == 0
    assert events[0]['jobs'][0]['title'] == TITLE
    assert rows[0]['job_title'] == TITLE
    assert rows[0]['identity_status'] == 'pending'
    assert rows[0]['content_eligible'] == 1
    assert '负责 Python 平台开发' in rows[0]['raw_text']


def test_hidden_list_title_cannot_be_used_as_identity_evidence(isolated_collector):
    browser = SyntheticBrowser([synthetic_card(hidden_title=True)])
    stats, events, rows = isolated_collector(browser)
    assert stats['content_eligible'] == 1
    assert stats['rejection_reasons'] == {'missing_list_title': 1}
    assert rows == []


def test_missing_list_title_stays_rejected_with_readable_detail(isolated_collector):
    browser = SyntheticBrowser([synthetic_card(title_selector='.unrecognized-title')])
    stats, events, rows = isolated_collector(browser)
    assert stats['content_eligible'] == 1
    assert stats['rejection_reasons'] == {'missing_list_title': 1}
    assert rows == []


def test_wrong_detail_title_cannot_persist_list_identity(isolated_collector):
    browser = SyntheticBrowser([synthetic_card(detail_title='另一个合成岗位')])
    stats, events, rows = isolated_collector(browser)
    assert stats['content_eligible'] == 1
    assert stats['rejection_reasons'] == {'title_mismatch': 1}
    assert rows == []


def test_same_title_cards_remain_distinct_pending_observations(isolated_collector):
    browser = SyntheticBrowser([
        synthetic_card(), synthetic_card(company='合成乙公司', body=BODY + '\n负责服务部署'),
    ])
    stats, events, rows = isolated_collector(browser)
    assert stats['identity_pending'] == stats['inserted'] == 2
    assert len({row['source_detail'] for row in rows}) == 2
    assert {json.loads(row['identity_evidence'])['company'] for row in rows} == {'合成甲公司', '合成乙公司'}


def test_same_title_card_replacement_before_click_is_rejected(isolated_collector):
    browser = SyntheticBrowser([synthetic_card()])
    def replace_card(script):
        if 'card.click();' in script:
            browser.cards[0] = synthetic_card(company='替换后的合成公司')
    browser.before_evaluate = replace_card
    stats, events, rows = isolated_collector(browser)
    assert stats['inserted'] == 0
    assert rows == []
    assert browser.state['clicks'] == 0


def test_active_target_lost_during_final_detail_capture_is_rejected(isolated_collector):
    browser = SyntheticBrowser([synthetic_card()])
    def deactivate(script):
        if 'description_truncated:' in script:
            browser.state['active'] = -1
    browser.before_evaluate = deactivate
    stats, events, rows = isolated_collector(browser)
    assert stats['inserted'] == 0
    assert rows == []


def test_panel_body_changes_after_stability_are_rejected(isolated_collector):
    browser = SyntheticBrowser([synthetic_card()])
    def change_panel(script):
        if 'description_truncated:' in script:
            browser.cards[0]['body'] = '负责另一个合成系统维护'
    browser.before_evaluate = change_panel
    stats, events, rows = isolated_collector(browser)
    assert stats['rejection_reasons'] == {'panel_changed_during_capture': 1}
    assert rows == []


def test_same_title_panel_company_changes_after_stability_are_rejected(isolated_collector):
    browser = SyntheticBrowser([synthetic_card()])
    def change_company(script):
        if 'description_truncated:' in script:
            browser.cards[0]['detail_company'] = '另一个合成公司'
    browser.before_evaluate = change_company
    stats, events, rows = isolated_collector(browser)
    assert stats['rejection_reasons'] == {'panel_changed_during_capture': 1}
    assert rows == []
