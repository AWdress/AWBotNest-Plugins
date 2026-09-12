"""药丸签到：AWBotNest V2 原生实现。"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any, Dict

import requests


__plugin__ = {
    "name": "药丸签到",
    "id": "invites_signin",
    "version": "0.0.1",
    "author": "AWdress",
    "description": "invites.fun 药丸论坛自动签到，支持 Cookie 保活、立即执行、定时签到和历史记录。",
    "icon": "https://raw.githubusercontent.com/thsrite/MoviePilot-Plugins/main/icons/invites.png",
    "changelog": "v0.0.1 首次发布\n- 移植药丸论坛签到、连续签到天数与药丸余额记录\n- 使用 AWBotNest V2 原生定时、异步存储、动作和生命周期接口\n- 保留每小时 Cookie 保活，并提供可见的最近运行状态\n- 签到结果统一使用平台富文本表格通知",
    "scope": "standalone",
    "plugin_api_version": 2,
    "tags": ["药丸论坛", "自动签到", "Cookie保活"],
    "default_enabled": False,
    "requirements": ["requests>=2.28"],
    "resources": {
        "timeout_seconds": 180,
        "max_concurrency": 1,
        "max_background_tasks": 2,
    },
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": False, "label": "启用自动签到",
            "section": "功能开关", "cols": 4, "order": 1,
        },
        "notify": {
            "type": "boolean", "default": False, "label": "推送签到结果",
            "section": "功能开关", "cols": 4, "order": 2,
        },
        "keepalive": {
            "type": "boolean", "default": True, "label": "每小时 Cookie 保活",
            "help": "启用自动签到后，每小时整点访问一次论坛。",
            "section": "功能开关", "cols": 4, "order": 3,
        },
        "cookie": {
            "type": "password", "default": "", "label": "药丸 Cookie",
            "help": "登录 https://invites.fun 后复制完整 Cookie。",
            "section": "账号", "cols": 12, "order": 10, "secret": True,
        },
        "cron": {
            "type": "string", "default": "0 9 * * *", "label": "签到 Cron",
            "help": "标准五段 Cron，默认每天 09:00。整点失败时可换成非整点分钟。",
            "section": "定时", "cols": 6, "order": 20,
        },
        "history_days": {
            "type": "number", "default": 30, "label": "历史保留天数",
            "min": 1, "max": 365, "step": 1, "section": "定时", "cols": 3, "order": 21,
        },
        "timeout": {
            "type": "number", "default": 30, "label": "请求超时（秒）",
            "min": 5, "max": 120, "step": 1, "section": "定时", "cols": 3, "order": 22,
        },
        "run_now": {
            "type": "action", "label": "立即签到", "action": "run_now",
            "section": "操作", "cols": 6, "order": 30,
        },
        "last_result": {
            "type": "info", "default": "尚未运行", "label": "最近结果",
            "section": "运行状态", "cols": 12, "order": 40,
        },
        "history": {
            "type": "info", "default": "暂无记录", "label": "最近签到记录",
            "section": "运行状态", "cols": 12, "order": 41,
        },
    },
}


BASE_URL = "https://invites.fun"
USER_API = f"{BASE_URL}/api/users"
SESSION_RE = re.compile(r'"session"\s*:\s*\{[^{}]*?"userId"\s*:\s*(\d+)[^{}]*?"csrfToken"\s*:\s*"([^"]+)"', re.S)
CSRF_RE = re.compile(r'"csrfToken"\s*:\s*"([^"]+)"')
USER_RE = re.compile(r'"userId"\s*:\s*(\d+)')
_run_lock: asyncio.Lock | None = None


def _bounded_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _cron_fields(expression: str) -> Dict[str, str]:
    parts = str(expression or "").strip().split()
    if len(parts) != 5:
        raise ValueError("必须是标准五段 Cron：分 时 日 月 星期")
    return dict(zip(("minute", "hour", "day", "month", "day_of_week"), parts))


def _headers(cookie: str) -> Dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookie,
        "Referer": f"{BASE_URL}/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    }


def _message_from_response(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return (response.text or "").strip()[:300]
    errors = body.get("errors") if isinstance(body, dict) else None
    if isinstance(errors, list):
        details = [str(item.get("detail") or item.get("title") or "") for item in errors if isinstance(item, dict)]
        if any(details):
            return "；".join(item for item in details if item)
    if isinstance(body, dict):
        return str(body.get("message") or body.get("msg") or "")
    return ""


def _signin(cookie: str, timeout: int) -> Dict[str, Any]:
    session = requests.Session()
    headers = _headers(cookie)
    try:
        home = session.get(BASE_URL, headers=headers, timeout=timeout)
    except Exception as exc:
        return {"ok": False, "message": f"访问药丸论坛失败：{exc}"}
    if home.status_code != 200:
        return {"ok": False, "message": f"访问药丸论坛失败：HTTP {home.status_code}"}

    match = SESSION_RE.search(home.text or "")
    if match:
        user_id, csrf_token = match.groups()
    else:
        csrf = CSRF_RE.search(home.text or "")
        user = USER_RE.search(home.text or "")
        if not csrf or not user:
            return {"ok": False, "message": "页面中未找到会话信息，站点页面可能已更新"}
        user_id, csrf_token = user.group(1), csrf.group(1)
    if user_id == "0":
        return {"ok": False, "message": "Cookie 已失效或尚未登录"}

    payload = {
        "data": {
            "type": "users",
            "attributes": {"canCheckin": False, "totalContinuousCheckIn": 2},
            "id": user_id,
        }
    }
    request_headers = {
        **headers,
        "Content-Type": "application/json",
        "X-Csrf-Token": csrf_token,
        "X-Http-Method-Override": "PATCH",
    }
    try:
        response = session.post(f"{USER_API}/{user_id}", headers=request_headers, json=payload, timeout=timeout)
    except Exception as exc:
        return {"ok": False, "message": f"签到请求失败：{exc}"}

    if response.status_code != 200:
        detail = _message_from_response(response)
        already = any(word in detail for word in ("已签到", "已经签到", "今日已签"))
        return {
            "ok": already,
            "already": already,
            "message": detail or f"签到失败：HTTP {response.status_code}",
        }
    try:
        body = response.json()
        attributes = body["data"]["attributes"]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"ok": False, "message": f"签到响应结构异常：{exc}"}
    days = attributes.get("totalContinuousCheckIn")
    money = attributes.get("money")
    return {
        "ok": True,
        "already": False,
        "message": "签到成功",
        "days": days,
        "money": money,
    }


def _keepalive(cookie: str, timeout: int) -> Dict[str, Any]:
    try:
        response = requests.get(BASE_URL, headers=_headers(cookie), timeout=timeout)
        if response.status_code != 200:
            return {"ok": False, "message": f"HTTP {response.status_code}"}
        match = SESSION_RE.search(response.text or "")
        valid = bool(match and match.group(1) != "0")
        return {"ok": valid, "message": "Cookie 有效" if valid else "Cookie 已失效"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


async def setup(ctx):
    global _run_lock
    _run_lock = asyncio.Lock()
    scheduled_jobs = []

    async def save_result(result: Dict[str, Any], source: str) -> None:
        now = datetime.now()
        stamp = now.strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "time": stamp,
            "source": source,
            "ok": bool(result.get("ok")),
            "already": bool(result.get("already")),
            "message": str(result.get("message") or ""),
            "days": result.get("days"),
            "money": result.get("money"),
        }
        history = await ctx.storage.get("history", [])
        if not isinstance(history, list):
            history = []
        retain_days = _bounded_int(ctx.config.get("history_days"), 30, 1, 365)
        cutoff = time.time() - retain_days * 86400
        kept = []
        for item in [*history, record]:
            try:
                if datetime.strptime(str(item.get("time")), "%Y-%m-%d %H:%M:%S").timestamp() >= cutoff:
                    kept.append(item)
            except (TypeError, ValueError):
                continue
        kept = kept[-365:]
        await ctx.storage.set("last_result", record)
        await ctx.storage.set("history", kept)
        history_text = "\n".join(
            f"{item['time']} · {'成功' if item.get('ok') else '失败'} · {item.get('message', '')}"
            for item in reversed(kept[-10:])
        )
        ctx.update_config({
            "last_result": f"{stamp} · {result.get('message', '')}",
            "history": history_text or "暂无记录",
        })

    async def run_once(source: str) -> Dict[str, Any]:
        assert _run_lock is not None
        if _run_lock.locked():
            return {"ok": False, "message": "药丸签到任务正在运行"}
        async with _run_lock:
            cookie = str(ctx.config.get("cookie") or "").strip()
            if not cookie:
                result = {"ok": False, "message": "请先配置药丸 Cookie"}
            else:
                timeout = _bounded_int(ctx.config.get("timeout"), 30, 5, 120)
                ctx.log.info("[药丸签到] 开始执行，来源=%s", source)
                result = await asyncio.to_thread(_signin, cookie, timeout)
            await save_result(result, source)
            if ctx.config.get("notify", False):
                rows = [{
                    "任务": "药丸签到",
                    "状态": "今日已签" if result.get("already") else ("成功" if result.get("ok") else "失败"),
                    "连续签到": result.get("days") if result.get("days") is not None else "-",
                    "剩余药丸": result.get("money") if result.get("money") is not None else "-",
                    "详情": result.get("message", ""),
                }]
                try:
                    await asyncio.wait_for(ctx.notify(rows, category="药丸签到"), timeout=30)
                except Exception as exc:
                    ctx.log.warning("[药丸签到] 通知发送失败：%r", exc)
            (ctx.log.info if result.get("ok") else ctx.log.error)("[药丸签到] %s", result.get("message"))
            return result

    async def keepalive() -> Dict[str, Any]:
        cookie = str(ctx.config.get("cookie") or "").strip()
        if not cookie:
            return {"ok": False, "message": "未配置 Cookie"}
        result = await asyncio.to_thread(
            _keepalive,
            cookie,
            _bounded_int(ctx.config.get("timeout"), 30, 5, 120),
        )
        if result.get("ok"):
            ctx.log.info("[药丸签到] Cookie 保活成功")
        else:
            ctx.log.warning("[药丸签到] Cookie 保活失败：%s", result.get("message"))
        return result

    @ctx.action("run_now")
    async def run_now():
        return await run_once("手动")

    @ctx.on_api("/run", methods=["POST"])
    async def api_run(request):
        return await run_once("API")

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(request):
        return {
            "running": bool(_run_lock and _run_lock.locked()),
            "last_result": await ctx.storage.get("last_result", None),
            "history": (await ctx.storage.get("history", []))[-30:],
        }

    if ctx.config.get("enabled", False):
        try:
            fields = _cron_fields(ctx.config.get("cron") or "0 9 * * *")
            scheduled_jobs.append(ctx.schedule(lambda: run_once("定时"), "cron", id="药丸签到·定时", **fields))
            ctx.log.info("[药丸签到] 定时任务已启用：%s", ctx.config.get("cron") or "0 9 * * *")
        except ValueError as exc:
            ctx.log.error("[药丸签到] Cron 配置无效：%s", exc)
        if ctx.config.get("keepalive", True):
            scheduled_jobs.append(ctx.schedule(keepalive, "cron", minute="0", id="药丸签到·Cookie保活"))
            ctx.log.info("[药丸签到] Cookie 保活已启用：每小时整点")

    async def cleanup():
        for job in scheduled_jobs:
            try:
                if hasattr(job, "cancel"):
                    job.cancel()
            except Exception:
                pass

    ctx.add_cleanup(cleanup)


async def teardown(ctx):
    ctx.log.info("[药丸签到] 插件已停用")
