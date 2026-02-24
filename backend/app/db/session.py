from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


_ENGINE = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


def _create_engine(database_url: str):
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    return create_engine(
        database_url, future=True, pool_pre_ping=True, connect_args=connect_args
    )


def configure_engine(database_url: str) -> None:
    global _ENGINE
    global _SESSION_FACTORY

    if _ENGINE is not None:
        _ENGINE.dispose()

    _ENGINE = _create_engine(database_url)
    _SESSION_FACTORY = sessionmaker(
        bind=_ENGINE, autoflush=False, autocommit=False, expire_on_commit=False
    )


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        configure_engine(os.getenv("DATABASE_URL", "sqlite:///./life_event.db"))
    return _ENGINE


def get_session_factory() -> sessionmaker[Session]:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        get_engine()
    assert _SESSION_FACTORY is not None
    return _SESSION_FACTORY


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
