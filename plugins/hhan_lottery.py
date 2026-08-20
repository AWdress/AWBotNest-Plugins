"""憨憨转盘：使用平台同步 Cookie 调用 HHCLUB 幸运转盘。"""

from __future__ import annotations

import asyncio
import html
import re
from collections import Counter
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


__plugin__ = {
    "name": "憨憨转盘",
    "id": "hhan_lottery",
    "version": "1.0.2",
    "author": "AWdress",
    "description": "读取平台同步的 HHCLUB Cookie，通过配置页控制自动抽取幸运转盘并推送、保存结果。",
    "icon": "https://hhanclub.net/favicon.ico",
    "changelog": "v1.0.2 修复后台任务与跳转安全\n- 后台抽奖任务改由平台统一托管，确保插件停用或重载时可靠清理\n- 页面和抽奖接口仅允许跟随 hhanclub.net 站内跳转，避免 Cookie 随跨站跳转泄露\n- 插件重载时修复残留的运行中状态\n\nv1.0.1 改为配置页控制\n- 移除聊天命令，抽奖次数直接在插件配置中填写\n- 配置页提供开始、停止、查看最近结果和累计统计操作\n- 抽奖完成后通过平台通知推送，并保存最近一次结果\n\nv1.0.0 初始版本\n- 使用平台 Cookie 同步读取 HHCLUB 登录态\n- 支持按次数自动抽奖、手动停止和统计查询\n- 自动识别余额与单次消耗，并对重复点击进行退避\n- 保存累计抽奖、消耗、憨豆收益与奖品统计",
    "scope": "user",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "cookie_domains": ["hhanclub.net", "*.hhanclub.net"],
    "default_enabled": False,
    "resources": {
        "timeout_seconds": 43200,
        "max_concurrency": 2,
        "max_background_tasks": 8,
        "failure_threshold": 5,
        "recovery_seconds": 60,
    },
    "requirements": ["httpx>=0.27", "beautifulsoup4>=4.12", "lxml>=5.0"],
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": True, "label": "启用憨憨转盘",
            "section": "功能开关", "cols": 6, "order": 1,
        },
        "notify_cookie_error": {
            "type": "boolean", "default": True, "label": "Cookie 异常时通知",
            "section": "功能开关", "cols": 6, "order": 2,
        },
        "notify_result": {
            "type": "boolean", "default": True, "label": "完成后推送结果",
            "section": "功能开关", "cols": 6, "order": 3,
        },
        "lottery_count": {
            "type": "number", "default": 10, "label": "抽奖次数",
            "min": 1, "max": 1000, "section": "抽奖设置", "cols": 4, "order": 20,
        },
        "max_count": {
            "type": "number", "default": 100, "label": "单次任务上限",
            "min": 1, "max": 10000, "section": "抽奖设置", "cols": 4, "order": 21,
        },
        "interval_seconds": {
            "type": "slider", "default": 7, "label": "抽奖间隔（秒）",
            "min": 3, "max": 60, "step": 1, "section": "抽奖设置", "cols": 4,
            "order": 22, "help": "连续遇到重复点击或请稍后时会自动延长，最长 30 秒。",
        },
        "start_lottery": {
            "type": "action", "label": "开始抽奖", "action": "start_lottery",
            "section": "任务控制", "cols": 4, "order": 30,
        },
        "stop_lottery": {
            "type": "action", "label": "停止抽奖", "action": "stop_lottery",
            "section": "任务控制", "cols": 4, "order": 31,
        },
        "view_result": {
            "type": "action", "label": "查看最近结果", "action": "view_result",
            "section": "任务控制", "cols": 4, "order": 32,
        },
        "view_stats": {
            "type": "action", "label": "查看累计统计", "action": "view_stats",
            "section": "任务控制", "cols": 6, "order": 33,
        },
        "test_cookie": {
            "type": "action", "label": "检查平台 Cookie", "action": "test_cookie",
            "section": "任务控制", "cols": 6, "order": 34,
        },
        "command_help": {
            "type": "info", "default": (
                "在“抽奖次数”中填写数量并保存，然后点击“开始抽奖”。\n"
                "完成结果可通过平台通知推送，也可点击“查看最近结果”。\n"
                "Cookie 由平台同步读取；请先在浏览器登录 hhanclub.net。"
            ),
            "label": "使用说明", "section": "说明", "cols": 12, "order": 40,
        },
    },
}


