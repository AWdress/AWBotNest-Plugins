"""Bounded upstream access through the platform HTTP service."""
from __future__ import annotations

import asyncio
import json as jsonlib
from urllib.parse import urljoin, urlsplit


HOSTS = frozenset({
    "d2.guduomedia.com", "m.douban.com", "www.douban.com", "pianku.api.mgtv.com",
    "bgm.tv", "bangumi.tv", "api.themoviedb.org", "api.bilibili.com",
    "myanimelist.net", "graphql.anilist.co", "api.trakt.tv",
})


class FetchError(ValueError):
    """An intentionally credential-free error suitable for the status page."""


def safe_error(error: Exception) -> str:
    if isinstance(error, FetchError):
        return str(error)
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return "请求超时，请检查平台代理或稍后重试"
    if isinstance(error, ExceptionGroup):
        return safe_error(error.exceptions[0])
    return "请求或解析失败（%s），请检查源站和平台代理" % type(error).__name__


class Transport:
    def __init__(self, http, tmdb_key: str = ""):
        self.http = http
        self.tmdb_key = tmdb_key.strip()

    async def _read(self, url, *, params=None, method="GET", json=None, headers=None):
        headers = {"User-Agent": "Mozilla/5.0 AWBotNest-VPSWidget/0.0.1", **(headers or {})}
        # Authenticated APIs never follow redirects; public pages allow only known HTTPS hosts.
        authenticated = bool(headers.get("Authorization") or headers.get("trakt-api-key")
                             or (params or {}).get("api_key"))
        for redirect in range(4):
            parts = urlsplit(url)
            if parts.scheme != "https" or parts.hostname not in HOSTS or parts.username or parts.password:
                raise FetchError("源站地址不在允许列表中")
            try:
                async with self.http.stream(method, url, params=params, json=json, headers=headers,
                                            timeout=25, follow_redirects=False) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        if authenticated or method != "GET" or redirect == 3:
                            raise FetchError("源站返回不允许的重定向")
                        location = response.headers.get("location", "")
                        if not location:
                            raise FetchError("源站重定向地址缺失")
                        url = urljoin(str(response.url), location)
                        params = None
                        continue
                    if response.status_code >= 400:
                        raise FetchError("源站返回 HTTP %d" % response.status_code)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 5 * 1024 * 1024:
                            raise FetchError("源站响应超过 5 MB，已停止读取")
                    return bytes(body).decode("utf-8", errors="replace")
            except FetchError:
                raise
            except Exception as error:
                # Do not emit httpx exception strings: they can include an API key in a URL.
                name = type(error).__name__
                if "Timeout" in name:
                    raise FetchError("请求超时，请检查平台代理或稍后重试") from None
                raise FetchError("网络请求失败（%s），请检查证书、网络和平台代理" % name) from None
        raise FetchError("源站重定向次数过多")

    async def text(self, url, params=None, headers=None):
        return await self._read(url, params=params, headers=headers)

    async def json(self, url, params=None, method="GET", json=None, headers=None):
        text = await self._read(url, params=params, method=method, json=json, headers=headers)
        try:
            return jsonlib.loads(text)
        except (ValueError, TypeError):
            raise FetchError("源站响应不是有效 JSON") from None

    async def tmdb_json(self, path, params=None):
        if not self.tmdb_key or self.tmdb_key == "********":
            raise FetchError("尚未配置 TMDB 密钥，请先保存配置")
        if not path.startswith("/") or ".." in path or "?" in path or "#" in path:
            raise FetchError("TMDB 请求路径无效")
        params = {"language": "zh-CN", **(params or {})}
        headers = {}
        if self.tmdb_key.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + self.tmdb_key
        else:
            params["api_key"] = self.tmdb_key
        return await self.json("https://api.themoviedb.org/3" + path, params=params, headers=headers)
