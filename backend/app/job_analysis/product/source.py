"""Shared source identity and read-only connection for explicit delivery selections."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


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


def connect():
    import pymysql
    from sqlalchemy.engine import make_url
    from app.config import get_settings
    url = make_url(get_settings().mysql_url)
    return pymysql.connect(host=url.host, port=url.port or 3306, user=url.username,
        password=url.password, database=url.database, charset='utf8mb4', autocommit=False,
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5, read_timeout=30)
