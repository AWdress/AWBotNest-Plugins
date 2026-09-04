"""猫站赠粮：使用平台同步 Cookie 向 pterclub.net 用户赠送猫粮。"""

from __future__ import annotations

import asyncio
import html
import re
import time
from decimal import Decimal
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


__plugin__ = {
    "name": "猫站赠粮",
    "id": "pterclub_bonus",
    "version": "1.0.0",
    "author": "AWdress",
    "description": "使用平台同步的 PTerClub Cookie，通过用户账号命令单人或批量赠送猫粮。",
    "icon": "https://pterclub.net/favicon.ico",
    "changelog": "v1.0.0 初始版本\n- 支持 .pm 单人赠粮与 .pms 批量赠粮\n- Cookie 统一从平台 Cookie 同步读取，不在插件配置中保存\n- 按猫站规则校验每份 25–50,000 猫粮并显示 10% 税后到账\n- 支持登录检查、持久化冷却、安全站内跳转和赠送结果解析",
    "scope": "user",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "cookie_domains": ["pterclub.net", "*.pterclub.net"],
    "default_enabled": False,
    "resources": {
        "timeout_seconds": 1800,
        "max_concurrency": 2,
        "max_background_tasks": 16,
        "failure_threshold": 5,
        "recovery_seconds": 60,
    },
    "requirements": ["httpx>=0.27", "beautifulsoup4>=4.12", "lxml>=5.0"],
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": True, "label": "启用赠粮命令",
            "section": "功能开关", "cols": 6, "order": 1,
        },
        "notify_cookie_error": {
            "type": "boolean", "default": True, "label": "Cookie 异常时通知",
            "section": "功能开关", "cols": 6, "order": 2,
        },
        "single_command": {
            "type": "string", "default": ".pm", "label": "单人赠粮命令",
            "help": "格式：.pm 用户名 数量 留言（留言可包含空格）。",
            "section": "命令", "cols": 6, "order": 10,
        },
        "batch_command": {
            "type": "string", "default": ".pms", "label": "批量赠粮命令",
            "help": "格式：.pms 用户1 用户2 ... 数量 留言；批量留言请不要包含空格。",
            "section": "命令", "cols": 6, "order": 11,
        },
        "cooldown_seconds": {
            "type": "slider", "default": 10, "label": "赠送冷却（秒）",
            "min": 0, "max": 600, "step": 5,
            "help": "每次向猫站提交赠送之间的最小间隔，批量任务同样生效。",
            "section": "限频与清理", "cols": 6, "order": 20,
        },
        "result_delete": {
            "type": "slider", "default": 90, "label": "结果自动删除（秒）",
            "min": 10, "max": 600, "step": 10,
            "section": "限频与清理", "cols": 6, "order": 21,
        },
        "test_cookie": {
            "type": "action", "label": "检查平台 Cookie", "action": "test_cookie",
            "section": "检查", "cols": 6, "order": 30,
        },
        "command_help": {
            "type": "info", "default": (
                "单人：.pm 用户名 1000 留言内容\n"
                "批量：.pms 用户1 用户2 1000 留言\n"
                "每份最低 25、最高 50,000；接收者到账 90%。"
            ),
            "label": "命令说明", "section": "检查", "cols": 12, "order": 31,
        },
    },
}


_PAGE_URL = "https://pterclub.net/mybonus.php"
_POST_URL = "https://pterclub.net/mybonus.php?action=exchange"
_DOMAIN = "pterclub.net"
_KV_LAST = "last_gift_ts"
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_gift_lock: asyncio.Lock | None = None


def _bare(value: str, default: str) -> str:
    return (value or "").lstrip("/.").strip().lower() or default


def _head(text: str) -> str:
    return text.split(maxsplit=1)[0].lstrip("/.").lower() if text else ""


def _headers(cookie: str) -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie,
        "Origin": "https://pterclub.net",
        "Referer": _PAGE_URL,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }


async def _cookie_header(ctx, *, request_sync: bool = True) -> tuple[str, str]:
    cookies = getattr(ctx, "cookies", None)
    if cookies is None or not callable(getattr(cookies, "header", None)):
        if request_sync:
            try:
                if callable(getattr(cookies, "request_sync", None)):
                    await cookies.request_sync(_DOMAIN)
            except Exception:
                pass
        return "", "平台 Cookie 同步未启用或尚无可用数据"
    try:
        try:
            cookie = await cookies.header(_DOMAIN, path="/mybonus.php")
        except TypeError:
            cookie = await cookies.header(_DOMAIN)
    except Exception as exc:  # noqa: BLE001
        return "", f"读取平台 Cookie 失败：{exc}"
    if cookie:
        return cookie, ""
    if request_sync:
        try:
            await cookies.request_sync(_DOMAIN)
        except Exception:
            pass
    return "", "未找到 pterclub.net Cookie，请登录网站后重新同步"


