import hashlib

from app.collect.fetchers.job_sites import SITES


def job(*, dom=True, title='Python 工程师'):
    return {
        'url': 'dom://zhaopin/provisional' if dom else 'https://www.zhaopin.com/job/real-1',
        'title': title,
        'company': '甲公司',
        'salary': '20-30K',
        'location': '上海 浦东',
        '_card_index': 0,
        '_dom': dom,
        '_list_url': 'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1',
    }


def detail(*, title='Python 工程师', description='负责 Python 平台开发\n熟悉 SQL 和 Docker', **extra):
    return {
        'url': 'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1',
        'title': title,
        'description': description,
        'description_truncated': False,
        **extra,
    }


def binding(**extra):
    result = {
        'target_card_found': True,
        'target_active_before': False,
        'target_active_after': True,
        'panel_visible': True,
        'panel_changed': True,
        'stable_samples': 2,
        'panel_title': 'Python 工程师',
        'before_panel_title': 'Java 工程师',
        'description': '负责 Python 平台开发\n熟悉 SQL 和 Docker',
        'list_url': 'https://www.zhaopin.com/jobs/?jl=538&kw=Java&page=1',
        'list_title': 'Python 工程师',
        'list_company': '甲公司',
        'binding_policy': 'zhaopin-dom-panel-v1',
    }
    result.update(extra)
    return result


def test_valid_dom_binding_is_pending_not_verified():
    from app.collect.identity import identity_decision

    status, evidence, rejection = identity_decision(
        SITES['zhaopin'],
        job(),
        detail(),
        binding(),
        '2026-10-21T22:00:00+08:00',
    )

    assert (status, rejection) == ('pending', None)
    assert evidence['binding_policy'] == 'zhaopin-dom-panel-v1'
    assert evidence['target_active_after'] is True
    assert evidence['stable_samples'] == 2
    assert evidence['list_url'].startswith('https://www.zhaopin.com/jobs/')


def test_panel_not_updated_is_rejected_even_when_title_matches():
    from app.collect.identity import identity_decision

    status, _, rejection = identity_decision(
        SITES['zhaopin'],
        job(),
        detail(),
        binding(panel_changed=False, before_panel_title='Python 工程师'),
        '2026-10-21T22:00:00+08:00',
    )

    assert status == 'unknown'
    assert rejection == 'panel_not_updated'


def test_same_title_does_not_replace_missing_panel_transition():
    from app.collect.identity import identity_decision

    status, _, rejection = identity_decision(
        SITES['zhaopin'],
        job(title='后端工程师'),
        detail(title='后端工程师'),
        binding(
            panel_changed=False,
            list_title='后端工程师',
            panel_title='后端工程师',
            before_panel_title='后端工程师',
        ),
        '2026-10-21T22:00:00+08:00',
    )

    assert status == 'unknown'
    assert rejection == 'panel_not_updated'


def test_target_must_be_active_and_panel_must_be_stable():
    from app.collect.identity import identity_decision

    status, _, rejection = identity_decision(
        SITES['zhaopin'], job(), detail(), binding(target_active_after=False),
        '2026-10-21T22:00:00+08:00',
    )
    assert (status, rejection) == ('unknown', 'target_card_not_active')

    status, _, rejection = identity_decision(
        SITES['zhaopin'], job(), detail(), binding(stable_samples=1),
        '2026-10-21T22:00:00+08:00',
    )
    assert (status, rejection) == ('unknown', 'panel_unstable')


def test_title_mismatch_is_rejected():
    from app.collect.identity import identity_decision

    status, _, rejection = identity_decision(
        SITES['zhaopin'], job(), detail(title='另一个岗位'), binding(),
        '2026-10-21T22:00:00+08:00',
    )

    assert (status, rejection) == ('unknown', 'title_mismatch')


def test_detail_must_still_match_stable_panel_description():
    from app.collect.identity import identity_decision

    status, _, rejection = identity_decision(
        SITES['zhaopin'], job(), detail(),
        binding(description='面板在抽取前又变成另一条详情'),
        '2026-10-21T22:00:00+08:00',
    )

    assert (status, rejection) == ('unknown', 'panel_changed_during_capture')


def test_url_identity_must_match_detail_url():
    from app.collect.identity import identity_decision

    status, evidence, rejection = identity_decision(
        SITES['zhaopin'],
        job(dom=False),
        {**detail(), 'url': 'https://www.zhaopin.com/job/real-1?utm=1'},
        None,
        '2026-10-21T22:00:00+08:00',
    )
    assert (status, rejection) == ('verified', None)
    assert evidence['strategy'] == 'source_url'

    status, _, rejection = identity_decision(
        SITES['zhaopin'],
        job(dom=False),
        {**detail(), 'url': 'https://www.zhaopin.com/job/other'},
        None,
        '2026-10-21T22:00:00+08:00',
    )
    assert (status, rejection) == ('unknown', 'identity_mismatch')


def test_empty_truncated_and_invalid_content_are_not_eligible():
    from app.collect.identity import content_rejection

    assert content_rejection(SITES['zhaopin'], job(), detail(description='')) == 'empty_detail'
    assert content_rejection(
        SITES['zhaopin'], job(), detail(description_truncated=True)
    ) == 'truncated_description'
    assert content_rejection(
        SITES['zhaopin'], job(), detail(description='暂无描述')
    ) == 'invalid_detail_body'


def test_fingerprint_is_sha256_and_changes_with_observation_time():
    from app.collect.identity import dom_fingerprint

    evidence = binding()
    evidence.update({
        'platform': 'zhaopin',
        'card_index': 0,
        'title': 'Python 工程师',
        'company': '甲公司',
        'salary': '20-30K',
        'location': '上海 浦东',
        'description_sha256': hashlib.sha256(detail()['description'].encode()).hexdigest(),
    })

    first = dom_fingerprint({**evidence, 'observed_at': '2026-10-21T22:00:00+08:00'})
    duplicate = dom_fingerprint({**evidence, 'observed_at': '2026-10-21T22:00:00+08:00'})
    later = dom_fingerprint({**evidence, 'observed_at': '2026-10-21T22:05:00+08:00'})

    assert first == duplicate
    assert len(first) == 64
    int(first, 16)
    assert first != later
