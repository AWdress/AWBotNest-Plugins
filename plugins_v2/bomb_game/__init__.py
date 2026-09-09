"""Native AWBotNest V2 number-bomb game."""
from __future__ import annotations

from collections import deque
from datetime import datetime

from .game import NumberBombGame
from .helpers import (extract_amount, group_allowed, is_continuous_command,
                      is_end_command, is_start_command, parse_bot_ids,
                      parse_groups, parse_guess, parse_plus_amount, text_of)
from .state import GameStateManager

__plugin__ = {
    "id": "bomb_game", "name": "数字炸弹", "version": "2.0.0",
    "author": "AWdress", "scope": "user", "plugin_api_version": 2,
    "description": "群内数字炸弹竞猜：开启后群友回复+金额参与组奖池，轮流猜数字，猜中/范围耗尽即爆炸，中奖者按比例分奖池。",
    "requirements": [],
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/bomb_game.png",
    "tags": ["数字炸弹", "群组游戏", "奖池互动"], "render_mode": "vue",
    "config_schema": {},
    "resources": {"timeout_seconds": 120, "max_concurrency": 16, "max_background_tasks": 64},
    "changelog": "v2.0.0 原生 AWBotNest V2 迁移\n- 移除 V1 兼容运行层与 Pyrogram 模拟层\n- 使用 Telethon 原生事件和交互快速通道\n- 活跃游戏迁移到平台会话运行时，关键状态使用异步存储检查点\n- 后台等待与自动删除任务纳入平台生命周期管理",
}

DEFAULTS = {
    "valid_groups": "", "entry_fee": 888, "pool_ratio": 50, "wait_time": 30,
    "default_min": 1, "default_max": 100, "enable_range_shrink": True,
    "shrink_1_5": -10, "shrink_6_15": -4, "shrink_16_30": -2, "shrink_31plus": 2,
    "instant_win_permille": 5, "auto_delete_enabled": True, "auto_delete_delay": 30,
    "no_delete_groups": "", "monitor_disabled_groups": "",
    "require_transfer_confirm": False, "transfer_bot_ids": "",
}

def _cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}

async def _prepare_event(ctx, state, event):
    if not getattr(event, "is_group", False):
        return None
    if ctx.user is not None and event.client is not ctx.user:
        return None
    chat_id = int(event.chat_id)
    cfg = _cfg(ctx)
    valid = parse_groups(cfg.get("valid_groups", ""))
    disabled = parse_groups(cfg.get("monitor_disabled_groups", ""))
    if (valid and not group_allowed(valid, chat_id)) or group_allowed(disabled, chat_id):
        return None
    await state.ensure_session(chat_id)
    sender = await event.get_sender()
    setattr(event, "_bomb_sender", sender)
    return chat_id, sender, cfg, valid

