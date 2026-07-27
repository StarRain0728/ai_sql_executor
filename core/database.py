from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_metadata_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.metadata_database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=settings.metadata_db_pool_size,
        max_overflow=settings.metadata_db_max_overflow,
        future=True
    )


def get_session_factory() -> sessionmaker[Session]:
    """
    根据元数据引擎创建并返回一个session工厂。
    """
    metadata_engine = get_metadata_engine()
    return sessionmaker(bind=metadata_engine, autoflush=False, autocommit=False, future=True)


def get_metadata_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
