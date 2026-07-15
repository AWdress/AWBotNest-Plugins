# =============================================================================
# auto_subscribe 私有辅助：猫眼榜单来源（票房 + 网播热度）
#
# 移植自原 MoviePilot 版，但**降级为无 Cookie**：平台无 Playwright，去掉
# PlaywrightHelper 取 Cookie 的步骤，直接用随机 UA 请求猫眼专业版 JSON 接口
# （实测多数榜单无 Cookie 仍可返回；个别受风控可能为空，当作无结果跳过）。
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
        data = ((payload or {}).get("movieList") or {}).get("list") or []
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
        data = ((payload or {}).get("dataList") or {}).get("list") or []
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
    def _request_json(url: str, headers: dict) -> Optional[dict]:
        """GET 并解析 JSON；无响应/解析失败返回 None（无 Cookie 降级，空当无结果）。"""
        try:
            with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True,
                              headers=headers) as client:
                resp = client.get(url)
                if resp.status_code != 200 or not resp.text:
                    return None
                return resp.json()
        except Exception:  # noqa: BLE001 - 风控/网络失败当无结果
            return None
