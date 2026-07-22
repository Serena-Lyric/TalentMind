import redis
from app.config import get_settings

_pool = redis.ConnectionPool.from_url(get_settings().redis_url)

def get_redis():
    return redis.Redis(connection_pool=_pool)
