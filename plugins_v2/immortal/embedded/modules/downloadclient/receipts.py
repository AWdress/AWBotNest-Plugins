"""Persistent at-most-once receipts for external download submissions."""
import hashlib
import json
import sqlite3
import time
import httpx
from pathlib import Path
from contextlib import contextmanager

from ...core.runtime import get_runtime


class DownloadResultUnknown(RuntimeError):
    pass


@contextmanager
def _connection(path):
    db = sqlite3.connect(path, timeout=10)
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def submit_once(name, endpoint, resource, save_path, callback):
    runtime = get_runtime()
    runtime.require_download()
    runtime.check_cancelled()
    key = hashlib.sha256(json.dumps([name, endpoint, resource, save_path],
                                   ensure_ascii=False).encode('utf-8')).hexdigest()
    path = Path(runtime.ctx.data_dir) / 'download-receipts.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connection(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS receipts '
                   '(key TEXT PRIMARY KEY, state TEXT NOT NULL, changed_at REAL NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT state FROM receipts WHERE key=?', (key,)).fetchone()
        if row:
            if row[0] == 'accepted':
                return True, None
            raise DownloadResultUnknown('上次下载提交结果未确认，请先到下载器核实；不会重复提交')
        db.execute('INSERT INTO receipts VALUES (?, ?, ?)', (key, 'unknown', time.time()))
        db.commit()
    # Persist uncertainty before the external mutation. A crash or timeout must
    # not make a subsequent task blindly submit the same resource again.
    try:
        accepted, reason = callback()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {400, 401, 403, 404, 405, 409, 413, 415, 422, 429}:
            with _connection(path) as db:
                db.execute('DELETE FROM receipts WHERE key=?', (key,))
            return False, f'下载器拒绝了请求（HTTP {exc.response.status_code}）'
        raise DownloadResultUnknown('下载提交结果未确认，请先到下载器核实') from exc
    except Exception as exc:
        raise DownloadResultUnknown('下载提交结果未确认，请先到下载器核实') from exc
    with _connection(path) as db:
        if accepted:
            db.execute('UPDATE receipts SET state=?, changed_at=? WHERE key=?',
                       ('accepted', time.time(), key))
        else:
            db.execute('DELETE FROM receipts WHERE key=?', (key,))
    return bool(accepted), reason
