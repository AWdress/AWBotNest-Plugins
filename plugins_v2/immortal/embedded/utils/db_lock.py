from sqlalchemy import text
from sqlalchemy.orm import Session

CAST_WRITE_LOCK_KEY = 2001001
MOVIE_WRITE_LOCK_KEY = 2001002
SUBSCRIBE_WRITE_LOCK_KEY = 2001003
_LOCK_STATE_KEY = '_advisory_write_lock_keys'
_LOCK_TRANSACTION_KEY = '_immortal_write_lock_transaction'
# advisory lock 获取等待超时（秒）。超时后会抛出 LockNotAvailable，
# 上层通过捕获可以跳过当前订阅，避免一条卡住阻塞整批。
LOCK_TIMEOUT_SECONDS = 5


def _acquire_write_locks(session: Session, *keys: int) -> None:
    current_transaction = session.get_transaction()
    if session.info.get(_LOCK_TRANSACTION_KEY) is not current_transaction:
        session.info.pop(_LOCK_STATE_KEY, None)
    acquired = set(session.info.get(_LOCK_STATE_KEY, set()))
    pending_keys = sorted({int(key) for key in keys if key not in acquired})
    if not pending_keys:
        return

    bind = session.get_bind()
    if bind is None:
        raise RuntimeError('数据库会话尚未绑定')
    if bind.dialect.name == 'sqlite':
        connection = session.connection()
        # SQLAlchemy may have an ORM transaction after SELECT while SQLite's
        # DBAPI has not begun one. Reserve the write slot before reading state.
        raw_connection = connection.connection.driver_connection
        connection.exec_driver_sql(f'PRAGMA busy_timeout={LOCK_TIMEOUT_SECONDS * 1000}')
        try:
            if not raw_connection.in_transaction:
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            else:
                # An explicit deferred transaction can also reserve its writer
                # without changing any row; an existing write stays a write.
                connection.exec_driver_sql('UPDATE config SET id=id WHERE 0')
        finally:
            connection.exec_driver_sql('PRAGMA busy_timeout=30000')
        session.info[_LOCK_STATE_KEY] = acquired | set(pending_keys)
        session.info[_LOCK_TRANSACTION_KEY] = session.get_transaction()
        return
    if bind.dialect.name != 'postgresql':
        session.info[_LOCK_STATE_KEY] = acquired | set(pending_keys)
        session.info[_LOCK_TRANSACTION_KEY] = session.get_transaction()
        return

    # 仅在本事务内生效，事务结束自动还原
    session.execute(text(f"SET LOCAL lock_timeout = '{int(LOCK_TIMEOUT_SECONDS)}s'"))
    for key in pending_keys:
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})
        acquired.add(key)

    session.info[_LOCK_STATE_KEY] = acquired
    session.info[_LOCK_TRANSACTION_KEY] = session.get_transaction()



def acquire_cast_movie_write_lock(session: Session) -> None:
    _acquire_write_locks(session, CAST_WRITE_LOCK_KEY, MOVIE_WRITE_LOCK_KEY)



def acquire_subscribe_write_lock(session: Session) -> None:
    _acquire_write_locks(session, SUBSCRIBE_WRITE_LOCK_KEY)



def acquire_cast_movie_subscribe_write_lock(session: Session) -> None:
    _acquire_write_locks(session, CAST_WRITE_LOCK_KEY, MOVIE_WRITE_LOCK_KEY, SUBSCRIBE_WRITE_LOCK_KEY)
