# =============================================================================
# auto_subscribe 私有辅助：Mikan(蜜柑计划) 季度新番来源
#
# 抓蜜柑季度番剧列表页（div.sk-bangumi li），可选逐条抓详情补真实放送年。
# 移植自原 MoviePilot 版：RequestUtils -> httpx（默认走平台代理），bs4 解析不变。
# 番剧统一 type_hint="tv"，落地时按标题 + 年份走 NextFind /search 识别。
# =============================================================================

from __future__ import annotations

import re
from datetime import datetime
from time import sleep
from typing import Iterator, List, Optional, Tuple
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from ._base import RankProvider, register
from ._models import RankMediaItem

# 蜜柑计划基址（主 + 备），逐个尝试。
MIKAN_URLS = ["https://mikanani.me", "https://mikanime.tv"]
MIKAN_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 MikanProject/1.0.0"
)

# 季度 seasonStr 真实取值（中文季名）。
MIKAN_SEASONS = ["春", "夏", "秋", "冬"]
# “当前”自动项哨兵：按当前月推导实际季度。
SEASON_AUTO = "当前"

_REQUEST_TIMEOUT = 30
_DETAIL_SLEEP = 0.6

_BGM_ID_PATTERN = re.compile(r"b(?:gm|angumi)\.tv/subject/(\d+)")
_YEAR_PATTERN = re.compile(r"(\d{4})")
_AIR_START_KEY = "放送开始"
_DATE_KEY_HINTS = ("放送", "开播", "首播", "播出")


def _to_int(value) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


class MikanApi:
    """蜜柑计划轻客户端：季度列表 + 详情页 bgm id / 放送年 提取。"""

    def _get(self, path: str) -> Optional[Tuple[str, str]]:
        """按主/备基址依次 GET，返回 (HTML, 命中的基址)；全部失败返回 None。"""
        for base in MIKAN_URLS:
            url = f"{base}{path}"
            try:
                with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True,
                                  headers={"User-Agent": MIKAN_UA}) as client:
                    resp = client.get(url)
                    if resp.status_code == 200 and resp.text:
                        return resp.text, base
            except Exception:  # noqa: BLE001 - 单个基址失败则尝试备用
                continue
        return None

    def season(self, year, season_str: str) -> List[dict]:
        """GET 季度新番列表并解析，产出 [{mikan_id, title, cover, week}]。"""
        path = (
            f"/Home/BangumiCoverFlowByDayOfWeek"
            f"?year={year}&seasonStr={quote(str(season_str))}"
        )
        ret = self._get(path)
        if not ret:
            return []
        html, base = ret
        return self._parse_season(html, base)

    def bangumi_detail(self, mikan_id: str) -> dict:
        """GET 详情页，解析 {bgm_id, year, air_date}。"""
        ret = self._get(f"/Home/Bangumi/{mikan_id}")
        if not ret:
            return {}
        return self._parse_detail(ret[0])

    @staticmethod
    def _parse_season(html: str, base: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        results: List[dict] = []
        seen: set = set()
        for group in soup.select("div.sk-bangumi"):
            row = group.select_one("div.row")
            week = row.get_text(strip=True) if row else str(group.get("data-dayofweek") or "")
            for li in group.select("li"):
                span = li.select_one("span[data-bangumiid]")
                if span is None:
                    continue
                mikan_id = str(span.get("data-bangumiid") or "").strip()
                if not mikan_id or mikan_id in seen:
                    continue
                anchor = li.select_one("a.an-text")
                title = ""
                if anchor is not None:
                    title = str(anchor.get("title") or anchor.get_text(strip=True) or "").strip()
                if not title:
                    continue
                seen.add(mikan_id)
                cover = str(span.get("data-src") or "").strip()
                if cover.startswith("/"):
                    cover = f"{base}{cover}"
                results.append(
                    {"mikan_id": mikan_id, "title": title, "cover": cover, "week": week}
                )
        return results

    @classmethod
    def _parse_detail(cls, html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        nodes = soup.select("p.bangumi-info") or soup.select(".bangumi-info")
        more: dict = {}
        for node in nodes:
            text = node.get_text(" ", strip=True)
            if "：" not in text:
                continue
            key, _sep, value = text.partition("：")
            key, value = key.strip(), value.strip()
            if key and value:
                more[key] = value
        search_text = "\n".join(n.get_text(" ", strip=True) for n in nodes) if nodes else html
        bgm_id: Optional[int] = None
        match = _BGM_ID_PATTERN.search(search_text)
        if match:
            bgm_id = _to_int(match.group(1)) or None
        air_date = more.get(_AIR_START_KEY) or None
        return {"bgm_id": bgm_id, "year": cls._extract_year(more, air_date), "air_date": air_date}

    @staticmethod
    def _extract_year(more: dict, air_date: Optional[str]) -> Optional[str]:
        candidates: List[str] = []
        if air_date:
            candidates.append(air_date)
        for key, value in more.items():
            if value and any(hint in key for hint in _DATE_KEY_HINTS):
                candidates.append(value)
        for candidate in candidates:
            ym = _YEAR_PATTERN.search(candidate)
            if ym and 1900 <= int(ym.group(1)) <= 2100:
                return ym.group(1)
        return None


@register
class MikanRankProvider(RankProvider):
    """Mikan 季度新番来源。"""

    provider_id = "mikan"
    provider_name = "Mikan季度新番"

    def fetch(self, options: dict) -> Iterator[RankMediaItem]:
        options = options or {}
        year = self._resolve_year(options.get("year"))
        season_str = self._resolve_season(options.get("season"))
        resolve_bgm = bool(options.get("resolve_bangumi_id", True))

        api = MikanApi()
        entries = api.season(year, season_str)
        config_year = str(year)
        for entry in entries:
            try:
                detail: dict = {}
                if resolve_bgm:
                    detail = self._safe_detail(api, entry)
                    sleep(_DETAIL_SLEEP)
                yield self._build_item(entry, config_year, detail)
            except Exception:  # noqa: BLE001 - 单条兜底，不影响其余番剧
                continue

    @staticmethod
    def _safe_detail(api: "MikanApi", entry: dict) -> dict:
        try:
            return api.bangumi_detail(entry["mikan_id"])
        except Exception:  # noqa: BLE001 - 单条详情失败退化名称识别
            return {}

    @staticmethod
    def _build_item(entry: dict, config_year: str, detail: dict) -> RankMediaItem:
        detail = detail or {}
        cover = entry.get("cover")
        year = detail.get("year") or config_year
        return RankMediaItem(
            title=entry["title"],
            year=year,
            type_hint="tv",
            bangumi_id=detail.get("bgm_id"),
            poster=cover,
            source_meta={"mikan_id": entry["mikan_id"], "week": entry.get("week")},
            unique_seed=entry["mikan_id"],
        )

    @staticmethod
    def _resolve_year(raw) -> int:
        year = _to_int(raw)
        return year if year > 0 else datetime.now().year

    @classmethod
    def _resolve_season(cls, raw) -> str:
        value = str(raw or "").strip()
        if value in MIKAN_SEASONS:
            return value
        return cls._season_by_month(datetime.now().month)

    @staticmethod
    def _season_by_month(month: int) -> str:
        if month in (1, 2, 3):
            return "冬"
        if month in (4, 5, 6):
            return "春"
        if month in (7, 8, 9):
            return "夏"
        return "秋"
