"""Signed WeCom callbacks and media access through the platform HTTP service."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import struct
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlencode, urlsplit

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from defusedxml.ElementTree import fromstring


MAX_CALLBACK_BYTES = 1024 * 1024
_API = "https://qyapi.weixin.qq.com/cgi-bin/"
_EXPIRED_TOKEN_CODES = {40001, 40014, 42001}
_MESSAGE_FIELDS = {
    "MsgType", "FromUserName", "ToUserName", "AgentID", "MsgId",
    "MediaId", "FileName", "Content", "CreateTime",
}


def _xml(body: bytes):
    if not body or len(body) > MAX_CALLBACK_BYTES:
        raise ValueError("企业微信回调内容大小无效")
    try:
        root = fromstring(body, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception:
        raise ValueError("企业微信回调 XML 无效") from None
    if root.tag != "xml":
        raise ValueError("企业微信回调 XML 无效")
    return root


def _filename(headers: Mapping[str, str]) -> str:
    disposition = str(headers.get("content-disposition", ""))
    extended = re.search(r"(?:^|;)\s*filename\*\s*=\s*(?:\"([^\"]*)\"|([^;]*))", disposition, re.I)
    regular = re.search(r"(?:^|;)\s*filename\s*=\s*(?:\"([^\"]*)\"|([^;]*))", disposition, re.I)
    name = ""
    if extended:
        value = (extended.group(1) or extended.group(2) or "").strip()
        try:
            charset, _language, encoded = value.split("'", 2)
            if charset.lower() in {"utf-8", "us-ascii"}:
                name = unquote(encoded, encoding=charset, errors="strict")
        except (ValueError, UnicodeError):
            pass
    if not name and regular:
        name = (regular.group(1) or regular.group(2) or "").strip()
    # Returned metadata is a display name, never a path chosen by the server.
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "_", name).strip(" .")[:180]
    if name and name not in {".", ".."}:
        return name
    content_type = str(headers.get("content-type", "")).split(";", 1)[0].lower().strip()
    suffix = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        "application/pdf": ".pdf", "image/tiff": ".tiff", "image/gif": ".gif",
    }.get(content_type, "")
    return "media" + suffix if suffix else ""


def _safe_media_redirect(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in {None, 443}
            and (host == "qyapi.weixin.qq.com" or host == "wework.qpic.cn")
        )
    except ValueError:
        return False


class WeCom:
    """The configuration getter is re-read so changed credentials take effect."""

    def __init__(self, ctx: Any, config_getter: Callable[[], Mapping[str, Any]]) -> None:
        self.ctx = ctx
        self.config_getter = config_getter
        self._token_lock = asyncio.Lock()
        self._access_token = ""
        self._token_until = 0.0
        self._token_credentials: tuple[str, str] | None = None

    def _config(self) -> Mapping[str, Any]:
        config = self.config_getter()
        if not isinstance(config, Mapping):
            raise ValueError("企业微信配置无效")
        return config

    @staticmethod
    def _setting(config: Mapping[str, Any], key: str) -> str:
        value = str(config.get(key) or "").strip()
        if not value or len(value) > 512:
            raise ValueError("企业微信配置不完整")
        return value

    @staticmethod
    def _decrypt(encrypted: str, config: Mapping[str, Any]) -> bytes:
        corp_id = WeCom._setting(config, "wecom_corp_id").encode("utf-8")
        encoding_key = WeCom._setting(config, "wecom_encoding_aes_key")
        if not re.fullmatch(r"[A-Za-z0-9+/]{43}", encoding_key):
            raise ValueError("企业微信 EncodingAESKey 无效")
        try:
            key = base64.b64decode(encoding_key + "=", validate=True)
            ciphertext = base64.b64decode(encrypted, validate=True)
            if len(key) != 32 or not ciphertext or len(ciphertext) % 16:
                raise ValueError
            decryptor = Cipher(algorithms.AES(key), modes.CBC(key[:16])).decryptor()
            padded = decryptor.update(ciphertext) + decryptor.finalize()
            padding = padded[-1]
            # WeCom's padding block is 32 bytes, although AES has 16-byte blocks.
            if len(padded) % 32 or not 1 <= padding <= 32:
                raise ValueError
            if not hmac.compare_digest(padded[-padding:], bytes([padding]) * padding):
                raise ValueError
            frame = padded[:-padding]
            if len(frame) < 20:
                raise ValueError
            message_length = struct.unpack("!I", frame[16:20])[0]
            if not 0 < message_length <= MAX_CALLBACK_BYTES or 20 + message_length > len(frame):
                raise ValueError
            receive_id = frame[20 + message_length:]
            if not hmac.compare_digest(receive_id, corp_id):
                raise ValueError
            message = frame[20:20 + message_length]
            message.decode("utf-8")
            return message
        except Exception:
            raise ValueError("企业微信回调解密失败") from None

    async def verify(self, request: Any) -> bytes:
        """Verify GET URL checks or POST envelopes and return authenticated bytes."""
        config = self._config()
        token = self._setting(config, "wecom_token")
        method = str(request.method).upper()
        if method not in {"GET", "POST"}:
            raise ValueError("企业微信回调请求方式无效")
        query = request.query
        timestamp = str(query.get("timestamp", ""))
        nonce = str(query.get("nonce", ""))
        signature = str(query.get("msg_signature", ""))
        if not re.fullmatch(r"[0-9]{1,12}", timestamp) or abs(time.time() - int(timestamp)) > 300:
            raise ValueError("企业微信回调时间戳无效")
        if not nonce or len(nonce) > 256 or not re.fullmatch(r"[0-9a-fA-F]{40}", signature):
            raise ValueError("企业微信回调参数无效")
        if method == "GET":
            encrypted = str(query.get("echostr", ""))
        else:
            try:
                content_length = request.headers.get("content-length")
                if content_length is not None and (int(content_length) < 0 or int(content_length) > MAX_CALLBACK_BYTES):
                    raise ValueError
                # Plugin SDK WebhookRequest already carries the received bytes.
                body = request.body
                if not isinstance(body, bytes) or len(body) > MAX_CALLBACK_BYTES:
                    raise ValueError
            except Exception:
                raise ValueError("企业微信回调内容大小无效") from None
            root = _xml(body)
            encrypted_nodes = root.findall("Encrypt")
            if len(encrypted_nodes) != 1 or len(encrypted_nodes[0]) or not encrypted_nodes[0].text:
                raise ValueError("企业微信回调加密内容无效")
            encrypted = encrypted_nodes[0].text
        if not encrypted or len(encrypted) > MAX_CALLBACK_BYTES:
            raise ValueError("企业微信回调加密内容无效")
        expected = hashlib.sha1("".join(sorted((token, timestamp, nonce, encrypted))).encode("utf-8")).hexdigest()
        if not hmac.compare_digest(expected, signature.lower()):
            raise ValueError("企业微信回调签名无效")
        return self._decrypt(encrypted, config)

    @staticmethod
    def parse(body: bytes) -> dict[str, str]:
        root = _xml(body)
        result: dict[str, str] = {}
        for child in root:
            if child.tag not in _MESSAGE_FIELDS:
                continue
            if child.tag in result or len(child):
                raise ValueError("企业微信消息字段无效")
            result[child.tag] = child.text or ""
        return result

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        try:
            response = await self.ctx.http.request(
                method, _API + endpoint, timeout=30, follow_redirects=False, **kwargs,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # HTTP errors can contain query strings with secrets or access tokens.
            raise ValueError("企业微信接口连接失败") from None
        if not 200 <= response.status_code < 300:
            raise ValueError("企业微信接口请求失败")
        try:
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError
            return result
        except Exception:
            raise ValueError("企业微信接口响应无效") from None

    @staticmethod
    def _error_code(result: Mapping[str, Any]) -> int:
        try:
            return int(result.get("errcode", 0))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("企业微信接口响应无效") from None

    async def _token(self) -> str:
        config = self._config()
        credentials = (
            self._setting(config, "wecom_corp_id"), self._setting(config, "wecom_secret"),
        )
        async with self._token_lock:
            if credentials == self._token_credentials and self._access_token and time.monotonic() < self._token_until:
                return self._access_token
            result = await self._request("GET", "gettoken", params={
                "corpid": credentials[0], "corpsecret": credentials[1],
            })
            access_token = result.get("access_token")
            if self._error_code(result) or not isinstance(access_token, str) or not access_token or len(access_token) > 1024:
                raise ValueError("企业微信访问凭据获取失败，请检查应用配置")
            try:
                expires = int(result.get("expires_in", 7200))
                if expires <= 0:
                    raise ValueError
            except (TypeError, ValueError, OverflowError):
                raise ValueError("企业微信访问凭据有效期无效") from None
            self._access_token = access_token
            self._token_credentials = credentials
            self._token_until = time.monotonic() + max(0, min(expires, 7200) - 60)
            return access_token

    async def _invalidate(self, access_token: str) -> None:
        async with self._token_lock:
            if hmac.compare_digest(self._access_token, access_token):
                self._token_until = 0.0

    async def _media_headers(self, url: str, max_bytes: int) -> Mapping[str, str]:
        """HEAD is optional metadata; never fetch a complete media body here."""
        try:
            response = await self.ctx.http.request("HEAD", url, timeout=30, follow_redirects=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            return {}
        if response.status_code in {301, 302, 303, 307, 308}:
            if not _safe_media_redirect(str(response.headers.get("location", ""))):
                raise ValueError("企业微信媒体跳转地址无效")
            return {}
        if not 200 <= response.status_code < 300:
            return {}
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    raise ValueError
            except (TypeError, ValueError, OverflowError):
                raise ValueError("企业微信媒体超过允许的大小") from None
        return response.headers

    async def download(self, media_id: str, path: str | Path, max_bytes: int) -> str:
        """Download a fixed official API resource; return sanitized filename metadata.

        The platform's download facade bounds streaming bytes and handles its proxy.
        It follows redirects internally. Only the trusted official media/get endpoint
        receives a validated opaque ID; callers cannot supply a download URL.
        """
        if not isinstance(media_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", media_id):
            raise ValueError("企业微信媒体 ID 无效")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 0 < max_bytes <= 25 * 1024 * 1024:
            raise ValueError("企业微信媒体大小限制无效")
        target = Path(path)
        for attempt in range(2):
            access_token = await self._token()
            url = _API + "media/get?" + urlencode({"access_token": access_token, "media_id": media_id})
            headers = await self._media_headers(url, max_bytes)
            try:
                await self.ctx.http.download(url, target, max_bytes=max_bytes)
                if not target.is_file() or target.stat().st_size == 0 or target.stat().st_size > max_bytes:
                    raise ValueError
                with target.open("rb") as source:
                    prefix = source.read(min(MAX_CALLBACK_BYTES, max_bytes))
            except asyncio.CancelledError:
                target.unlink(missing_ok=True)
                raise
            except Exception:
                target.unlink(missing_ok=True)
                raise ValueError("企业微信媒体下载失败或超过允许的大小") from None
            # WeCom may return HTTP 200 with a JSON error instead of file bytes.
            if prefix.lstrip().startswith((b"{", b"[")):
                target.unlink(missing_ok=True)
                try:
                    result = json.loads(prefix)
                    code = self._error_code(result) if isinstance(result, dict) else -1
                except (ValueError, TypeError):
                    code = -1
                if code in _EXPIRED_TOKEN_CODES and not attempt:
                    await self._invalidate(access_token)
                    continue
                raise ValueError("企业微信媒体获取失败，请重新发送文件")
            return _filename(headers)
        raise ValueError("企业微信媒体访问凭据已失效")

    async def send(self, user: str, text: str) -> None:
        if not isinstance(user, str) or user.lower() == "@all" or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,128}", user):
            raise ValueError("企业微信通知用户无效")
        config = self._config()
        try:
            agent_id = int(config.get("wecom_agent_id", 0))
            if isinstance(config.get("wecom_agent_id"), bool) or not 0 < agent_id < 2 ** 31:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            raise ValueError("企业微信应用 AgentID 无效") from None
        content = str(text).encode("utf-8")[:2048].decode("utf-8", errors="ignore")
        if not content:
            return
        for attempt in range(2):
            access_token = await self._token()
            result = await self._request("POST", "message/send", params={"access_token": access_token}, json={
                "touser": user, "msgtype": "text", "agentid": agent_id,
                "text": {"content": content}, "safe": 0,
            })
            code = self._error_code(result)
            if code in _EXPIRED_TOKEN_CODES and not attempt:
                await self._invalidate(access_token)
                continue
            if code or result.get("invaliduser") or result.get("unlicenseduser"):
                raise ValueError("企业微信通知发送失败，请检查应用可见范围")
            return
        raise ValueError("企业微信通知访问凭据已失效")
