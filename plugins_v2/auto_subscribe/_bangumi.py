"""利用蜜柑详情页已有的 Bangumi ID 获取番剧标准标题与别名。"""

from __future__ import annotations

from threading import RLock
from time import monotonic

import httpx


_API = "https://api.bgm.tv/v0/subjects/{subject_id}"
_UA = "AWBotNest-AutoSubscribe/1.3"
_CACHE_TTL = 3600
_cache: dict[int, tuple[float, list[str]]] = {}
_lock = RLock()


def _append_unique(output: list[str], value) -> None:
    text = " ".join(str(value or "").split()).strip()
    if text and text not in output:
        output.append(text)


def subject_titles(subject_id: int, timeout: int = 12) -> list[str]:
    """返回中文名、原名及 infobox 别名；失败安全返回空列表。"""
    try:
        subject_id = int(subject_id)
    except (TypeError, ValueError):
        return []
    if subject_id <= 0:
        return []
    now = monotonic()
    with _lock:
        cached = _cache.get(subject_id)
        if cached and now - cached[0] < _CACHE_TTL:
            return list(cached[1])

    titles: list[str] = []
    try:
        response = httpx.get(
            _API.format(subject_id=subject_id),
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=max(3, min(int(timeout or 12), 30)),
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            _append_unique(titles, payload.get("name_cn"))
            _append_unique(titles, payload.get("name"))
            for row in payload.get("infobox") or []:
                if not isinstance(row, dict) or row.get("key") not in ("别名", "中文名", "原作名"):
                    continue
                value = row.get("value")
                values = value if isinstance(value, list) else [value]
                for item in values:
                    if isinstance(item, dict):
                        _append_unique(titles, item.get("v") or item.get("value"))
                    else:
                        _append_unique(titles, item)
    except (httpx.HTTPError, ValueError, TypeError):
        titles = []

    with _lock:
        _cache[subject_id] = (monotonic(), list(titles))
    return titles
