"""Read-only schema checks against isolated synthetic databases."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


@pytest.mark.parametrize('columns,missing', [
    ('', ['identity_status', 'content_eligible', 'identity_evidence']),
    (', identity_status TEXT', ['content_eligible', 'identity_evidence']),
    (', identity_status TEXT, content_eligible INTEGER, identity_evidence TEXT', []),
])
def test_readiness_reports_actual_columns_without_mutation(columns, missing):
    from app.collect.readiness import inspect_database, require_database_ready
    engine = create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE jd_pool (id INTEGER PRIMARY KEY, job_title TEXT' + columns + ')'))
            connection.execute(text("INSERT INTO jd_pool(id,job_title) VALUES (1,'readiness-sentinel')"))
        with Session(engine) as session:
            result = inspect_database(session)
            assert result['ready'] is (not missing)
            assert result['missing_columns'] == missing
            if missing:
                with pytest.raises(RuntimeError, match='identity_schema_migration_required'):
                    require_database_ready(session)
            else:
                require_database_ready(session)
            assert session.execute(text('SELECT job_title FROM jd_pool')).scalars().all() == ['readiness-sentinel']
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM jd_pool WHERE id=1 AND job_title='readiness-sentinel'"))
            assert connection.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar() == 0
    finally:
        engine.dispose()


def test_unreachable_database_is_not_reported_as_missing_columns():
    from app.collect.readiness import inspect_database
    class BrokenSession:
        def get_bind(self):
            raise RuntimeError('private connection detail')
    result = inspect_database(BrokenSession())
    assert result['ready'] is False
    assert result['reason'] == 'collection_database_unavailable'
    assert result['missing_columns'] == []
    assert 'private' not in str(result)
