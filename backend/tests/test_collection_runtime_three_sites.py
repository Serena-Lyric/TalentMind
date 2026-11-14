"""Three isolated workers against synthetic CDP runners and temporary SQLite."""
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.collect import browser
from app.collect.pipeline import run_pipeline
from app.collect.repository import save_incremental_jd_rows
from app.collect.runtime import state
from app.collect.runtime.browser import CdpEngine
from app.collect.runtime.platforms import RuntimeConfig
from app.collect.runtime.sink import DatabaseSink
from app.collect.runtime.worker import run_worker
from app.collect.schema import RawJD


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def create_database(path):
    engine = create_engine(f'sqlite:///{path}')
    with engine.begin() as db:
        db.execute(text('''CREATE TABLE jd_pool (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, source_detail TEXT,
            job_title TEXT, raw_text TEXT, duties TEXT, experience TEXT, quality FLOAT,
            dup_group TEXT, crawled_at DATETIME, status TEXT,
            identity_status TEXT NOT NULL DEFAULT 'unknown', content_eligible BOOLEAN NULL,
            identity_evidence TEXT NULL)'''))
    return engine


def provider_for(engine):
    def provider():
        with Session(engine) as db:
            yield db
    return provider


def config():
    return RuntimeConfig(
        keywords=('Python',),
        cities={
            'boss': (('北京', '101'),),
            'zhaopin': (('北京', '530'),),
            'liepin': (('北京', '北京'),),
        },
        pages=1, detail_limit=1, max_jobs=1,
        page_delay_min=15, page_delay_max=30,
        switch_interval_min=360, switch_interval_max=720, settle=5,
    )


def runner(calls):
    def run(platform, *args, **kwargs):
        calls.setdefault(platform, 0)
        calls[platform] += 1
        provider = kwargs['db_provider']()
        db = next(provider)
        try:
            raw = RawJD(
                source=platform,
                job_title=f'{platform} 合成岗位',
                raw_html='职位描述:\n负责 Python 服务开发\n熟悉 SQL',
                source_detail=f'https://example.test/{platform}/job-1',
                identity_status='verified', content_eligible=True,
                identity_evidence='{"strategy":"source_url"}',
            )
            inserted = run_pipeline(db, [raw], jd_saver=lambda session, rows: save_incremental_jd_rows(session, rows, created_ids=set()))
            return {'listed': 1, 'detail_attempted': 1, 'inserted': inserted, 'stop_reason': None}
        finally:
            provider.close()
    return run


def test_three_site_round_trip_idempotency_and_stop_restart(tmp_path):
    engine = create_database(tmp_path / 'jobs.sqlite3')
    calls = {}
    provider = provider_for(engine)
    sink = DatabaseSink(provider)
    def boss_runner(*args, **kwargs):
        return runner(calls)('boss', *args, **kwargs)

    cdp = CdpEngine(boss_runner=boss_runner, cn_runner=runner(calls))
    cfg = config()
    clocks = {platform: Clock() for platform in ('boss', 'zhaopin', 'liepin')}

    first = {
        platform: run_worker(platform, cfg, engine=cdp, sink=sink, state_root=tmp_path,
                             max_rounds=1, clock=clocks[platform], sleeper=clocks[platform].sleep)
        for platform in ('boss', 'zhaopin', 'liepin')
    }
    assert all(value.status == 'waiting' for value in first.values())
    with engine.connect() as db:
        assert db.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar_one() == 3

    second = {
        platform: run_worker(platform, cfg, engine=cdp, sink=sink, state_root=tmp_path,
                             max_rounds=1, clock=Clock(2000), sleeper=lambda seconds: None)
        for platform in ('boss', 'zhaopin', 'liepin')
    }
    assert all(value.status == 'waiting' for value in second.values())
    assert calls == {'boss': 2, 'zhaopin': 2, 'liepin': 2}
    with engine.connect() as db:
        assert db.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar_one() == 3

    state.request_stop('boss', root=tmp_path)
    stopped = run_worker('boss', cfg, engine=cdp, sink=sink, state_root=tmp_path,
                         max_rounds=0, clock=Clock(2000), sleeper=lambda seconds: None)
    assert stopped.status == 'stopped'
    assert calls['boss'] == 2
    state.clear_stop('boss', root=tmp_path)
    resumed = run_worker('boss', cfg, engine=cdp, sink=sink, state_root=tmp_path,
                         max_rounds=1, clock=Clock(2000), sleeper=lambda seconds: None)
    assert resumed.status == 'waiting'
    assert calls['boss'] == 3
    engine.dispose()


def test_boss_blocked_does_not_prevent_other_platform_persistence(tmp_path):
    engine = create_database(tmp_path / 'jobs-blocked.sqlite3')
    calls = {}
    provider = provider_for(engine)
    sink = DatabaseSink(provider)

    def behavior(platform, *args, **kwargs):
        if platform == 'boss':
            calls['boss'] = calls.get('boss', 0) + 1
            raise browser.AccessBlocked('verification_required')
        return runner(calls)(platform, *args, **kwargs)

    def boss_behavior(*args, **kwargs):
        return behavior('boss', *args, **kwargs)

    cdp = CdpEngine(boss_runner=boss_behavior, cn_runner=behavior)
    cfg = config()
    clocks = {platform: Clock() for platform in ('boss', 'zhaopin', 'liepin')}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            platform: pool.submit(run_worker, platform, cfg, engine=cdp, sink=sink,
                                  state_root=tmp_path, max_rounds=2, clock=clocks[platform],
                                  sleeper=clocks[platform].sleep)
            for platform in ('boss', 'zhaopin', 'liepin')
        }
        results = {platform: future.result(timeout=3) for platform, future in futures.items()}

    assert results['boss'].status == 'blocked'
    assert calls['boss'] == 1
    assert results['zhaopin'].status == 'waiting'
    assert results['liepin'].status == 'waiting'
    with engine.connect() as db:
        assert db.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar_one() == 2
    engine.dispose()
