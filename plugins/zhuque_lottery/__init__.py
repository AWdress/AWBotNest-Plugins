# =============================================================================
# AWBotNest 插件：朱雀（zhuque_lottery）
#
# 朱雀（https://zhuque.in）PT 站自动化合集，迁移自 AWLottery 的「朱雀系列」。
# 子功能（均可在配置面板分区开关）：
#   1. 个人信息查询  /getinfo      —— HTTP getInfo
#   2. 大转盘抽奖    /prizewheel N —— HTTP spinThePrizeWheel
#   3. 倍投起手表    /betbonus c n —— 纯计算
#   4. 魔法卡定时    （ctx.schedule）—— HTTP fireGenshinCharacterMagic
#   5. 大劫/反击     （群内监听 zhuque bot）—— 自动反打劫 + 概率返现
#   6. 红包雨        （群内监听）—— 自动抢红包（点回调）
#   7. 灵石转账记录  （群内监听）—— 记 kv + 可选通知
#   8. 鳄鱼丼 YDX    （群内监听+下注）—— 骰子大小投注（默认关闭，需实盘校验）
#
# 迁移铁律：禁止 import pyrogram/core/config/...；一切走 ctx。
#   - cookie / x-csrf-token：config password 字段（浏览器 F12 抓）。
#   - 旧 ZHUQUE state section / Zhuqueydx 表 → ctx.kv。
#   - MY_TGID → ctx.owner_id；通知 → ctx.notify；TARGET 群组 → config。
#   - HTTP 用 httpx（第三方库，可 import），封装在 _api.py。
# =============================================================================
from __future__ import annotations

import asyncio
import random
import re
import time
from datetime import datetime, date
from decimal import Decimal

import httpx

from ._api import (
    ZhuqueAPI, INFO_FIELDS, WHEEL_PRIZES, CARD_BONUS_VALUES, CARD_NAMES, SPIN_COST,
)
from ._helpers import (
    calc_starting_bet, extract_lingshi_amount, build_reply_messages,
    parse_blacklist, safe_int,
)
from . import _ydx


__plugin__ = {
    "name": "朱雀",
    "id": "zhuque_lottery",
    "version": "1.0.6",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
    "description": "朱雀PT站自动化：个人查询、大劫反击、红包雨、大转盘、转账、鳄鱼丼投注、魔法卡定时、道具卡回收、倍投计算。自带 Vue 配置界面 + 战绩/记录管理。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/zhuque_lottery.png",
    "changelog": "v1.0.6 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
}

# vue 模式无 config_schema：配置默认值集中此处备查（后端各处 ctx.config.get(k, 默认) 已带默认，
# 前端 Config.vue 用同一套默认初始化表单）。
DEFAULTS = {
    "cookie": "", "xcsrf": "", "my_name": "我",
    "enable_getinfo": True, "getinfo_command": "getinfo",
    "enable_prizewheel": True, "prizewheel_command": "prizewheel", "prize_tasks": 4,
    "enable_betbonus": True, "betbonus_command": "betbonus",
    "enable_firegenshin": False, "firegenshin_interval": 20,
    "enable_raiding": False, "fanda_mode": "off", "fanxian": False,
    "fanxian_probability": 1, "fanxian_blacklist": "", "raid_cd_minutes": 5,
    "enable_redpocket": False, "redpocket_max_retry": 20,
    "enable_transform": False, "transform_notification": False,
    "transform_leaderboard": False, "transform_payleaderboard": False,
    "enable_ydx": False, "ydx_dice_reveal": True, "ydx_dice_bet": False,
    "ydx_wwd_switch": False, "ydx_start_count": 5, "ydx_stop_count": 5,
    "ydx_start_bouns": 500, "ydx_bet_model": "a",
    "enable_card": False, "card_command": "card",
    "card_id_1": "1", "card_id_2": "2", "card_id_3": "3", "card_id_4": "4",
    "owner_notify": True,
}


# ─── 写死常量（PT 站固定信息，照原项目，不做成可配字段）─────────────────────
# 朱雀官方 bot 的 Telegram 数字ID（原 custom_filters.zhuque_bot）。
_ZHUQUE_BOT_ID = 5697370563
# 各子功能监听群组，各不相同，全部写死（原各 *_zhuque.py 的模块级 TARGET）。
_RAID_GROUPS = [-1001833464786, -1002262543959, -1002522450068]      # raiding_zhuque.py
_REDPOCKET_GROUPS = [-1001833464786, -1002262543959]                 # redpocket_pie_zhuque.py
_YDX_GROUPS = [-1002262543959]                                       # ydx_zhuque.py
_TRANSFORM_GROUPS = [-1001833464786, -1002262543959]                 # transform_zhuque.py


# ─── 模块级运行态（每次 setup 重建）──────────────────────────────────────────
def _new_state():
    return {
        "bet_models": _ydx.make_models(),
        "big_count": 0,
        "small_count": 0,
        "bet_count": 0,
    }


