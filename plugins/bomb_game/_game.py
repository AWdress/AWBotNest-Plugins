# =============================================================================
# 数字炸弹游戏 - 核心逻辑（NumberBombGame）
#
# 开始/猜测/范围调整/爆炸三场景/一发命中/连续模式/参与确认/奖池结算。
# 所有后台延时任务（等待开始、持续重开、自动删除）登记到 self._tasks，
# teardown 时统一 cancel。
#
# 不 import pyrogram / core / config。client 为平台传入的 pyrogram Client，
# ctx 提供配置/日志。
# =============================================================================

import asyncio
import random

from ._helpers import (
    generate_difficult_bomb_number,
    build_shrink_config,
    calc_shrink_amount,
    difficulty_description,
    build_start_message,
)


class NumberBombGame:
    """数字炸弹游戏主逻辑。"""

    def __init__(self, ctx, state_manager, valid_groups: set):
        self._ctx = ctx
        self.log = ctx.log
        self.state_manager = state_manager
        self.valid_groups = valid_groups          # 由 __init__.py 在每次操作前刷新
        self._processing_locks = {}
        self._tasks: set = set()
        # 已提示过的非参与者，避免重复提示。key:(chat_id,user_id) value:"no_game"或start_time
        self._notified_non_participants: dict = {}

    @property
    def config(self) -> dict:
        return self._ctx.config

    # ── 后台任务管理 ─────────────────────────────────────────────────────────
    def _track(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def cancel_all_tasks(self):
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()

    def _get_processing_lock(self, chat_id: int):
        if chat_id not in self._processing_locks:
            self._processing_locks[chat_id] = asyncio.Lock()
        return self._processing_locks[chat_id]

    # ── 自动删除 ─────────────────────────────────────────────────────────────
    def _should_auto_delete(self) -> bool:
        return bool(self.config.get("auto_delete_enabled", True))

    async def _schedule_auto_delete(self, message, delay: int = 15):
        if not self._should_auto_delete():
            return

        async def _delete():
            await asyncio.sleep(delay)
            try:
                await message.delete()
            except Exception as e:
                self.log.warning("自动删除消息失败: %s", e)

        self._track(_delete())

    # ── 难度 ─────────────────────────────────────────────────────────────────
    def _generate_difficult_bomb_number(self) -> int:
        return generate_difficult_bomb_number()

    def _shrink_cfg(self) -> dict:
        return build_shrink_config(self.config)

    def _calculate_shrink_amount(self, distance: int, result_type: str) -> int:
        return calc_shrink_amount(self._shrink_cfg(), distance)

    def _get_difficulty_description(self) -> str:
        return difficulty_description(self._shrink_cfg())

    def _instant_win_probability(self) -> float:
        # 配置存千分率（0-50），换算成概率。原项目固定 0.5% = 5‰。
        try:
            return float(self.config.get("instant_win_permille", 5) or 0) / 1000.0
        except (ValueError, TypeError):
            return 0.005

    # ── 开始消息更新（追加参与者列表） ───────────────────────────────────────
    async def update_start_message_with_participants(self, client, chat_id: int):
        try:
            start_message_id = self.state_manager.get_start_message_id(chat_id)
            if not start_message_id:
                return
            pool_info = self.state_manager.get_pool_info(chat_id)
            participant_ids = self.state_manager.get_participant_ids(chat_id)

            names = []
            for uid in participant_ids:
                try:
                    user = await client.get_users(uid)
                    name = user.first_name or str(uid)
                    if user.last_name:
                        name += f" {user.last_name}"
                    names.append(name)
                except Exception:
                    names.append(str(uid))

            wait_time = self.state_manager.get_wait_time()
            entry_fee = pool_info.get("entry_fee", 888)
            winner_reward = int(pool_info["amount"] * pool_info["pool_ratio"])

            participant_lines = "\n".join(f"  • {name}" for name in names)
            participant_section = (
                f"\n\n👥 **已参与（{len(names)}人）：**\n{participant_lines}\n"
                f"🎫 当前奖池：{pool_info['amount']} 魔力 | 🏆 预计奖励：{winner_reward} 魔力"
            )
            new_text = (
                f"🎯 **数字炸弹游戏准备中！**\n\n"
                f"💣 炸弹数字已设置（1-100之间）\n"
                f"💰 **奖池模式已启用**\n\n"
                f"🎫 **参与阶段（{wait_time}秒）**\n"
                f"💰 参与费用：{entry_fee} 魔力\n"
                f"📝 参与方式：**回复此消息** +{entry_fee}\n"
                f"⚠️ 注意：等待群组bot转账确认后即可参与\n"
                f"💸 **重要**：只能回复此消息参与，其他消息参与无效且魔力不退还\n\n"
                f"⏰ **{wait_time}秒后游戏正式开始**\n"
                f"🎮 只有参与者才能猜数字\n"
                f"🏆 中奖者获得奖池奖励"
                f"{participant_section}"
            )
            await client.edit_message_text(chat_id, start_message_id, new_text)
            self.log.info("已更新群组 %s 的游戏开始消息，参与者: %s 人", chat_id, len(names))
        except Exception as e:
            self.log.warning("更新游戏开始消息失败: %s", e)

    # ── 开始游戏 ─────────────────────────────────────────────────────────────
    async def start_game(self, client, message, admin_id: int, continuous: bool = False) -> bool:
        chat_id = message.chat.id
        if chat_id not in self.valid_groups and self.valid_groups:
            self.log.warning("群组 %s 不在有效群组列表中", chat_id)
            return False
        sender_id = message.from_user.id if message.from_user else admin_id
        if sender_id != admin_id:
            self.log.warning("用户 %s 不是管理员 %s", sender_id, admin_id)
            return False
        if self.state_manager.is_game_active(chat_id):
            self.log.warning("群组 %s 已有游戏进行中", chat_id)
            return False

        bomb_number = self._generate_difficult_bomb_number()
        start_result = await self.state_manager.start_game(client, chat_id, bomb_number, admin_id, continuous)
        if not start_result:
            self.log.error("state_manager.start_game 返回 False")
            return False

        wait_time = self.state_manager.get_wait_time()
        entry_fee = self.state_manager.get_entry_fee()
        start_msg = build_start_message(wait_time, entry_fee, continuous)
        try:
            sent_message = await client.send_message(chat_id, start_msg)
            # 新局开始，清理该群非参与者通知记录
            for k in [k for k in self._notified_non_participants if k[0] == chat_id]:
                del self._notified_non_participants[k]
            self.state_manager.set_start_message_id(chat_id, sent_message.id)
            self._track(self._start_game_after_wait(client, chat_id, wait_time, continuous))
            return True
        except Exception as e:
            self.log.error("发送开始消息失败: %s", e)
            return False

    async def _start_game_after_wait(self, client, chat_id: int, wait_time: int, continuous: bool):
        try:
            await asyncio.sleep(wait_time)
            if not self.state_manager.is_game_active(chat_id):
                self.log.warning("等待时间结束后，游戏已不活跃: %s", chat_id)
                return

            pool_info = self.state_manager.get_pool_info(chat_id)
            participants_count = pool_info.get("participants", 0)
            pool_amount = pool_info.get("amount", 0)

            if participants_count == 0:
                self.log.warning("没有玩家参与，取消游戏: %s", chat_id)
                start_message_id = self.state_manager.get_start_message_id(chat_id)
                self.state_manager.end_game(chat_id)
                try:
                    sent_message = await client.send_message(
                        chat_id, "❌ **游戏取消**\n\n⚠️ 没有玩家参与，游戏自动取消")
                    await self._schedule_auto_delete(sent_message, 15)
                except Exception as e:
                    self.log.error("发送取消消息失败: %s", e)
                if start_message_id:
                    try:
                        await client.delete_messages(chat_id, start_message_id)
                    except Exception as e:
                        self.log.warning("删除开始消息失败: %s", e)
                return

            self.state_manager.set_game_phase(chat_id, "playing")

            start_message_id = self.state_manager.get_start_message_id(chat_id)
            if start_message_id:
                try:
                    await client.delete_messages(chat_id, start_message_id)
                except Exception as e:
                    self.log.warning("删除开始消息失败: %s", e)

            self.state_manager.cleanup_expired_pending_participants(chat_id, 5)

            pool_ratio = self.state_manager.get_pool_ratio()
            winner_reward = int(pool_amount * pool_ratio)
            system_cut = pool_amount - winner_reward

            game_start_msg = (
                f"🎯 **数字炸弹游戏正式开始！**\n\n"
                f"💰 **奖池信息**\n"
                f"🎫 总奖池：{pool_amount} 魔力\n"
                f"👥 参与人数：{participants_count} 人\n"
                f"🏆 中奖奖励：{winner_reward} 魔力 ({int(pool_ratio*100)}%)\n"
                f"💼 系统抽成：{system_cut} 魔力 ({int((1-pool_ratio)*100)}%)\n\n"
                f"🎮 **游戏规则**\n"
                f"• 发送格式：**我猜是XX**（XX为1-100的数字）\n"
                f"• 只有参与者才能猜数字\n"
                f"• 系统会提示\"太大了\"或\"太小了\"\n"
                f"• 每个玩家10秒内只能猜测一次\n\n"
                f"🎯 **难度机制：**\n" + self._get_difficulty_description() + "\n"
                f"⚠️ 注意：只有严格按照格式发送的数字才有效！"
            )
            try:
                sent_message = await client.send_message(chat_id, game_start_msg)
                self.state_manager.set_last_game_message_id(chat_id, sent_message.id)
                self.log.info("数字炸弹游戏在群组 %s 中正式开始，参与者: %s 人", chat_id, participants_count)
            except Exception as e:
                self.log.error("发送游戏开始消息失败: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.log.error("启动游戏失败: %s", e)

    # ── 结束游戏 ─────────────────────────────────────────────────────────────
    async def end_game(self, client, message, admin_id: int) -> bool:
        chat_id = message.chat.id
        sender_id = message.from_user.id if message.from_user else admin_id
        if sender_id != admin_id:
            return False
        if not self.state_manager.is_game_active(chat_id):
            return False

        pool_info = self.state_manager.get_pool_info(chat_id)
        had_pool = pool_info.get("amount", 0) > 0
        if await self.state_manager.interrupt_game_and_return_pool(client, chat_id, "admin_stop"):
            end_msg = "🛑 **数字炸弹游戏已结束**\n\n游戏被管理员强制停止。"
            if had_pool:
                end_msg += "\n\n💰 奖池已返还给所有参与者"
            try:
                sent_message = await client.send_message(chat_id, end_msg)
                await self._schedule_auto_delete(sent_message, 20)
                return True
            except Exception as e:
                self.log.error("发送结束消息失败: %s", e)
                return False
        return False

    # ── 处理猜测 ─────────────────────────────────────────────────────────────
    async def process_guess(self, client, message) -> bool:
        chat_id = message.chat.id
        user_id = message.from_user.id
        if chat_id not in self.valid_groups and self.valid_groups:
            return False

        if not self.state_manager.is_game_active(chat_id):
            key = (chat_id, user_id)
            if self._notified_non_participants.get(key) != "no_game":
                try:
                    sent_message = await message.reply("❌ 当前没有进行中的数字炸弹游戏！\n\n💡 请联系管理员开启！")
                    await self._schedule_auto_delete(sent_message, 5)
                except Exception as e:
                    self.log.error("发送游戏未开始提示失败: %s", e)
                self._notified_non_participants[key] = "no_game"
            return False

        lock = self._get_processing_lock(chat_id)
        try:
            async with asyncio.timeout(10):
                async with lock:
                    return await self._process_guess_internal(client, message, user_id)
        except asyncio.TimeoutError:
            self.log.warning("处理猜测超时: 群组 %s, 用户 %s", chat_id, user_id)
            return False
        except Exception as e:
            self.log.error("处理猜测时发生异常: %s", e)
            return False

    async def _process_guess_internal(self, client, message, user_id: int) -> bool:
        from ._helpers import parse_guess
        chat_id = message.chat.id

        if not self.state_manager.is_playing_phase(chat_id):
            if self.state_manager.is_waiting_phase(chat_id):
                try:
                    pool_info = self.state_manager.get_pool_info(chat_id)
                    if self.state_manager.is_participant(chat_id, user_id) or \
                            self.state_manager.has_pending_participation(chat_id, user_id):
                        sent_message = await message.reply("⏰ 游戏还在参与阶段，等待正式开始后再猜数字！")
                        await self._schedule_auto_delete(sent_message, 8)
                    else:
                        game_info = self.state_manager.get_game_info(chat_id)
                        start_time = game_info.get("start_time", "") if game_info else ""
                        key = (chat_id, user_id)
                        if self._notified_non_participants.get(key) != start_time:
                            sent_message = await message.reply(
                                f"⏰ 游戏还在参与阶段！\n\n"
                                f"💡 现在还能参与哦，回复游戏开始消息发送 +{pool_info.get('entry_fee', 888)} 即可加入～\n"
                                f"⚠️ 注意：参与费用一经确认不退还"
                            )
                            await self._schedule_auto_delete(sent_message, 8)
                            self._notified_non_participants[key] = start_time
                except Exception as e:
                    self.log.error("发送等待提示失败: %s", e)
            else:
                key = (chat_id, user_id)
                if self._notified_non_participants.get(key) != "no_game":
                    try:
                        sent_message = await message.reply("❌ 当前没有进行中的数字炸弹游戏！")
                        await self._schedule_auto_delete(sent_message, 5)
                    except Exception as e:
                        self.log.error("发送游戏未开始提示失败: %s", e)
                    self._notified_non_participants[key] = "no_game"
            return False

        # 必须参与奖池才能猜
        if not self.state_manager.is_participant(chat_id, user_id):
            game_info = self.state_manager.get_game_info(chat_id)
            start_time = game_info.get("start_time", "") if game_info else ""
            key = (chat_id, user_id)
            if self._notified_non_participants.get(key) != start_time:
                try:
                    pool_info = self.state_manager.get_pool_info(chat_id)
                    sent_message = await message.reply(
                        f"❌ 只有参与奖池的玩家才能猜数字！\n\n"
                        f"💰 参与费用：{pool_info['entry_fee']} 魔力\n"
                        f"📝 下次游戏开始时记得回复开始消息参与哦！\n"
                        f"⚠️ 注意：参与费用一经确认不退还"
                    )
                    await self._schedule_auto_delete(sent_message, 8)
                except Exception as e:
                    self.log.error("发送参与提示失败: %s", e)
                self._notified_non_participants[key] = start_time
            return False

        guess = parse_guess((message.text or "").strip())
        if guess is None:
            try:
                sent_message = await message.reply(
                    "❌ 请使用正确格式：**我猜是XX**（XX为1-100的数字）\n\n"
                    "💡 正确格式：\n• 我猜是50\n• 我猜是25\n• 我猜是99")
                await self._schedule_auto_delete(sent_message, 5)
            except Exception as e:
                self.log.error("发送格式提示失败: %s", e)
            return False

        if not self.state_manager.is_valid_guess(chat_id, guess):
            min_range, max_range = self.state_manager.get_range_info(chat_id)
            try:
                sent_message = await message.reply(f"⚠️ 请输入 {min_range}-{max_range} 范围内的数字！")
                await self._schedule_auto_delete(sent_message, 10)
            except Exception as e:
                self.log.error("发送范围提示失败: %s", e)
            return False

        # 一发命中机制（千分率）
        if random.random() < self._instant_win_probability():
            self.log.info("用户 %s 触发一发猜中机制，猜测数字: %s", user_id, guess)
            await self.handle_bomb_explosion_with_pool(client, message, chat_id, user_id, guess)
            return True

        result = self.state_manager.check_guess(chat_id, guess)
        is_last_number = self.state_manager.is_last_number(chat_id)
        should_trigger = is_last_number

        min_range, max_range = self.state_manager.get_range_info(chat_id)
        is_last_5_numbers = (max_range - min_range + 1) <= 5

        game_info = self.state_manager.get_game_info(chat_id)

        # 10%场景：到最后5个数字时确定最终炸弹
        if (game_info["explosion_scenario"] == "last_5" and
                game_info["final_bomb"] is None and is_last_5_numbers):
            available_numbers = list(range(min_range, max_range + 1))
            if available_numbers:
                game_info["final_bomb"] = random.choice(available_numbers)

        should_explode = False
        if result == "bomb":
            should_explode = True
        elif should_trigger and is_last_number:
            should_explode = True
        elif game_info["explosion_scenario"] == "last_5" and is_last_5_numbers:
            if guess == game_info.get("final_bomb", guess):
                should_explode = True

        if should_explode:
            await self.handle_bomb_explosion_with_pool(client, message, chat_id, user_id, guess)
        else:
            guess_added, remaining_time = await self.state_manager.add_guess(chat_id, user_id, guess, result)
            if guess_added:
                await self._send_guess_feedback(client, message, result, guess)
            else:
                try:
                    sent_message = await message.reply(f"⏰ 请等待{remaining_time}秒后再猜测！")
                    await self._schedule_auto_delete(sent_message, 5)
                except Exception as e:
                    self.log.error("发送冷却提示失败: %s", e)
        return True

    async def _send_guess_feedback(self, client, message, result: str, guess: int):
        chat_id = message.chat.id
        min_range, max_range = self.state_manager.get_range_info(chat_id)
        game_info = self.state_manager.get_game_info(chat_id)

        if game_info:
            if result == "too_high":
                distance = guess - game_info.get("original_bomb_number", game_info["bomb_number"])
                feedback = f"📈 **{guess} 太大了！**\n\n请猜测更小的数字。"
            elif result == "too_low":
                distance = game_info.get("original_bomb_number", game_info["bomb_number"]) - guess
                feedback = f"📉 **{guess} 太小了！**\n\n请猜测更大的数字。"
            else:
                return
            adjust_amount = self._calculate_shrink_amount(distance, result)
            if adjust_amount > 0:
                feedback += f"\n\n🎯 奖励缩小了 {adjust_amount} 个数字！"
            elif adjust_amount < 0:
                feedback += f"\n\n🎯 惩罚扩大了 {abs(adjust_amount)} 个数字！"
        else:
            if result == "too_high":
                feedback = f"📈 **{guess} 太大了！**\n\n请猜测更小的数字。"
            elif result == "too_low":
                feedback = f"📉 **{guess} 太小了！**\n\n请猜测更大的数字。"
            else:
                return

        feedback += f"\n\n🎯 当前范围：**{min_range} - {max_range}**"

        pool_info = self.state_manager.get_pool_info(chat_id)
        if pool_info.get("enabled", False) and pool_info["amount"] > 0:
            winner_reward, system_cut = self.state_manager.calculate_pool_reward(chat_id)
            feedback += (
                f"\n\n💰 **奖池信息**\n"
                f"🎫 总奖池：{pool_info['amount']} 魔力\n"
                f"👥 参与人数：{pool_info['participants']} 人\n"
                f"🏆 预计奖励：{winner_reward} 魔力"
            )
        try:
            last_msg_id = self.state_manager.get_last_game_message_id(chat_id)
            if last_msg_id:
                try:
                    await client.delete_messages(chat_id, last_msg_id)
                except Exception:
                    pass
            sent_message = await message.reply(feedback)
            self.state_manager.set_last_game_message_id(chat_id, sent_message.id)
        except Exception as e:
            self.log.error("发送反馈消息失败: %s", e)

    # ── 发奖 ─────────────────────────────────────────────────────────────────
    async def _award_magic_points(self, client, message, user_id: int, points: int):
        try:
            await message.reply(f"+{points}")
            self.log.info("数字炸弹游戏奖励：用户 %s 获得 %s 魔力值", user_id, points)
        except Exception as e:
            self.log.error("发放魔力值奖励失败: %s", e)

    # ── 爆炸结算 ─────────────────────────────────────────────────────────────
    async def handle_bomb_explosion_with_pool(self, client, message, chat_id: int, user_id: int, guess: int):
        try:
            game_info = self.state_manager.get_game_info(chat_id)
            continuous = game_info.get("continuous", False) if game_info else False
            original_admin_id = game_info.get("admin_id", user_id) if game_info else user_id

            pool_info = self.state_manager.get_pool_info(chat_id)
            if pool_info["amount"] > 0:
                winner_reward, system_cut = self.state_manager.calculate_pool_reward(chat_id)
                if winner_reward > 0:
                    await self._award_magic_points(client, message, user_id, winner_reward)
                pool_ratio = pool_info.get("pool_ratio", 0.5)
                explosion_msg = (
                    f"💥 **数字炸弹爆炸！**\n\n"
                    f"🏆 获胜者：{message.from_user.first_name}\n"
                    f"🎯 炸弹数字：{guess}\n\n"
                    f"💰 **奖池结算**\n"
                    f"🎫 总奖池：{pool_info['amount']} 魔力\n"
                    f"🏆 中奖奖励：{winner_reward} 魔力 ({int(pool_ratio*100)}%)\n"
                    f"💼 系统抽成：{system_cut} 魔力 ({int((1-pool_ratio)*100)}%)\n"
                    f"👥 参与人数：{pool_info['participants']} 人\n\n"
                    f"🎉 恭喜获胜！"
                )
            else:
                explosion_msg = (
                    f"💥 **数字炸弹爆炸！**\n\n"
                    f"🏆 获胜者：{message.from_user.first_name}\n"
                    f"🎯 炸弹数字：{guess}\n\n"
                    f"💰 **奖池为空**\n"
                    f"⚠️ 没有玩家参与奖池，无奖励发放\n\n"
                    f"🎉 恭喜猜中！"
                )

            if continuous:
                explosion_msg += "\n\n🔄 **持续模式**：游戏已结束，3秒后自动开始新游戏"
            else:
                explosion_msg += "\n\n🎯 **单次模式**：游戏已结束"

            last_msg_id = self.state_manager.get_last_game_message_id(chat_id)
            if last_msg_id:
                try:
                    await client.delete_messages(chat_id, last_msg_id)
                except Exception:
                    pass

            await client.send_message(chat_id, explosion_msg)  # 结算消息保留

            await self.state_manager.end_game_and_cleanup(client, chat_id, user_id)

            if continuous:
                self._track(self._auto_start_new_game(client, chat_id, original_admin_id))

            self.log.info("数字炸弹游戏结束，获胜者: %s", user_id)
        except Exception as e:
            self.log.error("处理奖池爆炸失败: %s", e)

    async def _auto_start_new_game(self, client, chat_id: int, original_admin_id: int):
        try:
            await asyncio.sleep(3)
            new_bomb_number = self._generate_difficult_bomb_number()
            start_result = await self.state_manager.start_game(
                client, chat_id, new_bomb_number, original_admin_id, True)
            if not start_result:
                self.log.warning("持续模式：在群组 %s 中自动开始新游戏失败", chat_id)
                return
            wait_time = self.state_manager.get_wait_time()
            entry_fee = self.state_manager.get_entry_fee()
            new_start_msg = build_start_message(wait_time, entry_fee, True, restart=True)
            sent_new_message = await client.send_message(chat_id, new_start_msg)
            self.log.info("持续模式：在群组 %s 中自动开始新游戏", chat_id)
            self.state_manager.set_start_message_id(chat_id, sent_new_message.id)
            self._track(self._start_game_after_wait(client, chat_id, wait_time, True))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.log.error("持续模式：自动开始新游戏失败: %s", e)

    # ── 参与确认逻辑（自监听转账或简单模式共用） ─────────────────────────────
    async def confirm_participation_logic(self, client, transform_message, bonus, chat_id: int,
                                          user_id: int, retry: bool = True):
        """核心参与确认逻辑。
        - transform_message: 触发确认的消息（用于回复提示），可为参与者的 +金额 消息。
        - bonus: 金额（int/float/str）。
        - retry: 待确认未命中时是否短暂重试（转账自监听有竞争条件，简单模式无需）。
        """
        if not self.state_manager.is_game_active(chat_id):
            return

        if not self.state_manager.is_waiting_phase(chat_id):
            if self.state_manager.is_playing_phase(chat_id):
                try:
                    hint_msg = await client.send_message(
                        chat_id,
                        "⚠️ 参与无效！游戏已正式开始，参与通道已关闭。\n\n"
                        "💸 本次魔力不退还，下次请在参与阶段回复开始消息参与哦～",
                        reply_to_message_id=transform_message.id if transform_message else None,
                    )
                    await self._schedule_auto_delete(hint_msg, 10)
                except Exception as e:
                    self.log.warning("发送游戏已开始提示失败: %s", e)
            return

        has_pending = self.state_manager.has_pending_participation(chat_id, user_id)
        if not has_pending and retry:
            await asyncio.sleep(0.5)
            has_pending = self.state_manager.has_pending_participation(chat_id, user_id)

        if not has_pending:
            try:
                pool_info = self.state_manager.get_pool_info(chat_id)
                hint_msg = await client.send_message(
                    chat_id,
                    f"⚠️ 参与无效！\n\n"
                    f"必须先**回复游戏开始消息**发送 +{pool_info.get('entry_fee', bonus)}，等待转账确认后才算参与。\n"
                    f"直接发送转账不算参与，💸 本次魔力不退还哦～",
                    reply_to_message_id=transform_message.id if transform_message else None,
                )
                await self._schedule_auto_delete(hint_msg, 10)
            except Exception as e:
                self.log.warning("发送参与无效提示失败: %s", e)
            return

        pool_info = self.state_manager.get_pool_info(chat_id)
        try:
            bonus_amount = int(float(bonus))
        except (ValueError, TypeError) as e:
            self.log.warning("转账金额格式错误: %s, 错误: %s", bonus, e)
            return

        if bonus_amount != pool_info["entry_fee"]:
            self.log.warning("转账金额 %s 与参与费用 %s 不一致", bonus_amount, pool_info["entry_fee"])
            return

        if self.state_manager.confirm_participation(chat_id, user_id):
            updated_pool_info = self.state_manager.get_pool_info(chat_id)
            winner_reward = int(updated_pool_info["amount"] * updated_pool_info["pool_ratio"])
            user_name = "未知用户"
            if transform_message and transform_message.from_user:
                user_name = transform_message.from_user.first_name or "未知用户"
            try:
                success_msg = await client.send_message(
                    chat_id,
                    f"✅ **参与确认成功！**\n\n"
                    f"👤 参与者：{user_name}\n"
                    f"💰 参与金额：{bonus_amount} 魔力\n"
                    f"🎫 当前奖池：{updated_pool_info['amount']} 魔力\n"
                    f"👥 参与人数：{updated_pool_info['participants']} 人\n"
                    f"🏆 预计奖励：{winner_reward} 魔力"
                )
                await self._schedule_auto_delete(success_msg, 10)
            except Exception as e:
                self.log.warning("发送参与成功消息失败: %s", e)
            await self.update_start_message_with_participants(client, chat_id)
            self.log.info("用户 %s 参与确认成功，金额: %s", user_id, bonus_amount)
        else:
            self.log.warning("用户 %s 参与确认失败", user_id)