_PAGE_URL = "https://hhanclub.net/lucky.php"
_API_URL = "https://hhanclub.net/plugin/lucky-draw"
_DOMAIN = "hhanclub.net"
_STATS_KEY = "lottery_stats"
_LAST_RESULT_KEY = "last_result"
_STATUS_KEY = "task_status"
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_active_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


def _int(value, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _headers(cookie: str, *, ajax: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "*/*" if ajax else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": cookie,
        "Origin": "https://hhanclub.net",
        "Referer": _PAGE_URL,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }
    if ajax:
        headers["X-Requested-With"] = "XMLHttpRequest"
    return headers


async def _cookie_header(ctx, *, request_sync: bool = True) -> tuple[str, str]:
    if not ctx.cookies.available:
        if request_sync:
            try:
                await ctx.cookies.request_sync(_DOMAIN)
            except Exception:
                pass
        return "", "平台 Cookie 同步未启用或尚无可用数据"
    try:
        cookie = await ctx.cookies.header(_DOMAIN, path="/lucky.php")
    except Exception as exc:  # noqa: BLE001
        return "", f"读取平台 Cookie 失败：{exc}"
    if cookie:
        return cookie, ""
    if request_sync:
        try:
            await ctx.cookies.request_sync(_DOMAIN)
        except Exception:
            pass
    return "", "未找到 hhanclub.net Cookie，请登录网站后重新同步"


def _looks_like_login(resp: httpx.Response) -> bool:
    path = urlparse(str(resp.url)).path.lower()
    text = (resp.text or "").lower()
    return path.endswith(("/login.php", "/takelogin.php")) or (
        "takelogin.php" in text
        or ('name="username"' in text and 'name="password"' in text)
    )


def _has_challenge(text: str) -> bool:
    low = (text or "").lower()
    return any(x in low for x in (
        "cf-chl-", "challenge-platform", "cloudflare ray id", "checking your browser"
    ))


async def _same_site_request(client: httpx.AsyncClient, method: str, url: str,
                             headers: dict[str, str]) -> tuple[httpx.Response, str]:
    """请求并只跟随 HHCLUB 站内跳转，避免显式 Cookie 泄露给其他域名。"""
    current_method = method.upper()
    resp = await client.request(current_method, url, headers=headers, follow_redirects=False)
    for _ in range(5):
        if resp.status_code not in _REDIRECT_CODES:
            return resp, ""
        location = str(resp.headers.get("location", "") or "").strip()
        if not location:
            return resp, f"HTTP {resp.status_code}（缺少 Location）"
        target = httpx.URL(str(resp.url)).join(location)
        if target.scheme not in {"http", "https"} or target.host != _DOMAIN:
            return resp, f"站点返回了不安全的跳转：{target}"
        current_method = "GET" if resp.status_code in {301, 302, 303} else current_method
        next_headers = dict(headers)
        if current_method == "GET":
            next_headers.pop("Origin", None)
            next_headers.pop("X-Requested-With", None)
        resp = await client.request(
            current_method, str(target), headers=next_headers, follow_redirects=False
        )
    return resp, "站点跳转次数过多"


async def _page_info(ctx) -> tuple[bool, str, int, int]:
    cookie, error = await _cookie_header(ctx)
    if error:
        return False, error, 0, 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=15.0)) as client:
            resp, redirect_error = await _same_site_request(client, "GET", _PAGE_URL, _headers(cookie))
        if redirect_error:
            return False, redirect_error, 0, 0
        if resp.status_code != 200:
            return False, f"网站返回 HTTP {resp.status_code}", 0, 0
        if _looks_like_login(resp):
            return False, "Cookie 已失效，网站返回登录页", 0, 0
        if _has_challenge(resp.text):
            return False, "站点触发了 Cloudflare 安全验证，请重新同步 Cookie", 0, 0
        soup = BeautifulSoup(resp.text or "", "lxml")
        balance_el = soup.select_one(".bean-number")
        cost_el = soup.select_one(".use-bean")
        balance_match = re.search(r"([\d,]+(?:\.\d+)?)", balance_el.get_text(" ", strip=True)) if balance_el else None
        cost_match = re.search(r"([\d,]+)", cost_el.get_text(" ", strip=True)) if cost_el else None
        if not balance_match:
            return False, "登录成功，但未识别到转盘余额，网页结构可能已更新", 0, 0
        balance = int(float(balance_match.group(1).replace(",", "")))
        cost = int(cost_match.group(1).replace(",", "")) if cost_match else 2000
        return True, "Cookie 有效，已识别幸运转盘", balance, cost
    except Exception as exc:  # noqa: BLE001
        return False, f"访问 HHCLUB 失败：{exc}", 0, 0