def _looks_like_login(resp: httpx.Response) -> bool:
    path = urlparse(str(resp.url)).path.lower()
    text = (resp.text or "").lower()
    return path.endswith(("/login.php", "/takelogin.php")) or (
        "takelogin.php" in text
        or ('name="username"' in text and 'name="password"' in text)
        or ("name='username'" in text and "name='password'" in text)
    )


async def _follow_redirects(client, resp, headers, log):
    redirected = False
    get_headers = dict(headers)
    get_headers.pop("Origin", None)
    get_headers.pop("Content-Type", None)
    for _ in range(5):
        if resp.status_code not in _REDIRECT_CODES:
            return resp, redirected, ""
        location = str(resp.headers.get("location", "") or "").strip()
        if not location:
            return resp, redirected, f"HTTP {resp.status_code}（缺少 Location）"
        target = urljoin(str(resp.url), location)
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or parsed.hostname != _DOMAIN:
            return resp, redirected, f"站点返回了不安全的跳转：{target}"
        path = parsed.path.lower()
        log.info("[猫站赠粮] 跟随站内跳转：HTTP %s -> %s", resp.status_code, target)
        if path.endswith(("/login.php", "/takelogin.php")):
            return resp, True, "Cookie 已失效，站点要求重新登录"
        if path.startswith("/cdn-cgi/"):
            return resp, True, "站点触发了 Cloudflare 安全验证，请重新同步 Cookie"
        redirected = True
        resp = await client.get(target, headers=get_headers, follow_redirects=False)
    return resp, redirected, "站点跳转次数过多"


def _feedback(resp: httpx.Response, *, redirected: bool) -> tuple[bool, str]:
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}"
    if _looks_like_login(resp):
        return False, "Cookie 已失效，最终响应为登录页"
    page_lower = (resp.text or "").lower()
    if any(marker in page_lower for marker in (
        "cf-chl-", "challenge-platform", "cloudflare ray id", "checking your browser"
    )):
        return False, "站点触发了 Cloudflare 安全验证，请重新同步 Cookie"

    soup = BeautifulSoup(resp.text or "", "lxml")
    tips = soup.select_one(".tips")
    detail = " ".join(tips.get_text(" ", strip=True).split()) if tips else ""
    error_markers = (
        "错误", "對不起", "对不起", "不存在", "不足", "失败", "失敗",
        "不能", "至少", "至多", "最多", "不允许", "不允許",
    )
    success_markers = ("成功", "赠送完成", "贈送完成", "已经赠送", "已經贈送")
    if detail and any(marker in detail for marker in error_markers):
        detail = re.sub(r"\s*点击回到.*$", "", detail).strip()
        return False, detail or "站点拒绝了赠送请求"
    if detail and any(marker in detail for marker in success_markers):
        return True, detail
    if "错误" in (resp.text or "") or "錯誤" in (resp.text or ""):
        return False, detail or "站点返回错误，请登录网页核对"
    if redirected:
        return True, detail or "赠送请求已提交，站点已跳转确认"
    # 猫站现有自定义赠粮脚本也以响应中不含“错误”作为成功依据。
    return True, detail or "赠粮完成"


async def _check_login(ctx) -> tuple[bool, str]:
    cookie, error = await _cookie_header(ctx)
    if error:
        return False, error
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=15.0)) as client:
            resp = await client.get(_PAGE_URL, headers=_headers(cookie), follow_redirects=False)
            resp, _, redirect_error = await _follow_redirects(client, resp, _headers(cookie), ctx.log)
        if redirect_error:
            return False, redirect_error
        if resp.status_code != 200:
            return False, f"网站返回 HTTP {resp.status_code}"
        if _looks_like_login(resp):
            return False, "Cookie 已失效，网站返回登录页"
        soup = BeautifulSoup(resp.text or "", "lxml")
        option = soup.find("input", attrs={"name": "option", "value": "13"})
        gift = soup.find(attrs={"name": "bonusgift"})
        username = soup.find(attrs={"name": "username"})
        if not ((option or gift) and username):
            return False, "登录成功，但未找到赠猫粮表单，网站页面可能已更新"
        title = soup.title.get_text(" ", strip=True) if soup.title else "PTerClub"
        return True, f"Cookie 有效，已识别赠猫粮页面：{title}"
    except Exception as exc:  # noqa: BLE001
        return False, f"访问猫站失败：{exc}"


