"""憨憨赠豆：使用平台同步 Cookie 向 hhanclub.net 用户赠送憨豆。"""

from __future__ import annotations

import asyncio
import re
import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


__plugin__ = {
    "name": "憨憨赠豆",
    "id": "hhan_bonus",
    "version": "1.0.0",
    "author": "AWdress",
    "description": "使用平台同步的 HHCLUB Cookie，通过用户账号命令单人或批量赠送憨豆。",
    "icon": "https://hhanclub.net/favicon.ico",
    "changelog": "v1.0.0 初始版本\n- 支持 .hh 单人赠豆与 .hhs 批量赠豆\n- Cookie 统一从平台 Cookie 同步读取，不在插件配置中保存\n- 支持登录检查、持久化冷却、安全站内跳转和赠送结果解析",
    "scope": "user",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "cookie_domains": ["hhanclub.net", "*.hhanclub.net"],
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
            "type": "boolean", "default": True, "label": "启用赠豆命令",
            "section": "功能开关", "cols": 6, "order": 1,
        },
        "notify_cookie_error": {
            "type": "boolean", "default": True, "label": "Cookie 异常时通知",
            "section": "功能开关", "cols": 6, "order": 2,
        },
        "single_command": {
            "type": "string", "default": ".hh", "label": "单人赠豆命令",
            "help": "格式：.hh 用户名 数量 留言（留言可包含空格）。",
            "section": "命令", "cols": 6, "order": 10,
        },
        "batch_command": {
            "type": "string", "default": ".hhs", "label": "批量赠豆命令",
            "help": "格式：.hhs 用户1 用户2 ... 数量 留言；批量留言请不要包含空格。",
            "section": "命令", "cols": 6, "order": 11,
        },
        "cooldown_seconds": {
            "type": "slider", "default": 10, "label": "赠送冷却（秒）",
            "min": 0, "max": 600, "step": 5,
            "help": "每次向站点提交赠送之间的最小间隔，批量任务同样生效。",
            "section": "限频与清理", "cols": 6, "order": 20,
        },
        "result_delete": {
            "type": "slider", "default": 90, "label": "结果自动删除（秒）",
            "min": 0, "max": 600, "step": 10,
            "section": "限频与清理", "cols": 6, "order": 21,
        },
        "test_cookie": {
            "type": "action", "label": "检查平台 Cookie", "action": "test_cookie",
            "section": "检查", "cols": 6, "order": 30,
        },
        "command_help": {
            "type": "info", "default": (
                "单人：.hh 用户名 100 留言内容\n"
                "批量：.hhs 用户1 用户2 100 留言\n"
                "站点最低赠送 100；接收者会被扣除 5 + 20% 作为税收。"
            ),
            "label": "命令说明", "section": "检查", "cols": 12, "order": 31,
        },
    },
}


_PAGE_URL = "https://hhanclub.net/mybonus.php"
_POST_URL = "https://hhanclub.net/mybonus.php?action=exchange"
_DOMAIN = "hhanclub.net"
_KV_LAST = "last_gift_ts"
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_gift_lock: asyncio.Lock | None = None


def _bare(value: str, default: str) -> str:
    return (value or "").lstrip("/.").strip().lower() or default


def _head(text: str) -> str:
    return text.split(maxsplit=1)[0].lstrip("/.").lower() if text else ""


def _looks_like_login(resp: httpx.Response) -> bool:
    path = urlparse(str(resp.url)).path.lower()
    if path.endswith(("/login.php", "/takelogin.php")):
        return True
    text = (resp.text or "").lower()
    return (
        "takelogin.php" in text
        or ('name="username"' in text and 'name="password"' in text)
        or ("name='username'" in text and "name='password'" in text)
    )


def _headers(cookie: str) -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": cookie,
        "Origin": "https://hhanclub.net",
        "Referer": _PAGE_URL,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }


async def _cookie_header(ctx, *, request_sync: bool = True) -> tuple[str, str]:
    if not ctx.cookies.available:
        if request_sync:
            try:
                await ctx.cookies.request_sync(_DOMAIN)
            except Exception:
                pass
        return "", "平台 Cookie 同步未启用或尚无可用数据"
    try:
        cookie = await ctx.cookies.header(_DOMAIN, path="/mybonus.php")
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


async def _follow_redirects(client, resp, headers, log):
    redirected = False
    get_headers = dict(headers)
    get_headers.pop("Origin", None)
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
        log.info("[憨憨赠豆] 跟随站内跳转：HTTP %s -> %s", resp.status_code, target)
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

    soup = BeautifulSoup(resp.text or "", "lxml")
    tips = soup.select_one(".tips")
    detail = " ".join(tips.get_text(" ", strip=True).split()) if tips else ""
    error_markers = ("错误", "对不起", "不存在", "不足", "失败", "不能", "至少")
    success_markers = ("成功", "赠送完成", "已经赠送", "礼物已送出")

    if detail and any(marker in detail for marker in error_markers):
        detail = re.sub(r"\s*点击回到.*$", "", detail).strip()
        return False, detail or "站点拒绝了赠送请求"
    if detail and any(marker in detail for marker in success_markers):
        return True, detail or "赠送成功"
    if redirected:
        return True, detail or "赠送请求已提交，站点已跳转确认"
    return False, detail or "站点未返回明确的赠送结果，请登录网页核对"


