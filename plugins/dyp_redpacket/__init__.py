# =============================================================================
# AWBotNest 插件：癫影积分红包（dyp_redpacket）
#
# 监控「癫影小助手」在癫影积分红包固定群发的积分红包，逐个点击未抢的数字按钮，
# 抢到一格即停（/已抢的、含中文的管理员按钮自动跳过）。
#
# 从原「抢红包(red_packet)」插件拆出独立维护。拼手气红包见 hdsky_redpacket，
# 口令红包见 yingchao_redpacket，三者互不影响。
#
# 注意：本插件用「用户账号」监听并点击红包（scope=user）。发包 bot 与群组按原项目写死。
# =============================================================================
from __future__ import annotations

import asyncio
import time as _time

from ._records import Records, to_float
from ._snatch import extract_text, find_numbered_buttons, is_snatch_success

__plugin__ = {
    "name": "癫影积分红包",
    "id": "dyp_redpacket",
    "version": "1.0.2",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "监控癫影小助手发的积分红包，逐个点击未抢数字按钮（1~9 已抢的跳过），抢到一格即停。发包bot/群组内置写死。",
    "config_schema": {
        "dyp_enabled": {
            "type": "boolean", "default": False, "label": "启用癫影积分红包",
            "section": "癫影积分红包",
            "help": "癫影小助手发的积分红包，逐个点击未抢数字按钮（1~9 已抢的跳过）。",
        },
        "dyp_delay": {
            "type": "slider", "default": 0, "label": "点击延迟(秒)",
            "min": 0, "max": 60, "step": 1, "section": "癫影积分红包",
            "show_if": {"dyp_enabled": True},
        },
        "notify_owner": {
            "type": "boolean", "default": True, "label": "抢包结果通知我",
            "section": "通用", "help": "抢到/未抢到时用机器人通知平台主人。",
        },
    },
}

# 按钮点击去重（进程内，TTL 清理）：key = "acct:chat:msg" → 时间戳
_clicked: dict[str, float] = {}
_CLICKED_TTL = 3600

# 发包机器人 / 癫影群（原项目写死，非可配）
_DYP_BOT_ID = 8704462066        # 癫影小助手（积分红包）
_DYP_GROUP_ID = -1003907877852  # 癫影积分红包固定群


def _prune_clicked() -> None:
    now = _time.time()
    for k in [k for k, ts in _clicked.items() if now - ts > _CLICKED_TTL]:
        _clicked.pop(k, None)


def _click_once(client, message) -> bool:
    """点击去重：返回 True 表示首次（可点击），False 表示已点过。"""
    me = getattr(client, "me", None)
    acct_id = me.id if me else id(client)
    key = f"{acct_id}:{message.chat.id}:{message.id}"
    _prune_clicked()
    if key in _clicked:
        return False
    _clicked[key] = _time.time()
    return True


async def setup(ctx):
    records = Records(ctx.kv, ctx.log)

    # ───────── 逐格点击 ─────────
    @ctx.on_message(ctx.filters.group, group=-9)
    async def on_dyp_packet(client, message):
        cfg = ctx.config
        if not cfg.get("dyp_enabled", False):
            return
        fu = message.from_user
        if not (fu and getattr(fu, "is_bot", False) and fu.id == _DYP_BOT_ID):
            return
        if "积分红包" not in extract_text(message):
            return
        if message.chat.id != _DYP_GROUP_ID:
            return
        if not _click_once(client, message):
            return

        delay = to_float(cfg.get("dyp_delay", 0))
        if delay > 0:
            await asyncio.sleep(delay)

        positions = find_numbered_buttons(message)
        if not positions:
            ctx.log.debug("[癫影积分红包] 无可点按钮 msg=%s", message.id)
            return
        ctx.log.info("[癫影积分红包] 找到 %d 个未抢按钮，逐格尝试", len(positions))

        for idx, (row, col) in enumerate(positions, start=1):
            try:
                result = await message.click(x=col, y=row, timeout=10)
                rtext = getattr(result, "text", None) or getattr(result, "message", None) or ""
                rstr = rtext or str(result)
                ctx.log.info("[癫影积分红包] 第%d格(行%d列%d) 结果=%r", idx, row, col, rstr)
                if is_snatch_success(rstr):
                    records.add_history({"type": "癫影积分红包", "group_id": message.chat.id, "result": rstr, "ok": True})
                    if cfg.get("notify_owner", True):
                        await _notify(ctx, client,
                            f"癫影积分红包-已抢\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n{rstr}\n\n{getattr(message,'link','')}",
                            level="success")
                    return
                await asyncio.sleep(0.3)
            except Exception as e:  # noqa: BLE001
                ctx.log.warning("[癫影积分红包] 第%d格点击异常: %r", idx, e)
                await asyncio.sleep(0.3)
        # 全部试完未抢到
        if cfg.get("notify_owner", True):
            await _notify(ctx, client,
                f"癫影积分红包-未抢到\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n所有格子均已被抢完",
                level="info")

    ctx.log.info("[癫影积分红包] 已加载")


async def _notify(ctx, client, text, level="info"):
    try:
        await ctx.notify(text, level=level, category="癫影积分红包", account=client)
    except Exception:  # noqa: BLE001
        pass


async def teardown(ctx):
    _clicked.clear()
