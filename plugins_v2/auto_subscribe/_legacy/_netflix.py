# =============================================================================
# auto_subscribe 私有辅助：奈飞(Netflix) Top10 全球榜来源
#
# 抓官方 Tudum Top10 公开 TSV（GET 无鉴权）。移植自原 MoviePilot 版，做了两处裁剪：
#   1) 只做**全球榜**（most-popular / all-weeks-global），国家榜（94 国、约 30MB）延后；
#   2) RequestUtils -> httpx（默认走平台代理，Netflix 境内直连不通）。
# 富元数据模式（rich_metadata）保留：抓 Tudum 榜单页内嵌 GraphQL，比 TSV 多带**年份**
# （Netflix TSV 无年份，年份能大幅提升 NextFind /search 消歧命中率），仅全球英语两类有富页。
#
# 周更缓存：Netflix Top10 固定 7 天周期，同一刷新周内重复抓取只会拿到相同内容、可能触发
# 风控。缓存存 options["_cache"]（由 pipeline 从 ctx.kv 读入的可变 dict，跑完写回，抗重启）。
# =============================================================================

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator, List, Optional

import httpx

from ._base import RankProvider, register
from ._models import RankMediaItem

MOST_POPULAR_URL = "https://www.netflix.com/tudum/top10/data/most-popular.tsv"
ALL_WEEKS_GLOBAL_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-global.tsv"
# 国家榜（94 国·每周·约 30MB，整表下载后内存过滤最新周 + 所选国家/类型；靠周更缓存摊薄成本）。
ALL_WEEKS_COUNTRIES_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"

# 全球榜 category（4 种，value=数据集内精确 category 串）。
GLOBAL_CATEGORIES = [
    {"value": "Films (English)", "label": "英语电影"},
    {"value": "Films (Non-English)", "label": "非英语电影"},
    {"value": "TV (English)", "label": "英语剧集"},
    {"value": "TV (Non-English)", "label": "非英语剧集"},
]

# 国家榜 category（2 种，数据集内仅 Films / TV）。
COUNTRY_CATEGORIES = [
    {"value": "Films", "label": "电影"},
    {"value": "TV", "label": "剧集"},
]

# 94 个上榜国家/地区：iso2 -> 英文国名（由 all-weeks-countries.tsv 实测提取）。
COUNTRIES = {
    "AE": "United Arab Emirates", "AR": "Argentina", "AT": "Austria", "AU": "Australia",
    "BD": "Bangladesh", "BE": "Belgium", "BG": "Bulgaria", "BH": "Bahrain", "BO": "Bolivia",
    "BR": "Brazil", "BS": "Bahamas", "CA": "Canada", "CH": "Switzerland", "CL": "Chile",
    "CO": "Colombia", "CR": "Costa Rica", "CY": "Cyprus", "CZ": "Czech Republic",
    "DE": "Germany", "DK": "Denmark", "DO": "Dominican Republic", "EC": "Ecuador",
    "EE": "Estonia", "EG": "Egypt", "ES": "Spain", "FI": "Finland", "FR": "France",
    "GB": "United Kingdom", "GP": "Guadeloupe", "GR": "Greece", "GT": "Guatemala",
    "HK": "Hong Kong", "HN": "Honduras", "HR": "Croatia", "HU": "Hungary", "ID": "Indonesia",
    "IE": "Ireland", "IL": "Israel", "IN": "India", "IS": "Iceland", "IT": "Italy",
    "JM": "Jamaica", "JO": "Jordan", "JP": "Japan", "KE": "Kenya", "KR": "South Korea",
    "KW": "Kuwait", "LB": "Lebanon", "LK": "Sri Lanka", "LT": "Lithuania", "LU": "Luxembourg",
    "LV": "Latvia", "MA": "Morocco", "MQ": "Martinique", "MT": "Malta", "MU": "Mauritius",
    "MV": "Maldives", "MX": "Mexico", "MY": "Malaysia", "NC": "New Caledonia", "NG": "Nigeria",
    "NI": "Nicaragua", "NL": "Netherlands", "NO": "Norway", "NZ": "New Zealand", "OM": "Oman",
    "PA": "Panama", "PE": "Peru", "PH": "Philippines", "PK": "Pakistan", "PL": "Poland",
    "PT": "Portugal", "PY": "Paraguay", "QA": "Qatar", "RE": "Réunion", "RO": "Romania",
    "RS": "Serbia", "RU": "Russia", "SA": "Saudi Arabia", "SE": "Sweden", "SG": "Singapore",
    "SI": "Slovenia", "SK": "Slovakia", "SV": "El Salvador", "TH": "Thailand", "TR": "Turkey",
    "TT": "Trinidad and Tobago", "TW": "Taiwan", "UA": "Ukraine", "US": "United States",
    "UY": "Uruguay", "VE": "Venezuela", "VN": "Vietnam", "ZA": "South Africa",
}

