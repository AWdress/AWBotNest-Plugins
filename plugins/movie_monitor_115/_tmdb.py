# =============================================================================
# movie_monitor_115 私有辅助：TMDB 查询 + Emby 媒体库检查
# =============================================================================

import re
from typing import List, Optional

import httpx


class TmdbApi:
    """TMDB 识别匹配（异步）。"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.language = "zh"
        self.base_url = "https://api.themoviedb.org/3"

    def _client(self) -> httpx.AsyncClient:
        # 出站自动走平台代理（httpx 默认 trust_env=True 读取平台注入的代理）
        return httpx.AsyncClient(timeout=10, verify=False)

    async def search_all(self, title: str, year: str = None, log=None) -> List[dict]:
        movie = await self._search(f"{self.base_url}/search/movie", title,
                                   {"year": year}, log)
        tv = await self._search(f"{self.base_url}/search/tv", title,
                                {"first_air_date_year": year}, log)
        for r in movie:
            r["media_type"] = "movie"
        for r in tv:
            r["media_type"] = "tv"
        return movie + tv

    def _auth(self):
        """兼容 TMDB v3 API Key（URL 参数）与 v4 Read Access Token（Bearer 头）。"""
        key = (self.api_key or "").strip()
        if key.startswith("eyJ"):  # v4 令牌是 JWT，必须走 Authorization: Bearer
            return {}, {"Authorization": f"Bearer {key}"}
        return {"api_key": key}, {}

    async def _search(self, url: str, title: str, extra: dict, log) -> List[dict]:
        if not title:
            return []
        key_param, headers = self._auth()
        params = {"language": self.language, "query": title, **key_param}
        params.update({k: v for k, v in extra.items() if v and str(v) != "0"})
        try:
            async with self._client() as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json().get("results", [])
        except Exception as e:  # noqa: BLE001
            if log:
                log.error("[115监控] TMDB 查询失败: %r", e)
            return []

    @staticmethod
    def compare_names(file_name: str, tmdb_names: list) -> bool:
        if not file_name or not tmdb_names:
            return False
        if not isinstance(tmdb_names, list):
            tmdb_names = [tmdb_names]
        file_name = re.sub(r"[\W_]+", " ", file_name).strip().upper()
        for n in tmdb_names:
            if file_name == re.sub(r"[\W_]+", " ", n).strip().upper():
                return True
        return False


def _item_types(media_type: Optional[str]) -> Optional[str]:
    mt = (media_type or "").lower()
    if mt == "movie":
        return "Movie"
    if mt == "tv":
        return "Series"
    return None


async def emby_has_tmdb_id(emby_server: str, emby_api: str, tmdb_id, media_type: Optional[str],
                           log=None) -> bool:
    """直接用 TMDB ID 查 Emby 是否已入库（最可靠，无需标题匹配）。"""
    if not emby_server or not emby_api or not tmdb_id:
        return False
    url = f"{emby_server}emby/Items"
    params = {
        "Recursive": "true",
        "AnyProviderIdEquals": f"tmdb.{tmdb_id}",
        "Fields": "ProviderIds",
        "api_key": emby_api,
    }
    item_types = _item_types(media_type)
    if item_types:
        params["IncludeItemTypes"] = item_types
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(url, params=params)
            res = resp.json()
            items = (res or {}).get("Items") or []
            for it in items:
                if str(it.get("ProviderIds", {}).get("Tmdb")) == str(tmdb_id):
                    return True
            return bool(items)
    except Exception as e:  # noqa: BLE001
        if log:
            log.error("[115监控] 按 TMDB ID 查 Emby 失败: %r", e)
        return False


async def get_emby_tmdb_ids(emby_server: str, emby_api: str, title: str,
                            media_type: Optional[str], log=None) -> List[str]:
    """查 Emby 媒体库里某标题已有项的 TMDB ID 列表。"""
    if not emby_server or not emby_api:
        return []
    if media_type and media_type.lower() == "movie":
        item_types = "Movie"
    elif media_type and media_type.lower() == "tv":
        item_types = "Series"
    else:
        item_types = None

    url = f"{emby_server}emby/Items"
    params = {
        "IncludeItemTypes": item_types or "",
        "Fields": "ProviderIds,OriginalTitle,ProductionYear,Path",
        "StartIndex": 0, "Recursive": "true", "SearchTerm": title,
        "Limit": 10, "IncludeSearchTypes": "false", "api_key": emby_api,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            res = resp.json()
            items = res.get("Items") if res else None
            if not items:
                return []
            return [it["ProviderIds"].get("Tmdb") for it in items
                    if "Tmdb" in it.get("ProviderIds", {})]
    except Exception as e:  # noqa: BLE001
        if log:
            log.error("[115监控] 连接 Emby 失败: %r", e)
        return []
