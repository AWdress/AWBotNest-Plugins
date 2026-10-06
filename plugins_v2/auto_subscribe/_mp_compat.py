"""A deliberately small MoviePilot v2 subscription contract backed by NextFind.

Public routes live under the host's plugin webhook namespace, not its admin
API. They use a separate plugin credential and never expose NextFind secrets.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import time
from email.message import Message
from urllib.parse import parse_qs, urlsplit

from starlette.datastructures import Headers
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.responses import JSONResponse

from ._nextfind import NextFindClient, NextFindError


BASE_PATH = "/api/plugin/auto_subscribe/mp"
_BODY_LIMIT = 32 * 1024
_RESPONSE_LIMIT = 2 * 1024 * 1024
_TIMEOUT = 30.0
_ROUTE_LIMIT = 8192
LOGIN_USER = "forward"
_TOKEN_LIFETIME = 24 * 3600
_TYPES = {"电影": "movie", "电视剧": "tv", "剧集": "tv", "movie": "movie", "tv": "tv", "series": "tv"}
_UNSUPPORTED = (
    "quality", "resolution", "effect", "include", "exclude", "filter", "sites",
    "save_path", "directory", "download_setting", "best_version", "start_episode",
    "current_episode", "total_episode", "lack_episode", "episode", "episodes",
)

# MoviePilot v2 serializes the whole Subscribe response model, including
# optional fields. Keep unknown metadata null instead of inventing a season,
# release year, completion progress or downloader settings.
_SUBSCRIBE_DEFAULTS = {
    "id": None, "name": None, "year": None, "type": None, "keyword": None,
    "tmdbid": None, "doubanid": None, "bangumiid": None, "anilistid": None,
    "mediaid": None, "media_source": None, "media_id": None, "season": None,
    "poster": None, "backdrop": None, "vote": 0.0, "description": None,
    "filter": None, "include": None, "exclude": None, "quality": None,
    "resolution": None, "effect": None, "total_episode": 0, "start_episode": 0,
    "lack_episode": 0, "completed_episode": None, "note": None, "state": None,
    "last_update": None, "username": None, "sites": [], "downloader": None,
    "best_version": None, "best_version_full": None, "current_priority": None,
    "episode_priority": None, "save_path": None, "search_imdbid": 0,
    "date": None, "custom_words": None, "media_category": None,
    "filter_groups": [], "episode_group": None,
}


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("重复字段")
        result[key] = value
    return result


class _LoginMultipartParser(MultiPartParser):
    ended = False

    def on_header_end(self):
        if self._current_partial_header_name.lower() == b"content-disposition":
            header = Message()
            header["Content-Disposition"] = self._current_partial_header_value.decode("latin-1")
            # Also reject RFC 2231 filename variants, which the form parser
            # can otherwise ignore and treat as ordinary text credentials.
            parameters = header.get_params(header="content-disposition") or []
            if any(name.lower() == "filename" for name, _ in parameters):
                raise MultiPartException("登录表单不能包含文件")
        super().on_header_end()

    def on_end(self):
        self.ended = True
        super().on_end()


async def _login_fields(req):
    """Parse only the explicitly declared format; never sniff/fall back."""
    content_type = (getattr(req, "headers", {}) or {}).get("content-type", "")
    kind = content_type.split(";", 1)[0].strip().lower()
    if kind in ("", "application/x-www-form-urlencoded"):
        return parse_qs(req.body.decode("utf-8"), keep_blank_values=True,
                        strict_parsing=True, max_num_fields=8, errors="strict")
    if kind == "application/json":
        def reject_constant(value):
            raise ValueError("非 JSON 数值")
        payload = json.loads(req.body.decode("utf-8"), object_pairs_hook=_unique_json_pairs,
                             parse_constant=reject_constant)
        if not isinstance(payload, dict) or len(payload) > 8:
            raise ValueError("登录内容格式无效")
        return {key: [value] for key, value in payload.items()}
    if kind == "multipart/form-data":
        async def body_stream():
            yield req.body
        # max_files=0 rejects any uploaded part before a temporary file opens.
        parser = _LoginMultipartParser(Headers({"content-type": content_type}), body_stream(),
                                      max_files=0, max_fields=8, max_part_size=_BODY_LIMIT)
        form = await parser.parse()
        try:
            if not parser.ended:
                raise ValueError("登录表单未完整提交")
            result = {}
            for key, value in form.multi_items():
                if not isinstance(value, str):
                    raise ValueError("登录表单不能包含文件")
                result.setdefault(key, []).append(value)
            return result
        finally:
            await form.close()
    raise ValueError("不支持的登录内容格式")


def valid_key(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9._~-]{32,256}", value))


def _identity(value):
    if isinstance(value, bool):
        raise ValueError("TMDB ID 必须是正整数")
    raw = str(value).strip() if isinstance(value, (str, int)) else ""
    if not re.fullmatch(r"[0-9]{1,10}", raw) or not 0 < int(raw) <= 2147483647:
        raise ValueError("TMDB ID 必须是正整数")
    return str(int(raw))


def _media_type(value):
    if not isinstance(value, str) or value.strip().lower() not in _TYPES:
        raise ValueError("媒体类型必须是电影或电视剧")
    return _TYPES[value.strip().lower()]


def _subscription_id(tmdb_id, media_type):
    # NF subscriptions represent a whole work. Stable IDs are independent of
    # titles and distinguish movie/tv TMDB IDs; they are not invented NF rows.
    return int(tmdb_id) * 2 + (media_type == "tv")


def parse_subscription(payload, *, allow_whole_series=False):
    if not isinstance(payload, dict):
        raise ValueError("订阅内容必须是 JSON 对象")
    if payload.get("media_source") not in (None, "", "tmdb", "themoviedb"):
        raise ValueError("仅支持 TMDB 作品订阅")
    if payload.get("media_id") not in (None, "") and payload.get("media_source") not in ("tmdb", "themoviedb"):
        raise ValueError("media_id 必须同时声明 TMDB 数据来源")
    identifiers = [payload[key] for key in ("tmdbid", "tmdb_id", "media_id")
                   if payload.get(key) not in (None, "")]
    if not identifiers:
        raise ValueError("请提供作品的 TMDB ID")
    identities = {_identity(value) for value in identifiers}
    if len(identities) != 1:
        raise ValueError("作品的 TMDB ID 字段不一致")
    media_type = _media_type(payload.get("type", payload.get("media_type")))
    if payload.get("type") is not None and payload.get("media_type") is not None:
        if _media_type(payload["type"]) != _media_type(payload["media_type"]):
            raise ValueError("媒体类型字段不一致")
    for key in _UNSUPPORTED:
        if payload.get(key) not in (None, "", False, 0, [], {}):
            raise ValueError(f"NextFind 不支持 MoviePilot 的 {key} 限制，请清空该选项")
    season = payload.get("season")
    if season not in (None, ""):
        if isinstance(season, bool) or not isinstance(season, (str, int)) or not re.fullmatch(r"[0-9]{1,4}", str(season)):
            raise ValueError("季号格式无效")
        season = int(season)
        if media_type == "movie" and season != 0:
            raise ValueError("电影不能指定季号")
        if media_type == "tv" and not allow_whole_series:
            raise ValueError("NextFind 不支持单季订阅；请由管理员在插件中明确允许转为整部订阅")
    name = payload.get("name", payload.get("title", ""))
    if not isinstance(name, str) or len(name) > 256 or any(ord(char) < 32 for char in name):
        raise ValueError("作品名称格式无效")
    return {"tmdb_id": identities.pop(), "media_type": media_type, "title": name.strip(), "requested_season": season}


def _b64(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _issue_token(key):
    now = int(time.time())
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64(json.dumps({"sub": LOGIN_USER, "aud": "nextfind-mp", "iat": now,
                              "exp": now + _TOKEN_LIFETIME}, separators=(",", ":")).encode())
    message = f"{header}.{payload}"
    signature = _b64(hmac.new(key.encode(), message.encode(), hashlib.sha256).digest())
    return f"{message}.{signature}"


def _valid_token(token, key):
    try:
        if not isinstance(token, str) or len(token) > 2048:
            return False
        header, payload, signature = token.split(".")
        expected = _b64(hmac.new(key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature.encode(), expected.encode()):
            return False
        decode = lambda value: json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        algorithm, claims = decode(header), decode(payload)
        now = time.time()
        return (algorithm == {"alg": "HS256", "typ": "JWT"} and isinstance(claims, dict)
                and claims.get("sub") == LOGIN_USER and claims.get("aud") == "nextfind-mp"
                and type(claims.get("iat")) is int and type(claims.get("exp")) is int
                and claims["iat"] <= now < claims["exp"] <= claims["iat"] + _TOKEN_LIFETIME)
    except (TypeError, ValueError, UnicodeError, KeyError):
        return False


class MoviePilotCompat:
    def __init__(self, ctx, config):
        self.ctx, self.config = ctx, config
        self._mutation_lock = asyncio.Lock()
        self._registered = False
        self._route_ids = set()
        self._media_types = {}

    def register(self):
        # PluginRoutes normalizes trailing slashes, matching MP's /subscribe/.
        self.ctx.on_webhook("mp/api/v1/subscribe", self.subscribe)
        self.ctx.on_webhook("mp/api/v1/subscribe/list", self.list_subscriptions)
        self.ctx.on_webhook(f"mp/api/v1/subscribe/user/{LOGIN_USER}", self.list_subscriptions)
        self.ctx.on_webhook("mp/api/v1/login/access-token", self.login)
        self._registered = True

    def _register_rows(self, rows):
        if not self._registered:
            return
        if len(self._route_ids | {row["id"] for row in rows}) > _ROUTE_LIMIT:
            raise NextFindError("兼容接口订阅路由已达上限，请重载插件")
        # The host SDK supports exact webhook paths, not path parameters.
        # Register verified works through the public SDK; never alter its router.
        # Keep old paths for safe, idempotent retries until the plugin is stopped.
        for row in rows:
            sid, tmdb_id = row["id"], str(row["tmdbid"])
            if sid in self._route_ids:
                continue
            async def by_id(req, sid=sid):
                return await self.subscription_item(req, sid=sid)
            self.ctx.on_webhook(f"mp/api/v1/subscribe/{sid}", by_id)
            self._route_ids.add(sid)
            if tmdb_id not in self._media_types:
                self._media_types[tmdb_id] = set()
                async def by_media(req, tmdb_id=tmdb_id):
                    return await self.subscription_item(req, tmdb_id=tmdb_id)
                self.ctx.on_webhook(f"mp/api/v1/subscribe/media/tmdb:{tmdb_id}", by_media)
            self._media_types[tmdb_id].add(_media_type(row["type"]))

    async def sync_routes(self):
        cfg = self.config()
        if self._configured(cfg) is not None:
            return
        try:
            async with asyncio.timeout(_TIMEOUT):
                await self._rows(cfg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.ctx.log.warning("[MoviePilot 接口] 订阅路由同步失败（%s），查询订阅时将重新同步", type(exc).__name__)

    @staticmethod
    def response(payload, status=200):
        return JSONResponse(payload, status_code=status, headers={"Cache-Control": "no-store"})

    def _configured(self, cfg):
        if cfg.get("mp_api_enabled") is not True:
            return self.response({"detail": "MoviePilot 兼容接口未开启"}, 404)
        key = cfg.get("mp_api_key")
        if not valid_key(key):
            return self.response({"detail": "兼容接口访问密钥未配置"}, 503)
        return None

    def _authorized(self, req, cfg):
        unavailable = self._configured(cfg)
        if unavailable is not None:
            return unavailable
        key = cfg["mp_api_key"]
        headers, query = getattr(req, "headers", {}) or {}, getattr(req, "query", {}) or {}
        supplied = [headers.get("x-api-key"), query.get("apikey"), query.get("token")]
        # MP v2 clients use API_TOKEN via X-API-KEY/apikey/token, not an admin JWT.
        nonempty = [value for value in supplied if isinstance(value, str) and value]
        authorization = headers.get("authorization", "")
        bearer = authorization.split(" ", 1)
        has_bearer = len(bearer) == 2 and bearer[0].lower() == "bearer"
        if ((not nonempty and not has_bearer)
                or any(not hmac.compare_digest(value.encode(), key.encode()) for value in nonempty)
                or (authorization and (not has_bearer or not _valid_token(bearer[1], key)))):
            return self.response({"detail": "访问密钥无效"}, 401)
        return None

    async def login(self, req):
        cfg = self.config()
        unavailable = self._configured(cfg)
        if unavailable is not None:
            return unavailable
        if str(getattr(req, "method", "")).upper() != "POST":
            return self.response({"detail": "请求方法不支持"}, 405)
        if len(getattr(req, "body", b"")) > _BODY_LIMIT:
            return self.response({"detail": "请求内容超过 32 KB"}, 413)
        try:
            data = await _login_fields(req)
            username, password = data.get("username", []), data.get("password", [])
            if (len(username) != 1 or len(password) != 1
                    or not isinstance(username[0], str) or not isinstance(password[0], str)):
                raise ValueError
            valid = hmac.compare_digest(username[0].encode(), LOGIN_USER.encode()) and hmac.compare_digest(password[0].encode(), cfg["mp_api_key"].encode())
        except (ValueError, UnicodeError, MultiPartException, RecursionError):
            valid = False
        if not valid:
            return self.response({"detail": "用户名或密码无效"}, 401)
        return self.response({"access_token": _issue_token(cfg["mp_api_key"]), "token_type": "bearer",
                              "user_id": 1, "user_name": LOGIN_USER, "super_user": False,
                              "level": 1, "avatar": None, "permissions": {}, "wizard": False})

    async def _nf(self, cfg, method, path, body=None):
        base, key = cfg.get("api_url"), cfg.get("api_key")
        if not isinstance(base, str) or not isinstance(key, str) or not key.strip():
            raise NextFindError("NextFind 连接尚未配置")
        base, key = base.strip(), key.strip()
        parsed = urlsplit(base)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise NextFindError("NextFind 服务地址格式无效")
        options = {"headers": {"X-API-Key": key}, "timeout": 20, "follow_redirects": False}
        if body is not None:
            options["json"] = body
        async with self.ctx.http.stream(method, base.rstrip("/") + path, **options) as response:
            NextFindClient._check(response, path)
            content = bytearray()
            async for chunk in response.aiter_bytes():
                if len(content) + len(chunk) > _RESPONSE_LIMIT:
                    raise NextFindError("NextFind 响应过大")
                content.extend(chunk)
        try:
            return json.loads(content)
        except (ValueError, UnicodeDecodeError):
            raise NextFindError("NextFind 返回了无效响应") from None

    async def _rows(self, cfg, *, register_routes=True):
        payload = await self._nf(cfg, "GET", "/subscriptions")
        rows = NextFindClient._list_data(payload, "/subscriptions")
        result = []
        seen = set()
        for row in rows:
            try:
                identifiers = [row[key] for key in ("tmdb_id", "tmdbId", "tmdbid")
                               if row.get(key) not in (None, "")]
                if row.get("media_source") in ("tmdb", "themoviedb") and row.get("media_id") not in (None, ""):
                    identifiers.append(row["media_id"])
                identities = {_identity(value) for value in identifiers}
                if len(identities) != 1:
                    raise ValueError("订阅身份缺失或冲突")
                tmdb_id = identities.pop()
                types = {_media_type(row[key]) for key in ("media_type", "mediaType", "raw_type", "type")
                         if row.get(key) not in (None, "")}
                if len(types) != 1:
                    raise ValueError("订阅媒体类型缺失或冲突")
                media_type = types.pop()
            except ValueError:
                raise NextFindError("NextFind 订阅列表包含无法核对的作品") from None
            identity = media_type, tmdb_id
            if identity in seen:
                continue
            seen.add(identity)
            name = row.get("title") or row.get("name") or ""
            result.append({**_SUBSCRIBE_DEFAULTS, "sites": [], "filter_groups": [],
                           "id": _subscription_id(tmdb_id, media_type),
                           "name": name if isinstance(name, str) else "",
                           "tmdbid": int(tmdb_id), "type": "电影" if media_type == "movie" else "电视剧",
                           "media_source": "themoviedb", "media_id": tmdb_id,
                           "year": row["year"] if isinstance(row.get("year"), str) else None,
                           "poster": row["poster"] if isinstance(row.get("poster"), str) else None,
                           "season": None, "state": "R"})
        if register_routes:
            self._register_rows(result)
        return result

    async def subscription_item(self, req, *, sid=None, tmdb_id=None):
        cfg = self.config()
        rejected = self._authorized(req, cfg)
        if rejected is not None:
            return self.response({"success": False, "message": json.loads(rejected.body)["detail"], "data": None}, rejected.status_code)
        method = str(getattr(req, "method", "")).upper()
        if method not in ("GET", "DELETE"):
            return self.response({"success": False, "message": "请求方法不支持", "data": None}, 405)
        body = getattr(req, "body", b"")
        if len(body) > _BODY_LIMIT:
            return self.response({"success": False, "message": "请求内容超过 32 KB", "data": None}, 413)
        query = getattr(req, "query", {}) or {}
        if body.strip() or set(query) - {"apikey", "token", "season"}:
            return self.response({"success": False, "message": "请通过订阅路径和可选季号指定作品，不支持其他筛选或请求体", "data": None}, 422)
        season = query.get("season")
        if "season" in query:
            if not isinstance(season, str) or not re.fullmatch(r"[0-9]{1,4}", season):
                return self.response({"success": False, "message": "季号格式无效", "data": None}, 422)
            season = int(season)
        try:
            async with asyncio.timeout(_TIMEOUT):
                async with self._mutation_lock:
                    # A historical route is not evidence of an active subscription.
                    # Do not register newly seen types during this identity check.
                    rows = await self._rows(cfg, register_routes=False)
                    matches = [row for row in rows if (row["id"] == sid if sid is not None
                                                       else str(row["tmdbid"]) == tmdb_id)]
                    if tmdb_id is not None and (len(matches) > 1 or len(self._media_types.get(tmdb_id, ())) != 1
                            or matches and _media_type(matches[0]["type"]) not in self._media_types[tmdb_id]):
                        return self.response({"success": False, "message": "TMDB 编号对应的媒体类型不明确，请使用订阅列表中的 ID 操作", "data": None}, 409)
                    if matches:
                        media_type = _media_type(matches[0]["type"])
                    elif sid is not None:
                        media_type = "tv" if sid % 2 else "movie"
                    else:
                        media_type = next(iter(self._media_types[tmdb_id]))
                    if season is not None:
                        if media_type == "movie" and season != 0:
                            return self.response({"success": False, "message": "电影不能指定季号", "data": None}, 422)
                        if media_type == "tv" and cfg.get("mp_whole_series") is not True:
                            return self.response({"success": False, "message": "NextFind 不支持单季操作；请由管理员明确允许转为整部剧订阅或取消", "data": None}, 422)
                    if method == "GET":
                        return self.response(matches[0] if matches else dict(_SUBSCRIBE_DEFAULTS))
                    if not matches:
                        return self.response({"success": True, "message": "NextFind 已无该作品订阅", "data": None})
                    item = matches[0]
                    body = {"tmdb_id": str(item["tmdbid"]), "media_type": media_type}
                    payload = await self._nf(cfg, "POST", "/subscriptions/remove", body)
                    ok, _ = NextFindClient("", cfg["api_key"])._mutation_result(payload, "/subscriptions/remove")
                    if not ok:
                        return self.response({"success": False, "message": "NextFind 未接受取消订阅", "data": None})
                    remaining = await self._rows(cfg, register_routes=False)
                    if any(row["id"] == item["id"] for row in remaining):
                        return self.response({"success": False, "message": "NextFind 尚未确认订阅已移除，请稍后重试", "data": None})
                    self.ctx.log.info("[MoviePilot 接口] 订阅移除已由 NextFind 确认：%s TMDB %s", media_type, body["tmdb_id"])
                    message = ("已取消 NextFind 整部剧订阅，媒体文件未删除" if media_type == "tv"
                               else "已取消 NextFind 订阅，媒体文件未删除")
                    return self.response({"success": True, "message": message, "data": None})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return self._failure(exc, cfg)

    def _failure(self, exc, cfg):
        # Neither client input nor upstream messages/URLs enter logs/responses.
        self.ctx.log.warning("[MoviePilot 接口] NextFind 请求失败（%s）", type(exc).__name__)
        return self.response({"success": False, "message": "NextFind 请求失败，请查看插件日志", "data": None}, 502)

    async def list_subscriptions(self, req):
        return await self.subscribe(req, list_only=True)

    async def subscribe(self, req, *, list_only=False):
        cfg = self.config()
        rejected = self._authorized(req, cfg)
        if rejected is not None:
            return rejected
        method = str(getattr(req, "method", "")).upper()
        if method not in (("GET",) if list_only else ("GET", "POST")):
            return self.response({"detail": "请求方法不支持"}, 405)
        if len(getattr(req, "body", b"")) > _BODY_LIMIT:
            return self.response({"detail": "请求内容超过 32 KB"}, 413)
        if method == "GET":
            try:
                async with asyncio.timeout(_TIMEOUT):
                    return self.response(await self._rows(cfg))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return self._failure(exc, cfg)
        payload = req.json
        # Forward 1.3.19 probes POST /subscribe/ with this exact invalid ID.
        # A MoviePilot result envelope confirms the route; success=False
        # honestly reports that no subscription was created by the probe.
        if payload == {"tmdbid": "-1"}:
            try:
                async with asyncio.timeout(_TIMEOUT):
                    await self._rows(cfg)
                return self.response({"success": False,
                                      "message": "连接正常，测试请求不会新增订阅", "data": None})
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return self._failure(exc, cfg)
        try:
            item = parse_subscription(payload, allow_whole_series=cfg.get("mp_whole_series") is True)
        except ValueError as exc:
            return self.response({"detail": str(exc)}, 422)
        try:
            async with asyncio.timeout(_TIMEOUT):
                async with self._mutation_lock:
                    rows = await self._rows(cfg)
                    sid = _subscription_id(item["tmdb_id"], item["media_type"])
                    if any(row["id"] == sid for row in rows):
                        return self.response({"success": True, "message": "NextFind 已订阅该作品", "data": {"id": sid}})
                    body = {key: item[key] for key in ("tmdb_id", "media_type", "title")}
                    if self._registered and sid not in self._route_ids and len(self._route_ids) >= _ROUTE_LIMIT:
                        raise NextFindError("兼容接口订阅路由已达上限，请重载插件")
                    payload = await self._nf(cfg, "POST", "/subscriptions/add", body)
                    ok, _ = NextFindClient("", cfg["api_key"])._mutation_result(payload, "/subscriptions/add")
                    if not ok:
                        return self.response({"success": False, "message": "NextFind 未接受该订阅", "data": None})
                    self._register_rows([{"id": sid, "tmdbid": int(item["tmdb_id"]), "type": item["media_type"]}])
                    self.ctx.log.info("[MoviePilot 接口] 订阅已由 NextFind 确认：%s TMDB %s", item["media_type"], item["tmdb_id"])
                    return self.response({"success": True, "message": "已向 NextFind 添加整部作品订阅", "data": {"id": sid}})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return self._failure(exc, cfg)
