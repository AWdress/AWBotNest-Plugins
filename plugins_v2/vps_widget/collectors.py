"""Read public media charts through the plugin's bounded HTTP transport.

The collectors own only source parsing. Authentication, proxies, retry policy,
TMDB matching and persistent cache updates belong to the caller.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any

from .transport import FetchError


_BEIJING = timezone(timedelta(hours=8))
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_MONTHS = dict(zip(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    range(1, 13),
))
_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr",
})

DOUBAN_CHANNELS = (
    "tv", "tv_domestic", "tv_american", "tv_japanese", "tv_korean",
    "tv_animation", "tv_documentary", "show_domestic", "show_foreign",
)
THEATERS = (
    ("迷雾剧场", "128396349"), ("白夜剧场", "158539495"),
    ("X剧场", "155026800"), ("玛卡巴卡的悬疑剧", "160885987"),
    ("横屏短剧", "152299516"), ("生花剧场", "159069554"),
    ("大家剧场", "160644809"), ("小逗剧场", "146055365"),
    ("十分剧场", "147708618"), ("板凳单元", "163392459"),
    ("萤火单元", "163549603"), ("正午阳光", "125370543"),
    ("恋恋剧场", "156086548"), ("悬疑剧场", "128400108"),
    ("微尘剧场", "161658331"),
)


class _Node:
    def __init__(self, tag: str, attrs: list[tuple[str, str | None]] | None = None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children: list[_Node | str] = []

    def has_class(self, name: str) -> bool:
        return name in (self.attrs.get("class") or "").split()

    def nodes(self):
        for child in self.children:
            if isinstance(child, _Node):
                yield child
                yield from child.nodes()

    def text(self) -> str:
        parts = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag not in {"script", "style"}:
                parts.append(child.text())
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    def first(self, *, tag: str | None = None, cls: str | None = None):
        return next((node for node in self.nodes()
                     if (tag is None or node.tag == tag)
                     and (cls is None or node.has_class(cls))), None)


class _Document(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.root = _Node("document")
        self.stack = [self.root]
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        # Browsers implicitly close repeated list/table rows in imperfect HTML.
        if tag in {"li", "tr"} and self.stack[-1].tag == tag:
            self.stack.pop()
        node = _Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(_Node(tag, attrs))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _mapping(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise FetchError(f"{label}：接口返回格式不正确")
    return value


def _array(value: Any, label: str) -> list:
    if not isinstance(value, list):
        raise FetchError(f"{label}：榜单数据不是列表")
    return value


def _code(data: dict, accepted: tuple, label: str) -> None:
    if data.get("code") not in accepted:
        raise FetchError(f"{label}：接口未返回有效榜单")


def _number(value: Any, default: float = 0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _year(value: Any) -> str | None:
    match = _YEAR.search(str(value or ""))
    return match.group(0) if match else None


def _title(value: Any) -> str:
    return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else ""


def _entry(title: Any, media_type: str = "tv", **extra) -> dict | None:
    title = _title(title)
    return {"title": title, "mediaType": media_type, **extra} if title else None


def _dedupe(items: list[dict], limit: int) -> list[dict]:
    output, seen = [], set()
    for item in items:
        key = (item.get("tmdbId") or item.get("title", "").casefold(),
               item.get("mediaType"), item.get("year"))
        if key not in seen:
            seen.add(key)
            output.append(item)
            if len(output) >= limit:
                break
    return output


def _nonempty(items: list, label: str) -> list:
    if not items:
        raise FetchError(f"{label}：未取得有效榜单条目")
    return items


def _page_signature(items: list[dict]) -> tuple:
    return tuple((item.get("title"), item.get("year")) for item in items)


def _repeat_guard(seen: set, items: list[dict], label: str) -> None:
    signature = _page_signature(items)
    if signature in seen:
        raise FetchError(f"{label}：接口重复返回同一页，已停止更新")
    seen.add(signature)


def parse_theater(text: str) -> list[dict]:
    """Accept desktop doulist cards and the older mobile list markup."""
    root = _Document(text).root
    desktop = [node for node in root.nodes() if node.has_class("doulist-item")]
    mobile_list = root.first(tag="ul", cls="doulist-items")
    cards = desktop or ([node for node in mobile_list.nodes() if node.tag == "li"] if mobile_list else [])
    items = []
    for card in cards:
        heading = card.first(cls="title")
        if not heading:
            continue
        details = card.first(cls="abstract") or card.first(cls="meta")
        detail_text = details.text() if details else ""
        explicit_year = re.search(r"年份\s*[:：]\s*((?:19|20)\d{2})", detail_text)
        year = explicit_year.group(1) if explicit_year else _year(detail_text)
        item = _entry(heading.text(), year=year)
        if item:
            items.append(item)
    return items


def parse_bangumi(text: str) -> list[dict]:
    root = _Document(text).root
    items = []
    for card in root.nodes():
        if card.tag != "li" or not card.has_class("item"):
            continue
        heading = card.first(tag="a", cls="l")
        if not heading:
            continue
        original = card.first(tag="small", cls="grey")
        info = card.first(tag="p", cls="info")
        titles = list(dict.fromkeys(filter(None, (heading.text(), original.text() if original else ""))))
        item = _entry(heading.text(), year=_year(info.text() if info else ""),
                      searchTitles=titles, requireGenre=16)
        if item:
            items.append(item)
    return items


def parse_mal(text: str) -> list[dict]:
    root = _Document(text).root
    items = []
    for row in root.nodes():
        if row.tag != "tr" or not row.has_class("ranking-list"):
            continue
        heading = row.first(tag="h3")
        candidates = heading.nodes() if heading else row.nodes()
        link = next((node for node in candidates if node.tag == "a"
                     and re.search(r"/anime/\d+", node.attrs.get("href") or "")), None)
        if not link:
            continue
        info = row.first(cls="information")
        score = row.first(cls="score-label")
        rank_cell = row.first(tag="td", cls="rank")
        rank_match = re.search(r"\d+", rank_cell.text()) if rank_cell else None
        date_match = re.search(r"\b([A-Z][a-z]{2})\s+((?:19|20)\d{2})\b", info.text() if info else "")
        release = ""
        if date_match and date_match.group(1) in _MONTHS:
            release = f"{date_match.group(2)}-{_MONTHS[date_match.group(1)]:02d}-01"
        title = link.text()
        cleaned = re.sub(r"\b\d+(?:st|nd|rd|th)\s+season\b|\bseason\s+\d+\b|\b(?:part|cour|course)\s+[IVXLC0-9]+\b", "", title, flags=re.I)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—:：")
        item = _entry(title, year=_year(release), rank=int(rank_match.group()) if rank_match else len(items) + 1,
                      heat=_number(score.text() if score else ""), releaseDate=release,
                      searchTitles=list(dict.fromkeys(filter(None, (cleaned, title)))),
                      searchLanguage="en-US", requireGenre=16)
        if item:
            items.append(item)
    return items


async def _guduo(transport, limit: int) -> dict:
    yesterday = (datetime.now(_BEIJING).date() - timedelta(days=1)).isoformat()
    categories = {}
    for name, category, media_type in (
        ("剧集", "NETWORK_DRAMA", "tv"), ("综艺", "NETWORK_VARIETY", "tv"),
        ("动漫", "ALL_ANIME", "tv"), ("电影", "NETWORK_MOVIE", "movie"),
    ):
        label = f"骨朵热度/{name}"
        data = _mapping(await transport.json("https://d2.guduomedia.com/m/v3/billboard/list", params={
            "type": "DAILY", "category": category, "date": yesterday,
            "attach": "gdi", "orderTitle": "gdi", "platformId": 0,
        }, headers={"User-Agent": _UA}), label)
        _code(data, (0, "0"), label)
        raw = _array(data.get("data"), label)
        items = []
        for rank, node in enumerate(raw[:limit], 1):
            if not isinstance(node, dict):
                continue
            extra = {"rank": rank, "heat": _number(node.get("gdi")), "category": name}
            if name == "动漫":
                extra["requireGenre"] = 16
            item = _entry(node.get("name"), media_type, **extra)
            if item:
                items.append(item)
        categories[name] = _nonempty(_dedupe(items, limit), label)
    return {"source": "Guduo Media", "billboard_date": yesterday, "categories": categories}


async def _douban(transport, limit: int) -> dict:
    output = {}
    for channel in DOUBAN_CHANNELS:
        label = f"豆瓣热榜/{channel}"
        data = _mapping(await transport.json(
            "https://m.douban.com/rexxar/api/v2/subject/recent_hot/tv",
            params={"start": 0, "limit": limit, "type": channel},
            headers={"User-Agent": _MOBILE_UA, "Referer": "https://m.douban.com/movie/"},
        ), label)
        raw = _array(data.get("items"), label)
        items = []
        for rank, node in enumerate(raw[:limit], 1):
            if not isinstance(node, dict):
                continue
            subtitle = str(node.get("card_subtitle") or "")
            item = _entry(node.get("title"), rank=rank, year=_year(subtitle.split("/")[0]))
            if item:
                items.append(item)
        output[channel] = _nonempty(_dedupe(items, limit), label)
    return output


async def _mgtv(transport, limit: int) -> dict:
    output = {}
    for key, channel_id in (("tv", 2), ("show", 1)):
        label = f"芒果TV/{key}"
        items, seen = [], set()
        for page in range(1, 5):
            params = {"allowedpn": 1, "channelId": channel_id, "pn": page, "pc": 30,
                      "kind": "a1", "area": "a1", "year": "all", "sort": "c1"}
            if key == "tv":
                params["chargeInfo"] = "a1"
            data = _mapping(await transport.json(
                "https://pianku.api.mgtv.com/rider/list/pcweb/v3", params=params,
                headers={"User-Agent": _UA, "Referer": "https://www.mgtv.com/"},
            ), label)
            _code(data, (200, "200", 0, "0"), label)
            raw = _array(_mapping(data.get("data"), label).get("hitDocs"), label)
            if not raw:
                break
            rows = []
            for node in raw:
                if not isinstance(node, dict):
                    continue
                item = _entry(node.get("title"), year=_year(node.get("subtitle")) or _year(node.get("title")))
                if item:
                    rows.append(item)
            _nonempty(rows, label)
            _repeat_guard(seen, rows, label)
            items.extend(rows)
            if len(_dedupe(items, limit)) >= limit or len(raw) < 30:
                break
        output[key] = _nonempty(_dedupe(items, limit), label)
    return output


async def _theater(transport, limit: int) -> dict:
    output = {}
    current_year = datetime.now(_BEIJING).year
    for name, list_id in THEATERS:
        label = f"剧场平台/{name}"
        items, seen, pages = [], set(), 0
        for page in range(4):
            html = await transport.text(f"https://www.douban.com/doulist/{list_id}/",
                                        params={"start": page * 25}, headers={"User-Agent": _UA})
            if not isinstance(html, str):
                raise FetchError(f"{label}：页面格式不正确")
            rows = parse_theater(html)
            if not rows:
                if page == 0:
                    raise FetchError(f"{label}：未找到片单，页面可能已变更或需要验证")
                break
            _repeat_guard(seen, rows, label)
            pages += 1
            items.extend(rows)
            if len(_dedupe(items, limit)) >= limit or len(rows) < 25:
                break
        items = _nonempty(_dedupe(items, limit), label)
        # Exact first-air dates are determined by the caller's TMDB enrichment.
        upcoming = [item for item in items if item.get("year") and int(item["year"]) > current_year]
        aired = [item for item in items if item not in upcoming]
        output[name] = {"aired": aired, "upcoming": upcoming, "totalItems": len(items), "totalPages": pages}
    return output


async def _bangumi(transport, limit: int) -> dict:
    label = "Bangumi 番剧"
    items, seen = [], set()
    for page in range(1, 6):
        html = await transport.text("https://bgm.tv/anime/browser", params={"sort": "rank", "page": page},
                                    headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"})
        rows = parse_bangumi(html)
        if not rows:
            if page == 1:
                raise FetchError(f"{label}：未找到排名条目，页面可能已变更或需要验证")
            break
        _repeat_guard(seen, rows, label)
        items.extend(rows)
        if len(_dedupe(items, limit)) >= limit:
            break
    items = _nonempty(_dedupe(items, limit), label)
    return {"hot_anime": items, "total_matched": len(items)}


def _tmdb_item(node: dict, media_type: str, rank: int) -> dict | None:
    ident = node.get("id")
    if isinstance(ident, bool) or not isinstance(ident, (int, str)) or not str(ident).isdigit() or int(ident) <= 0:
        return None
    return _entry(node.get("name") or node.get("title"), media_type,
                  id=int(ident), tmdbId=int(ident), rank=rank,
                  originalTitle=node.get("original_name") or node.get("original_title") or "",
                  description=node.get("overview") or "", rating=_number(node.get("vote_average")),
                  popularity=_number(node.get("popularity")), voteCount=node.get("vote_count") or 0,
                  releaseDate=node.get("first_air_date") or node.get("release_date") or "",
                  posterPath=node.get("poster_path"), backdropPath=node.get("backdrop_path"),
                  genreIds=node.get("genre_ids") or [], originCountry=node.get("origin_country") or [])


async def _tmdb(transport, limit: int) -> dict:
    output = {}
    for key, path, media_type in (
        ("tv", "/trending/tv/week", "tv"), ("movie", "/trending/movie/week", "movie"),
        ("tv_popular", "/tv/popular", "tv"), ("movie_popular", "/movie/popular", "movie"),
    ):
        label = f"TMDB/{key}"
        items, seen = [], set()
        for page in range(1, 6):
            data = _mapping(await transport.tmdb_json(path, params={"language": "zh-CN", "page": page}), label)
            raw = _array(data.get("results"), label)
            if not raw:
                break
            rows = [item for index, node in enumerate(raw, len(items) + 1)
                    if isinstance(node, dict) and (item := _tmdb_item(node, media_type, index))]
            _nonempty(rows, label)
            signature = tuple(item["id"] for item in rows)
            if signature in seen:
                raise FetchError(f"{label}：接口重复返回同一页，已停止更新")
            seen.add(signature)
            items.extend(rows)
            if len(_dedupe(items, limit)) >= limit or page >= _number(data.get("total_pages"), 5):
                break
        output[key] = _nonempty(_dedupe(items, limit), label)
    return output


async def _bili(transport, limit: int) -> dict:
    output = {}
    for key, season_type in (("bangumi", 1), ("guochuang", 4)):
        label = f"B站榜单/{key}"
        data = _mapping(await transport.json(
            "https://api.bilibili.com/pgc/web/rank/list", params={"day": 3, "season_type": season_type},
            headers={"User-Agent": _UA, "Referer": "https://www.bilibili.com/", "Accept-Language": "zh-CN,zh;q=0.9"},
        ), label)
        _code(data, (0, "0"), label)
        raw = _array(_mapping(data.get("result"), label).get("list"), label)
        items = []
        for rank, node in enumerate(raw[:200], 1):
            if not isinstance(node, dict):
                continue
            original = _title(node.get("title"))
            clean = re.sub(r"[（(]?\s*(?:中文配音|国语配音|普通话配音|国语版配音|普通话版|国语版|中配|台配|大陆配音|配音版)\s*[)）]?", "", original).strip()
            stat = node.get("stat") if isinstance(node.get("stat"), dict) else {}
            item = _entry(clean, sourceTitle=original, rank=rank, heat=_number(stat.get("view")), requireGenre=16)
            if item:
                items.append(item)
        output[key] = _nonempty(_dedupe(items, limit), label)
    return output


async def _mal(transport, limit: int) -> dict:
    label = "MAL 热播番剧"
    items, seen = [], set()
    for page in range(2):
        html = await transport.text("https://myanimelist.net/topanime.php",
                                    params={"type": "airing", "limit": page * 50},
                                    headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})
        rows = parse_mal(html)
        if not rows:
            if page == 0:
                raise FetchError(f"{label}：未找到排名条目，页面可能已变更或需要验证")
            break
        _repeat_guard(seen, rows, label)
        items.extend(rows)
        if len(_dedupe(items, limit)) >= limit or len(rows) < 50:
            break
    return {"airing": _nonempty(_dedupe(items, limit), label)}


async def _anilist(transport, limit: int) -> dict:
    label = "AniList 番剧"
    query = (
        "query($page:Int,$perPage:Int){Page(page:$page,perPage:$perPage){"
        "pageInfo{hasNextPage}media(sort:TRENDING_DESC,type:ANIME){"
        "id title{romaji english native}averageScore popularity trending "
        "startDate{year month day}genres format}}}"
    )
    items, seen = [], set()
    for page in range(1, 3):
        data = _mapping(await transport.json(
            "https://graphql.anilist.co", method="POST",
            json={"query": query, "variables": {"page": page, "perPage": min(limit, 50)}},
            headers={"User-Agent": _UA, "Accept": "application/json"},
        ), label)
        if data.get("errors"):
            raise FetchError(f"{label}：查询接口返回错误")
        container = _mapping(_mapping(data.get("data"), label).get("Page"), label)
        raw = _array(container.get("media"), label)
        if not raw:
            break
        rows = []
        for node in raw:
            if not isinstance(node, dict) or not isinstance(node.get("title"), dict):
                continue
            titles = list(dict.fromkeys(filter(None, (_title(node["title"].get(key)) for key in ("english", "romaji", "native")))))
            if not titles:
                continue
            start = node.get("startDate") if isinstance(node.get("startDate"), dict) else {}
            item = _entry(titles[0], year=_year(start.get("year")), rank=len(items) + len(rows) + 1,
                          searchTitles=titles, requireGenre=16, heat=_number(node.get("averageScore")),
                          popularity=_number(node.get("trending") or node.get("popularity")))
            if item:
                rows.append(item)
        _nonempty(rows, label)
        _repeat_guard(seen, rows, label)
        items.extend(rows)
        if len(_dedupe(items, limit)) >= limit or not _mapping(container.get("pageInfo"), label).get("hasNextPage"):
            break
    items = _nonempty(_dedupe(items, limit), label)
    return {"trending": items, "total": len(items)}


async def _trakt(transport, limit: int, client_id: str) -> dict:
    if not client_id.strip():
        raise FetchError("Trakt 榜单：请先填写 Trakt Client ID")
    headers = {"trakt-api-version": "2", "trakt-api-key": client_id.strip(), "Accept": "application/json"}
    output = {}
    for key, path, kind, media_type in (
        ("trending", "/shows/trending", "show", "tv"),
        ("popular", "/shows/popular", "show", "tv"),
        ("movie_trending", "/movies/trending", "movie", "movie"),
        ("movie_popular", "/movies/popular", "movie", "movie"),
    ):
        label = f"Trakt/{key}"
        raw = _array(await transport.json(f"https://api.trakt.tv{path}", params={"limit": limit}, headers=headers), label)
        items = []
        for rank, row in enumerate(raw[:limit], 1):
            if not isinstance(row, dict):
                continue
            node = row.get(kind, row)
            if not isinstance(node, dict):
                continue
            ids = node.get("ids") if isinstance(node.get("ids"), dict) else {}
            tmdb_id = ids.get("tmdb")
            extra = {"year": _year(node.get("year")), "rank": rank, "heat": _number(row.get("watchers"))}
            if not isinstance(tmdb_id, bool) and isinstance(tmdb_id, (int, str)) and str(tmdb_id).isdigit() and int(tmdb_id) > 0:
                extra["tmdbId"] = int(tmdb_id)
            item = _entry(node.get("title"), media_type, **extra)
            if item:
                items.append(item)
        output[key] = _nonempty(_dedupe(items, limit), label)
    return output


async def collect(source: str, transport, limit: int = 30, trakt_client_id: str = "") -> dict:
    """Fetch one source; errors propagate so failed updates cannot erase cache.

    ``transport`` must expose async ``json``/``text`` and authenticated
    ``tmdb_json`` methods. A collection has a hard bound of 100 entries per
    category and never loops indefinitely when an upstream ignores pagination.
    """
    if isinstance(limit, bool):
        raise FetchError("榜单数量必须是整数")
    try:
        bounded_limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError, OverflowError):
        raise FetchError("榜单数量必须是整数") from None
    handlers = {
        "guduo": _guduo, "douban": _douban, "mgtv": _mgtv,
        "theater": _theater, "bangumi": _bangumi, "tmdb": _tmdb,
        "bili": _bili, "mal": _mal, "anilist": _anilist,
    }
    if source == "trakt":
        result = await _trakt(transport, bounded_limit, trakt_client_id)
    elif source in handlers:
        result = await handlers[source](transport, bounded_limit)
    else:
        raise FetchError("未知榜单来源")
    result["last_updated"] = datetime.now(_BEIJING).strftime("%Y/%m/%d %H:%M:%S")
    return result