async def _check_login(ctx) -> tuple[bool, str]:
    cookie, error = await _cookie_header(ctx)
    if error:
        return False, error
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=15.0)) as client:
            resp = await client.get(_PAGE_URL, headers=_headers(cookie), follow_redirects=True)
        if resp.status_code != 200:
            return False, f"网站返回 HTTP {resp.status_code}"
        if _looks_like_login(resp):
            return False, "Cookie 已失效，网站返回登录页"
        soup = BeautifulSoup(resp.text or "", "lxml")
        form = soup.find("input", attrs={"name": "bonusgift"})
        if not form:
            return False, "登录成功，但未找到赠豆表单，网站页面可能已更新"
        title = soup.title.get_text(" ", strip=True) if soup.title else "HHCLUB"
        return True, f"Cookie 有效，已识别赠豆页面：{title}"
    except Exception as exc:  # noqa: BLE001
        return False, f"访问 HHCLUB 失败：{exc}"


async def _gift(ctx, username: str, amount: int, note: str) -> tuple[bool, str]:
    cookie, error = await _cookie_header(ctx)
    if error:
        return False, error
    data = {
        "option": "7",
        "username": username,
        "message": note,
        "bonusgift": str(amount),
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
        ctx.log.error("[憨憨赠豆] 请求失败：%r", exc)
        return False, f"请求失败：{exc}"


def _amount(value: str) -> int | None:
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return None
    return amount if amount >= 100 else None


def _estimated_received(amount: int) -> int:
    return max(0, amount - 5 - int(amount * 0.2))


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

    def _mark_gift():
        ctx.kv.set(_KV_LAST, time.time())

    def _schedule_delete(message, delay: int):
        if not message or delay <= 0:
            return

        async def worker():
            await asyncio.sleep(delay)
            try:
                await message.delete()
            except Exception:
                pass

        ctx.create_task(worker(), name="憨憨赠豆结果清理", operation="auto_delete")

    async def _cookie_error_notify(detail: str):
        if ctx.config.get("notify_cookie_error", True) and "Cookie" in detail:
            try:
                await ctx.notify(detail, level="warning", category="憨憨赠豆")
            except Exception as exc:  # noqa: BLE001
                ctx.log.warning("[憨憨赠豆] Cookie 异常通知失败：%r", exc)

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
        single = _bare(cfg.get("single_command", ".hh"), "hh")
        batch = _bare(cfg.get("batch_command", ".hhs"), "hhs")
        if head not in {single, batch}:
            return

        delete_after = int(cfg.get("result_delete", 90) or 0)
        line = "─" * 16
        if head == single:
            parts = text.split(maxsplit=3)
            if len(parts) < 4 or _amount(parts[2]) is None:
                edited = await message.edit(
                    "```\n格式：.hh 用户名 数量 留言\n示例：.hh Alice 100 感谢分享```"
                )
                _schedule_delete(edited, 20)
                return
            users = [parts[1]]
            amount = _amount(parts[2]) or 0
            note = parts[3].strip()
        else:
            parts = text.split()
            if len(parts) < 4 or _amount(parts[-2]) is None:
                edited = await message.edit(
                    "```\n格式：.hhs 用户1 用户2 ... 数量 留言\n示例：.hhs Alice Bob 100 感谢```"
                )
                _schedule_delete(edited, 20)
                return
            users = parts[1:-2]
            amount = _amount(parts[-2]) or 0
            note = parts[-1]

        if len(users) > 50:
            edited = await message.edit("```\n单次批量最多赠送 50 位用户，请拆分后重试```")
            _schedule_delete(edited, 20)
            return

        if not users or not note:
            edited = await message.edit("```\n用户名、赠送数量和留言均不能为空```")
            _schedule_delete(edited, 20)
            return
        if _gift_lock and _gift_lock.locked():
            edited = await message.edit("```\n已有赠豆任务正在执行，请稍后再试```")
            _schedule_delete(edited, 20)
            return

        status = await message.edit("```\n憨豆正在打包发送，请稍候…```")
        rows: list[str] = []
        success_count = 0
        last_detail = ""
        async with _gift_lock:
            for username in users:
                await _wait_cooldown()
                ok, detail = await _gift(ctx, username, amount, note)
                last_detail = detail
                _mark_gift()
                ctx.log.info(
                    "[憨憨赠豆] user=%s amount=%s ok=%s detail=%s",
                    username, amount, ok, detail,
                )
                if ok:
                    success_count += 1
                    rows.append(f"✓ {username}")
                else:
                    rows.append(f"✗ {username}  {detail}")
                    await _cookie_error_notify(detail)

        if len(users) == 1:
            if success_count:
                body = (
                    f"憨憨赠豆 · 成功\n{line}\n"
                    f"用户   {users[0]}\n"
                    f"赠送   {amount} 憨豆\n"
                    f"预计到账   {_estimated_received(amount)} 憨豆\n"
                    f"留言   {note}"
                )
            else:
                body = (
                    f"憨憨赠豆 · 失败\n{line}\n"
                    f"用户   {users[0]}\n原因   {last_detail or '未知错误'}"
                )
        else:
            body = (
                f"憨憨批量赠豆   每份 {amount} 憨豆\n"
                f"预计每人到账 {_estimated_received(amount)} 憨豆\n"
                f"留言 {note}\n{line}\n"
                + "\n".join(rows)
                + f"\n{line}\n成功 {success_count}/{len(users)}"
            )
        edited = await status.edit(f"```\n{body}```")
        _schedule_delete(edited, delete_after)


async def teardown(ctx):
    pass


async def self_check(ctx):
    cookie, error = await _cookie_header(ctx, request_sync=False)
    return {
        "id": "cookie_sync",
        "name": "平台 Cookie 同步",
        "ok": bool(cookie),
        "detail": "已读取 hhanclub.net Cookie" if cookie else error,
    }
