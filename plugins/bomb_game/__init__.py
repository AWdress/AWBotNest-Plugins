# =============================================================================
# AWBotNest 插件：数字炸弹（bomb_game）
#
# 群内数字炸弹竞猜：管理员（你的用户账号）在群里发「开启数字炸弹」/「持续数字炸弹」，
# 群友回复开始消息发 +金额 组奖池，轮流发「我猜是N」猜数字。系统按距离调整范围、
# 动态移弹、三种爆炸场景 + 千分率一发命中；爆炸时中奖者按比例分奖池（reply +金额
# 由群转账 bot 实际打款）。持续模式爆炸后 3 秒自动重开；管理员发「结束数字炸弹」
# 中断并返还奖池。
# =============================================================================

from collections import deque
from datetime import datetime

from ._helpers import (
    parse_groups, group_allowed, parse_bot_ids,
    text_of, is_start_command, is_continuous_command, is_end_command,
    parse_guess, parse_plus_amount, extract_amount, is_start_message_text,
)
from ._state import GameStateManager
from ._game import NumberBombGame

__plugin__ = {
    "name": "数字炸弹",
    "id": "bomb_game",
    "version": "1.0.2",
    "author": "AWdress",
    "description": "群内数字炸弹竞猜：开启后群友回复+金额参与组奖池，轮流猜数字，猜中/范围耗尽即爆炸，中奖者按比例分奖池。",
    "changelog": "v1.0.2 修复配置界面缺失\n- 随插件发布 frontend/dist 前端构建产物",
    "scope": "both",
    "default_enabled": False,
    "render_mode": "vue",
}

# ── 配置默认值 ──
DEFAULTS = {
    "valid_groups": "",
    "entry_fee": 888,
    "pool_ratio": 50,
    "wait_time": 30,
    "default_min": 1,
    "default_max": 100,
    "enable_range_shrink": True,
    "shrink_1_5": -10,
    "shrink_6_15": -4,
    "shrink_16_30": -2,
    "shrink_31plus": 2,
    "instant_win_permille": 5,
    "auto_delete_enabled": True,
    "auto_delete_delay": 30,
    "no_delete_groups": "",
    "monitor_disabled_groups": "",
    "require_transfer_confirm": False,
    "transfer_bot_ids": "",
}

# ── 运行态 ──
_state_mgr = GameStateManager()
_game_history = deque(maxlen=50)


def _effective_cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}


async def setup(ctx):
    # ───────── Vue 模式后端 API ─────────
    @ctx.on_api("/games", methods=["GET"])
    async def _api_games(req):
        return {"games": list(_game_history)}

    @ctx.on_api("/update_config", methods=["POST"])
    async def _api_update_config(req):
        body = await req.json()
        ctx.update_config(body)
        return {"ok": True}

    # ───────── 游戏逻辑（保留原有核心逻辑）─────────
    @ctx.on_message(ctx.filters.group, group=7)
    async def on_group_message(client, message):
        cfg = _effective_cfg(ctx)
        chat_id = message.chat.id
        text = text_of(message)

        # 检查群组允许
        valid = parse_groups(cfg.get("valid_groups", ""))
        if valid and not group_allowed(chat_id, valid):
            return
        disabled = parse_groups(cfg.get("monitor_disabled_groups", ""))
        if group_allowed(chat_id, disabled):
            return

        # 开启游戏
        if is_start_command(text) or is_continuous_command(text):
            if _state_mgr.get_game(chat_id):
                return
            continuous = is_continuous_command(text)
            game = NumberBombGame(
                chat_id=chat_id,
                start_message_id=message.id,
                continuous=continuous,
                config=cfg,
            )
            _state_mgr.set_game(chat_id, game)

            from ._game import start_game
            await start_game(client, message, game, cfg, ctx)

            _game_history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "group_name": message.chat.title or str(chat_id),
                "players": 0,
                "pool": 0,
                "winner": None,
                "status": "进行中",
            })
            return

        # 结束游戏
        if is_end_command(text):
            game = _state_mgr.get_game(chat_id)
            if game and message.from_user and message.from_user.id == game.owner_id:
                from ._game import end_game
                await end_game(client, message, game, cfg, ctx)
                _state_mgr.remove_game(chat_id)
                if _game_history:
                    _game_history[-1]["status"] = "取消"
            return

        # 参与游戏
        game = _state_mgr.get_game(chat_id)
        if not game:
            return

        reply_to = message.reply_to_message_id
        if reply_to == game.start_message_id:
            amount = parse_plus_amount(text)
            if amount == cfg.get("entry_fee", 888):
                from ._game import handle_join
                await handle_join(client, message, game, cfg, ctx)
                if _game_history:
                    _game_history[-1]["players"] = len(game.participants)
                    _game_history[-1]["pool"] = game.pool
                return

        # 猜数字
        guess = parse_guess(text)
        if guess is not None and game.is_participant(message.from_user.id):
            from ._game import handle_guess
            result = await handle_guess(client, message, game, guess, cfg, ctx)
            if result and result.get("winner"):
                if _game_history:
                    _game_history[-1]["winner"] = result["winner"]
                    _game_history[-1]["status"] = "完成"
                if not game.continuous:
                    _state_mgr.remove_game(chat_id)
            return

        # 转账确认
        if cfg.get("require_transfer_confirm", False):
            bot_ids = parse_bot_ids(cfg.get("transfer_bot_ids", ""))
            if message.from_user and message.from_user.is_bot and message.from_user.id in bot_ids:
                amount = extract_amount(text)
                if amount == cfg.get("entry_fee", 888):
                    from ._game import handle_transfer_confirm
                    await handle_transfer_confirm(client, message, game, amount, cfg, ctx)


async def teardown(ctx):
    pass


async def _auto_delete(message, delay: int):
    import asyncio
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
