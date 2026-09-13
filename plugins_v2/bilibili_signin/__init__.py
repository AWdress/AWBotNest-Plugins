"""B 站每日综合签到：AWBotNest V2 原生实现。"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List

import requests


__plugin__ = {
    "name": "B站每日综合签到",
    "id": "bilibili_signin",
    "version": "0.0.4",
    "author": "AWdress",
    "description": "使用 B 站 Cookie 完成分享、观看心跳、直播、漫画等每日签到并推送账号状态。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/bilibili_signin/logo.png",
    "changelog": "v0.0.1 首次发布\n- 接入分享、观看心跳、直播签到和漫画签到接口\n- 支持多账号 Cookie、定时 Cron、立即执行、硬币/等级/漫读券信息和富文本通知\n- 仅依据 B 站接口 code 与明确重复签到提示判断结果",
    "scope": "standalone",
    "plugin_api_version": 2,
    "tags": ["B站", "每日签到", "Cookie"],
    "default_enabled": False,
    "requirements": ["requests>=2.28"],
    "resources": {"timeout_seconds": 600, "max_concurrency": 1, "max_background_tasks": 2},
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用自动签到", "section": "功能开关", "order": 1},
        "notify": {"type": "boolean", "default": True, "label": "推送签到结果", "section": "功能开关", "order": 2},
        "accounts": {
            "type": "list", "default": [], "label": "B站账号", "item_label": "账号", "secret": True,
            "help": "逐个添加账号；建议使用浏览器无痕窗口登录 B 站后复制 Cookie，避免顶掉日常登录会话；平台默认隐藏并可按需显示。",
            "section": "账号", "cols": 12, "order": 10,
            "fields": {"name": {"type": "string", "label": "账号名称", "default": "B站账号"}, "cookie": {"type": "password", "label": "Cookie"}},
        },
        "share": {"type": "boolean", "default": True, "label": "每日分享签到", "section": "签到项目", "order": 20},
        "heartbeat": {"type": "boolean", "default": True, "label": "每日观看签到", "section": "签到项目", "order": 21},
        "live": {"type": "boolean", "default": True, "label": "直播签到", "section": "签到项目", "order": 22},
        "manga": {"type": "boolean", "default": True, "label": "漫画签到", "section": "签到项目", "order": 23},
        "delay": {"type": "number", "default": 10, "min": 0, "max": 60, "step": 1, "label": "项目间隔（秒）", "help": "项目请求之间的间隔，避免触发接口频率限制。", "section": "签到设置", "order": 30},
        "cron": {"type": "string", "format": "cron", "default": "10 8 * * *", "label": "签到 Cron", "help": "标准五段 Cron，默认每天 08:10。", "section": "签到设置", "order": 31},
        "timeout": {"type": "number", "default": 30, "min": 5, "max": 120, "step": 1, "label": "请求超时（秒）", "section": "签到设置", "order": 32},
        "run_now": {"type": "action", "label": "立即签到", "action": "run_now", "section": "操作", "order": 40},
        "last_result": {"type": "info", "default": "尚未运行", "label": "最近结果", "section": "运行状态", "cols": 12, "order": 50},
        "history": {"type": "info", "default": "暂无记录", "label": "最近签到记录", "section": "运行状态", "cols": 12, "order": 51},
    },
}

__plugin__["changelog"] = "v0.0.4 修复默认配置回填\n- 平台保存空字符串时自动恢复默认 Cron、间隔和请求超时\n- 不覆盖用户明确设置的 false、0 或空账号列表\n\n" + __plugin__["changelog"]

API = "https://api.bilibili.com"
LIVE_SIGN = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign"
MANGA_CLOCKIN = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
MANGA_COUPONS = "https://manga.bilibili.com/twirp/user.v1.User/GetCoupons"
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


def _accounts(raw: Any) -> List[Dict[str, str]]:
    if isinstance(raw, list):
        result = []
        for index, item in enumerate(raw, 1):
            if not isinstance(item, dict):
                continue
            cookie = str(item.get("cookie") or "").strip()
            if cookie:
                result.append({"name": str(item.get("name") or f"账号 {index}").strip(), "cookie": cookie})
        if result:
            return result
    return []


def _json(response: requests.Response) -> dict:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except (ValueError, json.JSONDecodeError):
        return {}


def _message(body: dict, text: str = "") -> str:
    for key in ("message", "msg", "message_text", "error"):  # B 站不同业务接口字段不完全一致
        if body.get(key):
            return str(body[key]).strip()
    return str(text or "").strip()[:180]


def _api_ok(body: dict, text: str = "", allow_duplicate: bool = True) -> bool:
    if body.get("code") == 0:
        return True
    message = _message(body, text).lower()
    if allow_duplicate and any(word in message for word in ("已签到", "已完成", "重复", "duplicate", "already")):
        return True
    return False


def _cookie_jar(raw: str) -> requests.cookies.RequestsCookieJar:
    jar = requests.cookies.RequestsCookieJar()
    for part in str(raw or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.strip().split("=", 1)
        if name:
            jar.set(name.strip(), value.strip(), domain=".bilibili.com", path="/")
    return jar


def _signin_one(account: Dict[str, str], enabled: Dict[str, bool], delay: int, timeout: int, log=None) -> Dict[str, Any]:
    name = account.get("name") or "默认账号"
    session = requests.Session()
    session.cookies.update(_cookie_jar(account.get("cookie", "")))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Origin": "https://www.bilibili.com",
        "Referer": "https://www.bilibili.com/",
    })
    result: Dict[str, Any] = {"name": name, "ok": True, "actions": []}
    try:
        nav = session.get(f"{API}/x/web-interface/nav", timeout=timeout)
        nav_body = _json(nav)
        nav_data = nav_body.get("data") if isinstance(nav_body.get("data"), dict) else {}
        if nav.status_code != 200 or nav_body.get("code") != 0 or nav_data.get("isLogin") is False:
            return {"name": name, "ok": False, "message": "Cookie 已失效或 B 站未登录"}
        result.update({"uid": nav_data.get("mid", "-"), "uname": nav_data.get("uname", name), "level": nav_data.get("level_info", {}).get("current_level", "-"), "coin": nav_data.get("money", "-"), "exp": nav_data.get("level_exp", {}).get("current_exp", "-")})
        csrf = next((c.value for c in session.cookies if c.name == "bili_jct"), "")
        if not csrf and enabled.get("share") or not csrf and enabled.get("heartbeat"):
            return {**result, "ok": False, "message": "Cookie 中缺少 bili_jct，无法完成分享/观看签到"}

        def record(label: str, ok: bool, message: str):
            result["actions"].append({"项目": label, "状态": "已完成" if ok else "失败", "详情": message})
            if log:
                log.info("[B站每日综合签到] [%s] %s：%s（%s）", name, label, "完成" if ok else "失败", message)

        bvid = ""
        if enabled.get("share") or enabled.get("heartbeat"):
            dynamic = session.get(f"{API}/x/web-interface/dynamic/region", params={"pn": 3, "ps": 12, "rid": 129}, timeout=timeout)
            matches = re.findall(r"BV[A-Za-z0-9]{10}", dynamic.text or "")
            bvid = matches[0] if matches else ""
            if not bvid:
                record("分享/观看", False, "未找到可用视频 BV 号")
        if enabled.get("share") and bvid:
            response = session.post(f"{API}/x/web-interface/share/add", data={"bvid": bvid, "csrf": csrf}, timeout=timeout)
            body = _json(response)
            record("分享签到", _api_ok(body, response.text), _message(body, response.text) or f"HTTP {response.status_code}")
            if delay: time.sleep(delay)
        if enabled.get("heartbeat") and bvid:
            response = session.post(f"{API}/x/click-interface/web/heartbeat", data={"bvid": bvid, "csrf": csrf, "played_time": 2}, timeout=timeout)
            body = _json(response)
            record("观看签到", _api_ok(body, response.text), _message(body, response.text) or f"HTTP {response.status_code}")
            if delay: time.sleep(delay)
        if enabled.get("live"):
            response = session.get(LIVE_SIGN, timeout=timeout)
            body = _json(response)
            record("直播签到", _api_ok(body, response.text), _message(body, response.text) or f"HTTP {response.status_code}")
            if delay: time.sleep(delay)
        if enabled.get("manga"):
            response = session.post(MANGA_CLOCKIN, data={"platform": "ios"}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=timeout)
            body = _json(response)
            record("漫画签到", _api_ok(body, response.text), _message(body, response.text) or f"HTTP {response.status_code}")
            if delay: time.sleep(delay)
        if enabled.get("manga"):
            response = session.post(MANGA_COUPONS, json={"notExpired": True, "pageNum": 1, "pageSize": 20, "tabType": 1, "type": 0}, headers={"Content-Type": "application/json; charset=utf-8"}, timeout=timeout)
            body = _json(response)
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            result["manga"] = data.get("total_remain_amount", "-")
        result["ok"] = all(item["状态"] == "已完成" for item in result["actions"])
        result["message"] = "综合签到完成" if result["ok"] else "部分签到失败"
        return result
    except requests.RequestException as exc:
        return {**result, "ok": False, "message": f"网络请求失败：{exc}"}
    except Exception as exc:  # noqa: BLE001
        return {**result, "ok": False, "message": f"签到处理失败：{exc}"}


async def setup(ctx):
    global _run_lock
    defaults = {}
    for key, spec in __plugin__["config_schema"].items():
        if "default" not in spec or spec.get("type") == "action":
            continue
        current = ctx.config.get(key)
        if key not in ctx.config or current is None or (isinstance(current, str) and not current.strip()):
            defaults[key] = spec["default"]
    if defaults:
        ctx.update_config(defaults)
    _run_lock = asyncio.Lock()
    jobs = []

    async def save_results(results: List[Dict[str, Any]], source: str):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = await ctx.storage.get("history", [])
        if not isinstance(history, list): history = []
        history.append({"time": stamp, "source": source, "results": results})
        history = history[-100:]
        await ctx.storage.set("history", history)
        await ctx.storage.set("last_result", {"time": stamp, "source": source, "results": results})
        ok_count = sum(bool(item.get("ok")) for item in results)
        ctx.update_config({"last_result": f"{stamp} · 成功 {ok_count}/{len(results)}", "history": "\n".join(f"{stamp} · {item.get('name', '')} · {item.get('message', '')}" for item in reversed(history[-10:]))})

    async def run_once(source: str):
        assert _run_lock is not None
        if _run_lock.locked(): return {"ok": False, "message": "B站签到任务正在运行"}
        async with _run_lock:
            accounts = _accounts(ctx.config.get("accounts"))
            if not accounts:
                result = {"ok": False, "message": "未配置 B 站 Cookie"}
                await save_results([result], source)
                return result
            enabled = {key: bool(ctx.config.get(key, True)) for key in ("share", "heartbeat", "live", "manga")}
            delay = _bounded_int(ctx.config.get("delay"), 10, 0, 60)
            timeout = _bounded_int(ctx.config.get("timeout"), 30, 5, 120)
            ctx.log.info("[B站每日综合签到] 开始执行，来源=%s，账号=%d", source, len(accounts))
            results = await asyncio.gather(*(asyncio.to_thread(_signin_one, account, enabled, delay, timeout, ctx.log) for account in accounts))
            await save_results(results, source)
            if ctx.config.get("notify", True):
                rows = []
                for item in results:
                    rows.append({"账号": item.get("name", "-"), "状态": "成功" if item.get("ok") else "失败", "等级": item.get("level", "-"), "硬币": item.get("coin", "-"), "漫读券": item.get("manga", "-"), "详情": item.get("message", "")})
                try: await asyncio.wait_for(ctx.notify(rows, category="B站每日综合签到"), timeout=30)
                except Exception as exc: ctx.log.warning("[B站每日综合签到] 通知发送失败：%r", exc)
            ok_count = sum(bool(item.get("ok")) for item in results)
            (ctx.log.info if ok_count == len(results) else ctx.log.warning)("[B站每日综合签到] 完成：成功 %d/%d", ok_count, len(results))
            return {"ok": ok_count == len(results), "results": results, "message": f"成功 {ok_count}/{len(results)}"}

    @ctx.action("run_now")
    async def run_now(): return await run_once("手动")

    @ctx.on_api("/run", methods=["POST"])
    async def api_run(request): return await run_once("API")

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(request): return {"running": bool(_run_lock and _run_lock.locked()), "last_result": await ctx.storage.get("last_result", None), "history": await ctx.storage.get("history", [])}

    if ctx.config.get("enabled", False):
        try:
            jobs.append(ctx.schedule_cron("B站每日综合签到·定时", lambda: run_once("定时"), **_cron_fields(ctx.config.get("cron") or "10 8 * * *")))
            ctx.log.info("[B站每日综合签到] 定时任务已启用：%s", ctx.config.get("cron") or "10 8 * * *")
        except ValueError as exc: ctx.log.error("[B站每日综合签到] Cron 配置无效：%s", exc)

    async def cleanup():
        for job in jobs:
            try:
                if hasattr(job, "cancel"): job.cancel()
            except Exception: pass
    ctx.add_cleanup(cleanup)


async def teardown(ctx):
    ctx.log.info("[B站每日综合签到] 插件已停用")