async def setup(ctx):
    cfg = ctx.config
    state = _new_state()
    ydx_store = _ydx.YdxStore(ctx)

    ctx.log.info("朱雀插件已启用")

    def _api() -> ZhuqueAPI:
        return ZhuqueAPI(ctx.config.get("cookie", ""), ctx.config.get("xcsrf", ""), ctx.log)

    def _is_zhuque_bot(message) -> bool:
        fu = getattr(message, "from_user", None)
        return bool(fu and getattr(fu, "is_bot", False) and fu.id == _ZHUQUE_BOT_ID)

    def _reply_to_me(message) -> bool:
        r = getattr(message, "reply_to_message", None)
        return bool(r and getattr(r, "from_user", None) and getattr(r.from_user, "is_self", False))

    # ── 命令处理（getinfo / prizewheel / betbonus）──────────────────────────
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-8, target="user")
    async def on_command(client, message):
        text = (message.text or "").strip()
        if not text or text[0] not in "/.":
            return
        parts = text[1:].split()
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]
        c = ctx.config
        try:
            if c.get("enable_getinfo", True) and cmd == (c.get("getinfo_command", "getinfo") or "getinfo").lower():
                await _handle_getinfo(ctx, _api, message)
            elif c.get("enable_prizewheel", True) and cmd == (c.get("prizewheel_command", "prizewheel") or "prizewheel").lower():
                await _handle_prizewheel(ctx, _api, client, message, args)
            elif c.get("enable_betbonus", True) and cmd == (c.get("betbonus_command", "betbonus") or "betbonus").lower():
                await _handle_betbonus(ctx, message, args)
            elif c.get("enable_card", False) and cmd == (c.get("card_command", "card") or "card").lower():
                await _handle_card(ctx, _api, message, args)
        except Exception as e:
            ctx.log.error("命令处理出错 cmd=%s: %s", cmd, e)

    # ── 大劫监听/反击 ──────────────────────────────────────────────────────
    @ctx.on_message(ctx.filters.incoming & ctx.filters.text, group=-7, target="user")
    async def on_raiding(client, message):
        if not ctx.config.get("enable_raiding", False):
            return
        if message.chat.id not in _RAID_GROUPS:
            return
        if not _is_zhuque_bot(message):
            return
        try:
            await _handle_raiding(ctx, state, ydx_store, client, message, _reply_to_me)
        except Exception as e:
            ctx.log.error("大劫处理出错: %s", e)

    # ── 红包雨 ──────────────────────────────────────────────────────────────
    @ctx.on_message(ctx.filters.incoming & ctx.filters.text, group=-7, target="user")
    async def on_redpocket(client, message):
        if not ctx.config.get("enable_redpocket", False):
            return
        if message.chat.id not in _REDPOCKET_GROUPS:
            return
        if not _is_zhuque_bot(message):
            return
        try:
            await _handle_redpocket(ctx, client, message)
        except Exception as e:
            ctx.log.error("红包雨处理出错: %s", e)

    # ── 转账记录 ──────────────────────────────────────────────────────────
    @ctx.on_message(ctx.filters.incoming & ctx.filters.text, group=-7, target="user")
    async def on_transform(client, message):
        if not ctx.config.get("enable_transform", False):
            return
        if message.chat.id not in _TRANSFORM_GROUPS:
            return
        if not _is_zhuque_bot(message):
            return
        try:
            await _handle_transform(ctx, client, message, _reply_to_me)
        except Exception as e:
            ctx.log.error("转账记录处理出错: %s", e)

    # ── 鳄鱼丼 YDX ────────────────────────────────────────────────────────
    @ctx.on_message(ctx.filters.incoming & ctx.filters.text, group=-7, target="user")
    async def on_ydx(client, message):
        if not ctx.config.get("enable_ydx", False):
            return
        if message.chat.id not in _YDX_GROUPS:
            return
        if not _is_zhuque_bot(message):
            return
        try:
            await _handle_ydx(ctx, state, ydx_store, client, message)
        except Exception as e:
            ctx.log.error("YDX 处理出错: %s", e)

    # ── 魔法卡定时 ────────────────────────────────────────────────────────
    if cfg.get("enable_firegenshin", False):
        async def fire_tick():
            if not ctx.config.get("enable_firegenshin", False):
                return
            try:
                await _do_firegenshin(ctx, _api)
            except Exception as e:
                ctx.log.error("魔法卡定时任务出错: %s", e)

        interval = max(5, safe_int(cfg.get("firegenshin_interval", 20), 20))
        ctx.schedule(fire_tick, "interval", minutes=interval, id="魔法卡释放")

    # ── 前端(Config.vue)用的后端接口 ──────────────────────────────────────────
    def _load_list(key):
        raw = ctx.kv.get(key) or []
        if isinstance(raw, str):
            import json as _json
            try:
                raw = _json.loads(raw)
            except (TypeError, ValueError):
                raw = []
        return raw if isinstance(raw, list) else []

    @ctx.on_api("/info", methods=["POST"])
    async def _api_info(req):
        """实时拉取朱雀个人信息（兼作凭据测试）。"""
        if not ctx.config.get("cookie") or not ctx.config.get("xcsrf"):
            return {"ok": False, "message": "未配置 Cookie / X-Csrf-Token"}
        try:
            info = await _api().get_info()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"查询失败：{e}"}
        if not info:
            return {"ok": False, "message": "查询失败，请检查凭据"}
        out = {}
        for key, label in INFO_FIELDS.items():
            if key in ("upload", "download"):
                try:
                    out[label] = f"{float(info.get(key, 0) or 0) / 1024 ** 4:.2f} TiB"
                except (ValueError, TypeError):
                    out[label] = str(info.get(key, ""))
            else:
                out[label] = info.get(key, "")
        return {"ok": True, "info": out,
                "firegenshin_total": float(ctx.kv.get("firegenshin_total", 0) or 0),
                "firegenshin_last_date": ctx.kv.get("firegenshin_last_date", "") or ""}

    @ctx.on_api("/transform", methods=["GET"])
    async def _api_transform(req):
        recs = _load_list("transform_records")
        get_total = sum(abs(float(r.get("amount", 0) or 0)) for r in recs if r.get("direction") == "get")
        pay_total = sum(abs(float(r.get("amount", 0) or 0)) for r in recs if r.get("direction") == "pay")
        def _lb(direction):
            return [{"name": e["name"], "total": e["total"], "count": e["count"]}
                    for e in _build_leaderboard(recs, direction, 10)]
        recent = [{"direction": r.get("direction"), "amount": r.get("amount"),
                   "user_name": r.get("user_name", ""), "ts": r.get("ts", "")}
                  for r in reversed(recs[-100:])]
        return {"get_leaderboard": _lb("get"), "pay_leaderboard": _lb("pay"),
                "get_total": get_total, "pay_total": pay_total, "recent": recent}

    @ctx.on_api("/raids", methods=["GET"])
    async def _api_raids(req):
        recs = _load_list("raid_records")
        def _sum(action):
            gain = sum(float(r.get("amount", 0)) for r in recs if r.get("action") == action and float(r.get("amount", 0)) > 0)
            loss = sum(-float(r.get("amount", 0)) for r in recs if r.get("action") == action and float(r.get("amount", 0)) < 0)
            cnt = sum(1 for r in recs if r.get("action") == action)
            return {"gain": gain, "loss": loss, "count": cnt}
        recent = [{"action": r.get("action"), "amount": r.get("amount"),
                   "count": r.get("count"), "ts": r.get("ts", "")}
                  for r in reversed(recs[-100:])]
        return {"raiding": _sum("raiding"), "beraided": _sum("beraided"), "recent": recent}

    @ctx.on_api("/ydx", methods=["GET"])
    async def _api_ydx(req):
        recs = _load_list("ydx_records")
        big = sum(1 for r in recs if r.get("lottery_result") == "Big")
        small = sum(1 for r in recs if r.get("lottery_result") == "Small")
        bet_total = sum(float(r.get("bet_amount", 0) or 0) for r in recs)
        win_total = sum(float(r.get("win_amount", 0) or 0) for r in recs)
        recent = [{"die_point": r.get("die_point"), "lottery_result": r.get("lottery_result"),
                   "bet_side": r.get("bet_side", ""), "bet_amount": r.get("bet_amount", 0),
                   "win_amount": r.get("win_amount", 0), "ts": r.get("ts", "")}
                  for r in reversed(recs[-100:])]
        return {"total": len(recs), "big": big, "small": small,
                "bet_total": bet_total, "win_total": win_total, "recent": recent}

    @ctx.on_api("/clear", methods=["POST"])
    async def _api_clear(req):
        data = req.json or {}
        which = data.get("type")
        keymap = {"transform": ["transform_records"], "raids": ["raid_records"],
                  "ydx": ["ydx_records", "ydx_history"]}
        keys = keymap.get(which)
        if not keys:
            return {"ok": False, "message": "未知类型"}
        for k in keys:
            try:
                ctx.kv.delete(k)
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True}


