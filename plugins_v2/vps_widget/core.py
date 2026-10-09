"""Platform-native list updates and authenticated read-only Widget delivery."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlsplit, urlunsplit

from starlette.responses import JSONResponse, Response

from .collectors import collect
from .tmdb import Resolver
from .transport import FetchError, Transport, safe_error
from .widget import build_widget


SOURCES = {
    "guduo": "骨朵", "douban": "豆瓣", "mgtv": "芒果 TV", "theater": "剧场片单",
    "bangumi": "Bangumi", "tmdb": "TMDB", "bili": "B站", "mal": "MyAnimeList",
    "anilist": "AniList", "trakt": "Trakt",
}
DEFAULTS = {"tmdb_key": "", "trakt_client_id": "", "sources": list(SOURCES),
            "auto_update": False, "update_time": "17:00", "category_limit": 30,
            "public_enabled": False, "public_base_url": "", "notify_results": False}


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_base_url(value):
    value = str(value).strip()
    if not value:
        return ""
    if any(ord(c) < 32 or c.isspace() for c in value) or "\\" in value:
        raise ValueError("平台访问地址不能包含空白或反斜杠")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise ValueError("平台访问地址格式无效") from None
    if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment
            or any(c in parts.path for c in {'"', "'", '<', '>'})
            or any(x in {"..", "."} for x in parts.path.split("/"))):
        raise ValueError("请填写 http(s) 平台地址，不含密码、查询参数或 /api 路径")
    if any(segment == "api" for segment in parts.path.split("/")):
        raise ValueError("填写平台访问地址即可，不要包含 /api 路径")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("平台访问端口无效")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def config_values(saved):
    if not isinstance(saved, dict):
        raise ValueError("插件配置格式无效")
    cfg = {key: saved.get(key) if saved.get(key) is not None else value for key, value in DEFAULTS.items()}
    for key in ("auto_update", "public_enabled", "notify_results"):
        if not isinstance(cfg[key], bool):
            raise ValueError("开关配置格式无效")
    if not isinstance(cfg["sources"], list) or any(not isinstance(s, str) or s not in SOURCES for s in cfg["sources"]):
        raise ValueError("榜单来源配置无效")
    cfg["sources"] = list(dict.fromkeys(cfg["sources"]))
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(cfg["update_time"])):
        raise ValueError("更新时间应为 00:00～23:59")
    if isinstance(cfg["category_limit"], bool):
        raise ValueError("每分类条数应为 10～100 的整数")
    try:
        limit = int(cfg["category_limit"])
    except (TypeError, ValueError):
        raise ValueError("每分类条数应为 10～100 的整数") from None
    if not 10 <= limit <= 100 or limit != cfg["category_limit"]:
        raise ValueError("每分类条数应为 10～100 的整数")
    cfg["category_limit"] = limit
    for key in ("tmdb_key", "trakt_client_id"):
        if not isinstance(cfg[key], str) or len(cfg[key]) > 2048 or any(ord(c) < 32 for c in cfg[key]):
            raise ValueError("密钥格式无效")
        cfg[key] = cfg[key].strip()
    cfg["public_base_url"] = validate_base_url(cfg["public_base_url"])
    if cfg["public_enabled"] and not cfg["public_base_url"]:
        raise ValueError("开启客户端读取前，请填写平台访问地址")
    return cfg


def count_items(data):
    if isinstance(data, list):
        return sum(isinstance(item, dict) and bool(item.get("tmdbId")) for item in data)
    if isinstance(data, dict):
        return sum(count_items(value) for value in data.values())
    return 0


class Service:
    def __init__(self, ctx):
        self.ctx = ctx
        self.cfg = config_values(ctx.config)
        self.records = {}
        self.states = {s: {"state": "empty", "count": 0} for s in SOURCES}
        self.token = ""
        self.task = None
        self.lock = asyncio.Lock()
        self.closed = False
        self.current = ""
        self.progress = {"done": 0, "total": 0, "matched": 0, "checked": 0}

    async def setup(self):
        self.token = await self.ctx.storage.get("read_token", "")
        if not isinstance(self.token, str) or len(self.token) < 32:
            self.token = secrets.token_urlsafe(32)
            await self.ctx.storage.set("read_token", self.token)
        for source in SOURCES:
            record = await self.ctx.storage.get("cache:" + source, {})
            if isinstance(record, dict) and isinstance(record.get("data"), dict):
                self.records[source] = record
                self.states[source] = {"state": "cached", "count": count_items(record["data"]),
                                       "last_success": record.get("updated", ""),
                                       "unmatched": record.get("unmatched", 0)}
            state = await self.ctx.storage.get("state:" + source, {})
            if isinstance(state, dict) and state:
                self.states[source].update(state)
                if self.states[source].get("state") == "running":
                    self.states[source].update(state="cancelled", error="上次更新已中断，保留原有榜单")
                self.states[source]["count"] = count_items(self.records.get(source, {}).get("data", {}))
        self.ctx.on_api("status", self.status_api, methods=["GET"])
        self.ctx.on_api("update", self.update_api, methods=["POST"])
        self.ctx.on_api("preview", self.preview_api, methods=["GET"])
        self.ctx.on_api("widget", self.widget_api, methods=["GET"])
        self.ctx.on_api("cancel", self.cancel_api, methods=["POST"])
        self.ctx.on_api("rotate-token", self.rotate_api, methods=["POST"])
        self.ctx.on_webhook("widget.js", self.public_widget)
        for source in SOURCES:
            async def handler(request, source=source):
                return await self.public_data(request, source)
            self.ctx.on_webhook("data/%s.json" % source, handler)
        if self.cfg["auto_update"]:
            hour, minute = map(int, self.cfg["update_time"].split(":"))
            self.ctx.schedule_cron("影视榜单更新", self.scheduled, hour=hour, minute=minute,
                                   timezone="Asia/Shanghai")
        self.ctx.log.info("榜单服务已就绪，自动更新%s", "开启" if self.cfg["auto_update"] else "关闭")

    async def stop(self):
        self.closed = True
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def snapshot(self):
        return {"ok": True, "running": bool(self.task and not self.task.done()), "current": self.current,
                "progress": dict(self.progress), "auto_update": self.cfg["auto_update"],
                "update_time": self.cfg["update_time"], "public_enabled": self.cfg["public_enabled"],
                "sources": [{"id": source, "name": name, "enabled": source in self.cfg["sources"],
                             **self.states[source]} for source, name in SOURCES.items()]}

    async def status_api(self, request):
        return self.snapshot()

    async def start(self, source="all", origin="手动"):
        async with self.lock:
            if self.closed:
                return {"ok": False, "message": "插件已停用"}
            if self.task and not self.task.done():
                return {"ok": False, "message": "已有更新正在运行，请等待完成或停止更新"}
            sources = self.cfg["sources"] if source == "all" else [source]
            if not sources or any(s not in self.cfg["sources"] for s in sources):
                return {"ok": False, "message": "请先选择榜单来源并保存配置"}
            if not self.cfg["tmdb_key"] or self.cfg["tmdb_key"] == "********":
                return {"ok": False, "message": "请先填写 TMDB 密钥并保存，才能生成可用的影视榜单"}
            self.progress = {"done": 0, "total": len(sources), "matched": 0, "checked": 0}
            self.task = self.ctx.create_task(self._run(list(sources), origin), name="vps-widget-update")
            return {"ok": True, "message": "已开始更新，可在榜单状态查看进度；离开配置页不会停止任务"}

    async def scheduled(self):
        return await self.start(origin="定时")

    async def update_api(self, request):
        if len(request.body) > 2048 or not isinstance(request.json, dict):
            return JSONResponse({"ok": False, "message": "更新参数格式无效"}, status_code=400)
        source = request.json.get("source", "all")
        if not isinstance(source, str) or (source != "all" and source not in SOURCES):
            return JSONResponse({"ok": False, "message": "未知榜单来源"}, status_code=400)
        return await self.start(source)

    async def cancel_api(self, request):
        async with self.lock:
            if self.task and not self.task.done():
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
                return {"ok": True, "message": "已停止更新，已完成的来源与原有缓存均保留"}
        return {"ok": True, "message": "当前没有正在运行的更新"}

    async def _state(self, source, **state):
        self.states[source].update(state)
        await self.ctx.storage.set("state:" + source, self.states[source])

    async def _run(self, sources, origin):
        resolver = Resolver(Transport(self.ctx.http, self.cfg["tmdb_key"]), self.ctx.storage)
        success = failures = skipped = 0
        try:
            await resolver.load()
            async with asyncio.timeout(1800):
                for source in sources:
                    self.current = source
                    if source == "trakt" and not self.cfg["trakt_client_id"]:
                        await self._state(source, state="skipped", error="未配置 Trakt Client ID，保留原有榜单")
                        skipped += 1
                        self.progress["done"] += 1
                        continue
                    await self._state(source, state="running", error="", last_attempt=now())
                    try:
                        async with asyncio.timeout(360):
                            data, unmatched = await self._update_source(source, resolver)
                        record = {"data": data, "updated": now(), "unmatched": unmatched}
                        if len(json.dumps(record, ensure_ascii=False).encode("utf-8")) > 8 * 1024 * 1024:
                            raise FetchError("榜单数据超过 8 MB，请减少每分类条数后重试")
                        # Publish only after the complete source has been written successfully.
                        await self.ctx.storage.set("cache:" + source, record)
                        self.records[source] = record
                        await self._state(source, state="success", error="", count=count_items(data),
                                          last_success=record["updated"], unmatched=unmatched)
                        success += 1
                        self.ctx.log.info("%s 更新完成：%d 条，未匹配 %d 条", SOURCES[source], count_items(data), unmatched)
                    except Exception as error:
                        message = safe_error(error)
                        await self._state(source, state="failed", error=message)
                        failures += 1
                        self.ctx.log.warning("%s 更新失败，保留原榜单：%s", SOURCES[source], message)
                    await resolver.save()
                    self.progress["done"] += 1
            self.ctx.log.info("榜单更新完成（%s）：成功 %d，失败 %d，未配置 %d", origin, success, failures, skipped)
            if self.cfg["notify_results"] and not self.closed:
                try:
                    await self.ctx.notify("影视榜单更新完成：成功 %d，失败 %d，未配置 %d。详情见 VPS-Widget 榜单状态。"
                                          % (success, failures, skipped), category="影视榜单")
                except Exception:
                    self.ctx.log.warning("榜单更新通知未送达，请检查平台通知渠道")
        except asyncio.CancelledError:
            if self.current and self.states[self.current].get("state") == "running":
                await self._state(self.current, state="cancelled", error="更新已停止，保留原有榜单")
            raise
        except Exception as error:
            if self.current:
                await self._state(self.current, state="failed", error=safe_error(error))
            self.ctx.log.warning("榜单更新已结束：%s", safe_error(error))
        finally:
            self.current = ""

    async def _update_source(self, source, resolver):
        raw = await collect(source, resolver.transport, limit=self.cfg["category_limit"],
                            trakt_client_id=self.cfg["trakt_client_id"])
        slots = []
        def walk(value):
            if isinstance(value, list):
                slots.append(value)
            elif isinstance(value, dict):
                for nested in value.values():
                    walk(nested)
        walk(raw)
        jobs = [(slot, index, item) for slot in slots for index, item in enumerate(slot)
                if isinstance(item, dict) and item.get("title")]
        if not jobs:
            raise FetchError("没有抓取到条目，保留原有榜单；源站可能改变了接口")
        semaphore = asyncio.Semaphore(4)
        output = {}
        async def match(index, item):
            async with semaphore:
                output[index] = await resolver.resolve(item)
                self.progress["checked"] += 1
                self.progress["matched"] += bool(output[index])
        # Structured concurrency: source cancellation cancels every in-flight lookup.
        async with asyncio.TaskGroup() as group:
            for index, (_, _, item) in enumerate(jobs):
                group.create_task(match(index, item))
        unmatched = sum(value is None for value in output.values())
        for index, (slot, offset, _) in enumerate(jobs):
            slot[offset] = output[index]
        for slot in slots:
            seen = set()
            cleaned = []
            for item in slot:
                if isinstance(item, dict) and item.get("tmdbId"):
                    key = (item["mediaType"], item["tmdbId"])
                    if key not in seen:
                        cleaned.append(item)
                        seen.add(key)
            slot[:] = cleaned
        if count_items(raw) == 0:
            raise FetchError("抓取条目未匹配到有效 TMDB 海报，保留原有榜单")
        if source == "theater":
            today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            for value in raw.values():
                if isinstance(value, dict) and "aired" in value:
                    items = value.get("aired", []) + value.get("upcoming", [])
                    value["aired"] = [item for item in items if not item.get("releaseDate") or item["releaseDate"] <= today]
                    value["upcoming"] = [item for item in items if item.get("releaseDate") and item["releaseDate"] > today]
                    value["totalItems"] = len(items)
        raw["last_updated"] = now()
        return raw, unmatched

    async def preview_api(self, request):
        source = request.query.get("source", "guduo")
        if source not in SOURCES:
            return JSONResponse({"ok": False, "message": "未知榜单来源"}, status_code=400)
        record = self.records.get(source)
        return {"ok": True, "source": source, "data": record.get("data", {}) if record else {},
                "updated": record.get("updated", "") if record else ""}

    async def widget_api(self, request):
        base = self.cfg["public_base_url"]
        if not base:
            return {"ok": False, "message": "请在配置中填写平台访问地址并保存"}
        return {"ok": True, "enabled": self.cfg["public_enabled"],
                "url": base + "/api/plugin/vps_widget/widget.js?token=" + quote(self.token, safe=""),
                "message": "地址内含只读密钥，不要公开分享。"}

    async def rotate_api(self, request):
        if len(request.body) > 2048 or not isinstance(request.json, dict) or request.json.get("confirmed") is not True:
            return JSONResponse({"ok": False, "message": "请先确认：更换后所有旧 Widget 地址都会失效"}, status_code=400)
        token = secrets.token_urlsafe(32)
        await self.ctx.storage.set("read_token", token)
        self.token = token
        return {"ok": True, "message": "只读密钥已更换，请重新复制 Widget 地址并导入客户端"}

    def authorize(self, request):
        if request.method != "GET":
            return JSONResponse({"ok": False, "message": "只允许读取榜单"}, status_code=405, headers={"Allow": "GET"})
        if len(request.body) > 2048:
            return JSONResponse({"ok": False}, status_code=413)
        supplied = request.query.get("token", "")
        if (self.closed or not self.cfg["public_enabled"] or not isinstance(supplied, str)
                or len(supplied) > 256 or not hmac.compare_digest(supplied.encode("utf-8"), self.token.encode("utf-8"))):
            return JSONResponse({"ok": False, "message": "读取服务未开启或访问密钥无效"}, status_code=403,
                                headers={"Cache-Control": "no-store"})
        return None

    def serve(self, request, body, media_type):
        etag = '"' + hashlib.sha256(body).hexdigest() + '"'
        headers = {"ETag": etag, "Cache-Control": "private, max-age=60", "Access-Control-Allow-Origin": "*",
                   "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type=media_type, headers=headers)

    async def public_widget(self, request):
        rejected = self.authorize(request)
        if rejected is not None:
            return rejected
        base = self.cfg["public_base_url"]
        if not base:
            return JSONResponse({"ok": False, "message": "平台访问地址未设置"}, status_code=503)
        return self.serve(request, build_widget(base + "/api/plugin/vps_widget", self.token).encode("utf-8"),
                          "application/javascript")

    async def public_data(self, request, source):
        rejected = self.authorize(request)
        if rejected is not None:
            return rejected
        if source not in self.cfg["sources"]:
            return JSONResponse({"ok": False, "message": "这个榜单来源未启用"}, status_code=404)
        record = self.records.get(source)
        if not record:
            return JSONResponse({"ok": False, "message": "这个来源尚无榜单，请先在插件中更新"}, status_code=503)
        body = json.dumps(record["data"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self.serve(request, body, "application/json")
