"""Bounded, parameterized, read-only history selection; no collection/import clients."""
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[4]
COHORTS = {
    'main120': ('quality-round2-v3/input.json', 120),
    'holdout60': ('quality-holdout-input/input.json', 60),
}

IDENTITY_STATUSES = ('verified', 'pending', 'unknown')


def normalize_identity(row):
    result = dict(row)
    status = result.get('identity_status') or 'unknown'
    if status not in IDENTITY_STATUSES:
        raise ValueError('invalid identity_status in jd_pool')
    result['identity_status'] = status
    eligible = result.get('content_eligible')
    result['content_eligible'] = None if eligible is None else bool(int(eligible))
    evidence = result.get('identity_evidence')
    if isinstance(evidence, str) and evidence.strip():
        evidence = json.loads(evidence)
    result['identity_evidence'] = evidence if isinstance(evidence, dict) else None
    return result


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    sources: list[str] = Field(default_factory=list, max_length=32)
    id_min: int | None = Field(default=None, ge=1)
    id_max: int | None = Field(default=None, ge=1)
    limit: int = Field(default=5, ge=1, le=5000)
    cohort: Literal['history', 'main120', 'holdout60'] = 'history'

    @model_validator(mode='after')
    def validate_bounds(self):
        if self.id_min is not None and self.id_max is not None and self.id_min > self.id_max:
            raise ValueError('ID range is reversed')
        if any(not s.strip() or len(s) > 32 or any(ord(c) < 32 for c in s) for s in self.sources):
            raise ValueError('invalid source filter')
        if self.cohort != 'history' and (self.sources or self.id_min is not None or self.id_max is not None):
            raise ValueError('frozen cohort membership cannot be combined with filters')
        return self


def connect():
    import pymysql
    from sqlalchemy.engine import make_url
    from app.config import get_settings
    url = make_url(get_settings().mysql_url)
    return pymysql.connect(host=url.host, port=url.port or 3306, user=url.username,
        password=url.password, database=url.database, charset='utf8mb4', autocommit=False,
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5, read_timeout=30)


def cohort_rows(name):
    path, expected = COHORTS[name]
    data = (ROOT / 'data/local' / path).read_bytes()
    rows = json.loads(data.decode('utf-8-sig'))
    if len(rows) != expected or len({r['id'] for r in rows}) != expected:
        raise ValueError('frozen cohort membership invalid')
    return rows, hashlib.sha256(data).hexdigest()


def read_mysql(selection):
    selection = Selection.model_validate(selection)
    clauses, args, reference, reference_sha = [], [], None, None
    if selection.cohort != 'history':
        reference, reference_sha = cohort_rows(selection.cohort)
        clauses.append('id IN (' + ','.join(['%s'] * len(reference)) + ')')
        args.extend(r['id'] for r in reference)
        limit = len(reference)
    else:
        limit = selection.limit
        if selection.sources:
            clauses.append('source IN (' + ','.join(['%s'] * len(selection.sources)) + ')')
            args.extend(selection.sources)
        for operator, value in (('>=', selection.id_min), ('<=', selection.id_max)):
            if value is not None:
                clauses.append(f'id {operator} %s')
                args.append(value)
    sql = 'SELECT * FROM jd_pool' + (' WHERE ' + ' AND '.join(clauses) if clauses else '') + ' ORDER BY id LIMIT %s'
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('START TRANSACTION READ ONLY')
            cursor.execute(sql, (*args, limit))
            rows = cursor.fetchall()
    finally:
        connection.rollback()
        connection.close()
    rows = [normalize_identity({
        k: str(v) if isinstance(v, (datetime, date)) else v for k, v in row.items()
    }) for row in rows]
    provenance = dict(kind='mysql_jd_pool', transaction='READ ONLY; ROLLBACK', selection=selection.model_dump(),
        selected=len(rows), counting_unit='jd_pool rows, not independent positions',
        identity_counts={status: sum(row['identity_status'] == status for row in rows)
                         for status in IDENTITY_STATUSES},
        content_eligible_counts={
            'eligible': sum(row['content_eligible'] is True for row in rows),
            'ineligible': sum(row['content_eligible'] is False for row in rows),
            'unknown': sum(row['content_eligible'] is None for row in rows),
        })
    if reference is not None:
        current = {str(row['id']): row for row in rows}
        # A disappeared member remains an explicit invalid input, never shrinks the denominator.
        rows = [current.get(str(row['id']), {'id': row['id'], '_input_error': 'historical_member_missing'}) for row in reference]
        fields = ('source', 'job_title', 'raw_text', 'duties', 'experience')
        changed = [row['id'] for row in reference if any(row.get(k) != current.get(str(row['id']), {}).get(k) for k in fields)]
        provenance.update(reference_input_sha256=reference_sha, reference_count=len(reference),
            changed_ids=changed, missing_ids=[r['id'] for r in rows if '_input_error' in r],
            interpretation='historical_members_current_mysql_snapshot_not_old_byte_replay')
    return rows, provenance


def available_sources():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('START TRANSACTION READ ONLY')
            cursor.execute('SELECT source, COUNT(*) AS total, MIN(id) AS id_min, MAX(id) AS id_max FROM jd_pool GROUP BY source ORDER BY source')
            rows = cursor.fetchall()
    finally:
        connection.rollback()
        connection.close()
    cohorts = []
    for name, (_, expected) in COHORTS.items():
        try:
            _, sha = cohort_rows(name)
            cohorts.append(dict(name=name, available=True, total=expected, sha256=sha))
        except (OSError, ValueError, KeyError, TypeError):
            cohorts.append(dict(name=name, available=False, total=expected))
    return dict(sources=rows, total=sum(r['total'] for r in rows), cohorts=cohorts, batch_limit=5000)
