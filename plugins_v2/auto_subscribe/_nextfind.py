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

import asyncio
import math
import time
from typing import List, Optional, Tuple

import httpx

# type 参数映射：内部媒体类型 -> NextFind /search 的中文 type。
_TYPE_PARAM = {"movie": "电影", "tv": "剧集"}
# add/remove 请求体的 media_type 取值（与 /search 的 raw_type 一致）。
VALID_MEDIA_TYPES = ("movie", "tv")


def _true_flag(value) -> bool:
    """API 布尔标志只接受明确的 true/1。"""
    return value is True or value == 1 or (
        isinstance(value, str) and value.strip().lower() in ("true", "1")
    )


class NextFindError(Exception):
    """NextFind 请求/响应异常。"""


class NextFindAuthError(NextFindError):
    """鉴权失败（401/403）：API 密钥无效或已过期。运行时据此立即中止整轮。"""


class NextFindResponseError(NextFindError):
    """HTTP 成功但响应无法作为可靠查询结果使用。"""


class NextFindTimeoutError(NextFindError):
    """整次请求超过墙钟截止时间，已停止底层网络任务。"""


class NextFindDeadlineError(NextFindTimeoutError):
    """整轮截止时间已到，不能继续发出其他请求。"""


class NextFindCancelledError(NextFindError):
    """调用方取消了运行，底层请求已关闭。"""


class NextFindServerError(NextFindError):
    """NextFind 服务端 5xx；插件可以选择稳定接口继续工作。"""

    def __init__(self, status_code: int, path: str):
        self.status_code = int(status_code)
        self.path = str(path)
        super().__init__(f"NextFind 服务端接口异常（HTTP {self.status_code}）：{self.path}")


class NextFindHTTPError(NextFindError):
    """其他非成功 HTTP 响应；保留失败接口，不携带请求查询参数。"""

    def __init__(self, status_code: int, path: str):
        self.status_code = int(status_code)
        self.path = str(path)
        reason = "，接口不存在，请检查服务版本与 API 地址" if self.status_code == 404 else ""
        super().__init__(f"NextFind 请求失败（HTTP {self.status_code}{reason}）：{self.path}")


