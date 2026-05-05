"""Database connection and session management.

We use SQLModel's engine + Session pattern. The engine is a long-lived
connection pool created once per process; sessions are short-lived
units of work created per operation.

Why a context-managed session helper?
    - Guarantees rollback on exception (no partial writes)
    - Guarantees connection cleanup (no leaks)
    - Makes the calling code read clearly: `with session() as s: ...`
"""
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings


@lru_cache
def get_engine():
    """Create the database engine once per process and cache it."""
    settings = get_settings()
    engine = create_engine(settings.db_url, echo=False)
    SQLModel.metadata.create_all(engine)  # creates tables if they don't exist
    return engine


@contextmanager
def session() -> Iterator[Session]:
    """Yield a Session and ensure it's closed afterward.

    Usage:
        with session() as s:
            s.add(some_product)
            s.commit()
    """
    with Session(get_engine()) as s:
        yield s