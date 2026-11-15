"""Per-platform runtime state tests; no browser or production database."""
import sqlite3

import pytest

from app.collect.runtime import state


def test_state_round_trip_is_scoped_to_platform(tmp_path):
    value = state.RuntimeState(
        platform='boss', status='waiting', keyword_index=1, city_index=2, page=3,
        next_run_at=123.5, last_saved_identity='boss://stable-id',
        last_success_at=100.0, stop_reason=None, stats={'inserted': 2, 'failed': 0},
        updated_at=110.0,
    )
    state.save_state(value, root=tmp_path)

    loaded = state.load_state('boss', root=tmp_path)
    assert loaded == value
    assert state.load_state('zhaopin', root=tmp_path).status == 'idle'
    assert state.state_path('boss', root=tmp_path) != state.state_path('zhaopin', root=tmp_path)
    assert state.state_path('boss', root=tmp_path).exists()


def test_state_rejects_invalid_status_and_cursor(tmp_path):
    value = state.RuntimeState(platform='boss', status='running')
    value.status = 'unknown'
    with pytest.raises(ValueError, match='status'):
        state.save_state(value, root=tmp_path)

    value = state.RuntimeState(platform='boss', status='waiting', page=0)
    with pytest.raises(ValueError, match='page'):
        state.save_state(value, root=tmp_path)


def test_stop_marker_is_atomic_and_clearable(tmp_path):
    assert state.stop_requested('liepin', root=tmp_path) is False
    state.request_stop('liepin', root=tmp_path)
    assert state.stop_requested('liepin', root=tmp_path) is True
    assert state.stop_path('liepin', root=tmp_path).exists()
    state.clear_stop('liepin', root=tmp_path)
    assert state.stop_requested('liepin', root=tmp_path) is False
