"""Built-in media charts for NextFind, without a VPS-Widget dependency.

Collect asynchronously through the platform HTTP service before the synchronous
subscription pipeline starts. Only complete, fresh, selection-specific source
results are reused; failures never replace earlier successful cache records.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time

from ._base import RankProvider, register
from ._charts_collectors import BOARD_LABELS, collect
from ._charts_transport import FetchError, Transport, safe_error
from ._models import RankMediaItem


DEFAULTS = {
    "charts_enabled": False,
    "charts_boards": ["guduo:剧集", "tmdb:tv"],
    "charts_limit": 20,
    "charts_cache_hours": 6,
    "charts_trakt_client_id": "",
    "charts_filter_custom": False,
    "charts_min_year": 0,
    "charts_min_vote": 0,
    "charts_media_type": "all",
}
_NAMES = {
    "guduo": "骨朵", "douban": "豆瓣热榜", "mgtv": "芒果 TV", "theater": "剧场片单",
    "bangumi": "Bangumi", "tmdb": "TMDB", "bili": "B站", "mal": "MyAnimeList",
    "anilist": "AniList", "trakt": "Trakt",
}
SOURCE_NAMES = {"charts_" + key: name + "榜单" for key, name in _NAMES.items()}
SOURCE_NAMES["charts_config"] = "内置榜单配置"
CATALOG = [
    {"id": key, "name": name,
     "boards": [{"id": f"{key}:{board}", "name": label} for board, label in BOARD_LABELS[key].items()]}
    for key, name in _NAMES.items()
]
_ALL_BOARDS = {row["id"] for source in CATALOG for row in source["boards"]}
_CACHE_VERSION = 1
_SOURCE_TIMEOUT = 120.0
_STAGE_TIMEOUT = 300.0


def _integer(value, label, lower, upper):
    try:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError
        number = float(value)
        if not math.isfinite(number) or not number.is_integer() or not lower <= number <= upper:
            raise ValueError
        return int(number)
    except (ValueError, OverflowError):
        raise FetchError(f"{label}必须是 {lower}～{upper} 的整数") from None


def _selection(cfg):
    boards = cfg.get("charts_boards", DEFAULTS["charts_boards"])
    if not isinstance(boards, list) or not boards:
        raise FetchError("请至少选择一个内置榜单")
    if any(not isinstance(board, str) or board not in _ALL_BOARDS for board in boards):
        raise FetchError("内置榜单选择无效，请重新选择并保存")
    groups = {}
    for board in boards:
        source, local = board.split(":", 1)
        if local not in groups.setdefault(source, []):
            groups[source].append(local)
    return groups


def _check_running(cfg):
    event = cfg.get("_cancel_event")
    deadline = cfg.get("_run_deadline")
    if isinstance(deadline, (int, float)) and not isinstance(deadline, bool) and time.monotonic() >= deadline:
        if event is not None:
            event.set()
        raise TimeoutError("本轮运行已超时")
    if event is not None and event.is_set():
        raise asyncio.CancelledError


async def _bounded(awaitable, cfg, deadline):
    """Cancel in-flight work promptly even when a sync worker signals stop."""
    task = asyncio.create_task(awaitable)
    try:
        while True:
            _check_running(cfg)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FetchError("内置榜单读取超时，本轮跳过；未覆盖原有缓存")
            done, _ = await asyncio.wait({task}, timeout=min(0.2, remaining))
            if done:
                _check_running(cfg)
                return task.result()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def _cache_signature(source, boards, limit, credential):
    identity = hashlib.sha256(credential.encode("utf-8")).hexdigest()
    selection = json.dumps([_CACHE_VERSION, source, sorted(boards), limit, identity], ensure_ascii=False)
    return hashlib.sha256(selection.encode("utf-8")).hexdigest()


def _clean_item(raw, board):
    if not isinstance(raw, dict) or not isinstance(raw.get("title"), str) or not raw["title"].strip():
        return None
    kind = raw.get("mediaType")
    if kind not in ("movie", "tv"):
        return None
    if "tmdbId" in raw:
        ident = raw["tmdbId"]
        text = str(ident)
        if (isinstance(ident, bool) or not isinstance(ident, (int, str)) or len(text) > 20
                or not text.isascii() or not text.isdecimal() or int(text) <= 0):
            return None
    item = {"title": raw["title"].strip()[:300], "mediaType": kind, "board": board}
    if "tmdbId" in raw:
        item["tmdbId"] = int(raw["tmdbId"])
    for key in ("year", "releaseDate", "originalTitle", "sourceTitle", "searchLanguage", "chartDate"):
        if isinstance(raw.get(key), (str, int)) and not isinstance(raw[key], bool):
            item[key] = str(raw[key])[:300]
    for key in ("rank", "rating", "heat", "requireGenre", "popularity", "voteCount"):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            item[key] = value
    if isinstance(raw.get("searchTitles"), list):
        item["searchTitles"] = [value.strip()[:300] for value in raw["searchTitles"][:10]
                                if isinstance(value, str) and value.strip()]
    if isinstance(raw.get("genreIds"), list):
        item["genreIds"] = [value for value in raw["genreIds"][:64]
                            if isinstance(value, int) and not isinstance(value, bool) and 0 < value < 100000]
    return item


def _flatten(source, data, boards, limit):
    if not isinstance(data, dict):
        raise FetchError("榜单返回格式无效")
    categories = data.get("categories") if source == "guduo" else data
    if not isinstance(categories, dict):
        raise FetchError("榜单分类数据缺失")
    items = []
    for board in boards:
        rows = categories.get(board)
        if not isinstance(rows, list) or not rows:
            raise FetchError("所选榜单未返回完整数据，保留原有缓存")
        cleaned = [item for raw in rows[:limit] if (item := _clean_item(raw, f"{source}:{board}"))]
        if not cleaned:
            raise FetchError("所选榜单未返回有效影视条目，保留原有缓存")
        items.extend(cleaned)
    return items


def _cached_items(record, source, boards, limit, hours, signature):
    if (not isinstance(record, dict) or record.get("version") != _CACHE_VERSION
            or record.get("signature") != signature):
        return None
    updated = record.get("updated")
    if isinstance(updated, bool) or not isinstance(updated, (int, float)):
        return None
    age = time.time() - updated
    if not math.isfinite(age) or age < 0 or age >= hours * 3600:
        return None
    rows = record.get("items")
    if not isinstance(rows, list) or not rows or len(rows) > len(boards) * limit:
        return None
    expected = {f"{source}:{board}" for board in boards}
    if any(not isinstance(row, dict) or row.get("board") not in expected for row in rows):
        return None
    output = [_clean_item(row, row["board"]) for row in rows]
    if any(row is None for row in output):
        return None
    if {row["board"] for row in output} != expected:
        return None
    if any(sum(row["board"] == board for row in output) > limit for board in expected):
        return None
    return output


async def prepare(ctx, cfg):
    """Return private cfg additions consumed by :func:`source_options`."""
    result = {"_charts_data": {}, "_charts_errors": {}}
    _check_running(cfg)
    if not cfg.get("charts_enabled", False):
        return result
    try:
        groups = _selection(cfg)
        limit = _integer(cfg.get("charts_limit", 20), "每榜条数", 1, 100)
        hours = _integer(cfg.get("charts_cache_hours", 6), "榜单缓存小时数", 1, 24)
        tmdb_key = cfg.get("tmdb_key", "")
        trakt_key = cfg.get("charts_trakt_client_id", "")
        if not isinstance(tmdb_key, str) or not isinstance(trakt_key, str):
            raise FetchError("榜单鉴权配置无效，请重新保存密钥")
    except FetchError as error:
        result["_charts_errors"]["charts_config"] = str(error)
        return result
    storage = getattr(ctx, "storage", None)
    deadline = time.monotonic() + _STAGE_TIMEOUT
    round_deadline = cfg.get("_run_deadline")
    if isinstance(round_deadline, (int, float)) and not isinstance(round_deadline, bool) and math.isfinite(round_deadline):
        deadline = min(deadline, round_deadline)
    transport = Transport(ctx.http, tmdb_key, checkpoint=lambda: _check_running(cfg))
    for source, boards in groups.items():
        _check_running(cfg)
        provider = "charts_" + source
        try:
            if time.monotonic() >= deadline:
                raise FetchError("内置榜单阶段已达 300 秒，本轮未继续读取；原有缓存保留")
            if storage is None:
                raise FetchError("平台插件存储不可用，无法安全缓存榜单")
            credential = tmdb_key if source == "tmdb" else trakt_key if source == "trakt" else ""
            key = "charts_cache:" + source
            signature = _cache_signature(source, boards, limit, credential)
            source_deadline = min(deadline, time.monotonic() + _SOURCE_TIMEOUT)

            async def read_source():
                record = await storage.get(key)
                items = _cached_items(record, source, boards, limit, hours, signature)
                if items is not None:
                    return items, True
                data = await collect(source, transport, limit, trakt_key, boards=boards)
                items = _flatten(source, data, boards, limit)
                _check_running(cfg)
                record = {"version": _CACHE_VERSION, "signature": signature, "updated": time.time(), "items": items}
                if len(json.dumps(record, ensure_ascii=False).encode("utf-8")) > 8 * 1024 * 1024:
                    raise FetchError("榜单缓存超过 8 MB，请减少条数；原有缓存保留")
                await storage.set(key, record)
                return items, False

            items, cached = await _bounded(read_source(), cfg, source_deadline)
            result["_charts_data"][provider] = items
            dates = sorted({row["chartDate"] for row in items if row.get("chartDate")})
            suffix = ("（缓存）" if cached else "") + ("（榜单日期 " + "/".join(dates) + "）" if dates else "")
            ctx.log.info("[自动订阅] %s：%d 个榜单，%d 条%s", _NAMES[source], len(boards), len(items), suffix)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            _check_running(cfg)
            message = safe_error(error)
            result["_charts_errors"][provider] = message
            ctx.log.warning("[自动订阅] %s榜单：%s", _NAMES[source], message)
    return result


def source_options(cfg):
    """List selected sources even when preparation failed, so errors are visible."""
    if not cfg.get("charts_enabled", False):
        return []
    errors = cfg.get("_charts_errors") or {}
    if errors.get("charts_config"):
        return [("charts_config", {"error": errors["charts_config"], "items": []})]
    try:
        groups = _selection(cfg)
    except FetchError as error:
        return [("charts_config", {"error": str(error), "items": []})]
    data = cfg.get("_charts_data") or {}
    return [(provider, {"items": data.get(provider, []),
                        "error": errors.get(provider) or ("" if provider in data else "榜单尚未完成读取")})
            for provider in ("charts_" + source for source in groups)]


class _ChartProvider(RankProvider):
    def fetch(self, options):
        if options.get("error"):
            raise FetchError(str(options["error"]))
        rows = options.get("items")
        if not isinstance(rows, list) or not rows:
            raise FetchError("未读取到有效的内置榜单条目")
        for raw in rows:
            item = _clean_item(raw, raw.get("board", "")) if isinstance(raw, dict) else None
            if item is None:
                continue
            ident = item.get("tmdbId")
            tmdb_id = str(int(ident)) if ident is not None else None
            year = str(item.get("year") or "") or None
            title = item["title"]
            candidates = item.get("searchTitles")
            if not isinstance(candidates, list):
                candidates = []
            candidates = list(dict.fromkeys(value.strip() for value in [title, *candidates]
                                            if isinstance(value, str) and value.strip()))
            yield RankMediaItem(
                title=title, year=year, type_hint=item["mediaType"],
                unique_seed=f"{self.provider_id}:{item['mediaType']}:{tmdb_id or title}:{year or ''}",
                source_meta={"source": self.provider_name, **({"tmdb_id": tmdb_id} if tmdb_id is not None else {}), "search_titles": candidates,
                             "require_genre": item.get("requireGenre"), "chart_board": item["board"],
                             "chart_rank": item.get("rank"), "chart_date": item.get("chartDate"), "rating": item.get("rating"),
                             "popularity": item.get("popularity"), "vote_count": item.get("voteCount")},
            )


for _source, _name in SOURCE_NAMES.items():
    register(type("_" + _source + "Provider", (_ChartProvider,),
                  {"provider_id": _source, "provider_name": _name, "__module__": __name__}))
