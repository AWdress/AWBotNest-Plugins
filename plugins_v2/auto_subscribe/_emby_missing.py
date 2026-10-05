"""Read-only, fail-closed Emby inventory compared with aired TMDB episodes."""

from __future__ import annotations

import asyncio
import math
from datetime import date, datetime, timedelta, timezone
from time import monotonic
from urllib.parse import urlsplit, urlunsplit


_PAGE_SIZE = 1000
_MAX_PAGES = 5000
_HTTP_TIMEOUT_SECONDS = 35.0
_SCAN_TIMEOUT_SECONDS = 1500.0
_PROGRESS_LOG_INTERVAL_SECONDS = 60.0
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
        response = await asyncio.wait_for(
            http.get(url, params=params or {}, headers=headers or {}, timeout=30,
                     follow_redirects=False),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise LibraryScanError(f"{service} 请求超时（整次请求限时 {_HTTP_TIMEOUT_SECONDS:g} 秒）") from None
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


async def _emby_items(http, base, key, item_type, log=None):
    """Read every page; a short page alone never proves completeness."""
    fields = "ProviderIds,Path,SeriesId,ParentIndexNumber,IndexNumber,IndexNumberEnd,LocationType,IsMissing,IsVirtualItem"
    rows, seen = [], set()
    start = 0
    total = None
    total_present = None
    last_progress = monotonic()
    for _ in range(_MAX_PAGES):
        data = await _get_json(
            http, f"{base}/Items", service="Emby",
            headers={"X-Emby-Token": key, "Accept": "application/json"},
            params={"Recursive": "true", "IncludeItemTypes": item_type,
                    "Fields": fields, "StartIndex": start, "Limit": _PAGE_SIZE,
                    # SortName-first ordering can overlap pages even with a
                    # secondary key. Creation-first reduces those ties; the
                    # unique-ID and total checks below must still remain.
                    "EnableTotalRecordCount": "true", "SortBy": "DateCreated,SortName",
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
        if monotonic() - last_progress >= _PROGRESS_LOG_INTERVAL_SECONDS:
            _safe_log(log, "info", "[自动订阅] Emby %s 读取进度：%d/%s 条",
                      "剧集" if item_type == "Series" else "单集", start,
                      str(total) if total is not None else "总数待确认")
            last_progress = monotonic()
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


def _record_comparison(result, state, comparison):
    tmdb_id, group, missing, error = comparison
    state["processed"] += 1
    if error:
        result["failed"] += 1
        detail = f"剧集 {tmdb_id}：{error}"
    elif missing:
        result["items"].append({"tmdb_id": tmdb_id, "media_type": "tv", "title": group["title"], "missing_by_season": missing})
        count = sum(map(len, missing.values()))
        result["missing_episodes"] += count
        episodes = "；".join(f"S{season:02d}: " + ",".join(f"E{ep:02d}" for ep in eps) for season, eps in missing.items())
        if len(episodes) > 80:
            episodes = episodes[:80] + "…"
        detail = f"剧集 {tmdb_id} 缺 {count} 集（{episodes}）"
    else:
        result["complete"] += 1
        detail = ""
    # Keep progress informative without flooding a large library's logs.
    if detail and len(state["details"]) < 3:
        state["details"].append(detail)


def _report_progress(result, state, log, *, level="info", label="进度"):
    details = "；".join(state["details"])
    _safe_log(log, level, "[自动订阅] TMDB 缺集核对%s：已核对 %d/%d 部，完整 %d，缺集 %d，失败 %d，未核对 %d%s",
              label, state["processed"], state["eligible"], result["complete"],
              len(result["items"]), result["failed"],
              max(0, state["eligible"] - state["processed"]),
              f"；{details}" if details else "")
    state["details"].clear()


async def _scan_missing(cfg, http, log, result, state):
    try:
        base, emby_key, tmdb_key, delay = _settings(cfg)
        _safe_log(log, "info", "[自动订阅] Emby 缺集检查：开始完整读取剧集与单集库存")
        series = await _emby_items(http, base, emby_key, "Series", log)
        result["scanned"] = len(series)
        _safe_log(log, "info", "[自动订阅] Emby 剧集读取完成：%d 条，开始读取单集", len(series))
        # Inventory completion precedes all comparisons, so an interrupted
        # Episode page can never turn partially collected coverage into gaps.
        episodes = await _emby_items(http, base, emby_key, "Episode", log) if series else []
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
    state["inventory_complete"] = True
    state["eligible"] = sum(not group["unknown"] for group in groups.values())
    _safe_log(log, "info", "[自动订阅] Emby 库存读取完成：剧集 %d 条，单集 %d 条，待核对 TMDB 剧集 %d 部，资料不全跳过 %d",
              len(series), len(episodes), state["eligible"], result["unknown"])
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
    pending = set(tasks)
    last_progress = monotonic()
    try:
        while pending:
            remaining_interval = max(0.001, _PROGRESS_LOG_INTERVAL_SECONDS - (monotonic() - last_progress))
            done, pending = await asyncio.wait(
                pending, timeout=remaining_interval, return_when=asyncio.FIRST_COMPLETED,
            )
            first_result = state["processed"] == 0 and bool(done)
            for task in done:
                _record_comparison(result, state, task.result())
            if first_result or monotonic() - last_progress >= _PROGRESS_LOG_INTERVAL_SECONDS:
                _report_progress(result, state, log)
                last_progress = monotonic()
    finally:
        # Cancellation must not leave HTTP workers running after plugin stop.
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    _report_progress(result, state, log, level="warning" if result["failed"] else "info", label="结束")
    return result


async def scan_missing(cfg, http, log=None) -> dict:
    """Return completed comparisons within a bounded, cancellable scan.

    An incomplete Emby inventory is fatal and yields no candidates. Once the
    inventory is complete, a time limit retains fully compared shows while
    explicitly marking the rest unprocessed; ``error`` remains fatal-only.
    """
    result = {"items": [], "scanned": 0, "matched": 0, "complete": 0,
              "unknown": 0, "failed": 0, "missing_episodes": 0, "error": "",
              "unprocessed": 0, "timed_out": False}
    state = {"inventory_complete": False, "eligible": 0, "processed": 0, "details": []}
    budget = _SCAN_TIMEOUT_SECONDS
    deadline = cfg.get("_run_deadline")
    if isinstance(deadline, (int, float)) and not isinstance(deadline, bool) and math.isfinite(deadline):
        budget = max(0.0, min(budget, deadline - monotonic()))
    try:
        await asyncio.wait_for(_scan_missing(cfg, http, log, result, state), timeout=budget)
    except TimeoutError:
        result["timed_out"] = True
        if not state["inventory_complete"]:
            result["error"] = "缺集检查达到时间上限，Emby 库存尚未完整读取，本轮未新增缺集订阅"
            result["items"].clear()
            result["missing_episodes"] = 0
            _safe_log(log, "warning", "[自动订阅] %s", result["error"])
        else:
            result["unprocessed"] = max(0, state["eligible"] - state["processed"])
            result["failed"] += result["unprocessed"]
            _report_progress(result, state, log, level="warning", label="达到时间上限")
            _safe_log(log, "warning", "[自动订阅] 已保留 %d 部完整核对的缺集结果，另有 %d 部未核对",
                      len(result["items"]), result["unprocessed"])
    result["items"].sort(key=lambda item: int(item["tmdb_id"]))
    return result


async def test_connections(cfg, http) -> dict:
    """Only read Series inventory and TMDB configuration; never mutate."""
    base, emby_key, tmdb_key, _ = _settings(cfg)
    series = await _emby_items(http, base, emby_key, "Series")
    config = await _tmdb_get(http, tmdb_key, "/configuration")
    if not isinstance(config.get("images"), dict) or not isinstance(config.get("change_keys"), list):
        raise LibraryScanError("TMDB 连接测试响应格式无效")
    return {"series_count": len(series), "message": f"Emby 与 TMDB 连接成功，读取到 {len(series)} 条剧集"}