async def _gift(ctx, username: str, amount: int, note: str) -> tuple[bool, str]:
    cookie, error = await _cookie_header(ctx)
    if error:
        return False, error
    data = {
        "option": "13",
        "username": username,
        "bonusgift": str(amount),
        "message": note,
        "submit": "赠送",
    }
    try:
        headers = _headers(cookie)
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=20.0)) as client:
            resp = await client.post(
                _POST_URL, headers=headers, data=data, follow_redirects=False
            )
            resp, redirected, redirect_error = await _follow_redirects(
                client, resp, headers, ctx.log
            )
        if redirect_error:
            return False, redirect_error
        return _feedback(resp, redirected=redirected)
    except Exception as exc:  # noqa: BLE001
        ctx.log.error("[猫站赠粮] 请求失败：%r", exc)
        return False, f"请求失败：{exc}"


def _amount(value: str) -> int | None:
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return None
    return amount if 25 <= amount <= 50_000 else None


def _estimated_received(amount: int) -> Decimal:
    return Decimal(amount) * Decimal("0.9")


def _rich_result(users: list[str], amount: int, note: str,
                 rows: list[tuple[str, bool, str]]) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    if len(users) == 1:
        username, ok, detail = rows[0]
        values = [("状态", "✅ 已完成" if ok else "❌ 未送达"), ("接收用户", username)]
        if ok:
            values.extend([
                ("赠送数量", f"{amount:,} 猫粮"),
                ("预计到账", f"{_estimated_received(amount):,} 猫粮"),
                ("留言", note),
            ])
        else:
            values.append(("失败原因", detail or "未知错误"))
        table_rows = "".join(
            f'<tr><th align="left">{esc(label)}</th><td align="left">{esc(value)}</td></tr>'
            for label, value in values
        )
        title = "🐱 猫站赠粮完成" if ok else "⚠️ 猫站赠粮失败"
        return f"<h2>{title}</h2><table bordered striped>{table_rows}</table>"

    success_count = sum(1 for _, ok, _ in rows if ok)
    table_rows = [
        '<tr><th align="center">状态</th><th align="left">用户</th>'
        '<th align="right">赠送</th><th align="left">结果</th></tr>'
    ]
    for username, ok, detail in rows:
        result = f"预计到账 {_estimated_received(amount):,}" if ok else (detail or "未知错误")
        table_rows.append(
            f'<tr><td align="center">{"✅" if ok else "❌"}</td>'
            f'<td align="left">{esc(username)}</td><td align="right">{amount:,}</td>'
            f'<td align="left">{esc(result)}</td></tr>'
        )
    return (
        f"<h2>🐱 猫站批量赠粮</h2>"
        f"<blockquote>成功 {success_count}/{len(rows)} · 每份 {amount:,} 猫粮</blockquote>"
        f'<table bordered striped>{"".join(table_rows)}</table><blockquote>💬 {esc(note)}</blockquote>'
    )


def _plain_result(users: list[str], amount: int, note: str,
                  rows: list[tuple[str, bool, str]]) -> str:
    if len(users) == 1:
        username, ok, detail = rows[0]
        if ok:
            return (
                "🐱 猫站赠粮完成\n\n"
                f"👤 接收用户：{username}\n🎁 赠送数量：{amount:,} 猫粮\n"
                f"💰 预计到账：{_estimated_received(amount):,} 猫粮\n💬 留言：{note}"
            )
        return f"⚠️ 猫站赠粮失败\n\n👤 接收用户：{username}\n❌ 原因：{detail or '未知错误'}"
    success_count = sum(1 for _, ok, _ in rows if ok)
    details = [
        f"{'✅' if ok else '❌'} {username}  "
        f"{'预计到账 ' + format(_estimated_received(amount), ',') if ok else (detail or '未知错误')}"
        for username, ok, detail in rows
    ]
    return (
        f"🐱 猫站批量赠粮\n成功 {success_count}/{len(rows)} · 每份 {amount:,} 猫粮\n"
        f"💬 {note}\n\n" + "\n".join(details)
    )


