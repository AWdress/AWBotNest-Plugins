"""憨憨赠豆：使用平台同步 Cookie 向 hhanclub.net 用户赠送憨豆。"""

from __future__ import annotations

import asyncio
import html
import random
import re
import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ._auth import cookie_header


_OFFICIAL_BOT_ID = 8780479105
_REDPACKET_HANDLED_KEY = "bonus_redpacket_handled"


def _random_packet_command(text: str) -> str:
    """从 HHanClub 官方随机红包正文提取口令；结构不完整时拒绝。"""
    required = ("总额", "共", "发送口令", "领取", "过期")
    # 官方文案有「随机红包」和「普通红包」两种标题，均为可参与的口令红包。
    if not all(marker in text for marker in required) or not ("随机红包" in text or "普通红包" in text):
        return ""
    match = re.search(r"发送口令\s*[「『“\"]\s*([^\n「」『』“”\"]{1,100}?)\s*[」』”\"]\s*领取", text)
    if not match:
        return ""
    command = match.group(1).strip()
    if not command or any(ord(char) < 32 for char in command):
        return ""
    return command


__plugin__ = {
    "name": "憨憨赠豆",
    "id": "hhan_bonus",
    "version": "1.0.3",
    "author": "AWdress",
    "description": "使用平台同步的 HHCLUB Cookie，通过用户账号命令单人或批量赠送憨豆。",
    "icon": "https://hhanclub.net/favicon.ico",
    "changelog": "v1.0.3 兼容无提示成功响应\n- 站点返回 HTTP 200 且没有错误、登录或安全验证特征时直接判定赠豆完成\n- 成功结果标题和状态统一显示为“赠豆完成”“已完成”\n\nv1.0.2 修复赠送成功误判\n- HHCLUB 成功后直接返回普通赠豆页时按成功处理\n- 仅在错误提示、登录页或异常页面出现时判定失败\n- 结果清理时间至少为 10 秒，保存为 0 的旧配置自动恢复默认清理\n\nv1.0.1 美化赠豆结果\n- 单人和批量结果优先使用 Premium 原生富文本表格\n- 非会员账号由平台自动降级为整齐的普通文本\n- 移除代码块复制框，优化执行中、格式错误和结果提示\n\nv1.0.0 初始版本\n- 支持 .hh 单人赠豆与 .hhs 批量赠豆\n- Cookie 统一从平台 Cookie 同步读取，不在插件配置中保存\n- 支持登录检查、持久化冷却、安全站内跳转和赠送结果解析",
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
            "min": 10, "max": 600, "step": 10,
            "help": "命令执行提示和最终结果会自动清理，最短保留 10 秒。",
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
    return await cookie_header(ctx, path="/mybonus.php", request_sync=request_sync)


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

    page_lower = (resp.text or "").lower()
    if any(marker in page_lower for marker in (
        "cf-chl-", "challenge-platform", "cloudflare ray id", "checking your browser"
    )):
        return False, "站点触发了 Cloudflare 安全验证，请重新同步 Cookie"

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
    # HHCLUB 当前成功后可能仅返回普通页面，不提供 success tips，也不一定
    # 保留赠豆表单。已知业务失败均通过 .tips 返回，因此剩余的正常 200
    # 响应按完成处理，避免已实际扣豆却向用户误报失败。
    if not detail:
        return True, "赠豆完成"
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


def _rich_result(users: list[str], amount: int, note: str,
                 rows: list[tuple[str, bool, str]]) -> str:
    """生成 Premium 原生表格；普通账号由平台 send_rich 自动转为文本。"""
    esc = lambda value: html.escape(str(value), quote=True)
    if len(users) == 1:
        username, ok, detail = rows[0]
        title = "🫘 憨憨赠豆完成" if ok else "⚠️ 憨憨赠豆失败"
        values = [("状态", "✅ 已完成" if ok else "❌ 未送达"), ("接收用户", username)]
        if ok:
            values.extend([
                ("赠送数量", f"{amount:,} 憨豆"),
                ("预计到账", f"{_estimated_received(amount):,} 憨豆"),
                ("留言", note),
            ])
        else:
            values.append(("失败原因", detail or "未知错误"))
        table_rows = "".join(
            f'<tr><th align="left">{esc(label)}</th><td align="left">{esc(value)}</td></tr>'
            for label, value in values
        )
        return f'<h2>{title}</h2><table bordered striped>{table_rows}</table>'

    success_count = sum(1 for _, ok, _ in rows if ok)
    table_rows = [
        '<tr><th align="center">状态</th><th align="left">用户</th>'
        '<th align="right">赠送</th><th align="left">结果</th></tr>'
    ]
    for username, ok, detail in rows:
        result = f"预计到账 {_estimated_received(amount):,}" if ok else (detail or "未知错误")
        table_rows.append(
            f'<tr><td align="center">{"✅" if ok else "❌"}</td>'
            f'<td align="left">{esc(username)}</td>'
            f'<td align="right">{amount:,}</td><td align="left">{esc(result)}</td></tr>'
        )
    summary = f"成功 {success_count}/{len(rows)} · 每份 {amount:,} 憨豆"
    return (
        f'<h2>🫘 憨憨批量赠豆</h2><blockquote>{esc(summary)}</blockquote>'
        f'<table bordered striped>{"".join(table_rows)}</table>'
        f'<blockquote>💬 {esc(note)}</blockquote>'
    )


def _plain_result(users: list[str], amount: int, note: str,
                  rows: list[tuple[str, bool, str]]) -> str:
    if len(users) == 1:
        username, ok, detail = rows[0]
        if ok:
            return (
                "🫘 憨憨赠豆完成\n\n"
                f"👤 接收用户：{username}\n"
                f"🎁 赠送数量：{amount:,} 憨豆\n"
                f"💰 预计到账：{_estimated_received(amount):,} 憨豆\n"
                f"💬 留言：{note}"
            )
        return f"⚠️ 憨憨赠豆失败\n\n👤 接收用户：{username}\n❌ 原因：{detail or '未知错误'}"
    success_count = sum(1 for _, ok, _ in rows if ok)
    details = [
        f"{'✅' if ok else '❌'} {username}  "
        f"{'预计到账 ' + format(_estimated_received(amount), ',') if ok else (detail or '未知错误')}"
        for username, ok, detail in rows
    ]
    return (
        f"🫘 憨憨批量赠豆\n成功 {success_count}/{len(rows)} · 每份 {amount:,} 憨豆\n"
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

    @ctx.action("test_bonus_cookie")
    async def test_cookie():
        ok, message = await _check_login(ctx)
        return {"ok": ok, "message": message}

    @ctx.on_api("/bonus/cookie/check", methods=["GET"])
    async def api_cookie_check(_request=None):
        return await test_cookie()

    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-9)
    async def gift_command(client, message):
        cfg = ctx.config
        if not cfg.get("bonus_enabled", cfg.get("enabled", True)):
            return
        text = (message.text or "").strip()
        head = _head(text)
        single = _bare(cfg.get("single_command", ".hh"), "hh")
        batch = _bare(cfg.get("batch_command", ".hhs"), "hhs")
        if head not in {single, batch}:
            return

        try:
            delete_after = max(10, int(cfg.get("result_delete", 90) or 90))
        except (TypeError, ValueError):
            delete_after = 90
        if head == single:
            parts = text.split(maxsplit=3)
            if len(parts) < 4 or _amount(parts[2]) is None:
                edited = await message.edit(
                    "⚠️ 格式不正确\n\n用法：.hh 用户名 数量 留言\n示例：.hh Alice 100 感谢分享"
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
                    "⚠️ 格式不正确\n\n用法：.hhs 用户1 用户2 ... 数量 留言\n示例：.hhs Alice Bob 100 感谢"
                )
                _schedule_delete(edited, 20)
                return
            users = parts[1:-2]
            amount = _amount(parts[-2]) or 0
            note = parts[-1]

        if len(users) > 50:
            edited = await message.edit("⚠️ 单次批量最多赠送 50 位用户，请拆分后重试。")
            _schedule_delete(edited, 20)
            return

        if not users or not note:
            edited = await message.edit("⚠️ 用户名、赠送数量和留言均不能为空。")
            _schedule_delete(edited, 20)
            return
        if _gift_lock and _gift_lock.locked():
            edited = await message.edit("⏳ 已有赠豆任务正在执行，请稍后再试。")
            _schedule_delete(edited, 20)
            return

        status = await message.edit("🫘 憨豆正在打包发送，请稍候…")
        result_rows: list[tuple[str, bool, str]] = []
        async with _gift_lock:
            for username in users:
                await _wait_cooldown()
                ok, detail = await _gift(ctx, username, amount, note)
                _mark_gift()
                ctx.log.info(
                    "[憨憨赠豆] user=%s amount=%s ok=%s detail=%s",
                    username, amount, ok, detail,
                )
                result_rows.append((username, ok, detail))
                if not ok:
                    await _cookie_error_notify(detail)

        rich = _rich_result(users, amount, note, result_rows)
        plain = _plain_result(users, amount, note, result_rows)
        sent = None
        try:
            supports_rich = bool(
                ctx.user and await ctx.user.supports_native_rich()
            )
            if supports_rich:
                sent = await ctx.user.send_rich(message.chat.id, rich, format="html")
                await status.delete()
            else:
                sent = await status.edit(plain)
        except Exception as exc:  # noqa: BLE001 - 富文本不可用时回退编辑原消息
            ctx.log.warning("[憨憨赠豆] 富文本结果发送失败，回退普通文本：%r", exc)
            sent = await status.edit(plain)
        _schedule_delete(sent, delete_after)

    @ctx.on_message(ctx.filters.incoming & ctx.filters.text, group=-10)
    async def auto_confirm_transfer(client, message):
        """仅自动确认官方机器人对本账号赠豆命令发出的二次确认。"""
        if not ctx.config.get("auto_confirm_bonus_transfer", False):
            return
        sender = getattr(message, "from_user", None)
        if not sender or int(getattr(sender, "id", 0) or 0) != _OFFICIAL_BOT_ID:
            return
        replied = getattr(message, "reply_to_message", None)
        replied_sender = getattr(replied, "from_user", None) if replied else None
        if not replied_sender or not getattr(replied_sender, "is_self", False):
            return
        text = str(getattr(message, "text", "") or "")
        required = ("确认憨豆转赠", "接收人", "转出", "手续费", "实际到账", "2 分钟内确认")
        if not all(marker in text for marker in required):
            return
        markup = getattr(message, "reply_markup", None)
        rows = getattr(markup, "inline_keyboard", None) if markup else None
        confirm_position = None
        for row_index, row in enumerate(rows or []):
            for column_index, button in enumerate(row):
                label = "".join(str(getattr(button, "text", "") or "").split())
                if label in {"确认赠送", "✅确认赠送", "☑️确认赠送"}:
                    confirm_position = (row_index, column_index)
                    break
            if confirm_position is not None:
                break
        if confirm_position is None:
            ctx.log.warning("[憨憨赠豆] 收到官方转赠确认消息，但未找到精确的“确认赠送”按钮")
            return
        try:
            result = await message.click(x=confirm_position[1], y=confirm_position[0], timeout=10)
            detail = getattr(result, "message", None) or getattr(result, "text", None) or str(result or "已提交")
            ctx.log.info("[憨憨赠豆] 已自动确认转赠：msg=%s result=%s", message.id, detail)
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("[憨憨赠豆] 自动确认转赠失败：msg=%s error=%r", message.id, exc)

    @ctx.on_message(ctx.filters.incoming & ctx.filters.group & ctx.filters.text, group=-10)
    async def auto_grab_random_packet(client, message):
        """解析官方机器人随机红包口令，随机延迟后使用用户账号参与。"""
        cfg = ctx.config
        if not cfg.get("auto_grab_random_packet", False):
            return
        sender = getattr(message, "from_user", None)
        if not sender or int(getattr(sender, "id", 0) or 0) != _OFFICIAL_BOT_ID:
            return
        text = str(getattr(message, "text", "") or "")
        command = _random_packet_command(text)
        if not command:
            if ("随机红包" in text or "普通红包" in text) and "发送口令" in text:
                ctx.log.warning("[憨憨红包] 收到官方随机红包，但正文结构或口令无效：msg=%s", message.id)
            return
        chat_id = int(getattr(getattr(message, "chat", None), "id", 0) or 0)
        message_id = int(getattr(message, "id", 0) or 0)
        if not chat_id or not message_id:
            return
        me = getattr(client, "me", None)
        account_id = int(getattr(me, "id", 0) or 0)
        packet_key = f"{account_id}:{chat_id}:{message_id}"
        handled = ctx.kv.get(_REDPACKET_HANDLED_KEY, []) or []
        handled = [str(item) for item in handled] if isinstance(handled, list) else []
        if packet_key in handled:
            return
        ctx.kv.set(_REDPACKET_HANDLED_KEY, [packet_key, *handled][:300])

        try:
            delay_min = max(0.0, min(float(cfg.get("random_packet_delay_min", 1) or 0), 3600.0))
            delay_max = max(0.0, min(float(cfg.get("random_packet_delay_max", 5) or 0), 3600.0))
        except (TypeError, ValueError):
            delay_min, delay_max = 1.0, 5.0
        if delay_min > delay_max:
            delay_min, delay_max = delay_max, delay_min
        delay = random.uniform(delay_min, delay_max)
        ctx.log.info(
            "[憨憨红包] 识别随机红包：chat=%s msg=%s，将在 %.1f 秒后发送口令 %r",
            chat_id, message_id, delay, command,
        )

        async def send_command():
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                sent = await client.send_message(chat_id, command)
                ctx.log.info(
                    "[憨憨红包] 已发送随机红包口令：chat=%s packet=%s sent=%s command=%r",
                    chat_id, message_id, getattr(sent, "id", 0), command,
                )
            except Exception as exc:  # noqa: BLE001
                latest = ctx.kv.get(_REDPACKET_HANDLED_KEY, []) or []
                if isinstance(latest, list):
                    ctx.kv.set(_REDPACKET_HANDLED_KEY, [item for item in latest if str(item) != packet_key])
                ctx.log.warning("[憨憨红包] 发送随机红包口令失败：msg=%s error=%r", message_id, exc)

        ctx.create_task(send_command(), name="憨憨随机红包延迟参与", operation="auto_grab_packet")


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
