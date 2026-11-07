"""Database engine and session management (plain SQLAlchemy 2.x)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


SessionLocal = scoped_session(sessionmaker(autoflush=False, expire_on_commit=False))
_engine: Engine | None = None


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
    # Enforce FK constraints (cascade deletes) and allow concurrent readers.
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def init_db(database_url: str) -> Engine:
    """Create the engine, bind the session factory and create tables."""
    global _engine
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        Path(database_url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    kwargs = {}
    if ":memory:" in database_url:
        from sqlalchemy.pool import StaticPool

        kwargs["poolclass"] = StaticPool
    _engine = create_engine(database_url, connect_args=connect_args, future=True, **kwargs)
    SessionLocal.remove()
    SessionLocal.configure(bind=_engine)
    from . import entities  # noqa: F401  (register mappers)

    Base.metadata.create_all(_engine)
    return _engine


def get_session():
    return SessionLocal()
