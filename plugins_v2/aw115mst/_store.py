"""Per-instance durable checkpoints. Transactions finish before cancellation."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
from datetime import datetime, timezone


async def settled(awaitable):
    task = asyncio.ensure_future(awaitable)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Never leave an I/O worker writing files or SQLite after plugin teardown.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not task.cancelled():
            task.exception()
        raise


def file_key(path):
    return hashlib.sha256(os.path.normcase(str(Path(path).absolute())).encode("utf-8")).hexdigest()


class Store:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "checkpoints.sqlite3"
        self.lock = asyncio.Lock()

    def _operation(self, operation, *args):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=30)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, updated TEXT, data TEXT)")
            if operation == "get":
                row = db.execute("SELECT data FROM records WHERE key=?", args).fetchone()
                return json.loads(row[0]) if row else None
            if operation == "put":
                row = args[0]
                db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)",
                           (row["key"], row["updated"], json.dumps(row, ensure_ascii=False)))
            elif operation == "put_many":
                db.executemany("INSERT OR REPLACE INTO records VALUES(?,?,?)",
                               [(row["key"], row["updated"], json.dumps(row, ensure_ascii=False)) for row in args[0]])
            elif operation == "all":
                return [json.loads(row[0]) for row in db.execute("SELECT data FROM records ORDER BY updated DESC")]
            elif operation == "clear":
                db.execute("DELETE FROM records")

    async def _call(self, operation, *args):
        async with self.lock:
            return await settled(asyncio.to_thread(self._operation, operation, *args))

    async def get(self, key):
        return await self._call("get", key)

    async def put(self, record):
        record["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        await self._call("put", dict(record))

    async def all(self):
        return await self._call("all")

    async def put_many(self, records):
        for record in records:
            record["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        await self._call("put_many", [dict(record) for record in records])

    async def clear(self):
        await self._call("clear")
