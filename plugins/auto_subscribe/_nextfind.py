# =============================================================================
# auto_subscribe 私有辅助：NextFind OpenAPI 客户端（同步）
#
# NextFind 是用户自建服务，出站必须直连、绕过平台境外代理（trust_env=False），
# 否则把自建域名路由到境外代理会失败或误判。鉴权走 X-API-Key 头。
#
# 关键：一次 /search 就同时返回 id(=tmdb)、raw_type、year、_vote_average、
# is_subscribed（去重）、is_in_library（库查重），故原 MoviePilot 版的
# recognize -> exists -> media-exists -> vote 四步在这里合并成一步。
# =============================================================================

from __future__ import annotations

from typing import List, Optional, Tuple

import httpx

# type 参数映射：内部媒体类型 -> NextFind /search 的中文 type。
_TYPE_PARAM = {"movie": "电影", "tv": "剧集"}
# add/remove 请求体的 media_type 取值（与 /search 的 raw_type 一致）。
VALID_MEDIA_TYPES = ("movie", "tv")


class NextFindError(Exception):
    """NextFind 请求/响应异常。"""


class NextFindAuthError(NextFindError):
    """鉴权失败（401/403）：API 密钥无效或已过期。运行时据此立即中止整轮。"""


class NextFindClient:
    """NextFind OpenAPI 轻客户端（同步，直连不走代理）。"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.api_key = str(api_key or "").strip()
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        # 自建服务：trust_env=False 直连，绕过平台注入的境外代理。
        return httpx.Client(
            timeout=self.timeout,
            trust_env=False,
            headers={"X-API-Key": self.api_key},
        )

    @staticmethod
    def _check(resp) -> None:
        """把 401/403 转成 NextFindAuthError（密钥问题），其余非 2xx 照常抛。"""
        if resp.status_code in (401, 403):
            raise NextFindAuthError(f"NextFind 鉴权失败（HTTP {resp.status_code}）：API 密钥无效或已过期")
        resp.raise_for_status()

    def _get(self, path: str, params: dict) -> dict:
        with self._client() as client:
            resp = client.get(f"{self.base_url}{path}", params=params)
            self._check(resp)
            return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        with self._client() as client:
            resp = client.post(f"{self.base_url}{path}", json=body)
            self._check(resp)
            return resp.json()

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def search(self, query: str, media_type: Optional[str] = None) -> List[dict]:
        """全局搜索：query 必填，type 按内部媒体类型映射（None -> 全部）。

        返回 data 列表；每条含 id(=tmdb,str)、title、raw_type、year、_vote_average、
        is_subscribed、is_in_library、total_episodes 等。
        """
        if not query:
            return []
        type_param = _TYPE_PARAM.get(str(media_type or "").lower(), "全部")
        payload = self._get("/search", {"query": query, "type": type_param})
        data = (payload or {}).get("data")
        return data if isinstance(data, list) else []

    def list_subscriptions(self) -> List[dict]:
        """活跃订阅列表（本插件主要靠 /search 的 is_subscribed 去重，此处备用）。"""
        payload = self._get("/subscriptions", {})
        data = (payload or {}).get("data")
        return data if isinstance(data, list) else []

    def quota(self) -> dict:
        """查询额度/积分（供「测试连接」动作）。"""
        payload = self._get("/quota", {})
        return (payload or {}).get("data") or {}

    # ------------------------------------------------------------------ #
    # 订阅
    # ------------------------------------------------------------------ #
    def add(self, tmdb_id, media_type: str, season: Optional[int] = None) -> Tuple[bool, str]:
        """加订阅：body {tmdb_id, media_type[, season]}。返回 (是否成功, 消息)。"""
        body = {"tmdb_id": str(tmdb_id), "media_type": str(media_type).lower()}
        if season is not None and str(media_type).lower() == "tv":
            body["season"] = season
        payload = self._post("/subscriptions/add", body)
        status = str((payload or {}).get("status") or "").lower()
        message = str((payload or {}).get("message") or "")
        return status == "success", message

    def remove(self, tmdb_id, media_type: str) -> Tuple[bool, str]:
        """取消订阅（本次不接入 UI，保留供将来用）。"""
        body = {"tmdb_id": str(tmdb_id), "media_type": str(media_type).lower()}
        payload = self._post("/subscriptions/remove", body)
        status = str((payload or {}).get("status") or "").lower()
        return status == "success", str((payload or {}).get("message") or "")
