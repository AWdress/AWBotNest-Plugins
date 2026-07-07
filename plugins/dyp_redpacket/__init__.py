# =============================================================================
# AWBotNest 插件：癫影积分红包（dyp_redpacket）
#
# 监控「癫影小助手」在癫影积分红包固定群发的积分红包，逐个点击未抢的数字按钮，
# 落地一格即停（/已抢的、含中文的管理员按钮自动跳过）。
#
# 癫影已改为「混合红包」：一条消息 M 格、暗含 N 个雷包、其余给分（如
# 「分值: 50 · 份数: 9 · 暗含 1 个雷包 · 余位: 9/9」）。不再有整包都是陷阱的
# 纯雷包消息，故不再按文案「见雷包就整包跳过」——那样会漏掉所有红包。策略改为
# 照抢、赌不中雷：点到一格落地（抢到分 or 踩雷）就算用掉唯一机会、停手；只有
# 「手慢了/已被抢」才继续点下一格。
#
# 从原「抢红包(red_packet)」插件拆出独立维护。拼手气红包见 hdsky_redpacket，
# 口令红包见 yingchao_redpacket，三者互不影响。
#
# 注意：本插件用「用户账号」监听并点击红包（scope=user）。发包 bot 与群组按原项目写死。
# =============================================================================
from __future__ import annotations

import asyncio
import random
import time as _time

from ._records import Records, to_float
from ._snatch import (
    extract_text,
    find_numbered_buttons,
    is_snatch_success,
    is_thunder_hit,
    parse_packet_meta,
)

__plugin__ = {
    "name": "癫影积分红包",
    "id": "dyp_redpacket",
    "version": "1.2.0",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "监控癫影小助手发的混合积分红包（暗含 N 个雷包），逐个点击未抢数字按钮，落地一格即停：抢到分或踩雷都算用掉唯一机会停手，只有「手慢了/已被抢」才试下一格。发包bot/群组内置写死。",
    "config_schema": {
        "dyp_enabled": {
            "type": "boolean", "default": False, "label": "启用癫影积分红包",
            "section": "癫影积分红包",
            "help": "癫影小助手发的积分红包，逐个点击未抢数字按钮（1~9 已抢的跳过）。现为混合红包（暗含 N 个雷包），照抢、赌不中雷。",
        },
        "dyp_delay": {
            "type": "slider", "default": 0, "label": "点击延迟-最小(秒)",
            "min": 0, "max": 60, "step": 1, "section": "癫影积分红包",
            "show_if": {"dyp_enabled": True},
            "help": "抢包前等待的最小秒数。与「点击延迟-最大」配合：最大>最小时在两者间取随机值，别太机械；相等或最大更小则固定等这么久。",
        },
        "dyp_delay_max": {
            "type": "slider", "default": 0, "label": "点击延迟-最大(秒)",
            "min": 0, "max": 60, "step": 1, "section": "癫影积分红包",
            "show_if": {"dyp_enabled": True},
            "help": "抢包前等待的最大秒数。填得比「最小」大即启用随机延迟(每次在最小~最大间随机)；填 0 或不大于最小则退化为固定延迟。",
        },
        "notify_owner": {
            "type": "boolean", "default": True, "label": "抢到/踩雷时通知我",
            "section": "通用", "help": "抢到红包或踩雷时用机器人通知平台主人；未抢到（都被别人抢完）仅记录日志不通知。",
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


def _meta_brief(meta: dict) -> str:
    """把红包元信息压成一行便于日志/通知。"""
    parts = []
    if meta.get("value") is not None:
        parts.append(f"分值{meta['value']}")
    if meta.get("shares") is not None:
        parts.append(f"份数{meta['shares']}")
    if meta.get("mines") is not None:
        parts.append(f"雷{meta['mines']}")
    if meta.get("total") is not None:
        parts.append(f"余位{meta.get('left')}/{meta['total']}")
    return " · ".join(parts)


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
        if message.chat.id != _DYP_GROUP_ID:
            return
        # 该 bot 在该群只发红包，匹配「红包」即可。混合红包文案含「红包」（也含「雷包」，
        # 但已不再据此整包跳过）。
        caption = extract_text(message)
        if "红包" not in caption:
            return
        if not _click_once(client, message):
            return

        meta = parse_packet_meta(caption)
        brief = _meta_brief(meta)

        delay = to_float(cfg.get("dyp_delay", 0))
        delay_max = to_float(cfg.get("dyp_delay_max", 0))
        if delay_max > delay:
            delay = random.uniform(delay, delay_max)
        if delay > 0:
            ctx.log.info("[癫影积分红包] 点击前随机延迟 %.2f 秒", delay)
            await asyncio.sleep(delay)

        positions = find_numbered_buttons(message)
        if not positions:
            ctx.log.debug("[癫影积分红包] 无可点按钮 msg=%s", message.id)
            return
        ctx.log.info("[癫影积分红包] %s，找到 %d 个未抢按钮，逐格尝试（落地即停）",
                     brief or "红包", len(positions))

        for idx, (row, col) in enumerate(positions, start=1):
            try:
                result = await message.click(x=col, y=row, timeout=10)
                rtext = getattr(result, "text", None) or getattr(result, "message", None) or ""
                rstr = rtext or str(result)
                ctx.log.info("[癫影积分红包] 第%d格(行%d列%d) 结果=%r", idx, row, col, rstr)

                if is_snatch_success(rstr):
                    records.add_history({"type": "癫影积分红包", "group_id": message.chat.id,
                                         "meta": brief, "result": rstr, "ok": True})
                    if cfg.get("notify_owner", True):
                        await _notify(ctx, client,
                            f"癫影积分红包-已抢\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n{brief}\n\n{rstr}\n\n{getattr(message,'link','')}",
                            level="success")
                    return

                if is_thunder_hit(rstr):
                    # 踩雷 = 用掉唯一一次机会，停手，别再点（赌输了）。
                    ctx.log.info("[癫影积分红包] 踩雷，停手 msg=%s 结果=%r", message.id, rstr)
                    records.add_history({"type": "癫影积分红包", "group_id": message.chat.id,
                                         "meta": brief, "result": rstr, "ok": False, "mine": True})
                    if cfg.get("notify_owner", True):
                        await _notify(ctx, client,
                            f"癫影积分红包-踩雷\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n{brief}\n\n{rstr}\n\n{getattr(message,'link','')}",
                            level="warning")
                    return

                # 其余（手慢了/已被抢/无内容）→ 该格已被他人抢走，试下一格。
                await asyncio.sleep(0.3)
            except Exception as e:  # noqa: BLE001
                ctx.log.warning("[癫影积分红包] 第%d格点击异常: %r", idx, e)
                await asyncio.sleep(0.3)
        # 全部试完，落地格全被别人抢走，自己没抢到
        ctx.log.info("[癫影积分红包] 所有格子均已被抢完，未抢到 msg=%s", message.id)
        records.add_history({"type": "癫影积分红包", "group_id": message.chat.id,
                             "meta": brief, "result": "未抢到", "ok": False})

    ctx.log.info("[癫影积分红包] 已加载")


async def _notify(ctx, client, text, level="info"):
    try:
        await ctx.notify(text, level=level, category="癫影积分红包", account=client)
    except Exception:  # noqa: BLE001
        pass


async def teardown(ctx):
    _clicked.clear()
