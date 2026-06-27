# =============================================================================
# AWBotNest 插件：U2 送糖（u2_dmhy）
#
# 用 /u2 或 /u2s 命令，带你的 u2.dmhy.org cookie，给指定用户赠送 UCoin。
#   /u2 用户ID 数量 附言            —— 单人赠送
#   /u2s 用户1 用户2 ... 数量 附言  —— 批量赠送（每个间隔约 5 分钟，u2 站限频）
#
# 这是「主动送礼」命令（HTTP 调 u2 站），不是转账监听。cookie 在配置里填。
# =============================================================================

import asyncio
import time

import httpx

__plugin__ = {
    "name": "U2送糖",
    "id": "u2_dmhy",
    "version": "1.0.0",
    "author": "AWdress",
    "description": "用 /u2 或 /u2s 带 cookie 给 u2.dmhy.org 用户赠送 UCoin。单人/批量，自带站点限频冷却。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "cookie": {
            "type": "password", "default": "", "label": "u2 Cookie",
            "section": "凭据", "help": "浏览器 F12 复制 u2.dmhy.org 的整条 Cookie 头。",
        },
        "cooldown_seconds": {
            "type": "number", "default": 300, "label": "赠送冷却(秒)",
            "min": 0, "max": 1200, "section": "参数",
            "help": "两次赠送的最小间隔（u2 站限频，建议 ≥300）。批量时每个之间也按此间隔。",
        },
        "u2_command": {
            "type": "string", "default": ".u2", "label": "单人命令", "section": "命令",
            "help": "单人赠送命令。/u2 与 .u2 等价。",
        },
        "u2s_command": {
            "type": "string", "default": ".u2s", "label": "批量命令", "section": "命令",
        },
        "result_delete": {
            "type": "slider", "default": 90, "label": "结果自动删除(秒)",
            "min": 0, "max": 300, "step": 10, "section": "参数",
        },
    },
}

_URL = "https://u2.dmhy.org/mpshop.php"
_KV_LAST = "last_pay_ts"


def _bare(cmd: str, default: str) -> str:
    return (cmd or "").lstrip("/.").strip().lower() or default


def _head(text: str) -> str:
    return text.split(maxsplit=1)[0].lstrip("/.").lower() if text else ""


async def _gift(cookie: str, recv_id: str, amount: str, note: str, log):
    """调 u2 mpshop 送 UCoin。返回 (成功, 详情)。"""
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh",
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    data = {"event": "1003", "recv": str(recv_id), "amount": str(amount), "message": str(note)}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_URL, headers=headers, data=data)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            h2 = soup.select_one("h2")
            if h2:
                tables = soup.select("table")
                if tables:
                    detail = tables[-1].get_text(strip=True).split("。")[0]
                    return True, f"{h2.get_text(strip=True)} ：\n    {detail}"
                return True, "无提示信息（无表格）"
            return True, "无提示信息（无 h2）"
        except Exception:  # noqa: BLE001 - 解析失败也算请求成功
            return True, "已提交（响应解析略过）"
    except Exception as e:  # noqa: BLE001
        log.error("[U2送糖] 请求失败: %r", e)
        return False, f"请求失败：{e}"


async def setup(ctx):
    async def _wait_cooldown():
        """按冷却间隔等待到可赠送。"""
        try:
            cd = float(ctx.config.get("cooldown_seconds", 300) or 0)
        except (ValueError, TypeError):
            cd = 300
        if cd <= 0:
            return
        last = float(ctx.kv.get(_KV_LAST, 0) or 0)
        remaining = cd - (time.time() - last)
        if remaining > 0:
            await asyncio.sleep(remaining)

    def _mark_pay():
        ctx.kv.set(_KV_LAST, time.time())

    async def _autodel(msg, delay):
        if delay <= 0 or not msg:
            return
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except Exception:
            pass

    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-9)
    async def u2_gift(client, message):
        cfg = ctx.config
        text = (message.text or "").strip()
        head = _head(text)
        u2 = _bare(cfg.get("u2_command", ".u2"), "u2")
        u2s = _bare(cfg.get("u2s_command", ".u2s"), "u2s")
        is_batch = head == u2s
        if head not in (u2, u2s):
            return

        if not cfg.get("cookie"):
            return await message.edit("❌ 未配置 u2 Cookie")

        parts = text.split()
        delete_after = int(cfg.get("result_delete", 90) or 0)

        if is_batch:
            # /u2s 用户1 用户2 ... 数量 附言
            if len(parts) <= 3:
                r = await message.edit("```\n格式：/u2s user1 user2 ... 数量 附言```")
                return await _autodel(r, 20)
            users, bonus, note = parts[1:-2], parts[-2], parts[-1]
            status = await message.edit("```\nU2 糖发射中···```")
            result = ""
            for i, user in enumerate(users):
                await _wait_cooldown()
                ok, detail = await _gift(cfg["cookie"], user, bonus, note, ctx.log)
                _mark_pay()
                result += (f"🎉 成功赠与 {user} {bonus} UCoin\n" if ok
                           else f"❌ 赠与 {user} 失败: {detail or '未知'}\n")
            r = await status.reply(f"```\n{result}```")
            await _autodel(status, delete_after)
            await _autodel(r, delete_after)
        else:
            # /u2 用户 数量 附言
            if len(parts) != 4:
                r = await message.edit("```\n格式：/u2 用户ID 数量 附言```")
                return await _autodel(r, 20)
            user, bonus, note = parts[1], parts[2], parts[3]
            await message.edit("```\n幼儿糖发射中···```")
            await _wait_cooldown()
            ok, detail = await _gift(cfg["cookie"], user, bonus, note, ctx.log)
            _mark_pay()
            r = await message.edit(
                f"```\n🎉 成功赠与 {user} {bonus} UCoin```" if ok
                else f"```\n❌ 赠与 {user} 失败\n原因: {detail}```"
            )
            await _autodel(r, delete_after)


async def teardown(ctx):
    pass