DATASET_WEEKLY = "all-weeks-global"
DATASET_POPULAR = "most-popular"

_REQUEST_TIMEOUT = 120
_DEFAULT_LIMIT = 10
_RANK_FALLBACK = 10 ** 6
_SEASON_PATTERN = re.compile(r"Season\s*(\d+)", re.IGNORECASE)

# ---- 富元数据模式（Tudum 榜单页内嵌 GraphQL）----
_TUDUM_TOP10_BASE = "https://www.netflix.com/tudum/top10"
_RICH_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
_RICH_TIMEOUT = 30
_GRAPHQL_MARKER = "reactContext.models.graphql = JSON.parse('"
_JS_UNESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)", re.DOTALL)
_JS_SIMPLE_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v",
    "0": "\0", "\\": "\\", "'": "'", '"': '"', "/": "/", "`": "`",
    "\n": "", "\r": "",
}
# 全球英语 category -> 富页路径后缀（仅英语两类有稳定内嵌富页）。
_GLOBAL_ENGLISH_RICH = {"Films (English)": "films", "TV (English)": "tv"}
_GLOBAL_NON_ENGLISH = ("Films (Non-English)", "TV (Non-English)")

# ---- 周更缓存 ----
_PUBLISH_LAG_DAYS = 9
_PUBLISH_HOUR_UTC = 12
_MIN_RECHECK_SECONDS = 12 * 3600
_FALLBACK_TTL_SECONDS = 6 * 24 * 3600