async def teardown(ctx):
    ctx.log.info("朱雀插件已停用")


# ═══════════════════════════════════════════════════════════════════════════
# 子功能实现
# ═══════════════════════════════════════════════════════════════════════════

# ─── 1. 个人信息查询 ─────────────────────────────────────────────────────────
async def _handle_getinfo(ctx, api_fn, message):
    starttime = time.time()
    try:
        waiting = await message.edit("```\n信息查询中……```")
    except Exception:
        waiting = await message.reply("```\n信息查询中……```")
    info = await api_fn().get_info()
    if not info:
        await waiting.edit("```\n查询失败，请检查 Cookie / X-Csrf-Token 配置```")
        return
    lines = []
    for key, label in INFO_FIELDS.items():
        if key in ("upload", "download"):
            continue
        lines.append(f"{label} : {info.get(key, '')} ")
    body = "\n".join(lines)
    try:
        up = float(info.get("upload", 0) or 0) / 1024 ** 4
        dn = float(info.get("download", 0) or 0) / 1024 ** 4
        body += f"\n{INFO_FIELDS['upload']} : {up:.2f} TiB\n{INFO_FIELDS['download']} : {dn:.2f} TiB"
    except (ValueError, TypeError):
        pass
    await waiting.edit(
        f"**查询完成：**耗时：{(time.time() - starttime):.3f} Sec \n**个人信息如下：**\n{body}"
    )


