from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ..core.config import config_manager

try:
    import aiohttp
except ImportError:  # pragma: no cover - runtime dependency
    aiohttp = None

try:
    from aiohttp_socks import ProxyConnector
except ImportError:  # pragma: no cover - runtime dependency
    ProxyConnector = None

try:
    from python_socks import ProxyType
except ImportError:  # pragma: no cover - runtime dependency
    ProxyType = None

try:
    import socks  # noqa: F401
except ImportError:  # pragma: no cover - runtime dependency
    socks = None


SOCKS_PROXY_SCHEMES = {'socks4', 'socks4a', 'socks5', 'socks5h'}
HTTP_PROXY_SCHEMES = {'http', 'https'}


def get_proxy_url() -> str | None:
    proxy = str(config_manager.get().PROXY or '').strip()
    return proxy or None


def get_proxy_scheme(proxy: str | None = None) -> str | None:
    proxy_url = proxy or get_proxy_url()
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    return (parsed.scheme or '').lower() or None


def is_socks_proxy(proxy: str | None = None) -> bool:
    return (get_proxy_scheme(proxy) or '') in SOCKS_PROXY_SCHEMES


def is_http_proxy(proxy: str | None = None) -> bool:
    return (get_proxy_scheme(proxy) or '') in HTTP_PROXY_SCHEMES


def build_requests_proxies(proxy: str | None = None) -> dict[str, str] | None:
    proxy_url = proxy or get_proxy_url()
    if not proxy_url:
        return None
    if is_socks_proxy(proxy_url) and socks is None:
        raise RuntimeError('当前配置了 SOCKS 代理，但运行环境缺少 PySocks 依赖')
    return {'http': proxy_url, 'https': proxy_url}


def build_telebot_proxy(proxy: str | None = None) -> dict[str, str] | None:
    return build_requests_proxies(proxy)


def build_discord_proxy_options(proxy: str | None = None, loop: Any = None) -> dict[str, Any]:
    proxy_url = proxy or get_proxy_url()
    if not proxy_url:
        return {}

    if is_socks_proxy(proxy_url):
        if ProxyConnector is None or ProxyType is None:
            raise RuntimeError('当前配置了 SOCKS 代理，但运行环境缺少 aiohttp-socks 依赖')
        parsed = urlparse(proxy_url)
        if not parsed.hostname or not parsed.port:
            raise RuntimeError(f'代理地址格式不正确: {proxy_url}')
        connector_kwargs: dict[str, Any] = {
            'host': parsed.hostname,
            'port': parsed.port,
            'proxy_type': ProxyType.SOCKS5 if parsed.scheme in {'socks5', 'socks5h'} else ProxyType.SOCKS4,
            'username': parsed.username,
            'password': parsed.password,
            'rdns': parsed.scheme in {'socks4a', 'socks5h'},
        }
        if loop is not None:
            connector_kwargs['loop'] = loop
        return {'connector': ProxyConnector(**connector_kwargs)}

    if is_http_proxy(proxy_url):
        options: dict[str, Any] = {'proxy': proxy_url}
        proxy_auth = build_aiohttp_proxy_auth(proxy_url)
        if proxy_auth is not None:
            options['proxy_auth'] = proxy_auth
        return options

    raise RuntimeError(f'不支持的代理协议: {proxy_url}')


def build_aiohttp_proxy_auth(proxy: str | None = None):
    proxy_url = proxy or get_proxy_url()
    if not proxy_url or aiohttp is None or not is_http_proxy(proxy_url):
        return None
    parsed = urlparse(proxy_url)
    if parsed.username and parsed.password:
        return aiohttp.BasicAuth(parsed.username, parsed.password)
    return None
