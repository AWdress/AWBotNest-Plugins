"""Plugin-owned database; importing models never opens a database connection."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import threading

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from .portable_types import install_sqlite_functions


Base = declarative_base()
engine = None
database_url = ""
_factory = None
_configure_lock = threading.Lock()


def configure(data_dir, database_url=""):
    """Use SQLite by default, optionally an explicit PostgreSQL connection URL.

    Call before loading service modules. Reconfiguration requires the runtime to
    drain its workers first; this function never changes the host platform DB.
    """
    global engine, _factory
    if str(database_url or "").strip():
        url = make_url(str(database_url).strip())
        if url.get_backend_name() != "postgresql":
            raise ValueError("外部数据库只支持 PostgreSQL；留空使用插件内置数据库")
    else:
        directory = Path(data_dir).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        url = URL.create("sqlite", database=str(directory / "immortal.sqlite3"))

    with _configure_lock:
        options = {"pool_pre_ping": True}
        if url.get_backend_name() == "sqlite":
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
        new_engine = create_engine(url, **options)
        if url.get_backend_name() == "sqlite":
            @event.listens_for(new_engine, "connect")
            def sqlite_connect(connection, record):
                install_sqlite_functions(connection)
                cursor = connection.cursor()
                try:
                    cursor.execute("PRAGMA busy_timeout=30000")
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA foreign_keys=ON")
                finally:
                    cursor.close()

        old_engine = engine
        engine = new_engine
        _factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        globals()["database_url"] = url.render_as_string(hide_password=False)
        if old_engine is not None:
            old_engine.dispose()
        return engine


def get_engine():
    if engine is None:
        raise RuntimeError("Immortal 数据库尚未初始化")
    return engine


def SessionLocal():
    if _factory is None:
        raise RuntimeError("Immortal 数据库尚未初始化")
    return _factory()


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def insert(table):
    """The upsert constructor must belong to the configured database dialect."""
    if get_engine().dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    return dialect_insert(table)


def close():
    global engine, _factory, database_url
    with _configure_lock:
        old_engine, engine = engine, None
        _factory = None
        database_url = ""
        if old_engine is not None:
            old_engine.dispose()
