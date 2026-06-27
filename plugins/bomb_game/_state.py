# =============================================================================
# 数字炸弹游戏 - 状态管理（GameStateManager）
#
# 原项目用 data/bomb_game_state.json 在 user/bot 多实例间同步状态。
# 迁到平台后是单插件单进程：这里改为「内存单实例 + ctx.kv 持久化」。
#   - 每群一个 kv 键：game:<chat_id>，值为 JSON-able dict。
#   - 实例化时从 kv 一次性恢复所有活跃局，之后内存状态即权威，每次变更立刻写 kv。
#   - 配置（entry_fee / pool_ratio / wait_time / 范围调整）从 ctx.config 实时读取，
#     不再 import config。
#
# 不 import pyrogram / core；方法接收的 client 是平台传入的 pyrogram Client。
# =============================================================================

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional

from ._helpers import build_shrink_config, calc_shrink_amount, select_smart_bomb_position

_KEY_PREFIX = "game:"


class GameStateManager:
    """游戏状态管理器（内存权威 + ctx.kv 持久化）。"""

    def __init__(self, ctx):
        self._ctx = ctx
        self.kv = ctx.kv
        self.log = ctx.log
        self.state: Dict[str, dict] = {}
        self._locks: Dict[int, asyncio.Lock] = {}
        self._invalid_chat_ids: set = set()
        self._load_state()

    # ── 配置读取（实时） ─────────────────────────────────────────────────────
    @property
    def config(self) -> dict:
        return self._ctx.config

    def get_entry_fee(self) -> int:
        try:
            return int(self.config.get("entry_fee", 888) or 888)
        except (ValueError, TypeError):
            return 888

    def get_pool_ratio(self) -> float:
        # 配置里存的是百分比（10-90），换算成 0-1 小数
        try:
            return float(self.config.get("pool_ratio", 50) or 50) / 100.0
        except (ValueError, TypeError):
            return 0.5

    def get_wait_time(self) -> int:
        try:
            return int(self.config.get("wait_time", 30) or 30)
        except (ValueError, TypeError):
            return 30

    def _shrink_cfg(self) -> dict:
        return build_shrink_config(self.config)

    # ── 持久化 ───────────────────────────────────────────────────────────────
    def _load_state(self):
        """从 kv 恢复所有局（仅在实例化时调用一次）。"""
        self.state = {}
        try:
            for key in self.kv.keys():
                if key.startswith(_KEY_PREFIX):
                    chat_id_str = key[len(_KEY_PREFIX):]
                    data = self.kv.get(key)
                    if isinstance(data, dict):
                        self.state[chat_id_str] = data
        except Exception as e:
            self.log.warning("加载游戏状态失败: %s", e)
            self.state = {}

    def _persist(self, chat_id_str: str):
        """把单局写回 kv（不存在则删除对应键）。"""
        key = _KEY_PREFIX + chat_id_str
        if chat_id_str in self.state:
            self.kv.set(key, self.state[chat_id_str])
        else:
            self.kv.delete(key)

    def _save_state(self):
        """兼容旧调用：全量写回所有局。"""
        for chat_id_str in list(self.state.keys()):
            self.kv.set(_KEY_PREFIX + chat_id_str, self.state[chat_id_str])

    # 旧代码到处调用 _load_state() 做跨进程同步；单进程下内存即权威，置为 no-op。
    def reload(self):
        pass

    # ── 并发锁 / 黑名单 ──────────────────────────────────────────────────────
    def _get_lock(self, chat_id: int):
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    def _is_chat_id_valid(self, chat_id: int) -> bool:
        return chat_id not in self._invalid_chat_ids

    def _add_invalid_chat_id(self, chat_id: int):
        self._invalid_chat_ids.add(chat_id)
        self.log.warning("聊天ID %s 已添加到无效列表", chat_id)

    async def _validate_chat_access(self, client, chat_id: int) -> bool:
        """验证聊天访问权限（用异常类名判断 PeerIdInvalid，避免 import core 异常）。"""
        try:
            if not self._is_chat_id_valid(chat_id):
                return False
            await client.get_chat(chat_id)
            return True
        except Exception as e:
            name = type(e).__name__
            if name == "PeerIdInvalid":
                self.log.error("聊天ID无效或无权限访问: %s", chat_id)
                self._add_invalid_chat_id(chat_id)
                await self._cleanup_invalid_chat_state(chat_id)
                return False
            self.log.error("验证聊天ID %s 失败: %s", chat_id, e)
            return False

    async def _cleanup_invalid_chat_state(self, chat_id: int):
        chat_id_str = str(chat_id)
        if chat_id_str in self.state:
            del self.state[chat_id_str]
            self._persist(chat_id_str)
            self._locks.pop(chat_id, None)

    # ── 范围调整 / 动态移弹 ──────────────────────────────────────────────────
    def _calculate_shrink_amount(self, distance: int, result_type: str) -> int:
        return calc_shrink_amount(self._shrink_cfg(), distance)

    def _adjust_bomb_number(self, chat_id: int, guess: int, result: str) -> bool:
        if not self.is_game_active(chat_id):
            return False
        game_info = self.state[str(chat_id)]
        if not game_info.get("dynamic_mode", False):
            return False

        current_bomb = game_info["bomb_number"]
        min_range = game_info["min_range"]
        max_range = game_info["max_range"]

        available_numbers = [n for n in range(min_range, max_range + 1) if n != current_bomb]
        if not available_numbers:
            extended_min = max(1, min_range - 5)
            extended_max = min(100, max_range + 5)
            for num in range(extended_min, extended_max + 1):
                if num != current_bomb and min_range <= num <= max_range:
                    available_numbers.append(num)
        if not available_numbers:
            return False

        new_bomb = select_smart_bomb_position(available_numbers, game_info["guesses"])
        if new_bomb != current_bomb:
            game_info["bomb_number"] = new_bomb
            game_info["adjustment_count"] += 1
            self._persist(str(chat_id))
            return True
        return False

    # ── 游戏生命周期 ─────────────────────────────────────────────────────────
    async def start_game(self, client, chat_id: int, bomb_number: int, admin_id: int, continuous: bool = False) -> bool:
        """开始游戏（奖池模式总是启用）。"""
        if not await self._validate_chat_access(client, chat_id):
            self.log.error("无法在聊天ID %s 中开始游戏", chat_id)
            return False
        if self.is_game_active(chat_id):
            return False

        import random
        # 爆炸场景：90% 最后1个数字，10% 最后5个数字
        explosion_scenario = "last_1" if random.random() < 0.9 else "last_5"

        entry_fee = self.get_entry_fee()
        pool_ratio = self.get_pool_ratio()
        wait_time = self.get_wait_time()

        self.state[str(chat_id)] = {
            "active": True,
            "bomb_number": bomb_number,
            "original_bomb_number": bomb_number,
            "admin_id": admin_id,
            "continuous": continuous,
            "start_time": datetime.now().isoformat(),
            "guesses": [],
            "min_range": 1,
            "max_range": 100,
            "winner": None,
            "adjustment_count": 0,
            "dynamic_mode": True,
            "explosion_scenario": explosion_scenario,
            "final_bomb": None,
            "pool_amount": 0,
            "participants": {},          # {user_id: {amount, message_id}}
            "pending_participants": {},  # {user_id: {amount, timestamp, message_id}}
            "entry_fee": entry_fee,
            "pool_ratio": pool_ratio,
            "wait_time": wait_time,
            "game_phase": "waiting",
        }
        self._persist(str(chat_id))
        self.log.info("游戏已在聊天ID %s 中开始，奖池模式: 启用", chat_id)
        return True

    def end_game(self, chat_id: int, winner_id: Optional[int] = None) -> bool:
        if not self.is_game_active(chat_id):
            return False
        if winner_id:
            self.state[str(chat_id)]["winner"] = winner_id
        self.state[str(chat_id)]["active"] = False
        self.state[str(chat_id)]["end_time"] = datetime.now().isoformat()
        self._persist(str(chat_id))
        return True

    async def end_game_and_cleanup(self, client, chat_id: int, winner_id: Optional[int] = None) -> bool:
        if not self.is_game_active(chat_id):
            return False
        game_ended = self.end_game(chat_id, winner_id)
        if game_ended:
            await self.delete_start_message(client, chat_id)
        return game_ended

    def is_game_active(self, chat_id: int) -> bool:
        return self.state.get(str(chat_id), {}).get("active", False)

    def get_game_info(self, chat_id: int) -> Optional[Dict]:
        return self.state.get(str(chat_id))

    # ── 猜测 ─────────────────────────────────────────────────────────────────
    async def add_guess(self, chat_id: int, user_id: int, guess: int, result: str):
        """添加猜测记录，返回 (是否成功, 剩余冷却秒数)。"""
        try:
            if not self._is_chat_id_valid(chat_id):
                return False, 0
            if not self.is_game_active(chat_id):
                return False, 0

            lock = self._get_lock(chat_id)
            async with lock:
                game_info = self.state[str(chat_id)]
                current_time = datetime.now()

                # 10秒冷却
                for guess_record in reversed(game_info["guesses"]):
                    if guess_record["user_id"] == user_id:
                        last_guess_time = datetime.fromisoformat(guess_record["timestamp"])
                        time_diff = (current_time - last_guess_time).total_seconds()
                        if time_diff < 10:
                            return False, int(10 - time_diff)
                        break

                original_bomb_number = game_info["bomb_number"]

                bomb_adjusted = False
                if result != "bomb":
                    bomb_adjusted = self._adjust_bomb_number(chat_id, guess, result)

                game_info["guesses"].append({
                    "user_id": user_id,
                    "guess": guess,
                    "result": result,
                    "timestamp": current_time.isoformat(),
                    "bomb_adjusted": bomb_adjusted,
                })

                # 更新范围（用调整前炸弹位置算距离）
                if result == "too_high":
                    distance = guess - original_bomb_number
                    adjust_amount = self._calculate_shrink_amount(distance, "too_high")
                    new_max = min(game_info["max_range"], guess - 1)
                    if adjust_amount >= 0:
                        game_info["max_range"] = min(new_max, guess - adjust_amount)
                    else:
                        expanded_max = min(100, new_max + abs(adjust_amount))
                        game_info["max_range"] = min(expanded_max, guess - 1)
                    if game_info["max_range"] < game_info["min_range"]:
                        game_info["max_range"] = game_info["min_range"]
                elif result == "too_low":
                    distance = original_bomb_number - guess
                    adjust_amount = self._calculate_shrink_amount(distance, "too_low")
                    new_min = max(game_info["min_range"], guess + 1)
                    if adjust_amount >= 0:
                        game_info["min_range"] = max(new_min, guess + adjust_amount)
                    else:
                        expanded_min = max(1, new_min - abs(adjust_amount))
                        game_info["min_range"] = max(expanded_min, guess + 1)
                    if game_info["min_range"] > game_info["max_range"]:
                        game_info["min_range"] = game_info["max_range"]

                if game_info["min_range"] > game_info["max_range"]:
                    game_info["min_range"] = game_info["max_range"]

                self._persist(str(chat_id))
                return True, 0
        except Exception as e:
            self.log.error("添加猜测记录失败 (chat=%s, user=%s): %s", chat_id, user_id, e)
            return False, 0

    def check_guess(self, chat_id: int, guess: int) -> str:
        if not self.is_game_active(chat_id):
            return "no_game"
        game_info = self.state[str(chat_id)]
        bomb_number = game_info["bomb_number"]
        if guess == bomb_number:
            return "bomb"
        elif guess > bomb_number:
            return "too_high"
        else:
            return "too_low"

    def is_valid_guess(self, chat_id: int, guess: int) -> bool:
        if not self.is_game_active(chat_id):
            return False
        game_info = self.state[str(chat_id)]
        return game_info["min_range"] <= guess <= game_info["max_range"]

    def get_range_info(self, chat_id: int) -> tuple:
        if not self.is_game_active(chat_id):
            return (0, 0)
        game_info = self.state[str(chat_id)]
        return (game_info["min_range"], game_info["max_range"])

    def get_guesses_count(self, chat_id: int) -> int:
        if not self.is_game_active(chat_id):
            return 0
        return len(self.state[str(chat_id)]["guesses"])

    def is_last_number(self, chat_id: int) -> bool:
        if not self.is_game_active(chat_id):
            return False
        game_info = self.state[str(chat_id)]
        return game_info["min_range"] == game_info["max_range"]

    # ── 奖池 / 参与者 ────────────────────────────────────────────────────────
    def add_pending_participant(self, chat_id: int, user_id: int, amount: int, message_id: int = None) -> bool:
        if not self.is_game_active(chat_id):
            return False
        game_info = self.state[str(chat_id)]
        if str(user_id) in game_info["participants"]:
            return False
        if str(user_id) in game_info.get("pending_participants", {}):
            return False
        game_info.setdefault("pending_participants", {})[str(user_id)] = {
            "amount": amount,
            "timestamp": datetime.now().isoformat(),
            "message_id": message_id,
        }
        self._persist(str(chat_id))
        self.log.info("用户 %s 添加到待确认列表，金额: %s", user_id, amount)
        return True

    def has_pending_participation(self, chat_id: int, user_id: int) -> bool:
        if not self.is_game_active(chat_id):
            return False
        game_info = self.state[str(chat_id)]
        return str(user_id) in game_info.get("pending_participants", {})

    def confirm_participation(self, chat_id: int, user_id: int) -> bool:
        if not self.is_game_active(chat_id):
            return False
        game_info = self.state[str(chat_id)]
        pending = game_info.get("pending_participants", {})
        if str(user_id) not in pending:
            return False
        pending_info = pending[str(user_id)]
        amount = pending_info["amount"]
        message_id = pending_info.get("message_id")
        del pending[str(user_id)]
        game_info["participants"][str(user_id)] = {"amount": amount, "message_id": message_id}
        game_info["pool_amount"] += amount
        self._persist(str(chat_id))
        self.log.info("用户 %s 参与确认成功，金额: %s，总奖池: %s", user_id, amount, game_info["pool_amount"])
        return True

    def cleanup_expired_pending_participants(self, chat_id: int, max_age_minutes: int = 5) -> int:
        if not self.is_game_active(chat_id):
            return 0
        game_info = self.state[str(chat_id)]
        pending = game_info.get("pending_participants", {})
        if not pending:
            return 0
        current_time = datetime.now()
        expired = []
        for user_id_str, info in pending.items():
            try:
                pending_time = datetime.fromisoformat(info["timestamp"])
                if (current_time - pending_time).total_seconds() / 60 > max_age_minutes:
                    expired.append(user_id_str)
            except (ValueError, KeyError):
                expired.append(user_id_str)
        for user_id_str in expired:
            del pending[user_id_str]
        if expired:
            self._persist(str(chat_id))
        return len(expired)

    def get_pool_info(self, chat_id: int) -> dict:
        if not self.is_game_active(chat_id):
            return {}
        game_info = self.state[str(chat_id)]
        return {
            "enabled": True,
            "amount": game_info.get("pool_amount", 0),
            "participants": len(game_info.get("participants", {})),
            "entry_fee": game_info.get("entry_fee", self.get_entry_fee()),
            "pool_ratio": game_info.get("pool_ratio", self.get_pool_ratio()),
        }

    def calculate_pool_reward(self, chat_id: int) -> tuple:
        if not self.is_game_active(chat_id):
            return 0, 0
        game_info = self.state[str(chat_id)]
        pool_amount = game_info.get("pool_amount", 0)
        pool_ratio = game_info.get("pool_ratio", 0.5)
        winner_reward = int(pool_amount * pool_ratio)
        return winner_reward, pool_amount - winner_reward

    def is_participant(self, chat_id: int, user_id: int) -> bool:
        if not self.is_game_active(chat_id):
            return False
        game_info = self.state[str(chat_id)]
        return str(user_id) in game_info.get("participants", {})

    def get_participant_ids(self, chat_id: int) -> list:
        if not self.is_game_active(chat_id):
            return []
        game_info = self.state[str(chat_id)]
        return [int(uid) for uid in game_info.get("participants", {}).keys()]

    # ── 消息ID追踪 ───────────────────────────────────────────────────────────
    def set_start_message_id(self, chat_id: int, message_id: int) -> bool:
        if not self.is_game_active(chat_id):
            return False
        self.state[str(chat_id)]["start_message_id"] = message_id
        self._persist(str(chat_id))
        return True

    def get_start_message_id(self, chat_id: int) -> Optional[int]:
        info = self.state.get(str(chat_id))
        return info.get("start_message_id") if info else None

    def set_last_game_message_id(self, chat_id: int, message_id: int) -> bool:
        if str(chat_id) not in self.state:
            return False
        self.state[str(chat_id)]["last_game_message_id"] = message_id
        self._persist(str(chat_id))
        return True

    def get_last_game_message_id(self, chat_id: int) -> Optional[int]:
        info = self.state.get(str(chat_id))
        return info.get("last_game_message_id") if info else None

    async def delete_start_message(self, client, chat_id: int):
        try:
            message_id = self.get_start_message_id(chat_id)
            if message_id:
                await client.delete_messages(chat_id, message_id)
        except Exception as e:
            self.log.warning("删除开始消息失败: %s", e)

    # ── 游戏阶段 ─────────────────────────────────────────────────────────────
    def set_game_phase(self, chat_id: int, phase: str) -> bool:
        if not self.is_game_active(chat_id):
            return False
        self.state[str(chat_id)]["game_phase"] = phase
        self._persist(str(chat_id))
        return True

    def get_game_phase(self, chat_id: int) -> str:
        if not self.is_game_active(chat_id):
            return "none"
        return self.state[str(chat_id)].get("game_phase", "playing")

    def is_waiting_phase(self, chat_id: int) -> bool:
        return self.get_game_phase(chat_id) == "waiting"

    def is_playing_phase(self, chat_id: int) -> bool:
        return self.get_game_phase(chat_id) == "playing"

    # ── 中断 / 返还奖池 / 清理 ───────────────────────────────────────────────
    async def _return_pool_to_participants(self, client, chat_id: int, game_info: dict):
        """返还奖池给参与者（reply +金额 让群转账 bot 打款）。"""
        try:
            participants = game_info.get("participants", {})
            if not participants:
                return
            return_msg = (
                f"🔄 **游戏中断，奖池返还**\n\n"
                f"💰 总奖池：{game_info.get('pool_amount', 0)} 魔力\n"
                f"👥 参与人数：{len(participants)} 人\n\n"
                f"**返还详情：**\n"
            )
            for user_id_str, participant_info in participants.items():
                try:
                    user_id = int(user_id_str)
                    if isinstance(participant_info, dict):
                        amount = participant_info.get("amount", 0)
                        message_id = participant_info.get("message_id")
                    else:
                        amount = participant_info
                        message_id = None
                    try:
                        user = await client.get_users(user_id)
                        user_name = user.first_name or str(user_id)
                        if user.last_name:
                            user_name += f" {user.last_name}"
                    except Exception:
                        user_name = str(user_id)
                    if message_id:
                        await client.send_message(chat_id, f"+{amount}", reply_to_message_id=message_id)
                    else:
                        await client.send_message(chat_id, f"@{user_id} +{amount}")
                    return_msg += f"• {user_name}：+{amount} 魔力\n"
                except Exception as e:
                    self.log.error("返还奖池给用户 %s 失败: %s", user_id_str, e)
                    return_msg += f"• 用户 {user_id_str}：返还失败\n"
            await client.send_message(chat_id, return_msg)
            self.log.info("奖池返还完成，聊天ID: %s", chat_id)
        except Exception as e:
            self.log.error("返还奖池失败: %s", e)

    async def interrupt_game_and_return_pool(self, client, chat_id: int, reason: str = "manual") -> bool:
        if not self.is_game_active(chat_id):
            return False
        game_info = self.state[str(chat_id)]
        if game_info.get("pool_amount", 0) > 0:
            await self._return_pool_to_participants(client, chat_id, game_info)
        if game_info.get("pending_participants"):
            game_info["pending_participants"] = {}
        await self.delete_start_message(client, chat_id)
        game_info["active"] = False
        game_info["end_time"] = datetime.now().isoformat()
        game_info["end_reason"] = reason
        self._persist(str(chat_id))
        self.log.info("游戏已中断并返还奖池，聊天ID: %s, 原因: %s", chat_id, reason)
        return True

    async def cleanup_old_games(self, client):
        """清理旧游戏：非活跃且超24h删除；活跃超2h自动中断并返还奖池。"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        to_remove = []
        returned_pools = []
        for chat_id, game_info in list(self.state.items()):
            if not game_info.get("active", False):
                start_time = datetime.fromisoformat(game_info.get("start_time", "1970-01-01T00:00:00"))
                if start_time < cutoff_time:
                    to_remove.append(chat_id)
            else:
                start_time = datetime.fromisoformat(game_info.get("start_time", "1970-01-01T00:00:00"))
                if start_time < datetime.now() - timedelta(hours=2):
                    if game_info.get("pool_amount", 0) > 0:
                        await self._return_pool_to_participants(client, int(chat_id), game_info)
                        returned_pools.append(chat_id)
                    game_info["active"] = False
                    game_info["end_time"] = datetime.now().isoformat()
                    game_info["end_reason"] = "timeout"
                    to_remove.append(chat_id)
        for chat_id in to_remove:
            self.state.pop(chat_id, None)
            self.kv.delete(_KEY_PREFIX + chat_id)
        return len(to_remove), len(returned_pools)

    # ── 状态文案 ─────────────────────────────────────────────────────────────
    def get_game_status(self, chat_id: int) -> Optional[str]:
        if not self.is_game_active(chat_id):
            return "❌ 当前没有进行中的游戏"
        game_info = self.get_game_info(chat_id)
        if not game_info:
            return "❌ 游戏状态异常"
        game_phase = self.get_game_phase(chat_id)
        phase_text = "⏰ 等待参与阶段" if game_phase == "waiting" else "🎮 游戏进行中"
        pool_info = self.get_pool_info(chat_id)
        if game_phase == "waiting":
            pending_count = len(game_info.get("pending_participants", {}))
            return (
                f"🎯 **数字炸弹游戏准备中**\n\n"
                f"📊 游戏阶段：{phase_text}\n"
                f"💰 当前奖池：{pool_info['amount']} 魔力\n"
                f"👥 已确认参与：{pool_info['participants']} 人\n"
                f"⏳ 待确认参与：{pending_count} 人\n"
                f"🎫 参与费用：{pool_info['entry_fee']} 魔力\n"
                f"⏰ 开始时间：{game_info.get('start_time', '未知')}"
            )
        else:
            min_range, max_range = self.get_range_info(chat_id)
            guesses_count = self.get_guesses_count(chat_id)
            return (
                f"🎯 **数字炸弹游戏进行中**\n\n"
                f"📊 游戏阶段：{phase_text}\n"
                f"🔢 猜测次数：{guesses_count}\n"
                f"🎮 当前范围：{min_range} - {max_range}\n"
                f"💰 当前奖池：{pool_info['amount']} 魔力\n"
                f"👥 参与人数：{pool_info['participants']} 人\n"
                f"⏰ 开始时间：{game_info.get('start_time', '未知')}"
            )
