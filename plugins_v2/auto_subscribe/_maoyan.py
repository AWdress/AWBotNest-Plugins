# =============================================================================
# auto_subscribe 私有辅助：猫眼榜单来源（票房 + 网播热度）
#
# 移植自原 MoviePilot 版。Cookie 由 __init__ 用平台 ctx.browser（CloakBrowser/
# Playwright）在事件循环里预取后经 options["cookies"] 注入（本 provider 跑在
# asyncio.to_thread 里、不能直接 await 浏览器）。取不到 Cookie 时自动降级无 Cookie
# 请求；请求失败或风控页面必须明确报错，不能当作正常空榜单。
# 网络电影因数据源停更已移除。年份由 releaseInfo（距今天数）反推。
# =============================================================================

from __future__ import annotations

import random
import re
from datetime import date, timedelta
from typing import Dict, Iterator, List, Optional

import httpx

from ._base import RankProvider, register
from ._models import RankMediaItem
from ._http_errors import request_error

MAOYAN_URL = "https://piaofang.maoyan.com"

# 网播热度媒体类型（webHeatData 的 seriesType）。
SERIES_TYPE = {"series": "4", "tv": "0", "web": "1", "variety": "2"}
# 平台：选项值 -> platformType 参数（全网为空串）。
PLATFORM_TYPE = {
    "all": "", "tx": "3", "iqiyi": "2", "mgtv": "7", "youku": "1",
    "sohu": "5", "letv": "4", "pptv": "6",
}
PLATFORM_LABELS = {
    "all": "全网", "tx": "腾讯视频", "iqiyi": "爱奇艺", "youku": "优酷",
    "letv": "乐视", "mgtv": "芒果TV", "pptv": "PPTV", "sohu": "搜狐",
}
PLATFORM_ORDER = ("all", "tx", "iqiyi", "youku", "letv", "mgtv", "pptv", "sohu")
MEDIA_LABELS = {"series": "电视剧+网络剧", "tv": "电视剧", "web": "网络剧", "variety": "综艺"}
MEDIA_ORDER = ("series", "tv", "web", "variety")

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

_DEFAULT_NUM = 10
_REQUEST_TIMEOUT = 30


@register
class MaoyanRankProvider(RankProvider):
    """猫眼榜单来源：电影票房 + 网播热度（无 Cookie 降级）。"""

    provider_id = "maoyan"
    provider_name = "猫眼榜单"

    def fetch(self, options: dict) -> Iterator[RankMediaItem]:
        options = options or {}
        num = self.to_int(options.get("num"), _DEFAULT_NUM)
        headers = {"User-Agent": random.choice(_USER_AGENTS)}
        # Cookie 由 __init__ 经 ctx.browser 预取后注入（dict {name: value}）；无则降级。
        self._cookies = options.get("cookies") or None
        self._http = options.get("_http")
        seen: set = set()

        if bool(options.get("movie_box", True)):
            yield from self._fetch_movie_box(headers, num, seen)

        platforms = [p for p in self.as_list(options.get("web_platforms")) if p in PLATFORM_TYPE]
        media_types = [m for m in self.as_list(options.get("web_types")) if m in SERIES_TYPE]
        for platform in platforms:
            platform_type = PLATFORM_TYPE.get(platform, "")
            for media in media_types:
                yield from self._fetch_web_heat_one(SERIES_TYPE[media], platform_type,
                                                    headers, num, seen)

    def _fetch_movie_box(self, headers: dict, num: int, seen: set) -> Iterator[RankMediaItem]:
        """电影票房榜：/dashboard-ajax/movie。"""
        payload = self._request_json(f"{MAOYAN_URL}/dashboard-ajax/movie", headers)
        data = self._ranking_list(payload, "movieList")
        for entry in data[:num]:
            try:
                info = entry.get("movieInfo") or {}
                yield from self._emit(info.get("movieName"), info.get("releaseInfo"), "movie", seen)
            except Exception:  # noqa: BLE001 - 单条兜底
                continue

    def _fetch_web_heat_one(self, series_type: str, platform_type: str,
                            headers: dict, num: int, seen: set) -> Iterator[RankMediaItem]:
        """网播热度单榜：/dashboard/webHeatData。"""
        url = (f"{MAOYAN_URL}/dashboard/webHeatData"
               f"?seriesType={series_type}&platformType={platform_type}&showDate=2")
        payload = self._request_json(url, headers)
        data = self._ranking_list(payload, "dataList")
        for entry in data[:num]:
            try:
                info = entry.get("seriesInfo") or {}
                yield from self._emit(info.get("name"), info.get("releaseInfo"), "tv", seen)
            except Exception:  # noqa: BLE001 - 单条兜底
                continue

    def _emit(self, title, release_info, mtype: str, seen: set) -> Iterator[RankMediaItem]:
        if not title:
            return
        dedup = f"{mtype}_{title}"
        if dedup in seen:
            return
        seen.add(dedup)
        year = self._year_from_release_info(release_info)
        yield RankMediaItem(
            title=str(title),
            year=year,
            type_hint=mtype,
            source_meta={"releaseInfo": release_info},
            unique_seed=f"{mtype}_{title}_{year}",
        )

    @staticmethod
    def _year_from_release_info(release_info) -> Optional[str]:
        """由 releaseInfo（距今天数）反推年份；缺失或解析失败返回 None。"""
        if not release_info:
            return None
        try:
            days = int("".join(re.findall(r"\d", str(release_info))))
        except (ValueError, TypeError):
            return None
        try:
            target = date.today() - timedelta(days=days)
            return str(target.year)
        except (OverflowError, ValueError):
            return None

    @staticmethod
    def _ranking_list(payload: dict, key: str) -> List[dict]:
        container = payload.get(key)
        data = container.get("list") if isinstance(container, dict) else None
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise RuntimeError(f"猫眼榜单响应格式无效（缺少有效 {key}.list），请检查站点是否要求验证")
        return data

    def _request_json(self, url: str, headers: dict) -> dict:
        """GET 并解析 JSON；失败向上报告，只有合法空列表代表空榜单。

        带上 __init__ 经 ctx.browser 预取注入的 Cookie（self._cookies，可能为 None）。
        """
        cookies = getattr(self, "_cookies", None)
        try:
            http = getattr(self, "_http", None)
            if http is not None:
                resp = http.get(url, timeout=_REQUEST_TIMEOUT, follow_redirects=True,
                                headers=headers, cookies=cookies)
            else:
                with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True,
                                  headers=headers, cookies=cookies) as client:
                    resp = client.get(url)
            resp.raise_for_status()
            try:
                payload = resp.json()
            except ValueError:
                raise RuntimeError("猫眼榜单没有返回有效 JSON，请检查站点是否要求验证") from None
        except httpx.HTTPError as exc:
            raise RuntimeError(request_error(exc, "猫眼请求")) from None
        if not isinstance(payload, dict):
            raise RuntimeError("猫眼榜单响应格式无效（缺少数据对象）")
        if "success" in payload and not (
            payload["success"] is True or payload["success"] == 1
            or str(payload["success"]).strip().lower() in ("true", "1")
        ):
            raise RuntimeError("猫眼榜单返回失败，请检查站点是否要求验证")
        return payload
