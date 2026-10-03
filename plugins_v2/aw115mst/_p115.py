"""Async 115 adapter. Every HTTP request uses the platform's ``ctx.http``.

Only ``p115client==0.0.9.3.7`` is supported (Python 3.12+). Imports are lazy,
so a missing dependency never prevents the plugin module from being scanned.
``check_rapid_upload`` really performs upload initialization: status=2 means
the remote file has already been created, not merely that a lookup succeeded.
QR credentials and the string returned by ``finalize_qr`` are private values;
the caller must never include them in logs, notifications or public API output.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Iterable, Mapping
from hashlib import sha1 as _sha1
from importlib import import_module, metadata
import inspect
import json
import math
from pathlib import Path
import re
import secrets
import sys
import time
from urllib.parse import urlsplit

from . import _files


P115_VERSION = "0.0.9.3.7"
QR_APPS = ("115android", "qandroid", "tv", "web", "ios", "harmony")
_EXPIRED_CODES = {99, 990001, 990002, 40101017, 40101032}
_READ_SIZE = 1024 * 1024
_PART_SIZE = 16 * 1024 * 1024
_MAX_PART_SIZE = 64 * 1024 * 1024


class P115ClientError(RuntimeError):
    """A sanitized failure; no upstream response or credential is attached."""


class SessionExpiredError(P115ClientError):
    """The configured session is unusable; processing must stop immediately."""


def is_session_expired(value) -> bool:
    """Inspect known response fields without rendering arbitrary responses."""
    if not isinstance(value, Mapping):
        return isinstance(value, SessionExpiredError)
    candidates = [value]
    if isinstance(value.get("data"), Mapping):
        candidates.append(value["data"])
    for item in candidates:
        for key in ("errNo", "errno", "errcode", "errCode", "code"):
            try:
                if int(item.get(key, 0)) in _EXPIRED_CODES:
                    return True
            except (TypeError, ValueError):
                pass
        text = " ".join(str(item.get(key, "")) for key in ("error", "message", "msg"))
        if any(marker in text for marker in ("登录超时", "登陆超时", "请重新登录", "请重新登陆")):
            return True
    return False


def _cookie_string(value) -> str:
    if isinstance(value, Mapping):
        value = "; ".join(f"{key}={item}" for key, item in value.items() if item not in (None, ""))
    if not isinstance(value, str):
        raise P115ClientError("115 Cookie 格式无效")
    value = value.strip().strip(";")
    if len(value) > 32768 or any(character in value for character in ("\r", "\n", "\x00")):
        raise P115ClientError("115 Cookie 格式无效")
    return value


def _pid(value) -> int:
    try:
        text = str(value)
        if not re.fullmatch(r"\d+", text):
            raise ValueError
        return int(text)
    except (TypeError, ValueError):
        raise P115ClientError("115 目录 ID 必须是非负整数") from None


def _error_code(response) -> str:
    for key in ("errNo", "errno", "errcode", "errCode", "code"):
        value = response.get(key)
        if re.fullmatch(r"-?\d+", str(value)):
            return str(value)
    return "未知"


def _oss_endpoint(value) -> str:
    """Upgrade only standard trusted OSS region endpoints; never follow redirects."""
    try:
        target = urlsplit(str(value))
        host = (target.hostname or "").lower()
        port = target.port
    except (TypeError, ValueError):
        raise P115ClientError("115 上传地址格式异常") from None
    if (target.username or target.password or target.query or target.fragment or
            target.path not in ("", "/") or not host.endswith(".aliyuncs.com")):
        raise P115ClientError("115 上传地址格式异常")
    if target.scheme == "http":
        if port not in (None, 80) or not re.fullmatch(r"oss-[a-z0-9-]+\.aliyuncs\.com", host):
            raise P115ClientError("115 上传地址格式异常")
    elif target.scheme != "https" or port not in (None, 443):
        raise P115ClientError("115 上传地址格式异常")
    return f"https://{host}"


def _load_sdk():
    if sys.version_info < (3, 12):
        raise P115ClientError("p115client 0.0.9.3.7 需要 Python 3.12 或更高版本")
    try:
        version = metadata.version("p115client")
        if version != P115_VERSION:
            raise P115ClientError(f"需要 p115client=={P115_VERSION}，请检查插件依赖")
        return import_module("p115client").P115Client
    except P115ClientError:
        raise
    except Exception:
        raise P115ClientError("115 依赖缺失或不兼容，请检查插件依赖安装日志") from None


class P115Adapter:
    """One serialized SDK instance per plugin adapter, with no auto-relogin/retry."""

    def __init__(self, ctx, cookies: str = "", *, timeout: float = 30):
        self._ctx = ctx
        self._cookies = _cookie_string(cookies)
        self.timeout = max(5.0, min(float(timeout), 300.0))
        self._lock = asyncio.Lock()
        self._sdk_type = None
        self._client = None
        self._user_key = ""
        self._directories: dict[tuple[int, str], int] = {}
        self._qr: dict[str, dict] = {}
        self._expired = False
        self._closed = False

    async def close(self) -> None:
        """The caller first cancels/drains its worker, then closes this adapter."""
        async with self._lock:
            self._closed = True
            self._qr.clear()
            self._directories.clear()
            self._user_key = self._cookies = ""
            self._client = None

    async def set_cookies(self, cookies: str) -> None:
        """Explicit user login/config replacement; never called automatically."""
        replacement = _cookie_string(cookies)
        async with self._lock:
            self._check_open()
            self._replace_cookies(replacement)

    def _replace_cookies(self, cookies: str) -> None:
        self._cookies = cookies
        self._client = None
        self._user_key = ""
        self._directories.clear()
        self._expired = False

    def _check_open(self) -> None:
        if self._closed:
            raise P115ClientError("115 客户端已关闭")

    def _check_session(self) -> None:
        self._check_open()
        if self._expired or not self._cookies:
            raise SessionExpiredError("115 会话失效或尚未配置，请更新 Cookie 后重新运行")

    def _expire(self) -> None:
        self._expired = True
        self._user_key = ""
        self._directories.clear()
        raise SessionExpiredError("115 会话已失效，请更新 Cookie 后重新运行")

    async def _ensure_sdk(self):
        self._check_open()
        if self._sdk_type is None:
            self._sdk_type = await asyncio.to_thread(_load_sdk)
        if self._client is None:
            # An empty string is intentional: None would trigger SDK QR login.
            try:
                client = self._sdk_type(self._cookies, console_qrcode=False)
                client.check_for_relogin = False
                self._client = client
            except Exception:
                raise P115ClientError("115 客户端初始化失败，请检查 Cookie 和插件依赖") from None
        return self._client

    def _user_id(self) -> int:
        try:
            value = self._client.user_id
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError
            return value
        except Exception:
            raise P115ClientError("115 Cookie 缺少有效的账号 ID") from None

    async def _request(self, url: str, method: str = "GET", *, async_=True,
                       parse=True, raise_for_status=True, cookies=None, **kwargs):
        """Implement p115client's custom-request contract over the SDK facade."""
        self._check_open()
        if not async_:
            raise P115ClientError("115 适配层只允许异步请求")
        try:
            target = urlsplit(str(url))
            host = (target.hostname or "").lower()
            port = target.port
        except (TypeError, ValueError):
            raise P115ClientError("115 返回了无效的请求地址") from None
        is_115 = host == "115.com" or host.endswith(".115.com")
        is_oss = host.endswith(".aliyuncs.com")
        if target.scheme != "https" or target.username or target.password or not (is_115 or is_oss):
            raise P115ClientError("115 返回了不支持的请求地址")
        if port not in (None, 443):
            raise P115ClientError("115 返回了不支持的请求端口")
        headers = dict(kwargs.pop("headers", None) or {})
        if not is_115 and any(str(key).lower() == "cookie" for key in headers):
            raise P115ClientError("禁止向上传存储服务发送账号 Cookie")
        if cookies is not None and is_115:
            kwargs["cookies"] = cookies
        data = kwargs.pop("data", None)
        if data is not None:
            if isinstance(data, (bytes, bytearray, memoryview, str)):
                kwargs["content"] = bytes(data) if not isinstance(data, (bytes, str)) else data
            elif isinstance(data, Mapping):
                kwargs["data"] = dict(data)
            elif isinstance(data, AsyncIterable):
                kwargs["content"] = data
            elif isinstance(data, Iterable):
                # OSS passes chunk iterables; never hand an AsyncClient a sync stream.
                async def chunks():
                    for chunk in data:
                        yield bytes(chunk)
                kwargs["content"] = chunks()
            else:
                raise P115ClientError("115 请求数据格式不受支持")
        try:
            timeout = max(1.0, min(float(kwargs.pop("timeout", self.timeout)), 300.0))
        except (TypeError, ValueError, OverflowError):
            raise P115ClientError("115 请求超时配置无效") from None
        kwargs["follow_redirects"] = False
        if set(kwargs) - {"params", "data", "json", "content", "files", "cookies", "follow_redirects"}:
            raise P115ClientError("115 请求包含不支持的参数")
        try:
            response = await self._ctx.http.request(
                str(method).upper(), str(url), headers=headers, timeout=timeout, **kwargs,
            )
            if response.status_code in (401, 403) and is_115 and host != "qrcodeapi.115.com":
                self._expire()
            if raise_for_status:
                response.raise_for_status()
            if parse is None or parse is Ellipsis:
                return response
            content = response.content
            if parse is False:
                return content
            if callable(parse):
                try:
                    inspect.signature(parse).bind(response, content)
                except TypeError:
                    parsed = parse(response)
                except ValueError:
                    parsed = parse(response, content)
                else:
                    parsed = parse(response, content)
                return await parsed if inspect.isawaitable(parsed) else parsed
            content_type = response.headers.get("content-type", "").lower()
            if "json" in content_type or content.lstrip().startswith((b"{", b"[")):
                return json.loads(content)
            return response.text
        except asyncio.CancelledError:
            raise
        except P115ClientError:
            raise
        except Exception as exc:
            # HTTP errors may include signed URLs or request bodies: never echo them.
            raise P115ClientError(f"115 HTTP 请求失败（{type(exc).__name__}）") from None

    async def _call(self, operation: str, method: str, *args, **kwargs):
        client = await self._ensure_sdk()
        try:
            result = getattr(client, method)(
                *args, request=self._request, async_=True, timeout=self.timeout,
                headers={"cookie": self._cookies}, **kwargs,
            )
            result = await result if inspect.isawaitable(result) else result
        except asyncio.CancelledError:
            raise
        except P115ClientError:
            raise
        except Exception as exc:
            raise P115ClientError(f"{operation}失败（{type(exc).__name__}）") from None
        if is_session_expired(result):
            self._expire()
        if not isinstance(result, Mapping):
            raise P115ClientError(f"{operation}返回格式异常")
        return dict(result)

    def _success(self, response: dict, operation: str) -> dict:
        if is_session_expired(response):
            self._expire()
        if response.get("state") in (False, 0):
            raise P115ClientError(f"{operation}被 115 拒绝（错误码 {_error_code(response)}）")
        return response

    async def _upload_key(self, *, verify: bool = False) -> str:
        if verify or not self._user_key:
            response = self._success(await self._call("获取上传凭证", "upload_info"), "获取上传凭证")
            nested = response.get("data") if isinstance(response.get("data"), Mapping) else {}
            key = response.get("userkey") or nested.get("userkey")
            if not isinstance(key, str) or not key:
                raise P115ClientError("115 未返回上传凭证")
            self._user_key = key
        return self._user_key

    async def login_info(self) -> dict:
        async with self._lock:
            self._check_session()
            # user_info is a public lookup; upload_info also verifies this session.
            await self._upload_key(verify=True)
            response = self._success(await self._call("查询账号", "user_info"), "查询账号")
            raw = response.get("data") if isinstance(response.get("data"), Mapping) else response
            data = {key: raw[key] for key in ("user_id", "uid", "user_name", "nickname", "is_vip") if key in raw}
            data.setdefault("user_id", self._user_id())
            return {"success": True, "data": data, "user_id": data["user_id"],
                    "user_name": data.get("user_name") or data.get("nickname") or ""}

    async def _find_directory(self, parent: int, name: str) -> int | None:
        offset = 0
        for _ in range(1000):
            response = self._success(await self._call("查询目录", "fs_files", {
                "cid": parent, "show_dir": 1, "nf": "1", "limit": 1150,
                "offset": offset, "cur": 1,
            }), "查询目录")
            path = response.get("path")
            if isinstance(path, list) and path and isinstance(path[-1], Mapping):
                if _pid(path[-1].get("cid", parent)) != parent:
                    raise P115ClientError("目标 115 目录不存在，服务器返回了其他目录")
            items = response.get("data", [])
            if not isinstance(items, list):
                raise P115ClientError("115 目录列表格式异常")
            for item in items:
                if isinstance(item, Mapping) and item.get("n") == name and not item.get("fid"):
                    if item.get("cid") is not None:
                        return _pid(item["cid"])
            if len(items) < 1150:
                return None
            offset += len(items)
        raise P115ClientError("115 目录列表超过分页上限，请缩小目标目录")

    async def ensure_remote_path(self, parts, pid: int = 0) -> int:
        names = tuple(str(name) for name in parts)
        if len(names) > 25 or any(not name or name in {".", ".."} or len(name) > 255 or
                                  any(character in name for character in '/\\<>"\r\n\x00') for name in names):
            raise P115ClientError("115 远程目录名称或层级无效")
        async with self._lock:
            self._check_session()
            current = _pid(pid)
            for name in names:
                cache_key = (current, name)
                cached = self._directories.get(cache_key)
                if cached is not None:
                    current = cached
                    continue
                cid = await self._find_directory(current, name)
                if cid is None:
                    response = await self._call("创建目录", "fs_mkdir", {"cname": name, "pid": current})
                    data = response.get("data") if isinstance(response.get("data"), Mapping) else {}
                    if response.get("state") and data.get("cid") is not None:
                        cid = _pid(data["cid"])
                    else:
                        # Another actor may have created it; do not blindly repeat mkdir.
                        cid = await self._find_directory(current, name)
                    if cid is None:
                        raise P115ClientError(f"无法创建或找到 115 目录（错误码 {_error_code(response)}）")
                self._directories[cache_key] = cid
                current = cid
            return current

    async def _local_snapshot(self, path: Path, root, expected, *, size=None, sha1=None):
        if root is None or expected is None:
            raise P115ClientError("上传必须提供源目录和文件快照")
        snapshot = expected if isinstance(expected, _files.FileSnapshot) else _files.FileSnapshot(**dict(expected))
        current = await asyncio.to_thread(_files.signature, path, root)
        fields = ("size", "mtime_ns", "ctime_ns", "device", "inode")
        if any(getattr(current, field) != getattr(snapshot, field) for field in fields):
            raise _files.FileChangedError("本地文件已改变，已停止上传")
        if size is not None and snapshot.size != size:
            raise _files.FileChangedError("文件大小与快照不一致")
        if sha1 and snapshot.sha1 and str(sha1).upper() != snapshot.sha1.upper():
            raise _files.FileChangedError("文件摘要与快照不一致")
        return snapshot

    async def _read_checked(self, path: Path, root, expected, start: int, end: int, reader):
        result = reader(path, root, expected, f"{start}-{end}")
        data = await result if inspect.isawaitable(result) else result
        if not isinstance(data, bytes) or len(data) != end - start + 1:
            raise _files.FileChangedError("未取得完整的文件验证范围")
        return data

    async def _range_hash(self, path: Path, size: int, challenge: str, *, root, expected, range_reader) -> str:
        match = re.fullmatch(r"(\d+)-(\d+)", str(challenge))
        if not match:
            raise P115ClientError("115 二次验证范围格式无效")
        start, end = map(int, match.groups())
        if start > end or end >= size:
            raise P115ClientError("115 二次验证范围超出文件")
        digest = _sha1()
        while start <= end:
            length = min(_READ_SIZE, end - start + 1)
            chunk = await self._read_checked(path, root, expected, start, start + length - 1, range_reader)
            digest.update(chunk)
            start += length
        return digest.hexdigest().upper()

    async def _initialize_upload(self, filename: str, size: int, sha1: str,
                                 path: Path | None, pid: int, *, root=None, expected=None,
                                 range_reader=None) -> dict:
        if not filename or any(character in filename for character in '/\\\r\n\x00'):
            raise P115ClientError("上传文件名无效")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise P115ClientError("上传文件大小无效")
        if not re.fullmatch(r"[a-fA-F0-9]{40}", str(sha1)):
            raise P115ClientError("文件 SHA-1 必须是 40 位十六进制摘要")
        await self._ensure_sdk()
        payload = {"filename": filename, "filesize": size, "fileid": sha1.upper(),
                   "target": f"U_1_{_pid(pid)}", "userid": self._user_id(),
                   "userkey": await self._upload_key()}
        response = await self._call("秒传初始化", "upload_init", payload)
        if response.get("status") == 2:
            return response
        self._success(response, "秒传初始化")
        if response.get("status") == 7:
            if path is None:
                raise P115ClientError("115 要求二次验证，需要本地文件")
            sign_key = response.get("sign_key")
            if not sign_key:
                raise P115ClientError("115 未返回二次验证参数")
            payload.update(sign_key=sign_key, sign_val=await self._range_hash(
                path, size, response.get("sign_check", ""), root=root, expected=expected,
                range_reader=range_reader or _files.read_range))
            response = await self._call("秒传二次验证", "upload_init", payload)
            if response.get("status") != 2:
                self._success(response, "秒传二次验证")
        return response

    @staticmethod
    def _rapid_result(response: dict) -> dict:
        status = response.get("status")
        if isinstance(status, bool) or status not in (1, 2):
            raise P115ClientError("115 未能确定秒传结果，已停止处理此文件")
        pickcode = response.get("pickcode") or response.get("pick_code") or ""
        if status == 2 and (not isinstance(pickcode, str) or not pickcode):
            raise P115ClientError("115 返回秒传成功但没有文件提取码，无法确认入库")
        return {"success": True, "can_rapid": status == 2, "status": status,
                "pickcode": str(pickcode) if status == 2 else "",
                "message": "秒传成功" if status == 2 else "需要完整上传"}

    async def check_rapid_upload(self, filename: str, size: int, sha1: str,
                                 path: str | Path | None = None, pid: int = 0, *,
                                 expected=None, root=None, range_reader=None) -> dict:
        async with self._lock:
            self._check_session()
            local = Path(path) if path is not None else None
            if local is not None:
                expected = await self._local_snapshot(local, root, expected, size=size, sha1=sha1)
            response = await self._initialize_upload(
                filename, size, sha1, local, pid, root=root, expected=expected, range_reader=range_reader,
            )
            if local is not None:
                await self._local_snapshot(local, root, expected, size=size, sha1=sha1)
            return self._rapid_result(response)

    async def rapid_upload(self, filename: str, size: int, sha1: str,
                           path: str | Path | None = None, pid: int = 0, *,
                           expected=None, root=None, range_reader=None) -> dict:
        return await self.check_rapid_upload(
            filename, size, sha1, path, pid, expected=expected, root=root, range_reader=range_reader,
        )

    async def full_upload(self, path: str | Path, pid: int = 0, *,
                          expected=None, root=None, range_reader=None) -> dict:
        """Upload local bytes in bounded OSS parts; never follow a source URL."""
        async with self._lock:
            self._check_session()
            local = Path(path)
            expected = await self._local_snapshot(local, root, expected)
            size = expected.size
            digest, expected = await _files.hash_file(local, root, expected)
            part_size = max(_PART_SIZE, math.ceil(max(size, 1) / 10000))
            if part_size > _MAX_PART_SIZE:
                raise P115ClientError("文件超过安全完整上传分块上限")
            response = await self._initialize_upload(
                local.name, size, digest, local, pid, root=root, expected=expected, range_reader=range_reader,
            )
            if response.get("status") == 2:
                await self._local_snapshot(local, root, expected)
                return self._rapid_result(response)
            if response.get("status") != 1 or not all(response.get(key) for key in ("object", "bucket", "callback")):
                raise P115ClientError("115 未返回可用的完整上传参数")
            object_key = response["object"]
            bucket = response["bucket"]
            callback = response["callback"]
            if (not isinstance(object_key, str) or not object_key or len(object_key) > 1024 or
                    "://" in object_key or object_key.startswith("//") or
                    any(character in object_key for character in "\r\n\x00") or
                    not isinstance(bucket, str) or
                    not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket) or
                    not isinstance(callback, Mapping) or
                    not all(isinstance(callback.get(key), str) for key in ("callback", "callback_var"))):
                raise P115ClientError("115 完整上传参数格式异常")
            if not size:
                raise P115ClientError("115 不支持本次空文件完整上传")
            try:
                oss = await asyncio.to_thread(import_module, "p115oss")
                token_response = self._success(await self._call("获取上传令牌", "upload_gettoken"), "获取上传令牌")
                token = token_response.get("data") if isinstance(token_response.get("data"), Mapping) else token_response
                if not all(isinstance(token.get(key), str) and token[key] for key in
                           ("AccessKeyId", "AccessKeySecret", "SecurityToken")):
                    raise P115ClientError("115 上传令牌格式异常")
                upload_info = self._success(await self._call("获取上传地址", "upload_url"), "获取上传地址")
                endpoint = _oss_endpoint(upload_info.get("endpoint", ""))
                options = {"token": dict(token), "bucket": bucket, "endpoint": endpoint,
                           "request": self._request, "async_": True, "timeout": self.timeout}
                upload_id = await oss.oss_multipart_upload_init(object_key, **options)
                parts = []
                offset = 0
                while offset < size:
                    end = min(offset + part_size, size)
                    pieces = []
                    start = offset
                    while start < end:
                        stop = min(start + 8 * 1024 * 1024, end)
                        pieces.append(await self._read_checked(
                            local, root, expected, start, stop - 1, range_reader or _files.read_range,
                        ))
                        start = stop
                    chunk = b"".join(pieces)
                    pieces.clear()
                    part = await oss.oss_multipart_upload_part(
                        object_key, upload_id=upload_id, part_number=len(parts) + 1,
                        file=chunk, **options,
                    )
                    parts.append(part)
                    offset += len(chunk)
                    del chunk
                if not parts:
                    raise P115ClientError("115 不支持本次空文件完整上传")
                await self._local_snapshot(local, root, expected)
                result = await oss.oss_multipart_upload_complete(
                    object_key, upload_id=upload_id, parts=parts,
                    callback=dict(callback), **options,
                )
                if not isinstance(result, Mapping):
                    raise P115ClientError("115 完整上传回执格式异常")
                self._success(dict(result), "完整上传")
                if result.get("state") not in (True, 1):
                    raise P115ClientError("115 完整上传回执未确认成功")
                receipt = result.get("data") if isinstance(result.get("data"), Mapping) else result
                pickcode = (receipt.get("pickcode") or receipt.get("pick_code") or
                            response.get("pickcode") or response.get("pick_code"))
                if not isinstance(pickcode, str) or not pickcode:
                    raise P115ClientError("115 完整上传成功但缺少文件提取码，无法确认入库")
                return {"success": True, "can_rapid": False, "status": 1,
                        "pickcode": pickcode,
                        "message": "完整上传成功"}
            except asyncio.CancelledError:
                raise
            except P115ClientError:
                raise
            except Exception as exc:
                raise P115ClientError(f"115 完整上传失败（{type(exc).__name__}）") from None

    async def start_qr(self, app: str = "115android") -> dict:
        """Return a private session handle and PNG; raw UID/sign never leave here."""
        if app not in QR_APPS:
            raise P115ClientError("不支持的 115 登录设备")
        async with self._lock:
            await self._ensure_sdk()
            try:
                token = await self._sdk_type.login_qrcode_token(
                    request=self._request, async_=True, timeout=self.timeout,
                )
                if not isinstance(token, Mapping) or token.get("state") in (False, 0):
                    raise P115ClientError("115 未生成登录二维码")
                data = token.get("data") or {}
                if not isinstance(data, Mapping) or not all(data.get(key) for key in ("uid", "time", "sign")):
                    raise P115ClientError("115 登录二维码参数不完整")
                png = await self._sdk_type.login_qrcode(
                    str(data["uid"]), params={"uid": data["uid"]},
                    request=self._request, async_=True, timeout=self.timeout,
                )
                if not isinstance(png, bytes) or not png.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise P115ClientError("115 登录二维码图片格式异常")
                session_id = secrets.token_urlsafe(24)
                self._qr.clear()
                self._qr[session_id] = {"payload": {key: data[key] for key in ("uid", "time", "sign")},
                                        "app": app, "deadline": time.monotonic() + 120, "confirmed": False}
                return {"session_id": session_id, "qr_png": png, "app": app, "expires_in": 120}
            except asyncio.CancelledError:
                raise
            except P115ClientError:
                raise
            except Exception as exc:
                raise P115ClientError(f"115 二维码生成失败（{type(exc).__name__}）") from None

    def _qr_session(self, session_id: str) -> dict:
        self._check_open()
        session = self._qr.get(str(session_id))
        if session is None or time.monotonic() >= session["deadline"]:
            self._qr.pop(str(session_id), None)
            raise P115ClientError("115 二维码已过期，请重新生成")
        return session

    async def poll_qr(self, session_id: str) -> dict:
        async with self._lock:
            session = self._qr_session(session_id)
            try:
                response = await self._sdk_type.login_qrcode_scan_status(
                    dict(session["payload"]), request=self._request, async_=True,
                    timeout=min(self.timeout, 15, max(1, session["deadline"] - time.monotonic())),
                )
                if not isinstance(response, Mapping) or not isinstance(response.get("data"), Mapping):
                    raise P115ClientError("115 扫码状态格式异常")
                status = response["data"].get("status")
                if status not in (-2, -1, 0, 1, 2):
                    raise P115ClientError("115 返回了未知扫码状态")
                if status == 2:
                    session["confirmed"] = True
                elif status in (-2, -1):
                    self._qr.pop(session_id, None)
                return {"status": status, "confirmed": status == 2,
                        "message": {-2: "已取消", -1: "已过期", 0: "等待扫码", 1: "已扫码，等待确认", 2: "已确认"}[status]}
            except asyncio.CancelledError:
                raise
            except P115ClientError:
                raise
            except Exception as exc:
                raise P115ClientError(f"115 扫码状态查询失败（{type(exc).__name__}）") from None

    async def finalize_qr(self, session_id: str) -> str:
        """Return the sensitive Cookie privately for the caller's config update."""
        async with self._lock:
            session = self._qr_session(session_id)
            if not session["confirmed"]:
                raise P115ClientError("请先扫码并在 115 App 确认登录")
            try:
                response = await self._sdk_type.login_qrcode_scan_result(
                    str(session["payload"]["uid"]), session["app"],
                    request=self._request, async_=True, timeout=self.timeout,
                )
                if not isinstance(response, Mapping) or response.get("state") in (False, 0):
                    raise P115ClientError("115 扫码登录未成功，请重新生成二维码")
                data = response.get("data") or {}
                cookie = _cookie_string(data.get("cookie", "")) if isinstance(data, Mapping) else ""
                if not all(re.search(rf"(?:^|;\s*){key}=[^;]+", cookie) for key in ("UID", "CID", "SEID")):
                    raise P115ClientError("115 未返回完整登录 Cookie")
                self._replace_cookies(cookie)
                self._qr.clear()
                return cookie
            except asyncio.CancelledError:
                raise
            except P115ClientError:
                raise
            except Exception as exc:
                raise P115ClientError(f"115 扫码登录失败（{type(exc).__name__}）") from None