# ─── 2. 大转盘 ───────────────────────────────────────────────────────────────
async def _handle_prizewheel(ctx, api_fn, client, message, args):
    if len(args) != 1 or not args[0].isdigit():
        await message.reply(
            "```\n格式错误，请使用如下格式：\n/prizewheel 抽奖次数\n例如：/prizewheel 10```"
        )
        return
    count = int(args[0])
    api = api_fn()
    info = await api.get_info()
    if not info:
        await message.reply("```\n查询灵石失败，请检查凭据配置```")
        return
    available = safe_int(info.get("bonus", 0), 0)
    if count * SPIN_COST > available:
        max_draw = available // SPIN_COST
        await message.reply(f"```\n现有灵石不足，最多可抽奖 {max_draw} 次```")
        return

    waiting = await message.reply("```\n抽奖中……```")
    await _spin_wheel(ctx, api, count, client, waiting)


async def _spin_wheel(ctx, api, draws, client, message):
    """并发转盘抽奖，进度实时编辑到 message。迁移自 spinThePrizeWheel_zhuque.py。"""
    stats = {
        "cost": 0,
        "bonus_back": 0.0,
        "upload_in_gb": 0,
        "prize_counts": {k: 0 for k in WHEEL_PRIZES},
    }
    batch_size = 500
    tasks_count = max(1, safe_int(ctx.config.get("prize_tasks", 4), 4))
    lock = asyncio.Lock()
    start_time = time.time()

    async def fetch_batch(n, http_client):
        for _ in range(n):
            prize = await api.spin_once(http_client)
            if prize is None:
                continue
            async with lock:
                if prize in stats["prize_counts"]:
                    stats["prize_counts"][prize] += 1
                stats["cost"] += SPIN_COST
                if prize in CARD_BONUS_VALUES:
                    stats["bonus_back"] += CARD_BONUS_VALUES[prize] * 0.8
                elif prize == 5:
                    stats["upload_in_gb"] += 20
                elif prize == 6:
                    stats["upload_in_gb"] += 10

    async with httpx.AsyncClient(timeout=15) as http_client:
        for i in range(0, draws, batch_size):
            sub_draws = min(batch_size, draws - i)
            chunk = sub_draws // tasks_count
            extra = sub_draws % tasks_count
            tasks = [
                fetch_batch(chunk + (1 if j < extra else 0), http_client)
                for j in range(tasks_count)
            ]
            await asyncio.gather(*tasks)

            elapsed = time.time() - start_time
            cost = stats["cost"]
            bonus_back = stats["bonus_back"]
            gb = stats["upload_in_gb"]
            net = (gb / 86.9863 * 10000) - (cost - bonus_back)
            efficiency = gb / max((cost - bonus_back), 1) * 10000
            summary = "\n".join(
                f"{WHEEL_PRIZES.get(k)} : {v}"
                for k, v in stats["prize_counts"].items() if v > 0
            ) or "无"
            try:
                await message.edit(
                    f"**抽奖进度：**\n"
                    f"已完成 {i + sub_draws}/{draws} 次  耗时：{elapsed:.3f} 秒\n"
                    f"**上传灵石比：** {efficiency:.2f} GB/万灵石\n"
                    f"按86.98 GB/万灵石计算净赚：{net:.1f}\n\n"
                    f"耗费灵石 : **{cost}**\n"
                    f"道具回血 : **{int(bonus_back)}**\n"
                    f"获得上传 : **{gb} GB**\n\n"
                    f"**明细如下：**\n{summary}"
                )
            except Exception as e:
                ctx.log.debug("转盘进度更新失败: %s", e)
    return stats


# ─── 3. 倍投起手表 ───────────────────────────────────────────────────────────
async def _handle_betbonus(ctx, message, args):
    if len(args) < 2 or not args[0].isdigit() or not args[1].isdigit():
        await message.reply("```\n参数不足。用法：/betbonus 本金 连输次数\n例如：/betbonus 50000000 20```")
        return
    num = float(args[0])
    count = int(args[1])
    result = calc_starting_bet(c=num, max_n=count)
    try:
        sent = await message.edit(f"```\n{result}```")
    except Exception:
        sent = await message.reply(f"```\n{result}```")
    _schedule_delete(sent, 60)


# ─── 3b. 道具卡回收（.card）──────────────────────────────────────────────────
def _card_id_map(ctx) -> dict:
    """配置里的 4 个 card_id（字符串）→ {序号(1~4): card_id(int)}。"""
    c = ctx.config
    out = {}
    for n in (1, 2, 3, 4):
        out[n] = safe_int(c.get(f"card_id_{n}", n), n)
    return out


