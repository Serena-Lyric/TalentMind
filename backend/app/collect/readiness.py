"""Explain collection write prerequisites without changing the database schema."""
from sqlalchemy import inspect

from .repository import IDENTITY_COLUMNS


def inspect_database(db=None):
    owned = None
    try:
        if db is None:
            from app.db.mysql import SessionLocal
            owned = db = SessionLocal()
        columns = {column['name'] for column in inspect(db.get_bind()).get_columns('jd_pool')}
        missing = [name for name in IDENTITY_COLUMNS if name not in columns]
        return dict(ready=not missing,
                    reason='identity_schema_migration_required' if missing else None,
                    message='采集数据库缺少身份与内容资格字段' if missing else '采集数据库已就绪',
                    missing_columns=missing,
                    next_step='完成备份和获授权的字段升级后刷新检查' if missing else '可继续准备浏览器并显式开始采集')
    except Exception:
        return dict(ready=False, reason='collection_database_unavailable',
                    message='无法确认采集数据库状态', missing_columns=[],
                    next_step='检查数据库服务与连接配置后刷新检查')
    finally:
        if owned is not None:
            owned.close()


def require_database_ready(db=None):
    result = inspect_database(db)
    if not result['ready']:
        raise RuntimeError(f"{result['reason']}: {result['message']}")
