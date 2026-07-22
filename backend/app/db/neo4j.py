from neo4j import GraphDatabase
from app.config import get_settings

_s = get_settings()
_driver = GraphDatabase.driver(_s.neo4j_uri, auth=(_s.neo4j_user, _s.neo4j_password))

def get_neo4j():
    return _driver
