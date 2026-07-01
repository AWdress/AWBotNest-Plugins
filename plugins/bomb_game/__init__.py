# =============================================================================
# AWBotNest 插件：数字炸弹（bomb_game）
#
# 群内数字炸弹竞猜：管理员（你的用户账号）在群里发「开启数字炸弹」/「持续数字炸弹」，
# 群友回复开始消息发 +金额 组奖池，轮流发「我猜是N」猜数字。系统按距离调整范围、
# 动态移弹、三种爆炸场景 + 千分率一发命中；爆炸时中奖者按比例分奖池（reply +金额
# 由群转账 bot 实际打款）。持续模式爆炸后 3 秒自动重开；管理员发「结束数字炸弹」
# 中断并返还奖池。
#
# 迁移自 AWLottery。规范：禁止 import pyrogram/core/config/...，一切走 ctx。
# 私有辅助见 _state.py / _game.py / _helpers.py（包内 from . 导入）。
# =============================================================================

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
    "version": "1.0.3",
    "author": "AWdress",
    "description": "群内数字炸弹竞猜：开启后群友回复+金额参与组奖池，轮流猜数字，猜中/范围耗尽即爆炸，中奖者按比例分奖池。",
    "scope": "both",
    "default_enabled": False,
    "config_schema": {
        # —— 群组 ——
        "valid_groups": {
            "type": "text", "default": "", "label": "允许的群组ID",
            "section": "群组", "help": "一行一个群组ID。只有这些群能玩（需群内有转账bot发奖）。留空=不限制。",
        },
        # —— 奖池 ——
        "entry_fee": {
            "type": "number", "default": 888, "label": "参与费用(魔力)",
            "min": 1, "section": "奖池", "help": "玩家回复开始消息发 +此金额 参与。",
        },
        "pool_ratio": {
            "type": "slider", "default": 50, "label": "中奖者分成比例(%)",
            "min": 10, "max": 90, "step": 5, "section": "奖池",
            "help": "中奖者获得奖池的比例，其余为系统抽成。",
        },
        "wait_time": {
            "type": "slider", "default": 30, "label": "参与等待时间(秒)",
            "min": 15, "max": 120, "step": 5, "section": "奖池",
        },
        # —— 难度 ——
        "enable_range_shrink": {
            "type": "boolean", "default": False, "label": "启用范围调整机制",
            "section": "难度", "help": "开启后按猜测距炸弹的远近奖励缩小/惩罚扩大范围。",
        },
        "shrink_1_5": {
            "type": "number", "default": 0, "label": "距离1-5调整幅度",
            "section": "难度", "help": "正数=缩小(奖励)，负数=扩大(惩罚)。",
            "show_if": {"enable_range_shrink": True},
        },
        "shrink_6_15": {
            "type": "number", "default": -4, "label": "距离6-15调整幅度",
            "section": "难度", "show_if": {"enable_range_shrink": True},
        },
        "shrink_16_30": {
            "type": "number", "default": -2, "label": "距离16-30调整幅度",
            "section": "难度", "show_if": {"enable_range_shrink": True},
        },
        "shrink_31plus": {
            "type": "number", "default": 2, "label": "距离31+调整幅度",
            "section": "难度", "show_if": {"enable_range_shrink": True},
        },
        "instant_win_permille": {
            "type": "slider", "default": 5, "label": "一发命中概率(‰ 千分率)",
            "min": 0, "max": 50, "step": 1, "section": "难度",
            "help": "每次有效猜测直接命中炸弹的概率。默认5‰=0.5%。",
        },
        # —— 消息 ——
        "auto_delete_enabled": {
            "type": "boolean", "default": True, "label": "自动删除提示消息",
            "section": "消息", "help": "范围提示/冷却提示等临时消息自动删除（爆炸结算消息保留）。",
        },
        "auto_delete_disabled_groups": {
            "type": "text", "default": "", "label": "不自动删除的群",
            "section": "消息",
            "help": "一行一个群ID。即使上面总开关开着，这些群也不自动删除消息（对应原版按群关闭自动删除）。",
            "show_if": {"auto_delete_enabled": True},
        },
        # —— 群组临时停用 ——
        "monitor_disabled_groups": {
            "type": "text", "default": "", "label": "临时停用的群",
            "section": "群组",
            "help": "一行一个群ID。这些群虽在允许列表内，但暂时禁止开启数字炸弹（对应原版按群监控开关）。",
        },
        # —— 参与确认 ——
        "require_transfer_confirm": {
            "type": "boolean", "default": False, "label": "需转账bot确认才算参与",
            "section": "参与确认",
            "help": "关(默认/简单模式)：玩家回复开始消息发+金额即视为参与成功。"
                    "开(严格模式)：还需监听到群内转账bot确认转账后才算参与，更防白嫖但依赖转账bot消息形态。",
        },
        "transfer_bot_ids": {
            "type": "text", "default": "", "label": "转账确认bot的ID",
            "section": "参与确认",
            "help": "一行一个转账bot的数字ID。留空=接受群内任意bot的确认消息。仅严格模式生效。",
            "show_if": {"require_transfer_confirm": True},
        },
    },
}


