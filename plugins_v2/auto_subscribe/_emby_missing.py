"""Read-only, fail-closed Emby inventory compared with aired TMDB episodes."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit


_PAGE_SIZE = 200
_MAX_PAGES = 5000
_TMDB_BASE = "https://api.themoviedb.org/3"
_SHANGHAI = timezone(timedelta(hours=8))


class LibraryScanError(Exception):
    """A short diagnostic which never contains credentials or response bodies."""


def _now_date() -> date:
    return datetime.now(_SHANGHAI).date()


def _integer(value, minimum=0):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip().isdigit():
        result = int(value.strip())
    else:
        return None
    return result if result >= minimum else None


def _settings(cfg):
    server = str(cfg.get("emby_server") or "").strip().rstrip("/")
    emby_key = str(cfg.get("emby_api_key") or "").strip()
    tmdb_key = str(cfg.get("tmdb_key") or "").strip()
    if not server or not emby_key or not tmdb_key:
        raise LibraryScanError("请配置 Emby 地址、Emby API Key 和 TMDB 密钥")
    try:
        parsed = urlsplit(server)
        valid = parsed.scheme in ("http", "https") and parsed.hostname
        valid = valid and not (parsed.username or parsed.password or parsed.query or parsed.fragment)
        parsed.port  # Validate malformed ports without exposing the URL.
    except ValueError:
        valid = False
    if not valid:
        raise LibraryScanError("Emby 地址格式无效，请使用 HTTP 或 HTTPS 地址")
    path = parsed.path.rstrip("/")
    if not path.lower().endswith("/emby"):
        path += "/emby"
    base = urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    delay = _integer(cfg.get("missing_air_delay_days", 1))
    if delay is None or delay > 30:
        raise LibraryScanError("缺集播出缓冲天数必须是 0 到 30 的整数")
    return base, emby_key, tmdb_key, delay


async def _get_json(http, url, *, service, params=None, headers=None):
    try:
        # Use the host HTTP service so its proxy, timeout and request governance
        # remain in effect. Never redirect a request carrying a private token.
        response = await http.get(
            url, params=params or {}, headers=headers or {}, timeout=30,
            follow_redirects=False,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        kind = "请求超时" if "timeout" in type(exc).__name__.lower() else "连接失败"
        raise LibraryScanError(f"{service} {kind}") from None
    status = getattr(response, "status_code", 0)
    if not isinstance(status, int) or not 200 <= status < 300:
        raise LibraryScanError(f"{service} 请求失败（HTTP {status if isinstance(status, int) else '未知'}）")
    try:
        payload = response.json()
    except Exception:
        raise LibraryScanError(f"{service} 返回无效 JSON") from None
    if not isinstance(payload, dict):
        raise LibraryScanError(f"{service} 返回的数据格式无效")
    return payload


async def _emby_items(http, base, key, item_type):
    """Read every page; a short page alone never proves completeness."""
    fields = "ProviderIds,Path,SeriesId,ParentIndexNumber,IndexNumber,IndexNumberEnd,LocationType,IsMissing,IsVirtualItem"
    rows, seen = [], set()
    start = 0
    total = None
    total_present = None
    for _ in range(_MAX_PAGES):
        data = await _get_json(
            http, f"{base}/Items", service="Emby",
            headers={"X-Emby-Token": key, "Accept": "application/json"},
            params={"Recursive": "true", "IncludeItemTypes": item_type,
                    "Fields": fields, "StartIndex": start, "Limit": _PAGE_SIZE,
                    "EnableTotalRecordCount": "true", "SortBy": "SortName",
                    "SortOrder": "Ascending"},
        )
        page = data.get("Items")
        if not isinstance(page, list):
            raise LibraryScanError("Emby 条目列表格式无效，无法确认媒体库完整性")
        present = "TotalRecordCount" in data
        page_total = _integer(data.get("TotalRecordCount")) if present else None
        if present and page_total is None:
            raise LibraryScanError("Emby 分页总数无效")
        if total_present is None:
            total_present, total = present, page_total
        elif total_present != present or page_total != total:
            raise LibraryScanError("Emby 分页总数发生变化，请稍后重新检查")
        if not page:
            if total is not None and start != total:
                raise LibraryScanError("Emby 分页提前结束，无法确认媒体库完整性")
            return rows
        if total is not None and start + len(page) > total:
            raise LibraryScanError("Emby 分页条数与总数不一致")
        for row in page:
            if not isinstance(row, dict) or not row.get("Id") or row.get("Type") != item_type:
                raise LibraryScanError("Emby 返回的条目缺少编号或媒体类型不符")
            item_id = str(row["Id"])
            if item_id in seen:
                raise LibraryScanError("Emby 分页重复，无法确认媒体库完整性")
            seen.add(item_id)
            rows.append(row)
        start += len(page)
        if total is not None and start == total:
            return rows
    raise LibraryScanError("Emby 分页超过安全范围，无法确认媒体库完整性")


def _tmdb_id(row):
    providers = row.get("ProviderIds")
    if not isinstance(providers, dict):
        return ""
    ids = {_integer(value, 1) for name, value in providers.items() if str(name).lower() == "tmdb"}
    if len(ids) != 1 or None in ids:
        return ""
    return str(ids.pop())


def _true(value):
    return value is True or (not isinstance(value, bool) and str(value).strip().lower() in ("1", "true"))


def _local_groups(series, episodes):
    groups, owners = {}, {}
    series_ids = {str(row["Id"]) for row in series}
    unknown = 0
    for row in series:
        if (str(row.get("LocationType") or "").lower() == "virtual"
                or _true(row.get("IsMissing")) or _true(row.get("IsVirtualItem"))):
            unknown += 1
            continue
        tmdb_id = _tmdb_id(row)
        if not tmdb_id:
            unknown += 1
            continue
        group = groups.setdefault(tmdb_id, {"title": str(row.get("Name") or tmdb_id), "local": {}, "unknown": False})
        owners[str(row["Id"])] = tmdb_id
    for row in episodes:
        location = str(row.get("LocationType") or "").lower()
        if location == "virtual" or _true(row.get("IsMissing")) or _true(row.get("IsVirtualItem")):
            continue
        series_id = str(row.get("SeriesId") or "")
        if not series_id or series_id not in series_ids:
            raise LibraryScanError("Emby 单集缺少可核对的剧集归属，无法确认媒体库完整性")
        tmdb_id = owners.get(series_id)
        # Episodes from unmatched shows cannot establish a series identity.
        if not tmdb_id:
            continue
        group = groups[tmdb_id]
        season = _integer(row.get("ParentIndexNumber"))
        if season == 0:
            continue
        episode = _integer(row.get("IndexNumber"), 1)
        end_value = row.get("IndexNumberEnd")
        end = episode if end_value is None else _integer(end_value, 1)
        local = location in ("filesystem", "remote") or bool(str(row.get("Path") or "").strip())
        if (season is None or episode is None or end is None or end < episode
                or end - episode > 1000 or not local):
            group["unknown"] = True
            continue
        group["local"].setdefault(season, set()).update(range(episode, end + 1))
    return groups, unknown


async def _tmdb_get(http, key, path):
    if key.startswith("eyJ"):
        params, headers = {"language": "zh-CN"}, {"Authorization": f"Bearer {key}"}
    else:
        params, headers = {"language": "zh-CN", "api_key": key}, {}
    return await _get_json(http, f"{_TMDB_BASE}{path}", service="TMDB", params=params, headers=headers)


def _air_date(value):
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
        return parsed if parsed.isoformat() == value else None
    except ValueError:
        return None


async def _expected_episodes(http, key, tmdb_id, cutoff):
    detail = await _tmdb_get(http, key, f"/tv/{tmdb_id}")
    if _integer(detail.get("id"), 1) != int(tmdb_id) or not isinstance(detail.get("seasons"), list):
        raise LibraryScanError("TMDB 剧集详情格式无效")
    seasons = set()
    for season in detail["seasons"]:
        number = _integer(season.get("season_number")) if isinstance(season, dict) else None
        if number is None:
            raise LibraryScanError("TMDB 季号格式无效")
        if number > 0:
            seasons.add(number)
    expected = {}
    for number in sorted(seasons):
        data = await _tmdb_get(http, key, f"/tv/{tmdb_id}/season/{number}")
        if _integer(data.get("season_number")) != number or not isinstance(data.get("episodes"), list):
            raise LibraryScanError("TMDB 季详情格式无效")
        by_number = {}
        for episode in data["episodes"]:
            if not isinstance(episode, dict):
                raise LibraryScanError("TMDB 单集详情格式无效")
            episode_number = _integer(episode.get("episode_number"), 1)
            if (episode_number is None
                    or ("season_number" in episode and _integer(episode["season_number"]) != number)):
                raise LibraryScanError("TMDB 单集编号格式无效")
            air_date = _air_date(episode.get("air_date"))
            if episode_number in by_number and by_number[episode_number] != air_date:
                raise LibraryScanError("TMDB 单集编号重复且播出日期冲突")
            by_number[episode_number] = air_date
        expected[number] = {ep for ep, aired in by_number.items() if aired is not None and aired <= cutoff}
    return expected


def _safe_log(log, level, message, *args):
    if log:
        getattr(log, level)(message, *args)


async def scan_missing(cfg, http, log=None) -> dict:
    """Return confirmed candidates; never subscribe or alter Emby metadata."""
    result = {"items": [], "scanned": 0, "matched": 0, "complete": 0,
              "unknown": 0, "failed": 0, "missing_episodes": 0, "error": ""}
    try:
        base, emby_key, tmdb_key, delay = _settings(cfg)
        series = await _emby_items(http, base, emby_key, "Series")
        result["scanned"] = len(series)
        # Inventory completion precedes all comparisons, so an interrupted
        # Episode page can never turn partially collected coverage into gaps.
        episodes = await _emby_items(http, base, emby_key, "Episode") if series else []
    except LibraryScanError as exc:
        result["error"] = str(exc)
        _safe_log(log, "warning", "[自动订阅] Emby 缺集检查失败：%s", result["error"])
        return result
    try:
        groups, unknown = _local_groups(series, episodes)
    except LibraryScanError as exc:
        result["error"] = str(exc)
        _safe_log(log, "warning", "[自动订阅] Emby 缺集检查失败：%s", result["error"])
        return result
    result["matched"] = len(groups)
    result["unknown"] = unknown + sum(group["unknown"] for group in groups.values())
    cutoff = _now_date() - timedelta(days=delay)
    semaphore = asyncio.Semaphore(4)

    async def compare(tmdb_id, group):
        async with semaphore:
            try:
                expected = await _expected_episodes(http, tmdb_key, tmdb_id, cutoff)
            except LibraryScanError as exc:
                return tmdb_id, group, None, str(exc)
            missing = {season: sorted(numbers - group["local"].get(season, set()))
                       for season, numbers in expected.items()}
            return tmdb_id, group, {s: eps for s, eps in missing.items() if eps}, ""

    tasks = [asyncio.create_task(compare(tmdb_id, group)) for tmdb_id, group in groups.items() if not group["unknown"]]
    try:
        comparisons = await asyncio.gather(*tasks)
    finally:
        # Cancellation must not leave HTTP workers running after plugin stop.
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    for tmdb_id, group, missing, error in comparisons:
        if error:
            result["failed"] += 1
            _safe_log(log, "warning", "[自动订阅] TMDB 缺集检查跳过剧集 %s：%s", tmdb_id, error)
        elif missing:
            result["items"].append({"tmdb_id": tmdb_id, "media_type": "tv", "title": group["title"], "missing_by_season": missing})
            count = sum(map(len, missing.values()))
            result["missing_episodes"] += count
            details = "；".join(f"S{season:02d}: " + ",".join(f"E{ep:02d}" for ep in eps) for season, eps in missing.items())
            if len(details) > 400:
                details = details[:400] + "…"
            _safe_log(log, "info", "[自动订阅] Emby 剧集 %s 缺 %d 集：%s", tmdb_id, count, details)
        else:
            result["complete"] += 1
    return result


async def test_connections(cfg, http) -> dict:
    """Only read Series inventory and TMDB configuration; never mutate."""
    base, emby_key, tmdb_key, _ = _settings(cfg)
    series = await _emby_items(http, base, emby_key, "Series")
    config = await _tmdb_get(http, tmdb_key, "/configuration")
    if not isinstance(config.get("images"), dict) or not isinstance(config.get("change_keys"), list):
        raise LibraryScanError("TMDB 连接测试响应格式无效")
    return {"series_count": len(series), "message": f"Emby 与 TMDB 连接成功，读取到 {len(series)} 条剧集"}
