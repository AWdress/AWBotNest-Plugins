"""百度贴吧签到：AWBotNest V2 原生实现。"""
from __future__ import annotations

import asyncio
import html
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import unquote

import requests


__plugin__ = {
    "name": "百度贴吧签到",
    "id": "tieba_signin",
    "version": "0.0.2",
    "author": "AWdress",
    "description": "使用百度贴吧 Cookie 自动完成关注贴吧签到，支持多账号、定时执行和结果通知。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/tieba_signin/logo.png",
    "changelog": "v0.0.1 首次发布\n- 根据百度贴吧签到流程接入 Cookie 校验、TBS 获取、关注贴吧扫描和一键签到\n- 支持逐账号配置、定时签到、立即执行、签到统计与历史记录\n- 仅依据贴吧接口返回的签到数量生成结果，不把 HTTP 成功误判为签到成功",
    "scope": "standalone",
    "plugin_api_version": 2,
    "tags": ["百度贴吧", "自动签到", "Cookie"],
    "default_enabled": False,
    "requirements": ["requests>=2.28"],
    "resources": {"timeout_seconds": 900, "max_concurrency": 1, "max_background_tasks": 2},
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用自动签到", "section": "功能开关", "order": 1},
        "notify": {"type": "boolean", "default": True, "label": "推送签到结果", "section": "功能开关", "order": 2},
        "accounts": {
            "type": "list", "default": [], "label": "贴吧账号", "item_label": "账号", "secret": True,
            "help": "逐个添加账号；Cookie 可从浏览器开发者工具复制，平台默认隐藏并可按需显示。",
            "section": "账号", "cols": 12, "order": 10,
            "fields": {
                "name": {"type": "string", "label": "账号名称", "default": "百度账号"},
                "cookie": {"type": "password", "label": "Cookie"},
            },
        },
        "cookie": {
            "type": "password", "default": "", "label": "旧版单账号 Cookie",
            "help": "兼容旧版单 Cookie 配置；新配置请使用上面的逐账号列表。",
            "section": "兼容配置", "order": 90,
        },
        "delay": {"type": "number", "default": 3, "min": 0, "max": 15, "step": 1, "label": "贴吧间隔（秒）", "help": "每个贴吧签到请求之间的间隔，避免触发频率限制。", "section": "签到设置", "order": 20},
        "cron": {"type": "string", "format": "cron", "default": "5 8 * * *", "label": "签到 Cron", "help": "标准五段 Cron，默认每天 08:05。", "section": "签到设置", "order": 21},
        "timeout": {"type": "number", "default": 30, "min": 5, "max": 120, "step": 1, "label": "请求超时（秒）", "section": "签到设置", "order": 22},
        "run_now": {"type": "action", "label": "立即签到", "action": "run_now", "section": "操作", "cols": 6, "order": 30},
        "last_result": {"type": "info", "default": "尚未运行", "label": "最近结果", "section": "运行状态", "cols": 12, "order": 40},
        "history": {"type": "info", "default": "暂无记录", "label": "最近签到记录", "section": "运行状态", "cols": 12, "order": 41},
    },
}

__plugin__["changelog"] = "v0.0.2 更新百度贴吧 Logo\n- 使用用户提供的贴吧官方图标\n\n" + __plugin__["changelog"]


BASE_URL = "https://tieba.baidu.com"
USERINFO_API = f"{BASE_URL}/f/user/json_userinfo"
TBS_API = f"{BASE_URL}/dc/common/tbs"
MYLIKE_URL = f"{BASE_URL}/f/like/mylike"
SIGN_API = f"{BASE_URL}/sign/add"
ONEKEY_API = f"{BASE_URL}/tbmall/onekeySignin1"
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


def _accounts(raw: Any, legacy_cookie: str = "") -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw, 1):
            if not isinstance(item, dict):
                continue
            cookie = str(item.get("cookie") or "").strip()
            if cookie:
                result.append({"name": str(item.get("name") or f"账号 {index}").strip(), "cookie": cookie})
    if result:
        return result
    cookie = str(legacy_cookie or "").strip()
    return [{"name": "默认账号", "cookie": cookie}] if cookie else []


def _headers(session: requests.Session, referer: str = BASE_URL) -> Dict[str, str]:
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": referer,
        "Origin": BASE_URL,
    })
    return dict(session.headers)