async def setup(ctx):
    global _gift_lock
    _gift_lock = asyncio.Lock()

    async def _wait_cooldown():
        try:
            seconds = max(0.0, float(ctx.config.get("cooldown_seconds", 10) or 0))
        except (TypeError, ValueError):
            seconds = 10
        last = float(ctx.kv.get(_KV_LAST, 0) or 0)
        remaining = seconds - (time.time() - last)
        if remaining > 0:
            await asyncio.sleep(remaining)

    def _schedule_delete(message, delay: int):
        if not message or delay <= 0:
            return

        async def worker():
            await asyncio.sleep(delay)
            try:
                await message.delete()
            except Exception:
                pass

        ctx.create_task(worker(), name="猫站赠粮结果清理", operation="auto_delete")

    async def _cookie_error_notify(detail: str):
        if ctx.config.get("notify_cookie_error", True) and "Cookie" in detail:
            try:
                await ctx.notify(detail, level="warning", category="猫站赠粮")
            except Exception as exc:  # noqa: BLE001
                ctx.log.warning("[猫站赠粮] Cookie 异常通知失败：%r", exc)

    @ctx.action("test_cookie")
    async def test_cookie():
        ok, message = await _check_login(ctx)
        return {"ok": ok, "message": message}

    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-9)
    async def gift_command(client, message):
        cfg = ctx.config
        if not cfg.get("enabled", True):
            return
        text = (message.text or "").strip()
        head = _head(text)
        single = _bare(cfg.get("single_command", ".pm"), "pm")
        batch = _bare(cfg.get("batch_command", ".pms"), "pms")
        if head not in {single, batch}:
            return

        delete_after = max(10, _safe_int(cfg.get("result_delete"), 90))
        if head == single:
            parts = text.split(maxsplit=3)
            if len(parts) < 4 or _amount(parts[2]) is None:
                edited = await message.edit(
                    "⚠️ 格式不正确\n\n用法：.pm 用户名 数量 留言\n"
                    "数量需为 25–50,000，例如：.pm Alice 1000 感谢分享"
                )
                _schedule_delete(edited, 20)
                return
            users, amount, note = [parts[1]], _amount(parts[2]) or 0, parts[3].strip()
        else:
            parts = text.split()
            if len(parts) < 4 or _amount(parts[-2]) is None:
                edited = await message.edit(
                    "⚠️ 格式不正确\n\n用法：.pms 用户1 用户2 ... 数量 留言\n"
                    "数量需为 25–50,000，例如：.pms Alice Bob 1000 感谢"
                )
                _schedule_delete(edited, 20)
                return
            users, amount, note = parts[1:-2], _amount(parts[-2]) or 0, parts[-1]

        if len(users) > 50:
            edited = await message.edit("⚠️ 单次批量最多赠送 50 位用户，请拆分后重试。")
            _schedule_delete(edited, 20)
            return
        if not users or not note:
            edited = await message.edit("⚠️ 用户名、赠送数量和留言均不能为空。")
            _schedule_delete(edited, 20)
            return
        if _gift_lock and _gift_lock.locked():
            edited = await message.edit("⏳ 已有猫站赠粮任务正在执行，请稍后再试。")
            _schedule_delete(edited, 20)
            return

        status = await message.edit("🐱 猫粮正在打包发送，请稍候…")
        rows: list[tuple[str, bool, str]] = []
        async with _gift_lock:
            for username in users:
                await _wait_cooldown()
                ok, detail = await _gift(ctx, username, amount, note)
                ctx.kv.set(_KV_LAST, time.time())
                ctx.log.info(
                    "[猫站赠粮] user=%s amount=%s ok=%s detail=%s",
                    username, amount, ok, detail,
                )
                rows.append((username, ok, detail))
                if not ok:
                    await _cookie_error_notify(detail)

        rich = _rich_result(users, amount, note, rows)
        plain = _plain_result(users, amount, note, rows)
        sent = None
        try:
            supports_rich = bool(ctx.user and await ctx.user.supports_native_rich())
            if supports_rich:
                sent = await ctx.user.send_rich(message.chat.id, rich, format="html")
                await status.delete()
            else:
                sent = await status.edit(plain)
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("[猫站赠粮] 富文本结果发送失败，回退普通文本：%r", exc)
            sent = await status.edit(plain)
        _schedule_delete(sent, delete_after)


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def teardown(ctx):
    pass


async def self_check(ctx):
    cookie, error = await _cookie_header(ctx, request_sync=False)
    return {
        "id": "cookie_sync",
        "name": "平台 Cookie 同步",
        "ok": bool(cookie),
        "detail": "已读取 pterclub.net Cookie" if cookie else error,
    }
