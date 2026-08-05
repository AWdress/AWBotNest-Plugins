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
    parse_guess, parse_plus_amount, extract_amount,
)
from ._state import GameStateManager
from ._game import NumberBombGame

__plugin__ = {
    "name": "数字炸弹",
    "id": "bomb_game",
    "version": "1.0.5",
    "author": "AWdress",
    "description": "群内数字炸弹竞猜：开启后群友回复+金额参与组奖池，轮流猜数字，猜中/范围耗尽即爆炸，中奖者按比例分奖池。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/bomb_game.png",
    "changelog": "v1.0.4 修复核心接线错误\n- 修复处理函数调用了不存在的旧版 API 导致插件无法运行\n- 按真实游戏引擎接口重接开局/参与/猜数字/转账确认\n- 转账确认改为失败安全：无法唯一定位参与者时跳过，绝不错记金额\n\nv1.0.3 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示\n\nv1.0.2 修复配置界面缺失\n- 随插件发布 frontend/dist 前端构建产物",
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
_game_history = deque(maxlen=50)
_ENGINES = []  # 持有 NumberBombGame 实例，teardown 时统一取消其后台任务


def _effective_cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}


async def _chat_name_items(ctx) -> list[dict]:
    cfg = _effective_cfg(ctx)
    values = []
    for key in ("valid_groups", "monitor_disabled_groups", "no_delete_groups"):
        for value in parse_groups(cfg.get(key, "")):
            if value not in values:
                values.append(value)
    apps = list(getattr(ctx, "user_apps", None) or [])
    items = []
    for value in values:
        title = str(value)
        for app in apps:
            try:
                chat = await app.get_chat(value)
                title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or title
                break
            except Exception:  # noqa: BLE001
                continue
        items.append({"id": value, "title": title})
    return items


async def setup(ctx):
    # 状态管理器与游戏引擎都依赖 ctx，必须在 setup 内构造（不能在模块级）
    state_mgr = GameStateManager(ctx)
    game = NumberBombGame(ctx, state_mgr, parse_groups(_effective_cfg(ctx).get("valid_groups", "")))
    _ENGINES.append(game)

    # ───────── Vue 模式后端 API ─────────
    @ctx.on_api("/games", methods=["GET"])
    async def _api_games(req):
        return {"games": list(_game_history)}

    @ctx.on_api("/chat_names", methods=["GET"])
    async def _api_chat_names(req):
        return {"items": await _chat_name_items(ctx)}

    @ctx.on_api("/update_config", methods=["POST"])
    async def _api_update_config(req):
        body = req.json or {}
        ctx.update_config(body)
        return {"ok": True}

    async def _handle_transfer_confirm(client, message, chat_id, amount):
        """转账 bot 确认 → 定位待确认参与者并确认参与。
        失败安全：优先按「回复到的消息 id」精确匹配，其次按唯一金额匹配；
        都无法唯一定位时记日志跳过，绝不错记金额。
        """
        info = state_mgr.get_game_info(chat_id)
        if not info:
            return
        pending = info.get("pending_participants", {})
        if not pending:
            return
        user_id = None
        reply_to = message.reply_to_message_id
        if reply_to:
            for uid_str, p in pending.items():
                if p.get("message_id") == reply_to:
                    user_id = int(uid_str)
                    break
        if user_id is None:
            try:
                amt = int(float(amount))
            except (ValueError, TypeError):
                return
            matches = [uid for uid, p in pending.items() if int(p.get("amount", 0)) == amt]
            if len(matches) == 1:
                user_id = int(matches[0])
        if user_id is None:
            ctx.log.warning("[bomb_game] 转账确认无法唯一定位参与者，跳过 (chat=%s)", chat_id)
            return
        await game.confirm_participation_logic(client, message, amount, chat_id, user_id, retry=False)

    # ───────── 游戏逻辑 ─────────
    @ctx.on_message(ctx.filters.group, group=7)
    async def on_group_message(client, message):
        cfg = _effective_cfg(ctx)
        chat_id = message.chat.id
        text = text_of(message)

        # 群组白名单 / 停用名单（注意 group_allowed 形参顺序：groups 在前，chat_id 在后）
        valid = parse_groups(cfg.get("valid_groups", ""))
        disabled = parse_groups(cfg.get("monitor_disabled_groups", ""))
        game.valid_groups = valid  # 每次操作前刷新引擎的可见群组
        if valid and not group_allowed(valid, chat_id):
            return
        if group_allowed(disabled, chat_id):
            return

        admin_id = ctx.owner_id

        # 开启 / 持续
        if is_start_command(text) or is_continuous_command(text):
            if state_mgr.is_game_active(chat_id):
                return
            continuous = is_continuous_command(text)
            if await game.start_game(client, message, admin_id, continuous):
                _game_history.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "group_name": message.chat.title or str(chat_id),
                    "players": 0,
                    "pool": 0,
                    "winner": None,
                    "status": "进行中",
                })
            return

        # 结束（只有开局管理员可结束）
        if is_end_command(text):
            if state_mgr.is_game_active(chat_id):
                info = state_mgr.get_game_info(chat_id) or {}
                if await game.end_game(client, message, info.get("admin_id", admin_id)):
                    if _game_history:
                        _game_history[-1]["status"] = "取消"
            return

        # 参与：回复开始消息 +金额
        if state_mgr.is_game_active(chat_id) and state_mgr.is_waiting_phase(chat_id):
            amount = parse_plus_amount(text)
            reply_to = message.reply_to_message_id
            start_mid = state_mgr.get_start_message_id(chat_id)
            if (amount is not None and reply_to and start_mid
                    and reply_to == start_mid and message.from_user):
                user_id = message.from_user.id
                state_mgr.add_pending_participant(chat_id, user_id, amount, message.id)
                if not cfg.get("require_transfer_confirm", False):
                    # 简单模式：直接确认参与（confirm 内部校验金额是否等于参与费）
                    await game.confirm_participation_logic(client, message, amount, chat_id, user_id, retry=False)
                return

        # 转账 bot 确认（require_transfer_confirm 模式）
        if (cfg.get("require_transfer_confirm", False) and message.from_user
                and message.from_user.is_bot and state_mgr.is_game_active(chat_id)):
            bot_ids = parse_bot_ids(cfg.get("transfer_bot_ids", ""))
            if (not bot_ids) or (message.from_user.id in bot_ids):
                amount = extract_amount(text)
                if amount is not None:
                    await _handle_transfer_confirm(client, message, chat_id, amount)
            return

        # 猜数字（process_guess 内部处理阶段/参与者/范围/一发命中/爆炸结算）
        if parse_guess(text) is not None and state_mgr.is_game_active(chat_id):
            await game.process_guess(client, message)
            if not state_mgr.is_game_active(chat_id):
                info = state_mgr.get_game_info(chat_id) or {}
                if _game_history:
                    _game_history[-1]["status"] = "完成"
                    _game_history[-1]["winner"] = info.get("winner")
            return


async def teardown(ctx):
    while _ENGINES:
        engine = _ENGINES.pop()
        try:
            engine.cancel_all_tasks()
        except Exception:  # noqa: BLE001
            pass
