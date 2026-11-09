"""Worker orchestration tests use fake engines and isolated state only."""
from concurrent.futures import ThreadPoolExecutor

from app.collect.runtime import state
from app.collect.runtime.platforms import RuntimeConfig
from app.collect.runtime.worker import run_worker


class Clock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Sink:
    def __init__(self):
        self.stats = []

    def db_provider(self):
        return lambda: iter(())

    def record_stats(self, stats):
        self.stats.append(dict(stats))


class Engine:
    def __init__(self, behavior=None):
        self.behavior = behavior or (lambda *args, **kwargs: {'status': 'success', 'stats': {'inserted': 1}, 'events': []})
        self.calls = []

    def fetch_once(self, platform, keyword, city, page, db_provider, *, config, on_event=None):
        self.calls.append((platform, keyword, city, page))
        return self.behavior(platform, keyword, city, page)


def config_for_boss():
    return RuntimeConfig(
        keywords=('Python', 'Java'),
        cities={'boss': (('北京', '101'), ('上海', '102')), 'zhaopin': (('北京', '530'),), 'liepin': (('北京', '北京'),)},
        pages=2,
        detail_limit=1,
        max_jobs=1,
        page_delay_min=15,
        page_delay_max=30,
        switch_interval_min=360,
        switch_interval_max=720,
        settle=5,
    )


def test_worker_rotates_page_city_keyword_and_persists_checkpoint(tmp_path):
    clock = Clock()
    engine = Engine()
    sink = Sink()
    result = run_worker(
        'boss', config_for_boss(), engine=engine, sink=sink, state_root=tmp_path,
        max_rounds=5, clock=clock, sleeper=clock.sleep,
    )

    assert engine.calls == [
        ('boss', 'Python', ('北京', '101'), 1),
        ('boss', 'Python', ('北京', '101'), 2),
        ('boss', 'Python', ('上海', '102'), 1),
        ('boss', 'Python', ('上海', '102'), 2),
        ('boss', 'Java', ('北京', '101'), 1),
    ]
    assert result.status == 'waiting'
    assert (result.keyword_index, result.city_index, result.page) == (1, 0, 2)
    assert result.next_run_at == clock.now + 15
    assert state.load_state('boss', root=tmp_path).last_success_at == 1750.0


def test_blocked_worker_stops_without_retry_while_other_workers_continue(tmp_path):
    def behavior(platform, keyword, city, page):
        if platform == 'boss':
            return {'status': 'blocked', 'stats': {}, 'error': 'verification_required', 'events': []}
        return {'status': 'success', 'stats': {'inserted': 1}, 'events': []}

    engine = Engine(behavior)
    clocks = {platform: Clock() for platform in ('boss', 'zhaopin', 'liepin')}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(run_worker, platform, config_for_boss(), engine=engine, sink=Sink(),
                        state_root=tmp_path, max_rounds=2, clock=clocks[platform], sleeper=clocks[platform].sleep)
            for platform in ('boss', 'zhaopin', 'liepin')
        ]
        results = {platform: future.result(timeout=3) for platform, future in zip(('boss', 'zhaopin', 'liepin'), futures)}

    assert results['boss'].status == 'blocked'
    assert results['boss'].stop_reason == 'verification_required'
    assert sum(1 for call in engine.calls if call[0] == 'boss') == 1
    assert sum(1 for call in engine.calls if call[0] == 'zhaopin') == 2
    assert sum(1 for call in engine.calls if call[0] == 'liepin') == 2
    assert results['zhaopin'].status == results['liepin'].status == 'waiting'


def test_stop_during_wait_does_not_call_engine_again(tmp_path):
    clock = Clock()
    engine = Engine()

    def stop_during_sleep(seconds):
        clock.sleep(seconds)
        state.request_stop('boss', root=tmp_path)

    result = run_worker(
        'boss', config_for_boss(), engine=engine, sink=Sink(), state_root=tmp_path,
        max_rounds=0, clock=clock, sleeper=stop_during_sleep,
    )

    assert len(engine.calls) == 1
    assert result.status == 'stopped'


def test_failed_result_is_not_retried(tmp_path):
    engine = Engine(lambda *args: {'status': 'failed', 'stats': {}, 'error': 'db_error', 'events': []})
    result = run_worker(
        'boss', config_for_boss(), engine=engine, sink=Sink(), state_root=tmp_path,
        max_rounds=3, clock=Clock(), sleeper=lambda seconds: None,
    )
    assert len(engine.calls) == 1
    assert result.status == 'failed'
    assert result.stop_reason == 'db_error'
