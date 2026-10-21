from app.collect.identity_replay import replay_events


def event(description='负责 Python 平台开发\n熟悉 SQL 和 Docker', title='Python 工程师'):
    job = {
        'url': 'dom://zhaopin/provisional',
        'title': title,
        'company': '甲公司',
        'salary': '20-30K',
        'location': '上海',
        'tags': ['Python'],
        '_card_index': 0,
        '_dom': True,
        '_observation_key': 'zhaopin:card-0',
    }
    return {
        'event': 'detail',
        'platform': 'zhaopin',
        'observed_at': '2026-10-21T22:00:00+08:00',
        'job': job,
        'detail': {
            'url': 'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1',
            'title': title,
            'description': description,
            'description_truncated': False,
        },
    }


def test_replay_checks_valid_pending_wrong_job_stale_panel_and_content():
    result = replay_events([event()])
    cases = result['cases'][0]['checks']

    assert cases['valid_pending']['identity_status'] == 'pending'
    assert cases['valid_pending']['content_rejection'] is None
    assert cases['async_wrong_job']['identity_rejection'] == 'title_mismatch'
    assert cases['same_title_panel_not_updated']['identity_rejection'] == 'panel_not_updated'
    assert cases['empty_body']['content_rejection'] == 'empty_detail'
    assert cases['truncated_body']['content_rejection'] == 'truncated_description'
    assert result['binding_note'].startswith('old_events_lack_panel_transition')


def test_replay_fingerprint_dedupes_same_observation_and_separates_later_time():
    result = replay_events([event()])
    checks = result['cases'][0]['checks']

    assert checks['same_observation_duplicate']['fingerprint_same'] is True
    assert checks['different_observation_time']['fingerprint_same'] is False
    assert len(checks['valid_pending']['fingerprint']) == 64


def test_replay_reports_real_content_without_copying_body_into_summary():
    result = replay_events([event()])
    assert '负责 Python 平台开发' not in str(result['summary'])
    assert result['summary']['cases'] == 1
    assert result['summary']['valid_pending'] == 1
