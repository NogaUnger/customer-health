"""
db.py
=====
Centralized database setup for the Customer Health API.

Responsibilities
---------------
- Build a SQLAlchemy Engine from the `DATABASE_URL` environment variable.
  * In Docker (compose), this is Postgres:  postgresql+psycopg://app:app@db:5432/app
  * Locally/tests, if `DATABASE_URL` is unset, we fall back to SQLite: sqlite:///./app.db
- Provide a declarative `Base` for ORM models to inherit from.
- Create a `SessionLocal` factory to open/close DB sessions.
- Expose `get_db()` generator for FastAPI dependency injection (1 session per request).

Env Vars
--------
- DATABASE_URL  : SQLAlchemy URL (e.g., postgresql+psycopg://user:pass@host:port/dbname)
- ECHO_SQL      : "true" to enable SQL echo (debug), default off
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base


# -----------------------------------------------------------------------------
# Decide which database URL to use
# -----------------------------------------------------------------------------
def _resolve_database_url() -> str:
    """
    Resolve the database URL from env, defaulting to local SQLite for dev/tests.
    Returns:
        A SQLAlchemy connection URL.
    """
    url = os.getenv("DATABASE_URL")
    if url and url.strip():
        return url.strip()
    # Fallback for local usage (tests or running without compose)
    # Creates/uses a file `app.db` in the working directory.
    return "sqlite:///./app.db"


SQLALCHEMY_DATABASE_URL: str = _resolve_database_url()


# -----------------------------------------------------------------------------
# Create the SQLAlchemy engine
# -----------------------------------------------------------------------------
def _make_engine(url: str) -> Engine:
    """
    Build a SQLAlchemy Engine with sensible defaults for Postgres/SQLite.

    - pool_pre_ping=True to avoid stale connections (esp. with Postgres).
    - SQLite needs `check_same_thread=False` when used with FastAPI/uvicorn.
    - Optional SQL echo via ECHO_SQL=true for debugging.
    """
    echo_sql = os.getenv("ECHO_SQL", "false").lower() == "true"
    connect_args = {}

    # SQLite-specific tweaks
    if url.startswith("sqlite:"):
        # When using SQLite in a multi-threaded ASGI app, this flag is required.
        connect_args["check_same_thread"] = False

    return create_engine(url, echo=echo_sql, pool_pre_ping=True, connect_args=connect_args)


engine: Engine = _make_engine(SQLALCHEMY_DATABASE_URL)


# -----------------------------------------------------------------------------
# Declarative Base (imported by models.py)
# -----------------------------------------------------------------------------
Base = declarative_base()


# -----------------------------------------------------------------------------
# Session factory and FastAPI dependency
# -----------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """
    FastAPI dependency that yields a DB session and ensures it's closed.

    Usage in routers:
        from fastapi import Depends
        from .db import get_db

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

    Yields:
        sqlalchemy.orm.Session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