async def _draw(client: httpx.AsyncClient, cookie: str) -> tuple[bool, str, bool]:
    """返回 (成功, 奖品或错误, 是否可重试)。"""
    try:
        resp, redirect_error = await _same_site_request(
            client, "POST", _API_URL, _headers(cookie, ajax=True)
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"请求失败：{exc}", True
    if redirect_error:
        return False, redirect_error, False
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}", resp.status_code >= 500
    if _looks_like_login(resp):
        return False, "Cookie 已失效，站点要求重新登录", False
    if _has_challenge(resp.text):
        return False, "站点触发了 Cloudflare 安全验证", False
    try:
        data = resp.json()
    except Exception:
        return False, "站点返回了非 JSON 响应", False
    if not isinstance(data, dict):
        return False, "站点返回的数据格式异常", False
    if data.get("ret") == 0:
        prize = data.get("data") or {}
        if not isinstance(prize, dict):
            prize = {}
        return True, str(prize.get("prize_text") or "未知奖品"), False
    detail = str(data.get("msg") or "未知错误")
    retryable = "重复点击" in detail or "请稍后" in detail
    return False, detail, retryable


def _bean_value(prize: str) -> int:
    if "憨豆" not in prize and "魔力" not in prize:
        return 0
    match = re.search(r"(\d[\d,]*)", prize)
    return int(match.group(1).replace(",", "")) if match else 0


def _load_stats(ctx) -> dict:
    raw = ctx.kv.get(_STATS_KEY, {}) or {}
    return raw if isinstance(raw, dict) else {}


def _save_result(ctx, prizes: list[str], cost: int) -> None:
    stats = _load_stats(ctx)
    prize_stats = Counter(stats.get("prizes", {}) or {})
    prize_stats.update(prizes)
    stats.update({
        "count": _int(stats.get("count"), 0) + len(prizes),
        "cost": _int(stats.get("cost"), 0) + len(prizes) * cost,
        "beans": _int(stats.get("beans"), 0) + sum(_bean_value(x) for x in prizes),
        "prizes": dict(prize_stats),
    })
    ctx.kv.set(_STATS_KEY, stats)


def _summary(title: str, prizes: list[str], cost: int, balance: int, detail: str = "") -> str:
    counts = Counter(prizes)
    lines = [
        title, "",
        f"🎲 完成次数：{len(prizes)}",
        f"💸 本轮消耗：{len(prizes) * cost:,} 憨豆",
        f"🫘 开始余额：{balance:,} 憨豆",
    ]
    if counts:
        lines.extend(["", "🎁 奖品统计："])
        lines.extend(f"• {name} × {count}" for name, count in counts.most_common())
    if detail:
        lines.extend(["", f"ℹ️ {detail}"])
    return "\n".join(lines)


