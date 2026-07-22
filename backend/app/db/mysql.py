from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

class Base(DeclarativeBase):
    pass

_engine = create_engine(get_settings().mysql_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
