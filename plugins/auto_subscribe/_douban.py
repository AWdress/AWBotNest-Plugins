# =============================================================================
# auto_subscribe 私有辅助：豆瓣榜单来源（RSSHub RSS）
#
# 解析 RSSHub 的豆瓣榜单 RSS，产出标准化条目。抓取逻辑移植自原 MoviePilot 版，
# 把 RequestUtils 换成 httpx（默认 trust_env=True，走平台代理——rsshub.app 常被
# SNI 黑名单封锁），DOM 解析用 stdlib xml.dom.minidom。豆瓣评分/季号等在
# 落地阶段由 NextFind /search 提供，故此处不解析评分。
# =============================================================================

from __future__ import annotations

import re
import xml.dom.minidom
from typing import Iterator, List, Optional

import httpx

from ._base import DEFAULT_TIMEOUT, RankProvider, register
from ._models import RankMediaItem

# 默认 RSSHub 基址；被墙/SNI 封锁时可在配置里改为自建实例。
DEFAULT_RSSHUB_BASE = "https://rsshub.app"

# 内置榜单路由：select 值 -> RSSHub 相对路由。
DOUBAN_ADDRESS = {
    "movie-ustop": "/douban/movie/ustop",
    "movie-weekly": "/douban/movie/weekly",
    "movie-real-time": "/douban/movie/weekly/movie_real_time_hotest",
    "show-domestic": "/douban/movie/weekly/show_domestic",
    "movie-hot-gaia": "/douban/movie/weekly/movie_hot_gaia",
    "tv-hot": "/douban/movie/weekly/tv_hot",
    "movie-top250": "/douban/list/movie_top250",
}

# 榜单中文标签（供 __init__ 生成 multiselect options）。
DOUBAN_RANK_LABELS = {
    "movie-ustop": "电影北美票房榜",
    "movie-weekly": "一周口碑电影榜",
    "movie-real-time": "实时热门电影",
    "show-domestic": "热门综艺",
    "movie-hot-gaia": "热门电影",
    "tv-hot": "热门电视剧",
    "movie-top250": "电影TOP250",
}

_REQUEST_TIMEOUT = 60
_YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
_DOUBAN_ID_PATTERN = re.compile(r"/(\d+)/")


def _tag_value(node, tag: str, default: str = "") -> str:
    """取单个子标签的文本值（第一个匹配），无则返回 default。"""
    els = node.getElementsByTagName(tag)
    if not els or not els[0].childNodes:
        return default
    parts = [c.data for c in els[0].childNodes if hasattr(c, "data")]
    return "".join(parts).strip() or default


@register
class DoubanRankProvider(RankProvider):
    """豆瓣榜单来源：解析 RSS item 为标准化 RankMediaItem。"""

    provider_id = "douban"
    provider_name = "豆瓣榜单"

    def fetch(self, options: dict) -> Iterator[RankMediaItem]:
        options = options or {}
        ranks = self.as_list(options.get("ranks"))
        custom_addrs = [
            line.strip()
            for line in str(options.get("rss_addrs") or "").splitlines()
            if line.strip()
        ]
        base = self._normalize_base(options.get("rsshub_base"))
        addr_list = custom_addrs + [
            f"{base}{DOUBAN_ADDRESS[rank]}" for rank in ranks if rank in DOUBAN_ADDRESS
        ]
        for addr in addr_list:
            yield from self._fetch_addr(addr)

    @staticmethod
    def _normalize_base(raw) -> str:
        base = str(raw or "").strip()
        if not base:
            return DEFAULT_RSSHUB_BASE
        base = base.rstrip("/")
        if not re.match(r"^https?://", base):
            base = f"https://{base}"
        return base

    def _fetch_addr(self, addr: str) -> Iterator[RankMediaItem]:
        with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(addr)
            resp.raise_for_status()
            text = resp.text
        root = xml.dom.minidom.parseString(text).documentElement
        if root is None:
            return
        for item in root.getElementsByTagName("item"):
            try:
                media_item = self._parse_item(item)
            except Exception:  # noqa: BLE001 - 单条解析失败不影响其余
                continue
            if media_item is not None:
                yield media_item

    def _parse_item(self, item) -> Optional[RankMediaItem]:
        title = _tag_value(item, "title")
        link = _tag_value(item, "link")
        if not title and not link:
            return None
        douban_id = self._parse_douban_id(str(link or ""))
        year = self._parse_year(item)
        type_hint = self._parse_type(item)
        return RankMediaItem(
            title=str(title),
            year=year,
            type_hint=type_hint,
            douban_id=douban_id,
            poster=self._parse_poster(item),
            source_meta={"link": str(link)},
            unique_seed=f"{title}_{year}_(DB:{douban_id})",
        )

    @staticmethod
    def _parse_douban_id(link: str) -> Optional[str]:
        found = _DOUBAN_ID_PATTERN.findall(link)
        if found and str(found[0]).isdigit():
            return str(found[0])
        return None

    @staticmethod
    def _parse_year(item) -> Optional[str]:
        year = _tag_value(item, "year")
        if year:
            return str(year)
        description = str(_tag_value(item, "description") or "")
        description = re.sub(r"评价数.*?<br>", "", description)
        description = re.sub(r"<img.*?>", "", description)
        found_year = _YEAR_PATTERN.findall(description)
        return found_year[0] if found_year else None

    @staticmethod
    def _parse_type(item) -> Optional[str]:
        """type 标签：movie->movie，其它非空->tv，空->None。"""
        type_str = str(_tag_value(item, "type") or "")
        if type_str == "movie":
            return "movie"
        if type_str:
            return "tv"
        return None

    @staticmethod
    def _parse_poster(item) -> Optional[str]:
        description = str(_tag_value(item, "description") or "")
        found = re.findall(r"<img[^>]+src=\"([^\"]+)\"", description)
        return found[0] if found else None
