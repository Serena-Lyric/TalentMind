"""History identity is evidence based; counts never manufacture object versions."""
import json
from pathlib import Path

from app.routers import evolution


def baseline_row(index):
    value = json.loads((Path(__file__).resolve().parents[2] / 'exchange/m2/job_change_log.json').read_text(encoding='utf-8'))[index]
    return dict(value, m2_job_id=value['job_id'], source=json.dumps(value['source'], ensure_ascii=False), detail=json.dumps(value['detail'], ensure_ascii=False))


def test_demo_requires_exact_historical_identity_not_id_or_keyword():
    row = baseline_row(243)
    result = evolution.describe_change(row)
    assert result['change_nature'] == 'historical_demo'
    assert result['provenance']['baseline_index'] == 243
    assert result['version'] is None
    row['id'] = 99999
    assert evolution.describe_change(row)['change_nature'] == 'historical_demo'
    row['reason'] += ' changed'
    assert evolution.describe_change(row)['change_nature'] == 'unverified_history'


def test_legacy_has_values_but_no_invented_version_or_market_proof():
    row = baseline_row(0)
    result = evolution.describe_change(row)
    assert result['change_nature'] == 'unverified_history'
    assert result['before'] is None
    assert result['after'] == json.loads(row['detail'])['new_value']
    assert result['comparison_available'] is True
    assert result['version'] is None
    assert result['market_change_verified'] is False


def test_profile_edit_keeps_real_versions_and_explicit_missing_values():
    row = {'source': 'talentmind:profile-edit/v1', 'detail': {'change_nature': 'profile_edit', 'before': {'bonus_skills': ['SQL']}, 'after': {'bonus_skills': ['PostgreSQL']}, 'before_version': 'a' * 64, 'after_version': 'b' * 64}}
    result = evolution.describe_change(row)
    assert result['change_nature'] == 'profile_edit'
    assert result['version'] == 'b' * 64
    assert result['previous_version'] == 'a' * 64
    assert result['before']['bonus_skills'] == ['SQL']
    assert evolution.describe_change({'detail': {}})['comparison_available'] is False


def test_all_and_only_reviewed_demo_records_match():
    assert sum(evolution.describe_change(baseline_row(i))['change_nature'] == 'historical_demo' for i in range(275)) == 32