async def _handle_card(ctx, api_fn, message, args):
    """
    回收朱雀道具卡换灵石。迁移自原 plugins/bot/commands/zhuqe_card.py +
    libs/zhuque_listBackpack.py / zhuque_recycleMagicCard.py。

    用法：
      /card             → 回收背包里全部 4 种卡的现有库存
      /card 2           → 回收 2 号卡(神佑7天卡)的全部库存
      /card 2 10        → 回收 2 号卡 10 张

    待实盘校验：回收端点 POST /api/mall/recycleMagicCard 的 body 字段名({"id":card_id})、
    背包 listBackpack 的 card_id 取值，均按原项目(aiohttp 版)迁移。若站点改版需对照 F12。
    """
    ctx.log.warning("道具卡回收 .card 触发：API 端点/字段按原项目迁移，待实盘校验")
    api = api_fn()
    id_map = _card_id_map(ctx)

    # 解析参数：第 1 个=卡序号(1~4)，第 2 个=数量
    target_slot = None
    want_number = None
    if len(args) >= 1 and args[0].isdigit():
        slot = int(args[0])
        if slot in id_map:
            target_slot = slot
        else:
            await message.reply("```\n卡号需为 1~4：1改名卡 2神佑7天卡 3邀请卡 4释放7天卡```")
            return
    if len(args) >= 2 and args[1].isdigit():
        want_number = int(args[1])

    try:
        waiting = await message.edit("```\n查询背包中……```")
    except Exception:
        waiting = await message.reply("```\n查询背包中……```")

    backpack = await api.list_backpack()
    if backpack is None:
        await waiting.edit("```\n背包查询失败，请检查 Cookie / X-Csrf-Token 配置```")
        return

    slots = [target_slot] if target_slot else [1, 2, 3, 4]
    result_lines = []
    total_back = 0.0
    for slot in slots:
        card_id = id_map[slot]
        have = safe_int(backpack.get(slot, backpack.get(card_id, 0)), 0)
        number = want_number if (want_number is not None) else have
        if number <= 0:
            result_lines.append(f"{CARD_NAMES[slot]}：无库存，跳过")
            continue
        number = min(number, have) if have > 0 else number
        success = await api.recycle_card(card_id, number)
        back = CARD_BONUS_VALUES.get(slot, 0) * success * 0.8
        total_back += back
        result_lines.append(f"{CARD_NAMES[slot]}：回收 {success}/{number} 张，约 {back:,.0f} 灵石")

    body = "\n".join(result_lines) or "无可回收道具"
    await waiting.edit(f"**朱雀道具卡回收完成：**\n{body}\n\n合计回血约 **{total_back:,.0f}** 灵石")
    if ctx.config.get("owner_notify", True) and total_back > 0:
        await ctx.notify(f"朱雀道具卡回收回血约 {total_back:,.0f} 灵石", level="success", category="道具回收")


# ─── 4. 魔法卡定时 ───────────────────────────────────────────────────────────
async def _do_firegenshin(ctx, api_fn):
    """每天成功释放一次。kv 记录上次成功日期，今天已成功则跳过。"""
    today = date.today().isoformat()
    last = ctx.kv.get("firegenshin_last_date")
    if last == today:
        return  # 今天已成功，等次日

    api = api_fn()
    ctx.log.info("开始朱雀魔法卡释放")
    r1 = await api.fire_genshin()
    await asyncio.sleep(15)
    r2 = await api.fire_genshin()
    code1, bonus1 = r1 if r1 else ("", 0)
    code2, bonus2 = r2 if r2 else ("", 0)
    total = (bonus1 or 0) + (bonus2 or 0)
    success = any("SUCCESS" in (c or "") for c in (code1, code2))

    if success and total > 0:
        ctx.kv.set("firegenshin_last_date", today)
        prev = float(ctx.kv.get("firegenshin_total", 0) or 0)
        ctx.kv.set("firegenshin_total", prev + total)
        ctx.log.info("魔法卡释放成功，获得 %s 灵石", total)
        if ctx.config.get("owner_notify", True):
            await ctx.notify(f"朱雀魔法卡释放获得 {total} 灵石", level="success", category="魔法卡")
    else:
        ctx.log.warning("魔法卡释放失败或无奖励，将在下次间隔重试")


# ─── 5. 大劫监听/反击 ────────────────────────────────────────────────────────
_RE_RAID_RESULT = re.compile(r"(获得|亏损|你被反打劫|扣税)\s+([\d.]+)\s+灵石\s*$")
_RE_RAID_INFO = re.compile(r"(赢局总计|操作过于频繁|不能打劫|修为等阶)")


async def _handle_raiding(ctx, state, store, client, message, reply_to_me_fn):
    text = message.text or ""
    msgs = build_reply_messages(ctx.config.get("my_name", "我"))

    # A) 我主动打劫的结果（回复我的消息）
    if reply_to_me_fn(message) and _RE_RAID_RESULT.search(text):
        raiding_msg = message.reply_to_message
        raidcount = _extract_raidcount(getattr(raiding_msg, "text", ""))
        gain = extract_lingshi_amount(text, r"(获得) ([\d.]+) 灵石\s*$")
        loss = extract_lingshi_amount(text, r"(亏损|你被反打劫) ([\d.]+) 灵石\s*$")
        if gain or loss:
            bonus = gain if gain else (-loss if loss else Decimal(0))
            _record_raid(store, "raiding", bonus, raidcount)
            ctx.kv.set("last_raid_ts", time.time())
        return

    # B) 被打劫 / 被 info（回复链 reply.reply 是我）
    if _is_command_to_me(message):
        if "操作过于频繁" in text:
            r = await _safe_reply(message.reply_to_message, msgs["dajieCoolingDown"])
            _schedule_delete(r, 20)
        elif "赢局总计" in text:
            key = "dajieInfoLose" if "总计赢了" in text else "dajieInfoWin"
            r = await _safe_reply(message.reply_to_message, msgs[key])
            _schedule_delete(r, 20)
        elif "不能打劫" in text:
            if "对方灵石低于" in text:
                r = await _safe_reply(message.reply_to_message, msgs["meInsufficient"])
            else:
                tmp = await _safe_reply(message.reply_to_message, "+1")
                _schedule_delete(tmp, 5)
                r = await _safe_reply(message.reply_to_message, msgs["othersInsufficient"])
            _schedule_delete(r, 20)
        elif "修为等阶" in text:
            r = await _safe_reply(message.reply_to_message, msgs["infoBy"])
            _schedule_delete(r, 20)
        elif _RE_RAID_RESULT.search(text):
            raidcount = _extract_raidcount(getattr(message.reply_to_message, "text", ""))
            await _auto_fanda(ctx, store, client, message, raidcount, msgs)