@register
class NetflixRankProvider(RankProvider):
    """奈飞 Top10 全球榜来源。"""

    provider_id = "netflix"
    provider_name = "奈飞榜单"

    def fetch(self, options: dict) -> Iterator[RankMediaItem]:
        options = options or {}
        cache = options.get("_cache")
        use_cache = bool(options.get("use_cache", True)) and isinstance(cache, dict)
        now = time.time()

        if use_cache:
            key = self._cache_key(options)
            entry = cache.get(key)
            if entry and now < entry.get("valid_until", 0):
                for d in entry.get("items", []):
                    yield RankMediaItem.from_dict(d)
                return

        items = self._collect(options)

        if use_cache:
            week = self._latest_week(items)
            key = self._cache_key(options)
            cache[key] = {
                "items": [it.to_dict() for it in items],
                "week": week,
                "valid_until": self._valid_until(week, now),
                "fetched_ts": now,
            }
            # 剔除已过期条目，防缓存无限增长。
            for k in [k for k, v in cache.items()
                      if not (isinstance(v, dict) and now < v.get("valid_until", 0))]:
                cache.pop(k, None)
        yield from items

    # ------------------------------------------------------------------ #
    def _collect(self, options: dict) -> List[RankMediaItem]:
        limit = self.to_int(options.get("limit"), _DEFAULT_LIMIT)
        seen: set = set()
        rich = bool(options.get("rich_metadata", False))
        items: List[RankMediaItem] = []

        # 全球榜。
        global_on = bool(options.get("global", True))
        global_cats = [c for c in self.as_list(options.get("global_media_types"))
                       if c in {x["value"] for x in GLOBAL_CATEGORIES}] if global_on else []
        if global_cats:
            if rich:
                # 富模式：英语两类走富页（带年份），非英语两类回退 TSV。
                for cat in [c for c in global_cats if c in _GLOBAL_ENGLISH_RICH]:
                    items.extend(self._fetch_rich_path(
                        _GLOBAL_ENGLISH_RICH[cat], _GLOBAL_ENGLISH_RICH[cat], limit, seen))
                non_english = [c for c in global_cats if c in _GLOBAL_NON_ENGLISH]
                if non_english:
                    dataset = str(options.get("global_dataset") or DATASET_WEEKLY).strip()
                    items.extend(self._fetch_global(dataset, non_english, limit, seen))
            else:
                dataset = str(options.get("global_dataset") or DATASET_WEEKLY).strip()
                items.extend(self._fetch_global(dataset, global_cats, limit, seen))

        # 国家榜（与全球榜互不冲突，可同时启用）。所选国家 × 所选类型（笛卡尔积）。
        countries = [c for c in self.as_list(options.get("countries")) if c in COUNTRIES]
        country_cats = [c for c in self.as_list(options.get("country_types"))
                        if c in {x["value"] for x in COUNTRY_CATEGORIES}]
        if countries and country_cats:
            if rich:
                items.extend(self._fetch_countries_rich(countries, country_cats, limit, seen))
            else:
                items.extend(self._fetch_countries(countries, country_cats, limit, seen))
        return items

    def _fetch_countries(self, countries: List[str], categories: List[str], limit: int,
                         seen: set) -> Iterator[RankMediaItem]:
        """国家榜(TSV)：取最新周，对每个「国家 × 类型」按 weekly_rank 升序取前 limit。"""
        rows = self._latest_week_rows(self._load_tsv(ALL_WEEKS_COUNTRIES_URL))
        for iso2 in countries:
            country_rows = [r for r in rows if r.get("country_iso2") == iso2]
            for category in categories:
                cat_rows = sorted((r for r in country_rows if r.get("category") == category),
                                  key=self._row_rank)[:limit]
                yield from self._emit(cat_rows, category, seen)

    def _fetch_countries_rich(self, countries: List[str], categories: List[str], limit: int,
                              seen: set) -> Iterator[RankMediaItem]:
        """国家榜(富页)：/tudum/top10/{slug}/{films|tv}，带年份/干净剧名。"""
        for iso2 in countries:
            name = COUNTRIES.get(iso2)
            if not name:
                continue
            slug = self._country_slug(name)
            for category in categories:
                suffix = "films" if category == "Films" else "tv"
                yield from self._fetch_rich_path(f"{slug}/{suffix}", suffix, limit, seen)

    def _fetch_global(self, dataset: str, categories: List[str], limit: int,
                      seen: set) -> Iterator[RankMediaItem]:
        url = MOST_POPULAR_URL if dataset == DATASET_POPULAR else ALL_WEEKS_GLOBAL_URL
        rows = self._load_tsv(url)
        if dataset != DATASET_POPULAR:
            rows = self._latest_week_rows(rows)
        for category in categories:
            cat_rows = sorted((r for r in rows if r.get("category") == category),
                              key=self._row_rank)[:limit]
            yield from self._emit(cat_rows, category, seen)

    def _emit(self, rows: List[dict], category: str, seen: set) -> Iterator[RankMediaItem]:
        for row in rows:
            try:
                item = self._build_item(row, category)
            except Exception:  # noqa: BLE001 - 单条兜底
                continue
            if not item.title or item.unique_seed in seen:
                continue
            seen.add(item.unique_seed)
            yield item

    @classmethod
    def _build_item(cls, row: dict, category: str) -> RankMediaItem:
        show_title = str(row.get("show_title") or "").strip()
        is_movie = category.startswith("Films")
        type_value = "movie" if is_movie else "tv"
        season = None if is_movie else cls._extract_season(row.get("season_title"))
        source_meta = {"category": category, "rank": cls._row_rank(row)}
        if row.get("week"):
            source_meta["week"] = row.get("week")
        return RankMediaItem(
            title=show_title,
            year=None,
            type_hint=type_value,
            season=season,
            source_meta=source_meta,
            unique_seed=f"{type_value}_{show_title}",
        )

    # ---- 富元数据模式 ----
    def _fetch_rich_path(self, path: str, kind: str, limit: int,
                         seen: set) -> Iterator[RankMediaItem]:
        """抓一个富页（path 为 base 之后的相对路径，如 films / south-korea/tv），kind 定类型。"""
        url = f"{_TUDUM_TOP10_BASE}/{path}"
        try:
            entries = self._load_rich_page(url)
        except Exception:  # noqa: BLE001 - 单页失败跳过
            return
        top = sorted(entries, key=lambda e: e.get("rank") or _RANK_FALLBACK)[:limit]
        for entry in top:
            try:
                item = self._build_rich_item(entry, kind)
            except Exception:  # noqa: BLE001 - 单条兜底
                continue
            if not item.title or item.unique_seed in seen:
                continue
            seen.add(item.unique_seed)
            yield item

    @classmethod
    def _build_rich_item(cls, entry: dict, kind: str) -> RankMediaItem:
        title = str(entry.get("title") or "").strip()
        clean = str(entry.get("clean_title") or "").strip()
        title_used = clean or title
        is_movie = kind == "films"
        type_value = "movie" if is_movie else "tv"
        season = None if is_movie else cls._extract_season(title)
        year_val = entry.get("year")
        year = str(year_val) if year_val else None
        source_meta = {"category": entry.get("category"), "rank": entry.get("rank"),
                       "video_id": entry.get("video_id"), "source": "rich"}
        if entry.get("week"):
            source_meta["week"] = entry.get("week")
        return RankMediaItem(
            title=title_used,
            year=year,
            type_hint=type_value,
            season=season,
            source_meta=source_meta,
            unique_seed=f"{type_value}_{title_used}",
        )

    def _load_rich_page(self, url: str) -> List[dict]:
        with httpx.Client(timeout=_RICH_TIMEOUT, follow_redirects=True,
                          headers={"User-Agent": _RICH_UA}) as client:
            resp = client.get(url)
            if resp.status_code != 200 or not resp.text:
                raise RuntimeError(f"获取 {url} 失败或响应为空")
            html = resp.text
        return self._parse_rich_store(self._decode_graphql(html))

    @classmethod
    def _decode_graphql(cls, html: str) -> dict:
        raw = cls._extract_graphql_literal(html)
        data = json.loads(cls._decode_js_string(raw))
        if isinstance(data, dict):
            store = data.get("data", data)
            return store if isinstance(store, dict) else {}
        return {}

    @staticmethod
    def _extract_graphql_literal(html: str) -> str:
        start = html.rfind(_GRAPHQL_MARKER)
        if start == -1:
            raise RuntimeError("页面未找到内嵌 GraphQL 数据")
        body = start + len(_GRAPHQL_MARKER)
        i, n = body, len(html)
        while i < n:
            ch = html[i]
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                return html[body:i]
            i += 1
        raise RuntimeError("内嵌 GraphQL 单引号字符串未正确闭合")

    @classmethod
    def _decode_js_string(cls, raw: str) -> str:
        return _JS_UNESCAPE.sub(cls._js_unescape_sub, raw)

    @staticmethod
    def _js_unescape_sub(match: "re.Match") -> str:
        seq = match.group(1)
        if seq[0] in ("u", "x"):
            try:
                return chr(int(seq[1:], 16))
            except ValueError:
                return seq
        return _JS_SIMPLE_ESCAPES.get(seq, seq)

    @classmethod
    def _parse_rich_store(cls, store: dict) -> List[dict]:
        entries: List[dict] = []
        seen_ids: set = set()
        for obj in (store or {}).values():
            if not isinstance(obj, dict):
                continue
            video = obj.get("top10Video")
            top10 = obj.get("top10")
            if not isinstance(video, dict) or not isinstance(top10, dict):
                continue
            video_id = video.get("videoId")
            dedup = video_id if video_id is not None else video.get("title")
            if dedup in seen_ids:
                continue
            seen_ids.add(dedup)
            parent = video.get("parentShow")
            clean = parent.get("title") if isinstance(parent, dict) else None
            entries.append({
                "rank": cls._to_optional_int(top10.get("weeklyRank")),
                "title": video.get("title"),
                "clean_title": clean,
                "year": cls._to_optional_int(video.get("releaseYear")),
                "video_id": video_id,
                "category": top10.get("category"),
                "week": top10.get("weekEndDate"),
            })
        return entries

    # ---- TSV / 缓存辅助 ----
    def _load_tsv(self, url: str) -> List[dict]:
        with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200 or not resp.content:
                raise RuntimeError(f"获取 {url} 失败或响应为空")
            # 强制按 UTF-8 从原始字节解码（Netflix TSV 头不带 charset，避免 Latin-1 误解码）。
            text = resp.content.decode("utf-8", errors="replace")
        return self._parse_tsv(text)

    @staticmethod
    def _parse_tsv(text: str) -> List[dict]:
        lines = text.split("\n")
        if not lines:
            return []
        header = lines[0].strip("\r").split("\t")
        rows: List[dict] = []
        for line in lines[1:]:
            line = line.strip("\r")
            if not line.strip():
                continue
            rows.append(dict(zip(header, line.split("\t"))))
        return rows

    @staticmethod
    def _latest_week_rows(rows: List[dict]) -> List[dict]:
        weeks = [w for w in (r.get("week") for r in rows) if w]
        if not weeks:
            return rows
        latest = max(weeks)
        return [r for r in rows if r.get("week") == latest]

    @classmethod
    def _cache_key(cls, options: dict) -> str:
        options = options or {}
        payload = {
            "rich_metadata": bool(options.get("rich_metadata", False)),
            "global": bool(options.get("global", True)),
            "global_dataset": str(options.get("global_dataset") or DATASET_WEEKLY).strip(),
            "global_media_types": sorted(cls().as_list(options.get("global_media_types"))),
            "countries": sorted(cls().as_list(options.get("countries"))),
            "country_types": sorted(cls().as_list(options.get("country_types"))),
            "limit": cls().to_int(options.get("limit"), _DEFAULT_LIMIT),
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def _country_slug(name: str) -> str:
        """国家英文名 -> Tudum slug：小写、空格转连字符（South Korea -> south-korea）。"""
        return re.sub(r"\s+", "-", str(name).strip().lower())

    @classmethod
    def _valid_until(cls, week_str: Optional[str], now: float) -> float:
        if week_str:
            try:
                day = datetime.strptime(str(week_str).strip(), "%Y-%m-%d")
                base_dt = (day.replace(tzinfo=timezone.utc)
                           + timedelta(days=_PUBLISH_LAG_DAYS)).replace(
                    hour=_PUBLISH_HOUR_UTC, minute=0, second=0, microsecond=0)
                return max(base_dt.timestamp(), now + _MIN_RECHECK_SECONDS)
            except (ValueError, TypeError):
                pass
        return now + _FALLBACK_TTL_SECONDS

    @staticmethod
    def _latest_week(items: List[RankMediaItem]) -> Optional[str]:
        weeks = [w for w in (i.source_meta.get("week") for i in items) if w]
        return max(weeks) if weeks else None

    @classmethod
    def _extract_season(cls, season_title) -> Optional[int]:
        value = str(season_title or "").strip()
        if not value or value == "N/A":
            return None
        match = _SEASON_PATTERN.search(value)
        return int(match.group(1)) if match else None

    @classmethod
    def _row_rank(cls, row: dict) -> int:
        return cls().to_int(row.get("rank") or row.get("weekly_rank"), _RANK_FALLBACK)

    @staticmethod
    def _to_optional_int(value) -> Optional[int]:
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
