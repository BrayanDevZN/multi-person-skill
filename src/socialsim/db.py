"""Engine and session handling for the local SQLite database."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from socialsim.models import Base

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "socialsim.db"


def resolve_db_path(explicit: str | None = None) -> Path:
    """Priority: explicit argument > SOCIALSIM_DB env var > data/socialsim.db in the project."""
    return Path(explicit or os.environ.get("SOCIALSIM_DB") or DEFAULT_DB).expanduser().resolve()


def make_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def init_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    session = sessionmaker(engine, expire_on_commit=False)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
