from neo4j import GraphDatabase
from threading import Lock
from app.config import get_settings

_driver = None
_driver_lock = Lock()

def get_neo4j():
    global _driver
    with _driver_lock:
        if _driver is None:
            settings = get_settings()
            _driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        return _driver


def close_neo4j():
    global _driver
    with _driver_lock:
        driver, _driver = _driver, None
        if driver is not None:
            driver.close()
