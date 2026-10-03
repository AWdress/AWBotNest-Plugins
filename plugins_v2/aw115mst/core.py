"""AWBotNest V2 lifecycle, administrator APIs and optional Telegram commands."""
from __future__ import annotations

import asyncio
import base64
import re
import secrets
import time

from ._config import normalize
from ._engine import Engine


async def _body(request):
    if isinstance(request, dict):
        return request
    value = request.json
    if callable(value):
        value = value()
    if hasattr(value, "__await__"):
        value = await value
    return value if isinstance(value, dict) else {}


class Plugin:
    def __init__(self, ctx):
        self.ctx = ctx
        self.engine = Engine(ctx)
        self.qr = None
        self.qr_lock = asyncio.Lock()

    async def qr_start(self, request):
        from ._p115 import P115Adapter
        body = await _body(request)
        config = normalize(self.ctx.config)
        app = body.get("app", config["qr_app"])
        normalize({"qr_app": app})
        async with self.qr_lock:
            if self.qr is not None:
                await self.qr["adapter"].close()
            adapter = P115Adapter(self.ctx, "", timeout=config["request_timeout"])
            result = await adapter.start_qr(app)
            session = secrets.token_urlsafe(24)
            expires = min(int(result.get("expires_in", 120)), 180)
            self.qr = {"id": session, "adapter": adapter, "token": result["session_id"],
                       "expires": time.monotonic() + expires, "confirmed": False}
            return {"ok": True, "session": session, "expires_in": expires,
                    "image": "data:image/png;base64," + base64.b64encode(result["qr_png"]).decode("ascii")}

    async def qr_poll(self, request):
        body = await _body(request)
        async with self.qr_lock:
            session = self.qr
            if not session or not secrets.compare_digest(str(body.get("session", "")), session["id"]):
                return {"ok": False, "status": "expired", "message": "二维码会话无效，请重新获取"}
            if session["confirmed"]:
                return {"ok": True, "status": "confirmed", "message": "登录成功，Cookie 已保存"}
            if time.monotonic() > session["expires"]:
                await session["adapter"].close()
                self.qr = None
                return {"ok": True, "status": "expired", "message": "二维码已过期"}
            result = await session["adapter"].poll_qr(session["token"])
            status = result.get("status", 0)
            if result.get("confirmed") or status == 2:
                cookie = await session["adapter"].finalize_qr(session["token"])
                if not cookie:
                    raise ValueError("未取得有效登录 Cookie")
                self.ctx.update_config({"cookie": cookie})
                session["confirmed"] = True
                return {"ok": True, "status": "confirmed", "message": "登录成功，Cookie 已保存"}
            state = {0: "waiting", 1: "scanned", -1: "expired", -2: "expired"}.get(status, "waiting")
            return {"ok": True, "status": state,
                    "message": {"waiting": "等待扫码", "scanned": "已扫码，请在手机上确认", "expired": "二维码已过期或取消"}[state]}

    async def login_test(self, request=None):
        adapter = await self.engine.adapter(normalize(self.ctx.config))
        try:
            info = await adapter.login_info()
            return {"ok": bool(info.get("success")), "message": "115 登录有效" if info.get("success") else "115 登录已失效"}
        finally:
            await adapter.close()

    async def api(self, handler, request=None):
        try:
            return await handler(request)
        except (ValueError, RuntimeError) as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:
            return {"ok": False, "message": f"操作失败（{type(exc).__name__}），请检查网络或登录状态"}

    async def run(self, request):
        return await self.engine.start((await _body(request)).get("mode", "scan"))

    async def stop(self, request=None):
        return await self.engine.stop()

    async def status(self, request=None):
        return await self.engine.status()

    async def clear(self, request):
        if (await _body(request)).get("confirm") is not True:
            return {"ok": False, "message": "请先确认清空处理记录"}
        return await self.engine.clear()

    async def telegram(self, event):
        config = normalize(self.ctx.config)
        allowed = {int(item) for item in re.split(r"[\s,，]+", config["telegram_admin_ids"].strip()) if item.isdigit()}
        if getattr(event, "sender_id", None) not in allowed or not getattr(event, "is_private", False):
            return
        text = (getattr(event, "raw_text", "") or "").split()[0].split("@")[0]
        if text == "/mst_status":
            status = await self.engine.status()
            message = status["message"] + (f"\n{status['progress']}% · {status['current']}" if status["running"] else "")
        elif text == "/mst_stop":
            message = (await self.engine.stop())["message"]
        else:
            mode = "recheck" if text == "/mst_recheck" else "scan"
            message = (await self.engine.start(mode, "Telegram"))["message"]
        await event.respond(message, parse_mode=None)

    async def setup(self):
        config = normalize(self.ctx.config)
        await self.engine.recover()
        for path, handler, methods in (
            ("status", self.status, ["GET"]), ("run", self.run, ["POST"]),
            ("stop", self.stop, ["POST"]), ("clear_records", self.clear, ["POST"]),
            ("login_test", self.login_test, ["POST"]), ("qr/start", self.qr_start, ["POST"]),
            ("qr/poll", self.qr_poll, ["POST"]),
        ):
            async def guarded(request, handler=handler):
                return await self.api(handler, request)
            self.ctx.on_api(path, guarded, methods=methods)
        self.ctx.action("scan", lambda: self.engine.start("scan"))
        self.ctx.action("recheck", lambda: self.engine.start("recheck"))
        self.ctx.action("stop", self.engine.stop)
        self.ctx.action("status", self.engine.status)
        if config["watch_enabled"]:
            self.ctx.schedule_interval("文件巡检", self.engine.watch, seconds=config["watch_interval_seconds"])
        if config["schedule_enabled"]:
            async def scheduled():
                mode = "all" if config["recheck_enabled"] else "scan"
                await self.engine.start(mode, "定时")
            self.ctx.schedule_interval("定时检测", scheduled, seconds=config["interval_minutes"] * 60)
        if config["telegram_control"]:
            if not config["telegram_admin_ids"].strip():
                self.ctx.log.warning("Telegram 控制未启动：请填写允许操作的用户 ID")
            elif self.ctx.bot is None:
                self.ctx.log.warning("Telegram 控制未启动：平台 Bot 未连接")
            else:
                self.ctx.on_message(pattern=r"^/mst_(?:scan|recheck|stop|status)(?:@\w+)?(?:\s|$)")(self.telegram)

    async def close(self):
        await self.engine.close()
        async with self.qr_lock:
            if self.qr is not None:
                await self.qr["adapter"].close()
                self.qr = None


async def setup(ctx):
    plugin = Plugin(ctx)
    ctx._aw115mst_plugin = plugin
    await plugin.setup()


async def teardown(ctx):
    plugin = getattr(ctx, "_aw115mst_plugin", None)
    if plugin is not None:
        await plugin.close()
        del ctx._aw115mst_plugin