async def setup(ctx):
    state = GameStateManager(ctx)
    await state.initialize()
    game = NumberBombGame(ctx, state, parse_groups(_cfg(ctx).get("valid_groups", "")))
    history = deque(maxlen=50)
    ctx.add_cleanup(game.cancel_all_tasks)

    @ctx.on_api("games")
    async def api_games(request):
        return {"games": list(history)}

    @ctx.on_api("chat_names")
    async def api_chat_names(request):
        values = set()
        for key in ("valid_groups", "monitor_disabled_groups", "no_delete_groups"):
            values.update(parse_groups(_cfg(ctx).get(key, "")))
        items = []
        for chat_id in sorted(values):
            title = str(chat_id)
            if ctx.user is not None:
                try:
                    entity = await ctx.user.get_entity(chat_id)
                    title = getattr(entity, "title", None) or getattr(entity, "first_name", None) or title
                except Exception:
                    pass
            items.append({"id": chat_id, "title": title})
        return {"items": items}

    async def transfer_confirm(event, amount, chat_id):
        info = state.get_game_info(chat_id) or {}
        pending = info.get("pending_participants", {})
        if not pending:
            return
        user_id = None
        reply_to = getattr(event, "reply_to_msg_id", None)
        if reply_to:
            matches = [uid for uid, item in pending.items() if item.get("message_id") == reply_to]
            if len(matches) == 1:
                user_id = int(matches[0])
        if user_id is None:
            try: expected = int(float(amount))
            except (TypeError, ValueError): return
            matches = [uid for uid, item in pending.items() if int(item.get("amount", 0)) == expected]
            if len(matches) == 1: user_id = int(matches[0])
        if user_id is None:
            ctx.log.warning("[数字炸弹] 转账确认无法唯一定位参与者，已跳过 chat=%s", chat_id)
            return
        await game.confirm_participation_logic(event.client, event, amount, chat_id, user_id, retry=False)
        await state.checkpoint(chat_id)

    @ctx.on_message(pattern=r"(?:开启|开始|持续|连续|结束|停止|关闭).*数字炸弹", incoming=False, outgoing=True)
    async def game_command(event):
        prepared = await _prepare_event(ctx, state, event)
        if not prepared: return
        chat_id, sender, cfg, valid = prepared
        text = text_of(event)
        game.valid_groups = valid
        admin_id = sender.id if sender else 0
        if is_start_command(text) or is_continuous_command(text):
            if not state.is_game_active(chat_id) and await game.start_game(event.client, event, admin_id, is_continuous_command(text)):
                chat = await event.get_chat()
                history.append({"time": datetime.now().strftime("%H:%M:%S"), "group_name": getattr(chat, "title", str(chat_id)), "players": 0, "pool": 0, "winner": None, "status": "进行中"})
            return
        if is_end_command(text) and state.is_game_active(chat_id):
            info = state.get_game_info(chat_id) or {}
            if await game.end_game(event.client, event, info.get("admin_id", admin_id)):
                if history: history[-1]["status"] = "取消"
                await state.checkpoint(chat_id)

    @ctx.on_message(pattern=r"^\s*我猜是\s*\d{1,3}\s*$", incoming=True, outgoing=True, interactive=True)
    async def guess(event):
        prepared = await _prepare_event(ctx, state, event)
        if not prepared: return
        chat_id, sender, cfg, valid = prepared
        game.valid_groups = valid
        if parse_guess(text_of(event)) is not None and state.is_game_active(chat_id):
            await game.process_guess(event.client, event)
            await state.checkpoint(chat_id)
            if not state.is_game_active(chat_id) and history:
                history[-1]["status"] = "完成"
                history[-1]["winner"] = (state.get_game_info(chat_id) or {}).get("winner")

    @ctx.on_message(incoming=True, outgoing=False)
    async def participation_or_transfer(event):
        prepared = await _prepare_event(ctx, state, event)
        if not prepared: return
        chat_id, sender, cfg, valid = prepared
        if not state.is_game_active(chat_id): return
        text = text_of(event)
        if state.is_waiting_phase(chat_id):
            amount = parse_plus_amount(text)
            if amount is not None and event.reply_to_msg_id == state.get_start_message_id(chat_id) and sender:
                await state.add_pending_participant(chat_id, sender.id, amount, event.id)
                if not cfg.get("require_transfer_confirm", False):
                    await game.confirm_participation_logic(event.client, event, amount, chat_id, sender.id, retry=False)
                    await state.checkpoint(chat_id)
                return
        if cfg.get("require_transfer_confirm", False) and sender and getattr(sender, "bot", False):
            bot_ids = parse_bot_ids(cfg.get("transfer_bot_ids", ""))
            if not bot_ids or sender.id in bot_ids:
                amount = extract_amount(text)
                if amount is not None: await transfer_confirm(event, amount, chat_id)

    ctx.log.info("[数字炸弹] 原生 V2 插件已启用，恢复 %d 个会话", len(state.state))

async def teardown(ctx):
    ctx.log.info("[数字炸弹] 已停用")
