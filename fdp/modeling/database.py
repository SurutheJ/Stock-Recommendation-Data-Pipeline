"""Engine/session plumbing. Kept deliberately tiny: one place that knows how
to stand up a database, so tests can swap in an in-memory SQLite engine and
the CLI/API can share the same file-backed one.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fdp.config import DEFAULT_DB_URL
from fdp.modeling.orm_models import Base


def get_engine(db_url: str = DEFAULT_DB_URL):
    if db_url == "sqlite://" or ":memory:" in db_url:
        # a single shared in-memory database across connections (used by tests)
        return create_engine(
            db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    return create_engine(db_url, connect_args={"check_same_thread": False})


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def get_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def build_default_session_factory(db_url: str = DEFAULT_DB_URL) -> sessionmaker:
    """Convenience used by the CLI/API: ensure the parent dir exists, create
    the engine + schema, and hand back a ready-to-use session factory."""
    from pathlib import Path
    from urllib.parse import urlparse

    if db_url.startswith("sqlite:///") and db_url not in ("sqlite:///:memory:",):
        db_path = Path(urlparse(db_url).path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine(db_url)
    init_db(engine)
    return get_session_factory(engine)