def _json(response: requests.Response) -> dict:
    try:
        value = response.json()
        return value if isinstance(value, dict) else {}
    except (ValueError, json.JSONDecodeError):
        return {}


def _extract_tbs(response: requests.Response) -> str:
    body = _json(response)
    for value in (body.get("tbs"), (body.get("data") or {}).get("tbs") if isinstance(body.get("data"), dict) else None):
        if value:
            return str(value).strip()
    match = re.search(r'"tbs"\s*:\s*"([^"]+)"', response.text or "")
    return match.group(1).strip() if match else ""


def _page_count(content: str) -> int:
    matches = re.findall(r'(?:[?&]pn=|pn%3D)(\d+)[^>]{0,80}>\s*尾页', content or "", re.I)
    if matches:
        return max(1, max(int(item) for item in matches))
    matches = re.findall(r'[?&]pn=(\d+)', content or "", re.I)
    return max([1, *[int(item) for item in matches]]) if matches else 1


def _bars(content: str) -> List[str]:
    names = []
    for match in re.finditer(r'href=["\']/f\?kw=([^"\']+)["\'][^>]*\btitle=["\']([^"\']+)', content or "", re.I):
        name = html.unescape(match.group(2)).strip()
        if not name:
            name = html.unescape(unquote(match.group(1))).strip()
        if name and name not in names:
            names.append(name)
    return names


def _message(body: dict, text: str = "") -> str:
    for key in ("message", "msg", "error"):
        if body.get(key):
            return str(body[key]).strip()
    return str(text or "").strip()[:180]