async def _auto_fanda(ctx, store, client, message, raidcount, msgs):
    """被打劫后的自动反打 + 概率返现。迁移自 zhuque_dajie_fanda。"""
    c = ctx.config
    fanda_mode = c.get("fanda_mode", "off")
    fanxian_on = c.get("fanxian", False)
    probability = safe_int(c.get("fanxian_probability", 1), 1) / 100
    blacklist = parse_blacklist(c.get("fanxian_blacklist", ""))

    raiding_msg = message.reply_to_message
    if not raiding_msg:
        return
    text = message.text or ""

    win_amt = extract_lingshi_amount(text, r"(亏损|你被反打劫) ([\d.]+) 灵石\s*$")
    lose_amt = extract_lingshi_amount(text, r"(获得) ([\d.]+) 灵石\s*$")
    if "扣税" in text:
        win_amt = extract_lingshi_amount(text, r"(你被反打劫) ([\d.]+) 灵石\s*$")
        lose_amt = extract_lingshi_amount(text, r"(获得) ([\d.]+) 灵石\s*$")

    if win_amt:
        _record_raid(store, "beraided", win_amt, raidcount)
    elif lose_amt:
        _record_raid(store, "beraided", -lose_amt, raidcount)

    cd_ready = _cd_ready(ctx)

    if not (win_amt or lose_amt):
        return
    is_win = bool(win_amt)
    amount = float(win_amt if is_win else lose_amt)
    message_key = "robbedByWin" if is_win else "robbedByLose"
    fanda_off_key = "robbedwinfandaoff" if is_win else "robbedlosfandaoff"

    fanda_valid = (fanda_mode in ("win", "all")) if is_win else (fanda_mode in ("lose", "all"))

    reply = None
    if fanda_valid:
        if not cd_ready:
            reply = await _safe_reply(raiding_msg, msgs["robbedByLoseCD"])
        elif amount >= 2000:
            reply = await _safe_reply(raiding_msg, f"/dajie {raidcount} {msgs[message_key]}")
            ctx.kv.set("last_raid_ts", time.time())
        else:
            reply = await _safe_reply(raiding_msg, msgs["robbedBynosidepot"])
    else:
        reply = await _safe_reply(raiding_msg, msgs[fanda_off_key])

    # 概率返现（被打赢时）
    if is_win and fanxian_on:
        rfu = getattr(raiding_msg, "from_user", None)
        if rfu and rfu.id in blacklist:
            return
        if random.random() < probability:
            odds = random.random()
            refund = int(float(win_amt) * 0.9 * odds)
            await _safe_reply(raiding_msg, f"+{refund}")
            fx = await _safe_reply(
                raiding_msg,
                f"您触发了一次输后返现，表示对您的止损。倍率为 {odds * 100:.2f} %",
            )
            _schedule_delete(fx, 20)

    if reply:
        _schedule_delete(reply, 20)
    if not is_win and amount >= 20000:
        try:
            await raiding_msg.delete()
        except Exception:
            pass


def _extract_raidcount(text: str) -> int:
    m = re.search(r"^/dajie[\s\S]*\s(\d+)", text or "")
    return int(m.group(1)) if m else 1


def _is_command_to_me(message) -> bool:
    """reply.reply.from_user.is_self —— 我发的 /dajie 被 bot 回复后又被回复。"""
    r = getattr(message, "reply_to_message", None)
    if not r:
        return False
    rr = getattr(r, "reply_to_message", None)
    return bool(rr and getattr(rr, "from_user", None) and getattr(rr.from_user, "is_self", False))