class NextFindClient:
    """NextFind OpenAPI 轻客户端（同步，直连不走代理）。"""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30, *,
                 cancel_event=None, deadline: Optional[float] = None):
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.api_key = str(api_key or "").strip()
        try:
            self.timeout = float(timeout)
            self.deadline = float(deadline) if deadline is not None else None
        except (TypeError, ValueError):
            raise NextFindError("NextFind 请求超时或截止时间设置无效") from None
        if (not math.isfinite(self.timeout) or self.timeout <= 0
                or (self.deadline is not None and not math.isfinite(self.deadline))):
            raise NextFindError("NextFind 请求超时或截止时间设置无效")
        self.cancel_event = cancel_event

    def _client(self) -> httpx.AsyncClient:
        # 自建服务：trust_env=False 直连，绕过平台注入的境外代理。
        return httpx.AsyncClient(
            timeout=self.timeout,
            trust_env=False,
            follow_redirects=False,
            headers={"X-API-Key": self.api_key},
        )

    def _check_running(self, request_deadline: float, path: str) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise NextFindCancelledError(f"NextFind 请求已取消：{path}")
        now = time.monotonic()
        if self.deadline is not None and now >= self.deadline:
            if self.cancel_event is not None:
                self.cancel_event.set()
            raise NextFindDeadlineError(f"NextFind 整轮截止时间已到：{path}")
        if now >= request_deadline:
            raise NextFindTimeoutError(f"NextFind 请求超时：{path}")

    async def _request_async(self, method: str, path: str, kwargs: dict,
                             request_deadline: float):
        async def receive():
            self._check_running(request_deadline, path)
            async with self._client() as client:
                # Client initialization may consume time too. Do not send a
                # mutation if its deadline expired while preparing the client.
                self._check_running(request_deadline, path)
                async with client.stream(method, f"{self.base_url}{path}", **kwargs) as response:
                    self._check_running(request_deadline, path)
                    self._check(response, path)
                    await response.aread()
                    self._check_running(request_deadline, path)
                    try:
                        return response.json()
                    except ValueError:
                        raise NextFindResponseError(f"NextFind 响应不是有效 JSON：{path}") from None

        request = asyncio.create_task(receive())
        try:
            # A network-phase timeout alone permits an endless trickle of
            # response bytes. This deadline covers connection, headers and the
            # entire body, and the Event also stops a blocked network await.
            while True:
                self._check_running(request_deadline, path)
                done, _ = await asyncio.wait({request}, timeout=min(0.05, request_deadline - time.monotonic()))
                if done:
                    self._check_running(request_deadline, path)
                    return await request
        finally:
            if not request.done():
                request.cancel()
            # Return only after the actual AsyncClient request/context has
            # unwound and closed its stream. No orphaned writer is left behind.
            await asyncio.gather(request, return_exceptions=True)

    def _request(self, method: str, path: str, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise NextFindError("同步 NextFind 请求须在线程中执行")
        request_deadline = time.monotonic() + self.timeout
        if self.deadline is not None:
            request_deadline = min(request_deadline, self.deadline)
        self._check_running(request_deadline, path)
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._request_async(method, path, kwargs, request_deadline))
        except httpx.TimeoutException:
            raise NextFindTimeoutError(f"NextFind 请求超时：{path}") from None
        except httpx.RequestError:
            raise NextFindError(f"NextFind 连接失败：{path}") from None
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            # Cancelling a DNS lookup prevents its coroutine from proceeding to
            # connect/send. Do not wait indefinitely for an OS DNS worker here.
            # loop.close() shuts down its executor without waiting for that worker.
            loop.close()

    @staticmethod
    def _check(resp, path: str = "") -> None:
        """所有非成功响应都转换为短消息，不能把 HTTPX 帮助链接写进通知。"""
        if resp.status_code in (401, 403):
            raise NextFindAuthError(f"NextFind 鉴权失败（HTTP {resp.status_code}）：API 密钥无效或已过期")
        if 500 <= resp.status_code < 600:
            raise NextFindServerError(resp.status_code, path)
        if not 200 <= resp.status_code < 300:
            raise NextFindHTTPError(resp.status_code, path)

    def _get(self, path: str, params: dict) -> dict:
        return self._request("GET", path, params=params)

    def _post(self, path: str, body: dict) -> dict:
        # Never retry a mutation: after a timeout its server-side outcome may
        # already be committed, even though no response reached the client.
        return self._request("POST", path, json=body)

    @staticmethod
    def _true_flag(value) -> bool:
        """成功标志只接受明确的 true/1，不能把字符串 false 当作成功。"""
        return _true_flag(value)

    @classmethod
    def _check_payload(cls, payload, path: str) -> None:
        """成功 HTTP 状态不代表查询成功，还需检查数据包装。"""
        if not isinstance(payload, dict):
            raise NextFindResponseError(f"NextFind 响应格式异常：{path}（缺少数据包装）")
        if "status" in payload and str(payload["status"]).strip().lower() not in ("success", "ok"):
            raise NextFindResponseError(f"NextFind 响应表示失败：{path}（status）")
        if "success" in payload and not cls._true_flag(payload["success"]):
            raise NextFindResponseError(f"NextFind 响应表示失败：{path}（success）")

    @classmethod
    def _list_data(cls, payload, path: str) -> List[dict]:
        """查询失败或包装损坏必须报错；只有有效列表才能代表查询成功。"""
        cls._check_payload(payload, path)
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("items", "results", "subscriptions"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            raise NextFindResponseError(f"NextFind 响应格式异常：{path}（缺少有效列表）")
        if any(not isinstance(item, dict) for item in data):
            raise NextFindResponseError(f"NextFind 响应格式异常：{path}（列表项目不是对象）")
        return data

    def _mutation_result(self, payload, path: str) -> Tuple[bool, str]:
        if not isinstance(payload, dict):
            raise NextFindResponseError(f"NextFind 响应格式异常：{path}（缺少结果包装）")
        status = str(payload.get("status") or "").strip().lower()
        ok = status in ("success", "ok") or self._true_flag(payload.get("success"))
        if "status" in payload and status not in ("success", "ok"):
            ok = False
        if "success" in payload and not self._true_flag(payload["success"]):
            ok = False
        message = str(payload.get("message") or "")
        if self.api_key:
            message = message.replace(self.api_key, "[已隐藏 API 密钥]")
        return ok, message

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
        return self._list_data(payload, "/search")

    def list_subscriptions(self) -> List[dict]:
        """活跃订阅列表（本插件主要靠 /search 的 is_subscribed 去重，此处备用）。"""
        payload = self._get("/subscriptions", {})
        return self._list_data(payload, "/subscriptions")

    def subscription_info(self, items: List[dict]) -> List[dict]:
        """批量查询订阅入库进度，兼容常见的数据包装格式。"""
        payload = self._post("/subscriptions/info", {"items": items})
        return self._list_data(payload, "/subscriptions/info")

    def quota(self) -> dict:
        """查询额度/积分（供「测试连接」动作）。"""
        payload = self._get("/quota", {})
        self._check_payload(payload, "/quota")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise NextFindResponseError("NextFind 响应格式异常：/quota（缺少额度对象）")
        return data

    # Extended NextFind OpenAPI helpers.  These remain thin wrappers so the V1
    # plugin can expose new server capabilities without duplicating HTTP logic.
    def shield_search(self, **params):
        return self._get("/shield/search", params)

    def resources_search(self, **params):
        return self._get("/resources/search", params)

    def preview(self, slug: str):
        return self._post("/preview", {"slug": str(slug)})

    def hdhive_unlock(self, resource_id, media_type: str):
        return self._post("/hdhive/unlock", {"id": str(resource_id), "type": str(media_type)})

    def directories(self, cid="0"):
        return self._get("/directories", {"cid": str(cid)})

    def create_directory(self, parent_cid, name: str):
        return self._post("/directories", {"parent_cid": str(parent_cid), "name": str(name)})

    def delete_media(self, kind: str, **params):
        return self._request_delete(f"/media/{kind}", params)

    def local_library_filter(self, status_filter="missing"):
        return self._get("/local_library/filter", {"status_filter": status_filter})

    def logs(self, lines=50):
        return self._get("/logs", {"lines": int(lines)})

    def history(self, page=1, page_size=20):
        return self._get("/history", {"page": int(page), "page_size": int(page_size)})

    def delete_history(self, all_records=False, **params):
        path = "/history/all" if all_records else "/history/item"
        return self._request_delete(path, params)

    def _request_delete(self, path: str, params: dict):
        return self._request("DELETE", path, params=params)

    def settings(self, name: str):
        return self._get(f"/settings/{name}", {})

    def update_settings(self, name: str, body: dict):
        return self._post(f"/settings/{name}", body)

    def toggle_ignored_episode(self, tmdb_id, season):
        return self._post("/ignored_episodes/toggle", {"tmdb_id": str(tmdb_id), "season": int(season)})

    # ------------------------------------------------------------------ #
    # 订阅
    # ------------------------------------------------------------------ #
    def add(self, tmdb_id, media_type: str, season: Optional[int] = None) -> Tuple[bool, str]:
        """加订阅：body {tmdb_id, media_type[, season]}。返回 (是否成功, 消息)。"""
        body = {"tmdb_id": str(tmdb_id), "media_type": str(media_type).lower()}
        if season is not None and str(media_type).lower() == "tv":
            body["season"] = season
        payload = self._post("/subscriptions/add", body)
        return self._mutation_result(payload, "/subscriptions/add")

    def remove(self, tmdb_id, media_type: str) -> Tuple[bool, str]:
        """取消订阅（本次不接入 UI，保留供将来用）。"""
        body = {"tmdb_id": str(tmdb_id), "media_type": str(media_type).lower()}
        payload = self._post("/subscriptions/remove", body)
        return self._mutation_result(payload, "/subscriptions/remove")

    def fill_missing(self, tmdb_id, media_type: str, title: str = "") -> Tuple[bool, str]:
        """把存在缺集的订阅推入 NextFind 高优补缺队列。"""
        payload = self._post("/media/fill_missing", {
            "tmdb_id": str(tmdb_id),
            "media_type": str(media_type).lower(),
            "title": str(title or ""),
        })
        return self._mutation_result(payload, "/media/fill_missing")