def _signin_one(account: Dict[str, str], delay: int, timeout: int, log=None) -> Dict[str, Any]:
    name = account.get("name") or "默认账号"
    session = requests.Session()
    session.headers.update(_headers(session))
    try:
        session.headers["Cookie"] = account["cookie"]
        userinfo = session.get(USERINFO_API, params={"_": int(time.time() * 1000)}, timeout=timeout)
        user_text = userinfo.text or ""
        if userinfo.status_code != 200 or "session_id" not in user_text:
            return {"ok": False, "name": name, "message": "Cookie 已失效或未登录贴吧"}

        tbs_response = session.get(TBS_API, timeout=timeout)
        tbs = _extract_tbs(tbs_response)
        if tbs_response.status_code != 200 or not tbs:
            return {"ok": False, "name": name, "message": "获取 TBS 令牌失败"}

        first = session.get(MYLIKE_URL, timeout=timeout)
        if first.status_code != 200:
            return {"ok": False, "name": name, "message": f"获取关注贴吧列表失败：HTTP {first.status_code}"}
        pages = _page_count(first.text)
        bars = _bars(first.text)
        for page in range(2, pages + 1):
            current = session.get(MYLIKE_URL, params={"pn": page}, timeout=timeout)
            if current.status_code == 200:
                bars.extend(_bars(current.text))
        bars = list(dict.fromkeys(bars))
        if log:
            log.info("[百度贴吧签到] [%s] 获取关注贴吧 %d 个，共 %d 页", name, len(bars), pages)

        individual_failed = 0
        for bar in bars:
            response = session.post(SIGN_API, data={"ie": "utf-8", "kw": bar, "tbs": tbs}, timeout=timeout)
            body = _json(response)
            if response.status_code not in (200, 201) or (body and body.get("no") not in (None, 0, "0")):
                individual_failed += 1
            if delay:
                time.sleep(delay)

        summary = session.post(ONEKEY_API, data={"ie": "utf-8", "tbs": tbs}, timeout=timeout)
        body = _json(summary)
        text = summary.text or ""
        signed = int(body.get("signedForumAmount") or 0)
        failed = int(body.get("signedForumAmountFail") or individual_failed or 0)
        unsigned = int(body.get("unsignedForumAmount") or 0)
        success_marker = any(marker in text.lower() for marker in ("success", "forums is signed", "there is no forum"))
        if summary.status_code != 200 or (not body and not success_marker):
            return {"ok": False, "name": name, "message": _message(body, text) or f"一键签到失败：HTTP {summary.status_code}", "signed": signed, "failed": failed, "unsigned": unsigned}
        return {"ok": True, "name": name, "message": "贴吧签到完成", "signed": signed, "failed": failed, "unsigned": unsigned, "bars": len(bars)}
    except requests.RequestException as exc:
        return {"ok": False, "name": name, "message": f"网络请求失败：{exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "name": name, "message": f"签到处理失败：{exc}"}


async def setup(ctx):
    global _run_lock
    defaults = {
        key: spec["default"]
        for key, spec in __plugin__["config_schema"].items()
        if "default" in spec and spec.get("type") != "action" and key not in ctx.config
    }
    if defaults:
        ctx.update_config(defaults)
    _run_lock = asyncio.Lock()
    scheduled_jobs = []

    async def save_results(results: List[Dict[str, Any]], source: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = await ctx.storage.get("history", [])
        if not isinstance(history, list):
            history = []
        for result in results:
            history.append({"time": stamp, "source": source, **result})
        history = history[-100:]
        await ctx.storage.set("history", history)
        await ctx.storage.set("last_result", {"time": stamp, "source": source, "results": results})
        ok_count = sum(bool(item.get("ok")) for item in results)
        ctx.update_config({
            "last_result": f"{stamp} · 成功 {ok_count}/{len(results)}",
            "history": "\n".join(f"{item['time']} · {item.get('name', '')} · {item.get('message', '')}" for item in reversed(history[-10:])),
        })

    async def run_once(source: str) -> Dict[str, Any]:
        assert _run_lock is not None
        if _run_lock.locked():
            return {"ok": False, "message": "百度贴吧签到任务正在运行"}
        async with _run_lock:
            accounts = _accounts(ctx.config.get("accounts"), ctx.config.get("cookie"))
            if not accounts:
                result = {"ok": False, "message": "未配置贴吧 Cookie"}
                await save_results([result], source)
                ctx.log.error("[百度贴吧签到] %s", result["message"])
                return result
            delay = _bounded_int(ctx.config.get("delay"), 3, 0, 15)
            timeout = _bounded_int(ctx.config.get("timeout"), 30, 5, 120)
            ctx.log.info("[百度贴吧签到] 开始执行，来源=%s，账号=%d", source, len(accounts))
            results = await asyncio.gather(*(
                asyncio.to_thread(_signin_one, account, delay, timeout, ctx.log) for account in accounts
            ))
            await save_results(results, source)
            rows = []
            for item in results:
                rows.append({"账号": item.get("name", "-"), "状态": "成功" if item.get("ok") else "失败", "已签到": item.get("signed", "-"), "失败": item.get("failed", "-"), "未签到": item.get("unsigned", "-"), "详情": item.get("message", "")})
            if ctx.config.get("notify", True):
                try:
                    await asyncio.wait_for(ctx.notify(rows, category="百度贴吧签到"), timeout=30)
                except Exception as exc:  # noqa: BLE001
                    ctx.log.warning("[百度贴吧签到] 通知发送失败：%r", exc)
            ok_count = sum(bool(item.get("ok")) for item in results)
            (ctx.log.info if ok_count == len(results) else ctx.log.warning)("[百度贴吧签到] 完成：成功 %d/%d", ok_count, len(results))
            return {"ok": ok_count == len(results), "results": results, "message": f"成功 {ok_count}/{len(results)}"}

    @ctx.action("run_now")
    async def run_now():
        return await run_once("手动")

    @ctx.on_api("/run", methods=["POST"])
    async def api_run(request):
        return await run_once("API")

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(request):
        return {"running": bool(_run_lock and _run_lock.locked()), "last_result": await ctx.storage.get("last_result", None), "history": await ctx.storage.get("history", [])}

    if ctx.config.get("enabled", False):
        try:
            fields = _cron_fields(ctx.config.get("cron") or "5 8 * * *")
            scheduled_jobs.append(ctx.schedule_cron("百度贴吧签到·定时", lambda: run_once("定时"), **fields))
            ctx.log.info("[百度贴吧签到] 定时任务已启用：%s", ctx.config.get("cron") or "5 8 * * *")
        except ValueError as exc:
            ctx.log.error("[百度贴吧签到] Cron 配置无效：%s", exc)

    async def cleanup():
        for job in scheduled_jobs:
            try:
                if hasattr(job, "cancel"):
                    job.cancel()
            except Exception:
                pass

    ctx.add_cleanup(cleanup)


async def teardown(ctx):
    ctx.log.info("[百度贴吧签到] 插件已停用")