def _record_raid(store, action: str, amount, count: int):
    rec = {
        "action": action,
        "amount": float(amount),
        "count": count,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    raw = store._kv.get("raid_records") or []
    if isinstance(raw, str):
        try:
            import json
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = []
    raw.append(rec)
    if len(raw) > 300:
        raw = raw[-300:]
    try:
        store._kv.set("raid_records", raw)
    except Exception:
        import json
        store._kv.set("raid_records", json.dumps(raw, ensure_ascii=False))


def _cd_ready(ctx) -> bool:
    cd_min = safe_int(ctx.config.get("raid_cd_minutes", 5), 5)
    last = ctx.kv.get("last_raid_ts")
    if last is None:
        return True
    try:
        return (time.time() - float(last)) >= cd_min * 60
    except (ValueError, TypeError):
        return True


# ─── 6. 红包雨 ───────────────────────────────────────────────────────────────
_RE_REDPOCKET = re.compile(
    r"内容: ([\s\S]*?)\n灵石: (\d+(?:\.\d+)?)/\d+(?:\.\d+)?\n剩余: .*?\n大善人: (.*)"
)


async def _handle_redpocket(ctx, client, message):
    text = message.text or ""
    match = _RE_REDPOCKET.search(text)
    if not match:
        return
    markup = getattr(message, "reply_markup", None)
    if not markup or not getattr(markup, "inline_keyboard", None):
        return
    try:
        callback_data = markup.inline_keyboard[0][0].callback_data
    except (IndexError, AttributeError):
        return

    redpocket_name = match.group(1)
    red_from_user = match.group(3)
    max_retry = safe_int(ctx.config.get("redpocket_max_retry", 20), 20)

    for retry in range(max_retry):
        try:
            result = await client.request_callback_answer(
                chat_id=message.chat.id,
                message_id=message.id,
                callback_data=callback_data,
                timeout=10,
            )
        except TimeoutError:
            ctx.log.warning("红包回调超时(第%s次)", retry + 1)
            await asyncio.sleep(2)
            continue
        except Exception as e:
            ctx.log.warning("红包回调异常(第%s次): %s", retry + 1, e)
            await asyncio.sleep(1)
            continue

        m = re.search(r"已获得 (\d+) 灵石", getattr(result, "message", "") or "")
        if m:
            bonus = m.group(1)
            ctx.log.info("抢到红包 %s: %s 灵石(第%s次)", redpocket_name, bonus, retry + 1)
            if ctx.config.get("owner_notify", True):
                await ctx.notify(
                    f"{red_from_user} 发的朱雀红包\n\n"
                    f"{redpocket_name}\n\n"
                    f"抢了 {retry + 1} 次，成功抢到 {bonus} 灵石",
                    level="success", category="红包雨", account=client,
                )
            return


# ─── 7. 转账记录 ─────────────────────────────────────────────────────────────
_RE_TRANSFER = re.compile(r"转账成功, 信息如下: \n.+ 转出 (\d+)\n")
_LEADERBOARD_SIZE = 5


def _transfer_user_of(message, direction: str):
    """
    取被记账的对方用户。迁移自原 transform_zhuque.py：
      - 转入(get)：对方是 message.reply_to_message 的发送者（command_to_me 链）。
      - 转出(pay)：对方是 message.reply_to_message.reply_to_message 的发送者（reply_to_me 链）。
    返回 (user_id, user_name) 或 (0, "")。
    """
    if direction == "get":
        src = getattr(message, "reply_to_message", None)
    else:
        r = getattr(message, "reply_to_message", None)
        src = getattr(r, "reply_to_message", None) if r else None
    fu = getattr(src, "from_user", None) if src else None
    if not fu:
        return 0, ""
    parts = [p for p in (getattr(fu, "first_name", ""), getattr(fu, "last_name", "")) if p]
    name = " ".join(parts).strip() or getattr(fu, "username", "") or str(getattr(fu, "id", 0))
    return int(getattr(fu, "id", 0) or 0), name


def _build_leaderboard(records: list, direction: str, limit: int = _LEADERBOARD_SIZE) -> list:
    """按用户聚合某方向的转账总额，返回 [(name, total, count), ...] TOP limit。"""
    agg: dict = {}
    for rec in records:
        if rec.get("direction") != direction:
            continue
        uid = rec.get("user_id", 0)
        amt = abs(float(rec.get("amount", 0) or 0))
        name = rec.get("user_name", "") or str(uid)
        cur = agg.get(uid) or {"name": name, "total": 0.0, "count": 0}
        cur["total"] += amt
        cur["count"] += 1
        cur["name"] = name
        agg[uid] = cur
    ranked = sorted(agg.values(), key=lambda x: x["total"], reverse=True)
    return ranked[:limit]


async def _handle_transform(ctx, client, message, reply_to_me_fn):
    text = message.text or ""
    m = _RE_TRANSFER.search(text)
    if not m:
        return
    bonus = float(m.group(1))

    # 转入：command_to_me（reply.reply 是我）；转出：reply_to_me
    if _is_command_to_me(message):
        direction = "get"
        amount = bonus
    elif reply_to_me_fn(message):
        direction = "pay"
        amount = -bonus
    else:
        return

    user_id, user_name = _transfer_user_of(message, direction)
    rec = {
        "direction": direction,
        "amount": amount,
        "user_id": user_id,
        "user_name": user_name,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    raw = ctx.kv.get("transform_records") or []
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = []
    raw.append(rec)
    if len(raw) > 300:
        raw = raw[-300:]
    try:
        ctx.kv.set("transform_records", raw)
    except Exception:
        import json
        ctx.kv.set("transform_records", json.dumps(raw, ensure_ascii=False))

    ctx.log.info("记录灵石转账 dir=%s amount=%s user=%s", direction, amount, user_name)

    c = ctx.config
    # notification 总开关：关闭则只记录不发任何消息（对齐原 TransferService）
    if not c.get("transform_notification", False):
        return

    # 转入查 leaderboard，转出查 payleaderboard
    if direction == "get":
        lb_on = c.get("transform_leaderboard", False)
        table_title = "打赏"
    else:
        lb_on = c.get("transform_payleaderboard", False)
        table_title = "赏赐"

    word = "收到" if direction == "get" else "转出"
    body = f"朱雀{word}灵石转账 {abs(bonus):,.0f}"
    if user_name:
        body += f"（{user_name}）"

    # 排行榜数据已存 ctx.kv，按开关决定通知时是否附榜
    if lb_on:
        entries = _build_leaderboard(raw, direction, _LEADERBOARD_SIZE)
        if entries:
            lines = [f"个人{table_title}总榜 TOP{len(entries)}："]
            medals = ["No.1", "No.2", "No.3"]
            for i, e in enumerate(entries):
                medal = medals[i] if i < 3 else f"{i + 1}."
                lines.append(f"{medal} {e['name']} {e['total']:,.0f}（{e['count']}次）")
            # 正文与榜单之间空一行分隔
            body += "\n\n" + "\n".join(lines)

    await ctx.notify(body, level="info", category="转账", account=client)


# ─── 8. 鳄鱼丼 YDX ──────────────────────────────────────────────────────────
_RE_YDX_REVEAL = re.compile(r"已结算: 结果为 (\d+) (.)")


async def _handle_ydx(ctx, state, store, client, message):
    text = message.text or ""

    # 开奖结算
    m = _RE_YDX_REVEAL.search(text)
    if m:
        await _ydx_reveal(ctx, state, store, client, message, m)
        return

    # 开局（含「创建时间」）→ 判断是否下注
    if "创建时间" in text and ctx.config.get("ydx_dice_bet", False):
        await _ydx_new_round(ctx, state, store, client, message)


async def _ydx_reveal(ctx, state, store, client, message, match):
    me_id = client.me.id if client.me else 0
    die_point = int(match.group(1))
    result_map = {"大": "Big", "小": "Small"}
    lottery_result = result_map.get(match.group(2), "unknown")
    dx = 1 if lottery_result == "Big" else 0
    for md in state["bet_models"].values():
        md.set_result(dx)

    if lottery_result == "Big":
        state["big_count"] += 1
        state["small_count"] = 0
    elif lottery_result == "Small":
        state["small_count"] += 1
        state["big_count"] = 0
    else:
        state["big_count"] = 0
        state["small_count"] = 0
    consecutive = max(state["big_count"], state["small_count"])

    bet_side = ""
    bet_amount = 0
    win_amount = 0
    rmsg = getattr(message, "reply_to_message", None)
    if rmsg:
        firstname = _ydx.listof_winners_check(rmsg, me_id)
        if firstname:
            info = _ydx.extract_bet_info(getattr(rmsg, "text", "") or "", firstname)
            if info:
                bet_side, bet_amount = info
                state["bet_count"] += 1
            else:
                state["bet_count"] = 0
        else:
            state["bet_count"] = 0

    firstname_reveal = _ydx.listof_winners_check(message, me_id)
    if firstname_reveal:
        win_amount = _ydx.extract_winner_amount(message.text, firstname_reveal) or 0

    if ctx.config.get("ydx_dice_reveal", True):
        store.add_record({
            "die_point": die_point,
            "lottery_result": lottery_result,
            "consecutive_count": consecutive,
            "bet_side": bet_side,
            "bet_count": state["bet_count"],
            "bet_amount": float(bet_amount),
            "win_amount": float(win_amount),
            "ts": datetime.now().isoformat(timespec="seconds"),
        })


async def _ydx_new_round(ctx, state, store, client, message):
    c = ctx.config
    start_count = safe_int(c.get("ydx_start_count", 5), 5)
    stop_count = safe_int(c.get("ydx_stop_count", 5), 5)
    start_bonus = safe_int(c.get("ydx_start_bouns", 500), 500)
    model = (c.get("ydx_bet_model", "a") or "a").lower()

    # 延迟等待手动操作机会
    await asyncio.sleep(5)
    data = _ydx.history_list(message)
    if not data:
        ctx.log.warning("YDX 无法解析历史数据，跳过本局下注（需实盘校验 bot 文案格式）")
        return

    models = state["bet_models"]
    bet_model = models.get(model, models["a"])
    for md in models.values():
        await md.guess(data, store)
    dx = await bet_model.guess(data, store)
    bet_side = "sb"[dx]  # 0→s小 1→b大
    bet_count = bet_model.get_bet_count(data, start_count, stop_count)
    ctx.log.info("YDX 猜测 dx=%s side=%s bet_count=%s model=%s", dx, bet_side, bet_count, model)

    if bet_count > -1:
        bet_bonus = bet_model.get_bet_bonus(start_bonus, bet_count)
        # ydx_wwd_switch：下注分支的二级开关（原 ZHUQUE_<id>.ydx_wwd_switch，默认 off）。
        # 关闭时只计算下注方案、不实际点击下注按钮。需实盘校验其在原站的确切语义。
        if not c.get("ydx_wwd_switch", False):
            ctx.log.warning(
                "YDX 满足下注条件(side=%s bonus=%s)但 ydx_wwd_switch 关闭，仅计算不下注（待实盘校验）",
                bet_side, bet_bonus,
            )
            return
        total = await _ydx.manual_bet(client, message, bet_bonus, bet_side, ctx.log)
        if total == 0:
            ctx.log.warning("YDX 下注失败/零食不足")


# ═══════════════════════════════════════════════════════════════════════════
# 通用小工具
# ═══════════════════════════════════════════════════════════════════════════
async def _safe_reply(message, text):
    try:
        return await message.reply(text)
    except Exception:
        return None


def _schedule_delete(message, delay: int):
    if message is None:
        return

    async def _del():
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception:
            pass

    asyncio.create_task(_del())
