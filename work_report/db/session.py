"""SQLite engine / session。"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from work_report.config import ROOT_DIR

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_data_dir() -> Path:
    """数据目录：DATA_DIR 环境变量或项目根下 data/。"""
    raw = os.getenv("DATA_DIR", "").strip()
    path = Path(raw) if raw else ROOT_DIR / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    return get_data_dir() / "work_report.db"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        db_path = get_db_path()
        url = f"sqlite:///{db_path.as_posix()}"
        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            future=True,
        )

        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


def init_db() -> None:
    """建表并在空库时 seed。"""
    from work_report.db import models  # noqa: F401
    from work_report.db.models import Base
    from work_report.db.seed import seed_if_empty

    Base.metadata.create_all(bind=get_engine())
    _migrate_project_name_id()
    with session_scope() as session:
        seed_if_empty(session)


def _migrate_project_name_id() -> None:
    """为旧版 project_names 表补充可选的 GitLab 项目 ID。"""
    engine = get_engine()
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("project_names")}
    if "project_id" in columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE project_names ADD COLUMN project_id INTEGER")
        )


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖。"""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