def _stats_text(stats: dict) -> str:
    counts = Counter(stats.get("prizes", {}) or {})
    lines = [
        "📊 憨憨转盘累计统计", "",
        f"🎲 抽奖次数：{_int(stats.get('count'), 0):,}",
        f"💸 累计消耗：{_int(stats.get('cost'), 0):,} 憨豆",
        f"🫘 憨豆奖品：{_int(stats.get('beans'), 0):,}",
    ]
    if counts:
        lines.extend(["", "🎁 奖品明细："])
        lines.extend(f"• {html.unescape(str(name))} × {count}" for name, count in counts.most_common(20))
    return "\n".join(lines)


async def setup(ctx):
    global _active_task, _stop_event
    _active_task = None
    _stop_event = asyncio.Event()
    stale_status = ctx.kv.get(_STATUS_KEY, {}) or {}
    if isinstance(stale_status, dict) and stale_status.get("running"):
        stale_status.update({"running": False, "detail": "插件已重载，原任务已结束"})
        ctx.kv.set(_STATUS_KEY, stale_status)

    async def _notify_cookie(detail: str):
        if ctx.config.get("notify_cookie_error", True) and "Cookie" in detail:
            try:
                await ctx.notify(detail, level="warning", category="憨憨转盘")
            except Exception:
                pass

    async def _push_result(text: str, *, success: bool):
        if not ctx.config.get("notify_result", True):
            return
        try:
            await ctx.notify(
                text,
                level="success" if success else "warning",
                category="憨憨转盘",
            )
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("[憨憨转盘] 推送结果失败：%r", exc)

    async def _run(count: int):
        global _active_task
        prizes: list[str] = []
        ctx.kv.set(_STATUS_KEY, {"running": True, "completed": 0, "target": count})
        ok, detail, balance, cost = await _page_info(ctx)
        if not ok:
            await _notify_cookie(detail)
            result_text = f"⚠️ 憨憨转盘无法启动\n\n{detail}"
            ctx.kv.set(_LAST_RESULT_KEY, result_text)
            ctx.kv.set(_STATUS_KEY, {"running": False, "completed": 0, "target": count, "detail": detail})
            await _push_result(result_text, success=False)
            _active_task = None
            return
        possible = balance // cost if cost > 0 else 0
        target = min(count, possible)
        if target <= 0:
            result_text = f"💸 憨豆不足\n\n余额 {balance:,}，单次需要 {cost:,}。"
            ctx.kv.set(_LAST_RESULT_KEY, result_text)
            ctx.kv.set(_STATUS_KEY, {"running": False, "completed": 0, "target": count, "detail": "憨豆不足"})
            await _push_result(result_text, success=False)
            _active_task = None
            return

        cookie, error = await _cookie_header(ctx)
        if error:
            result_text = f"⚠️ {error}"
            ctx.kv.set(_LAST_RESULT_KEY, result_text)
            ctx.kv.set(_STATUS_KEY, {"running": False, "completed": 0, "target": count, "detail": error})
            await _push_result(result_text, success=False)
            _active_task = None
            return
        interval = _int(ctx.config.get("interval_seconds"), 7, 3)
        dynamic_interval = interval
        consecutive_retry = 0
        stop_detail = ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=15.0)) as client:
                while len(prizes) < target:
                    if _stop_event and _stop_event.is_set():
                        stop_detail = "用户已手动停止任务"
                        break
                    success, result, retryable = await _draw(client, cookie)
                    if success:
                        prizes.append(result)
                        consecutive_retry = 0
                        dynamic_interval = interval
                        ctx.kv.set(_STATUS_KEY, {
                            "running": True, "completed": len(prizes), "target": target,
                            "last_prize": result,
                        })
                        ctx.log.info("[憨憨转盘] %s/%s prize=%s", len(prizes), target, result)
                    elif retryable:
                        consecutive_retry += 1
                        ctx.log.warning("[憨憨转盘] 可重试错误：%s", result)
                        if consecutive_retry >= 3:
                            dynamic_interval = min(30, max(interval, int(dynamic_interval * 1.5)))
                        if consecutive_retry >= 10:
                            stop_detail = f"连续重试 {consecutive_retry} 次仍失败：{result}"
                            break
                        await asyncio.sleep(dynamic_interval)
                        continue
                    else:
                        stop_detail = result
                        await _notify_cookie(result)
                        break
                    if len(prizes) < target:
                        await asyncio.sleep(dynamic_interval)
        except asyncio.CancelledError:
            stop_detail = "插件停止，任务已取消"
        finally:
            if prizes:
                _save_result(ctx, prizes, cost)
            title = "🎉 憨憨转盘完成" if len(prizes) == target else "🛑 憨憨转盘已停止"
            if target < count and not stop_detail:
                stop_detail = f"余额最多支持 {target} 次，已自动缩减"
            result_text = _summary(title, prizes, cost, balance, stop_detail)
            ctx.kv.set(_LAST_RESULT_KEY, result_text)
            ctx.kv.set(_STATUS_KEY, {
                "running": False, "completed": len(prizes), "target": target,
                "detail": stop_detail,
            })
            await _push_result(result_text, success=len(prizes) == target)
            _active_task = None
            if _stop_event:
                _stop_event.clear()

    @ctx.action("test_cookie")
    async def test_cookie():
        ok, message, balance, cost = await _page_info(ctx)
        if ok:
            message += f"；余额 {balance:,}，单次消耗 {cost:,}"
        return {"ok": ok, "message": message}

    @ctx.action("start_lottery")
    async def start_lottery():
        global _active_task
        if not ctx.config.get("enabled", True):
            return {"ok": False, "message": "请先启用憨憨转盘插件"}
        if _active_task and not _active_task.done():
            status = ctx.kv.get(_STATUS_KEY, {}) or {}
            return {
                "ok": False,
                "message": f"已有任务运行中：{_int(status.get('completed'), 0)}/{_int(status.get('target'), 0)}",
            }
        count = _int(ctx.config.get("lottery_count"), 10, 1)
        maximum = _int(ctx.config.get("max_count"), 100, 1)
        if count < 1 or count > maximum:
            return {"ok": False, "message": f"抽奖次数需为 1–{maximum} 的整数"}
        if _stop_event:
            _stop_event.clear()
        _active_task = ctx.create_task(
            _run(count), name="憨憨转盘后台任务", operation="lottery"
        )
        return {"ok": True, "message": f"憨憨转盘已开始，计划抽奖 {count} 次；可稍后查看最近结果。"}

    @ctx.action("stop_lottery")
    async def stop_lottery():
        if not (_active_task and not _active_task.done()):
            return {"ok": False, "message": "当前没有正在运行的抽奖任务"}
        if _stop_event:
            _stop_event.set()
        return {"ok": True, "message": "已请求停止，当前请求完成后退出"}

    @ctx.action("view_result")
    async def view_result():
        status = ctx.kv.get(_STATUS_KEY, {}) or {}
        if status.get("running"):
            message = (
                f"抽奖进行中：{_int(status.get('completed'), 0)}/"
                f"{_int(status.get('target'), 0)}"
            )
            if status.get("last_prize"):
                message += f"；最近奖品：{status['last_prize']}"
            return {"ok": True, "message": message}
        result = str(ctx.kv.get(_LAST_RESULT_KEY, "") or "")
        return {"ok": bool(result), "message": result or "暂无抽奖结果"}

    @ctx.action("view_stats")
    async def view_stats():
        return {"ok": True, "message": _stats_text(_load_stats(ctx))}


async def teardown(ctx):
    global _active_task
    if _active_task and not _active_task.done():
        _active_task.cancel()
        try:
            await _active_task
        except (asyncio.CancelledError, Exception):
            pass
    _active_task = None


async def self_check(ctx):
    cookie, error = await _cookie_header(ctx, request_sync=False)
    return {
        "id": "cookie_sync",
        "name": "平台 Cookie 同步",
        "ok": bool(cookie),
        "detail": "已读取 hhanclub.net Cookie" if cookie else error,
    }
