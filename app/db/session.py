from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

_is_sqlite = "sqlite" in settings.database_url

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=False,
    pool_pre_ping=True,
    # SQLite 不支持连接池回收，仅对 PostgreSQL/MySQL 生效
    pool_recycle=1800 if not _is_sqlite else -1,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
