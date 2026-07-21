# =============================================================================
# AWBotNest 插件：拼手气红包(HDSKY)（hdsky_redpacket）
#
# 监控天空(HDSKY)群里「天空小秘」发的拼手气红包，自动点击「抢红包」内联按钮。
# 可选 /red 占位发言，应对「限最近发言人」的红包。
#
# 从原「抢红包(red_packet)」插件拆出独立维护。癫影积分红包见 dyp_redpacket，
# 口令红包见 yingchao_redpacket，三者互不影响。
#
# 注意：本插件用「用户账号」监听并点击红包（scope=user），请仅在可信群启用。
# =============================================================================
from __future__ import annotations

import asyncio
import time as _time

from ._records import Records, parse_groups, to_float
from ._snatch import find_snatch_button, is_lucky_packet

__plugin__ = {
    "name": "拼手气红包(HDSKY)",
    "id": "hdsky_redpacket",
    "version": "1.0.4",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "监控天空(HDSKY)群拼手气红包，自动点击「抢红包」按钮。可选 /red 占位发言应对「限最近发言人」。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_redpacket.png",
    "changelog": "v1.0.4 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "config_schema": {
        "button_enabled": {
            "type": "boolean", "default": False, "label": "启用拼手气红包",
            "section": "拼手气红包",
            "help": "检测「拼手气红包」消息并自动点击「抢红包」内联按钮。",
        },
        "button_groups": {
            "type": "string", "default": "", "label": "监听群组ID",
            "section": "拼手气红包", "show_if": {"button_enabled": True},
            "help": "逗号分隔的群组ID，留空=所有群。",
        },
        "button_delay": {
            "type": "slider", "default": 0, "label": "点击延迟(秒)",
            "min": 0, "max": 60, "step": 1, "section": "拼手气红包",
            "show_if": {"button_enabled": True},
        },
        "button_pre_send": {
            "type": "boolean", "default": False, "label": "发言占位（/red前）",
            "section": "拼手气红包", "show_if": {"button_enabled": True},
            "help": "检测到 /red 发包命令时先发一条消息占位（随即删除），应对「限最近发言人」。",
        },
        "button_pre_send_text": {
            "type": "string", "default": ".", "label": "占位消息内容",
            "section": "拼手气红包", "show_if": {"button_enabled": True},
        },
        "notify_owner": {
            "type": "boolean", "default": True, "label": "抢包结果通知我",
            "section": "通用", "help": "抢到/失败时用机器人通知平台主人。",
        },
    },
}

# 按钮点击去重（进程内，TTL 清理）：key = "acct:chat:msg" → 时间戳
_clicked: dict[str, float] = {}
_CLICKED_TTL = 3600

# 发包机器人（原项目写死，非可配）
_HDSKY_BOT_ID = 8907007783      # 天空小秘 HDSKY（拼手气红包）


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

    # ───────── /red 占位发言 ─────────
    @ctx.on_message(ctx.filters.group & ctx.filters.regex(r"^/red(@[\w]+)?(\s|$)"), group=-10)
    async def on_red_command(client, message):
        cfg = ctx.config
        if not cfg.get("button_enabled", False) or not cfg.get("button_pre_send", False):
            return
        groups = parse_groups(cfg.get("button_groups", ""))
        if groups and message.chat.id not in groups:
            return
        try:
            pre = cfg.get("button_pre_send_text", ".") or "."
            m = await client.send_message(message.chat.id, pre)
            await m.delete()
            ctx.log.debug("[拼手气红包] /red 占位发言 chat=%s", message.chat.id)
        except Exception as e:  # noqa: BLE001
            ctx.log.debug("[拼手气红包] /red 占位失败: %r", e)

    # ───────── 点击抢红包按钮 ─────────
    @ctx.on_message(ctx.filters.group, group=-9)
    async def on_button_packet(client, message):
        cfg = ctx.config
        if not cfg.get("button_enabled", False):
            return
        fu = message.from_user
        if not (fu and getattr(fu, "is_bot", False) and fu.id == _HDSKY_BOT_ID):
            return
        groups = parse_groups(cfg.get("button_groups", ""))
        if groups and message.chat.id not in groups:
            return
        if not is_lucky_packet(message):
            return
        pos = find_snatch_button(message)
        if not pos:
            return
        if not _click_once(client, message):
            return

        delay = to_float(cfg.get("button_delay", 0))
        if delay > 0:
            await asyncio.sleep(delay)
        row, col = pos
        try:
            result = await message.click(x=col, y=row, timeout=10)
            rtext = getattr(result, "text", None) or getattr(result, "message", None) or str(result)
            ctx.log.info("[拼手气红包] 已点击 chat=%s msg=%s 结果=%s", message.chat.id, message.id, rtext)
            records.add_history({"type": "拼手气红包", "group_id": message.chat.id, "result": str(rtext), "ok": True})
            if cfg.get("notify_owner", True):
                await _notify(ctx, client,
                    f"拼手气红包-已抢\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n{rtext}\n\n{getattr(message,'link','')}",
                    level="success")
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[拼手气红包] 点击失败 chat=%s msg=%s: %r", message.chat.id, message.id, e)
            if cfg.get("notify_owner", True):
                await _notify(ctx, client,
                    f"拼手气红包-点击失败\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n{e}",
                    level="error")

    ctx.log.info("[拼手气红包] 已加载")


async def _notify(ctx, client, text, level="info"):
    try:
        await ctx.notify(text, level=level, category="拼手气红包", account=client)
    except Exception:  # noqa: BLE001
        pass


async def teardown(ctx):
    _clicked.clear()
