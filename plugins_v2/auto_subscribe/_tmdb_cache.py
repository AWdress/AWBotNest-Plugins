"""Bounded asynchronous metadata cache and resumable ordering, without secrets."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from time import time


CACHE_PREFIX = "tmdb_meta:"
CHECKPOINT_KEY = "emby_scan_checkpoint"
_BUCKETS = 64
_BUCKET_MAX_ENTRIES = 128
_BUCKET_MAX_BYTES = 512 * 1024
_VALUE_MAX_BYTES = 256 * 1024
_INDEX_MAX_BYTES = 128 * 1024
_CHECKPOINT_MAX_IDS = 20000
_CHECKPOINT_TTL = 7 * 86400
# The host may briefly block its loop while four governed HTTP clients start
# (notably Windows TLS/proxy setup). A 2s wait misclassified an already-finished
# SQLite worker as unavailable; keep this above the SDK's 10s busy/drain bound.
_STORAGE_TIMEOUT_SECONDS = 15.0
_META_KEY = re.compile(r"^tmdb_meta:v1:(?:tv:[1-9][0-9]*|season:[1-9][0-9]*:[1-9][0-9]*)$")


def _size(value):
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError, OverflowError):
        return math.inf


def _data_digest(data):
    """Verify complete cached payloads, including valid-JSON truncation."""
    try:
        canonical = json.dumps(data, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(canonical).hexdigest()


class TmdbCache:
    """64 small accounting shards bound the cache to 32 MiB / 8192 entries.

    Each shard reserves the value size before the independent metadata write.
    A crash cannot create unaccounted values, and no operation rewrites a
    library-sized metadata/index blob. LRU touches are flushed at scan end.
    """

    def __init__(self, storage=None, log=None):
        self.storage, self.log = storage, log
        self.enabled = storage is not None
        self.buckets = {}
        self.locks = {}
        self.warned = False
        self.hits = self.misses = self.writes = 0

    def warn(self, message="TMDB 缓存存储暂不可用，本轮继续在线核对"):
        if not self.warned and self.log:
            self.log.warning("[自动订阅] %s", message)
        self.warned = True

    async def _op(self, method, *args):
        if not self.enabled:
            return False, None
        try:
            value = await asyncio.wait_for(getattr(self.storage, method)(*args), timeout=_STORAGE_TIMEOUT_SECONDS)
            return True, value
        except asyncio.CancelledError:
            raise
        except Exception:
            # Do not serialize underlying exceptions: they may include paths,
            # credentials, database contents or request URLs.
            self.enabled = False
            self.warn()
            return False, None

    @staticmethod
    def _bucket_number(key):
        return int.from_bytes(hashlib.sha256(key.encode()).digest()[:2], "big") % _BUCKETS

    @staticmethod
    def _index_key(number):
        return f"{CACHE_PREFIX}v1:index:{number:02d}"

    async def _bucket(self, number):
        if number in self.buckets:
            return self.buckets[number]
        ok, raw = await self._op("get", self._index_key(number), None)
        if not ok:
            return {}
        if raw is None:
            entries = {}
        else:
            valid = isinstance(raw, dict) and raw.get("version") == 1 and isinstance(raw.get("entries"), dict)
            entries = raw.get("entries", {}) if valid else {}
            if valid:
                valid = len(entries) <= _BUCKET_MAX_ENTRIES and _size(raw) <= _INDEX_MAX_BYTES
                for key, meta in entries.items():
                    valid = valid and isinstance(key, str) and bool(_META_KEY.fullmatch(key)) and self._bucket_number(key) == number
                    valid = valid and isinstance(meta, list) and len(meta) == 3
                    if not valid:
                        break
                    valid = (isinstance(meta[0], int) and not isinstance(meta[0], bool)
                             and 0 < meta[0] <= _VALUE_MAX_BYTES
                             and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                     and math.isfinite(v) for v in meta[1:]))
                    if not valid:
                        break
                valid = valid and sum(meta[0] for meta in entries.values()) <= _BUCKET_MAX_BYTES
            if not valid:
                self.enabled = False
                self.warn("TMDB 缓存索引无效，已停用本轮缓存并继续在线核对")
                return {}
        self.buckets[number] = entries
        return entries

    async def get(self, key):
        if not self.enabled:
            self.misses += 1
            return None
        number = self._bucket_number(key)
        async with self.locks.setdefault(number, asyncio.Lock()):
            entries = await self._bucket(number)
            meta = entries.get(key)
            if not meta or meta[1] <= time():
                self.misses += 1
                return None
            ok, value = await self._op("get", key, None)
            if (not ok or not isinstance(value, dict) or value.get("version") != 1
                    or value.get("expires_at") != meta[1] or _size(value) > meta[0]
                    or not isinstance(value.get("data_sha256"), str)
                    or _data_digest(value.get("data")) != value["data_sha256"]):
                self.misses += 1
                return None
            meta[2] = time()
            self.hits += 1
            return value.get("data")

    async def put(self, key, data, ttl):
        if not self.enabled:
            return
        now = time()
        digest = _data_digest(data)
        if digest is None:
            self.warn("TMDB 元数据无法完整编码，本轮仍使用在线核对结果")
            return
        value = {"version": 1, "expires_at": now + ttl, "data": data,
                 "data_sha256": digest}
        size = _size(value)
        if size > _VALUE_MAX_BYTES:
            self.warn("TMDB 单季元数据超过缓存容量，本轮仍使用完整在线核对结果")
            return
        number = self._bucket_number(key)
        async with self.locks.setdefault(number, asyncio.Lock()):
            entries = await self._bucket(number)
            if not self.enabled:
                return
            entries = dict(entries)
            previous = entries.pop(key, None)
            # A smaller replacement must still account for the previous value
            # until its overwrite completes (including process interruption).
            reserved_size = max(size, previous[0] if previous else 0)
            while (len(entries) >= _BUCKET_MAX_ENTRIES
                   or sum(meta[0] for meta in entries.values()) + reserved_size > _BUCKET_MAX_BYTES):
                victim = min(entries, key=lambda candidate: (entries[candidate][1] > now, entries[candidate][2]))
                ok, _ = await self._op("delete", victim)
                if not ok:
                    return
                entries.pop(victim)
            entries[key] = [reserved_size, value["expires_at"], now]
            # Reserve before writing data; stale reservations are harmless and
            # reclaimed like ordinary entries if the second write fails.
            ok, _ = await self._op("set", self._index_key(number), {"version": 1, "entries": entries})
            if not ok:
                return
            self.buckets[number] = entries
            ok, _ = await self._op("set", key, value)
            self.writes += int(ok)

    async def flush(self):
        for number, entries in self.buckets.items():
            if not self.enabled:
                break
            await self._op("set", self._index_key(number), {"version": 1, "entries": entries})

    async def load_checkpoint(self, scope):
        ok, value = await self._op("get", CHECKPOINT_KEY, None)
        if not ok or value is None:
            return set()
        valid = (isinstance(value, dict) and _size(value) <= _INDEX_MAX_BYTES * 4
                 and value.get("version") == 1 and value.get("scope") == scope
                 and isinstance(value.get("expires_at"), (int, float))
                 and not isinstance(value.get("expires_at"), bool)
                 and math.isfinite(value["expires_at"]) and value["expires_at"] > time()
                 and isinstance(value.get("done_ids"), list)
                 and len(value["done_ids"]) <= _CHECKPOINT_MAX_IDS)
        if not valid:
            return set()
        ids = value["done_ids"]
        if any(not isinstance(identity, str) or not re.fullmatch(r"[1-9][0-9]*", identity) for identity in ids):
            return set()
        return set(ids)

    async def save_checkpoint(self, scope, done_ids, *, complete=False):
        if not self.enabled:
            return
        if complete:
            await self._op("delete", CHECKPOINT_KEY)
            return
        ids = sorted(done_ids, key=int)
        if len(ids) > _CHECKPOINT_MAX_IDS:
            self.warn("缺集核对恢复标记达到容量上限，其余剧集仍将在后续轮次重新核对")
            ids = ids[:_CHECKPOINT_MAX_IDS]
        await self._op("set", CHECKPOINT_KEY, {"version": 1, "scope": scope,
                                              "expires_at": time() + _CHECKPOINT_TTL, "done_ids": ids})
