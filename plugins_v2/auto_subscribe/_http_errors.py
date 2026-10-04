"""插件内的请求错误摘要：保留状态与地址，不输出查询凭据或说明链接。"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

import httpx


_URL = re.compile(r"https?://[^\s\"'<>（）]+", re.IGNORECASE)


def safe_url(value) -> str:
    """诊断地址只保留协议、主机和路径。"""
    try:
        parts = urlsplit(str(value or ""))
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return ""
        host = parts.hostname
        if ":" in host:
            host = f"[{host}]"
        if parts.port is not None:
            host += f":{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, "", ""))
    except (ValueError, TypeError):
        return ""


def one_line(value) -> str:
    """异常说明不能因 HTTPX 的多行帮助文字而拆成多条通知。"""
    text = str(value or "").split("For more information check:", 1)[0]
    text = _URL.sub(lambda match: safe_url(match.group(0)), text)
    return " ".join(text.split())[:240]


def request_error(exc: Exception, service: str = "请求") -> str:
    """从异常对象取状态和失败地址，不依赖 HTTPX 的英文异常全文。"""
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    try:
        request = getattr(exc, "request", None)
    except RuntimeError:  # HTTPX 的异常可能还未绑定 Request。
        request = None
    location = safe_url(getattr(request, "url", ""))
    suffix = f"：{location}" if location else ""
    if status:
        reason = "，资源或接口不存在" if status == 404 else ""
        return f"{service}失败（HTTP {status}{reason}）{suffix}"
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)) or "Timeout" in type(exc).__name__:
        return f"{service}超时{suffix}"
    if isinstance(exc, httpx.ProxyError):
        return f"{service}代理连接失败{suffix}"
    if isinstance(exc, httpx.RequestError):
        return f"{service}网络连接失败（{type(exc).__name__}）{suffix}"
    return one_line(exc) or f"{service}失败（{type(exc).__name__}）"