async def setup(ctx):
    cfg = ctx.config

    # 单实例：状态机 + 游戏核心，闭包内各 handler 共享
    state_manager = GameStateManager(ctx)
    valid_groups = parse_groups(cfg.get("valid_groups", ""))
    game = NumberBombGame(ctx, state_manager, valid_groups)

    def _refresh_groups():
        """每次进入 handler 刷新群组配置（用户可能改了配置）。"""
        game.valid_groups = parse_groups(ctx.config.get("valid_groups", ""))
        return game.valid_groups

    ctx.log.info("数字炸弹插件已启用，允许群组数=%s", len(valid_groups) or "不限")

    # ── 用户侧 handler 1：群内发起命令（自己发的）+ 猜数字（别人发的）──────────
    # outgoing 捕获自己发的命令；incoming（非bot）捕获别人的猜数字。合并为一个
    # handler，避免原项目两个重叠 incoming handler 双触发。
    @ctx.on_message(
        (ctx.filters.outgoing & ctx.filters.group)
        | (ctx.filters.incoming & ctx.filters.group & ~ctx.filters.bot),
        group=-2, target="user",
    )
    async def bomb_game_messages(client, message):
        try:
            chat_id = message.chat.id
            groups = _refresh_groups()
            if not group_allowed(groups, chat_id):
                return
            text = text_of(message)
            admin_id = client.me.id if client.me else None

            # 开始 / 持续 / 结束命令（仅自己发的）
            if message.outgoing:
                # 临时停用的群：禁止开启（结束命令仍放行）
                disabled = parse_groups(ctx.config.get("monitor_disabled_groups", ""))
                if (is_start_command(text) or is_continuous_command(text)) and chat_id in disabled:
                    try:
                        await message.edit_text("本群已临时停用数字炸弹（可在插件配置移出停用列表）")
                        game._track(_auto_delete(message, 5))
                    except Exception:
                        pass
                    return
                if is_start_command(text):
                    ctx.log.info("检测到开始游戏命令，chat_id=%s", chat_id)
                    try:
                        await message.edit_text("正在开启数字炸弹游戏（单次模式）...")
                        game._track(_auto_delete(message, 5))
                    except Exception as e:
                        ctx.log.warning("编辑消息失败: %s", e)
                    ok = await game.start_game(client, message, admin_id, continuous=False)
                    if not ok:
                        try:
                            await message.edit_text("数字炸弹游戏启动失败，可能已有游戏进行中")
                        except Exception:
                            pass
                    return

                if is_continuous_command(text):
                    ctx.log.info("检测到持续游戏命令，chat_id=%s", chat_id)
                    try:
                        await message.edit_text("正在开启数字炸弹游戏（持续模式）...")
                        game._track(_auto_delete(message, 5))
                    except Exception as e:
                        ctx.log.warning("编辑消息失败: %s", e)
                    ok = await game.start_game(client, message, admin_id, continuous=True)
                    if not ok:
                        try:
                            await message.edit_text("数字炸弹游戏启动失败，可能已有游戏进行中")
                        except Exception:
                            pass
                    return

                if is_end_command(text):
                    ctx.log.info("检测到结束游戏命令，chat_id=%s", chat_id)
                    try:
                        await message.edit_text("正在结束数字炸弹游戏...")
                        game._track(_auto_delete(message, 5))
                    except Exception as e:
                        ctx.log.warning("编辑消息失败: %s", e)
                    ok = await game.end_game(client, message, admin_id)
                    if not ok:
                        try:
                            await message.edit_text("数字炸弹游戏结束失败，可能没有游戏进行中")
                        except Exception:
                            pass
                    return

            # 猜数字（别人发的 incoming，严格「我猜是N」）
            if not message.outgoing:
                if parse_guess(text) is not None:
                    await game.process_guess(client, message)
                    return

                # 参与：回复开始消息发 +金额（incoming）
                amount = parse_plus_amount(text)
                if amount is not None:
                    await _handle_participation(client, message, amount)
                    return
        except Exception as e:
            ctx.log.error("处理数字炸弹游戏消息时出错: %s", e)

    async def _handle_participation(client, message, amount: int):
        """玩家回复开始消息发 +金额。简单模式即时确认；严格模式仅入待确认。"""
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None
        if user_id is None:
            return

        replied = message.reply_to_message
        replied_from = replied.from_user if replied else None
        # 必须回复自己（user_app）发的游戏开始消息
        if not (replied and replied_from and replied_from.is_self):
            return
        if not is_start_message_text(replied.text):
            return

        if not state_manager.is_game_active(chat_id):
            return
        if not state_manager.is_waiting_phase(chat_id):
            return

        pool_info = state_manager.get_pool_info(chat_id)
        if amount != pool_info["entry_fee"]:
            return
        if state_manager.is_participant(chat_id, user_id):
            return
        if state_manager.has_pending_participation(chat_id, user_id):
            return

        # 入待确认列表
        if not state_manager.add_pending_participant(chat_id, user_id, amount, message.id):
            return

        if not ctx.config.get("require_transfer_confirm", False):
            # 简单模式：直接确认（无二段转账确认）
            await game.confirm_participation_logic(client, message, amount, chat_id, user_id, retry=False)
        else:
            ctx.log.info("用户 %s 已入待确认，等待转账bot确认", user_id)

    # ── 用户侧 handler 2：严格模式下监听转账 bot 的确认消息 ──────────────────
    # 验证逻辑对齐「多站点转账排行榜」的 GET(转入)判定：转账 bot 的确认消息处在回复链上
    #   bot确认 → 回复 → 玩家的「+金额」 → 回复 → 我发的游戏开始消息(is_self)
    # 即 message.reply_to_message.reply_to_message.from_user.is_self（command_to_me）——
    # 只有这样才证明玩家真的把 entry_fee「转给了我(游戏主)」，防白嫖。参与者=+金额发送者，
    # 金额优先取「+金额」文本（可靠），回退 bot 确认文本里的数字。同时兼容个别 bot 直接回复
    # 「+金额」(无更深一层)的形态：只要被回复的 +金额 又回复了我的开始消息即认。
    @ctx.on_message(
        ctx.filters.incoming & ctx.filters.group & ctx.filters.bot,
        group=-3, target="user",
    )
    async def transfer_confirm(client, message):
        try:
            if not ctx.config.get("require_transfer_confirm", False):
                return
            chat_id = message.chat.id
            groups = _refresh_groups()
            if not group_allowed(groups, chat_id):
                return
            if not state_manager.is_game_active(chat_id):
                return

            # 转账 bot 识别（留空=任意 bot）
            bot_ids = parse_bot_ids(ctx.config.get("transfer_bot_ids", ""))
            from_user = message.from_user
            if bot_ids and (not from_user or from_user.id not in bot_ids):
                return

            # bot 必须回复某条消息（即参与者的 +金额 消息）
            replied = message.reply_to_message
            if not (replied and replied.from_user):
                return

            # 关键：验证这是「转给我」的转账 —— 参与者的 +金额 回复的是「我」发的消息。
            # 与排行榜 GET(command_to_me) 判定一致：把群里别人之间的转账排除掉，防白嫖。
            # 若拿不到更深一层回复（个别 bot 形态）则无法判定，退回按 待确认+金额 继续。
            my_msg = getattr(replied, "reply_to_message", None)
            if my_msg is not None:
                mf = getattr(my_msg, "from_user", None)
                if not (mf and getattr(mf, "is_self", False)):
                    return  # 明确是转给别人的，不算参与

            # 参与者 = 被回复消息(+金额)的发送者；金额取 +N（更可靠），回退 bot 文本数字
            participant = replied.from_user
            user_id = participant.id
            plus_amount = parse_plus_amount(text_of(replied))
            if plus_amount is None:
                bonus = extract_amount(message.text or message.caption)
                if bonus is None:
                    return
            else:
                bonus = plus_amount

            # 必须该用户处于待确认
            if not state_manager.has_pending_participation(chat_id, user_id):
                return

            await game.confirm_participation_logic(client, replied, bonus, chat_id, user_id, retry=True)
        except Exception as e:
            ctx.log.error("处理转账确认消息出错: %s", e)

    # ── Bot 侧管理命令（私聊 bot）──────────────────────────────────────────────
    @ctx.on_message(ctx.filters.private & ctx.filters.text, group=-2, target="bot")
    async def bomb_admin_commands(client, message):
        try:
            owner = ctx.owner_id
            uid = message.from_user.id if message.from_user else None
            if owner and uid and uid != owner:
                return
            text = text_of(message)
            parts = text.split()
            if not parts:
                return
            cmd = parts[0].lstrip("./").lower()

            if cmd == "bomb_status":
                if len(parts) > 1:
                    try:
                        target_chat = int(parts[1])
                    except ValueError:
                        await message.reply("无效的群组ID格式")
                        return
                    await message.reply(state_manager.get_game_status(target_chat))
                    return
                msgs = []
                for cid_str in [k[len("game:"):] for k in state_manager.kv.keys() if k.startswith("game:")]:
                    try:
                        cid = int(cid_str)
                    except ValueError:
                        continue
                    if state_manager.is_game_active(cid):
                        msgs.append(f"**群组 {cid}:**\n{state_manager.get_game_status(cid)}")
                await message.reply("\n\n".join(msgs) if msgs else "没有进行中的游戏")

            elif cmd == "bomb_cleanup":
                cleaned, returned = await state_manager.cleanup_old_games(client)
                rmsg = f"清理完成！\n\n删除了 {cleaned} 个旧游戏"
                if returned > 0:
                    rmsg += f"\n返还了 {returned} 个奖池"
                await message.reply(rmsg)

            elif cmd == "bomb_interrupt":
                if len(parts) < 2:
                    await message.reply("格式：`.bomb_interrupt 群组ID`")
                    return
                try:
                    target_chat = int(parts[1])
                except ValueError:
                    await message.reply("无效的群组ID格式")
                    return
                if not state_manager.is_game_active(target_chat):
                    await message.reply(f"群组 {target_chat} 没有进行中的游戏")
                    return
                if await state_manager.interrupt_game_and_return_pool(client, target_chat, "manual_interrupt"):
                    await message.reply(
                        f"**游戏中断成功**\n\n群组ID：{target_chat}\n奖池：已返还给所有参与者")
                else:
                    await message.reply("中断游戏失败")
        except Exception as e:
            ctx.log.error("处理炸弹管理命令出错: %s", e)

    # 自管理后台 task：teardown 时全部取消
    ctx.add_cleanup(game.cancel_all_tasks)


async def teardown(ctx):
    ctx.log.info("数字炸弹插件已停用")


# ── 工具：延迟删除一条消息（模块级，供命令编辑后清理）──────────────────────────
import asyncio  # noqa: E402


async def _auto_delete(message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass
