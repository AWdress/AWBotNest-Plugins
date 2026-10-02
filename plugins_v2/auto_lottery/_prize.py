# =============================================================================
# 自动抽奖插件 - 发奖记录与发放
#
# 原项目用 PrizeService（DI 容器）+ _PrizeStateProxy + 全局 pending_prizes 字典
# 记录待发奖、跨模块共享。本平台改用 ctx.kv 持久化：
#
#   - 在「开奖」时解析中奖者并把**可序列化**的待发奖记录写进 ctx.kv（含每位中奖者的
#     reply_chat_id / message_id —— 在解析时即从 Message.entities 提取出来，因此后续
#     发奖完全不需要再持有 pyrogram Message 对象）。
#   - 发奖（自动/手动）从 ctx.kv 读记录，对每位中奖者回复 "+金额"。
#
# 这样既消除了对 PrizeService/DB 的依赖，也让待发奖列表可跨重启保留、在前端可见。
# =============================================================================
from __future__ import annotations

import asyncio
import json
import time as _time
from random import randint

from telethon.errors import RPCError, RandomIdDuplicateError

from ._helpers import parse_draw_identity, parse_winners

_PENDING_KEY = "pending_prizes"   # 待发奖记录 {lottery_id: record}
_HISTORY_KEY = "prize_history"    # 发奖历史（环形）
_HISTORY_MAX = 100
_COMPLETED_KEY = "completed_prizes"


class PrizeStore:
    """基于 ctx.kv 的待发奖记录器（替代 PrizeService / pending_prizes 全局字典）。"""

    def __init__(self, ctx):
        self._ctx = ctx
        self._kv = ctx.storage
        self._state = {}
        self._pending = set()
        self._sending: set[str] = set()
        self._write_lock = asyncio.Lock()
        self._write_errors: list[BaseException] = []

    async def initialize(self) -> None:
        self._state.update(dict(await self._kv.items()))

    def _persist(self, key, value) -> None:
        async def write():
            async with self._write_lock:
                await self._kv.set(key, value)

        task = self._ctx.create_task(write(), name=f"auto-lottery-storage:{key}")
        self._pending.add(task)

        def finished(value):
            self._pending.discard(value)
            if value.cancelled():
                self._write_errors.append(RuntimeError("发奖记录保存被取消"))
            elif value.exception() is not None:
                self._write_errors.append(value.exception())

        task.add_done_callback(finished)

    async def close(self) -> None:
        if self._pending:
            await asyncio.gather(*list(self._pending), return_exceptions=True)
        self._pending.clear()

    async def flush(self) -> None:
        if self._pending:
            # 停用插件时取消发奖任务，不应同时取消刚发出的结果写入。
            await asyncio.shield(asyncio.gather(*list(self._pending)))
        if self._write_errors:
            raise RuntimeError("发奖记录保存失败，请检查存储后重启插件") from self._write_errors[0]

    def is_completed(self, lottery_id: str) -> bool:
        completed = self._state.get(_COMPLETED_KEY, [])
        if isinstance(completed, list) and lottery_id in completed:
            return True
        # 升级前的历史没有 completed 字段，只有确实全部发出时才视为完成。
        return any(
            item.get("lottery_id") == lottery_id
            and item.get("total", 0) > 0
            and item.get("success", 0) == item.get("total")
            and item.get("failed", 0) == 0
            for item in self.history()
        )

    def mark_completed(self, lottery_id: str) -> None:
        completed = self._state.get(_COMPLETED_KEY, [])
        completed = completed if isinstance(completed, list) else []
        # 已付款 ID 不按展示历史截断，避免旧开奖再次编辑后重复发奖。
        self._state[_COMPLETED_KEY] = [lottery_id, *[item for item in completed if item != lottery_id]]
        self._persist(_COMPLETED_KEY, self._state[_COMPLETED_KEY])

    def _load(self) -> dict:
        data = self._state.get(_PENDING_KEY, {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict) -> None:
        self._state[_PENDING_KEY] = json.dumps(data, ensure_ascii=False)
        self._persist(_PENDING_KEY, self._state[_PENDING_KEY])

    def all(self) -> dict:
        return self._load()

    def get(self, lottery_id: str):
        return self._load().get(lottery_id)

    def count(self) -> int:
        return len(self._load())

    def add(self, lottery_id: str, record: dict) -> None:
        data = self._load()
        data[lottery_id] = record
        self._save(data)

    def remove(self, lottery_id: str) -> None:
        data = self._load()
        if lottery_id in data:
            del data[lottery_id]
            self._save(data)

    def clear(self) -> int:
        if self._sending:
            raise RuntimeError("正在发奖，暂不能清空待发列表")
        if any(winner.get('sent') or winner.get('send_state') in {'sending', 'unconfirmed'}
               for record in self._load().values() for winner in record.get('winners', [])):
            raise RuntimeError("存在已发奖或发送结果未确认的记录，不能清空，以免重复发奖")
        n = len(self._load())
        self._save({})
        return n

    def add_history(self, entry: dict) -> None:
        data = self._state.get(_HISTORY_KEY, None)
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = []
        if not isinstance(data, list):
            data = []
        entry = dict(entry)
        entry.setdefault("ts", _time.time())
        data.append(entry)
        if len(data) > _HISTORY_MAX:
            data = data[-_HISTORY_MAX:]
        self._state[_HISTORY_KEY] = json.dumps(data, ensure_ascii=False)
        self._persist(_HISTORY_KEY, self._state[_HISTORY_KEY])

    def history(self) -> list:
        data = self._state.get(_HISTORY_KEY, [])
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = []
        return data if isinstance(data, list) else []


async def record_draw_result(message, lottery_type: str, store: PrizeStore,
                             my_id: str, stored_prize_name: str = "", *, chat=None) -> dict | None:
    """
    解析开奖消息并把待发奖记录写入 store。返回记录 dict（无其他中奖者时返回 None）。
    在此处即把每位中奖者的参与消息位置（reply_chat_id/message_id）解析出来落盘。
    """
    text = message.raw_text or ""
    lottery_id, creator_id = parse_draw_identity(text)
    if not lottery_id or not creator_id:
        return None

    # 只记录自己发起的抽奖
    if str(creator_id) != str(my_id):
        return None

    if store.is_completed(lottery_id):
        return None
    existing = store.get(lottery_id)
    if existing and lottery_id in store._sending:
        return existing

    winners = parse_winners(text, message.entities, lottery_type, my_id, stored_prize_name)
    if existing:
        # 编辑后的开奖可补齐之前缺失的参与链接，但不能覆盖已发出的进度。
        candidates = {}
        for winner in winners:
            key = (winner['user_id'], winner['prize_name'])
            candidates.setdefault(key, []).append(winner)
        for winner in existing.get('winners', []):
            key = (winner.get('user_id'), winner.get('prize_name'))
            matches = candidates.get(key, [])
            parsed = matches.pop(0) if matches else None
            if parsed and not winner.get('sent'):
                if winner.get('reply_chat_id') is None or winner.get('message_id') is None:
                    winner['reply_chat_id'] = parsed['reply_chat_id']
                    winner['message_id'] = parsed['message_id']
        store.add(lottery_id, existing)
        await store.flush()
        return existing
    if not winners:
        return None

    record = {
        'lottery_id': lottery_id,
        'creator_id': creator_id,
        'winners': winners,
        'chat_id': message.chat_id,
        'chat_title': getattr(chat, "title", "") or "",
        'timestamp': _time.time(),
    }
    store.add(lottery_id, record)
    await store.flush()
    return record


async def send_prizes(record: dict, user_app, *, store: PrizeStore, log,
                      interval_enabled: bool, interval_min: int, interval_max: int,
                      send_blacklist: set[str]) -> tuple[int, int, list[dict]]:
    """
    给一条记录里的所有中奖者发奖（回复参与消息 "+金额"）。
    返回 (本次成功数, 本次待发人数, 失败明细列表)。失败者保留，已发送者不再重复发送。
    """
    lottery_id = record['lottery_id']
    if lottery_id in store._sending:
        raise RuntimeError("该抽奖正在发奖，请等待当前任务完成")
    store._sending.add(lottery_id)
    try:
        current = store.get(lottery_id)
        if current is None or store.is_completed(lottery_id):
            return 0, 0, []
        # 有存储故障时先停止，不能在发送后才发现无法保存进度。
        await store.flush()
        winners = [winner for winner in current['winners'] if not winner.get('sent')]
        success = 0
        failed: list[dict] = []
        interval_min, interval_max = sorted((max(0, interval_min), max(0, interval_max)))
        if winners:
            await asyncio.sleep(randint(3, 8))

        for winner in winners:
            user_name = winner.get('user_name', '')
            user_id = str(winner.get('user_id', ''))
            try:
                amount_text = str(winner.get('prize_amount', '')).strip()
                prize_amount = int(amount_text) if amount_text.isdecimal() else 0
            except (TypeError, ValueError):
                prize_amount = 0
            reason = ""
            sent = None
            if winner.get('send_state') in {'sending', 'unconfirmed'}:
                reason = '上次发送结果未确认，请核对参与消息，不能直接重复发奖'
            elif user_id in send_blacklist:
                reason = '命中发送黑名单'
            elif prize_amount <= 0:
                reason = '奖品数量为0或无法解析'
            elif winner.get('reply_chat_id') is None or winner.get('message_id') is None:
                reason = '未找到参与消息链接'
            else:
                # 先登记发送中的状态：断网或停用时可能已发出却没收到回执，不能盲目补发。
                winner['send_state'] = 'sending'
                store.add(lottery_id, current)
                await store.flush()
                try:
                    sent = await user_app.send_message(
                        winner['reply_chat_id'], f"+{prize_amount}",
                        reply_to=winner['message_id'], parse_mode=None,
                    )
                except Exception as exc:  # noqa: BLE001
                    if (isinstance(exc, RPCError) and not isinstance(exc, RandomIdDuplicateError)
                            and 0 < getattr(exc, 'code', 0) < 500):
                        winner['send_state'] = 'failed'
                        reason = str(exc) or type(exc).__name__
                    else:
                        winner['send_state'] = 'unconfirmed'
                        reason = f'发送结果未确认，请核对参与消息：{str(exc) or type(exc).__name__}'

            if reason:
                winner['failure_reason'] = reason
                failed.append({'user_name': user_name, 'user_id': user_id, 'reason': reason})
                if log:
                    log.warning("发奖失败 - %s (%s): %s", user_name, user_id, reason)
            else:
                winner.update({'sent': True, 'send_state': 'sent', 'sent_message_id': getattr(sent, 'id', None), 'sent_at': _time.time()})
                winner.pop('failure_reason', None)
                success += 1
                if log:
                    log.info("发奖指令已发送给 %s (%s): +%s", user_name, user_id, prize_amount)

            # 每位发出后立即落盘，取消或重启后的补发只处理未发者。
            store.add(lottery_id, current)
            await store.flush()
            if not reason and interval_enabled:
                await asyncio.sleep(randint(interval_min, interval_max))

        if all(winner.get('sent') for winner in current['winners']):
            store.mark_completed(lottery_id)
            store.remove(lottery_id)
        store.add_history({
            'lottery_id': lottery_id, 'total': len(winners), 'success': success,
            'failed': len(failed), 'failures': failed,
        })
        await store.flush()
        if log:
            log.info("抽奖 %s 发奖结束，成功 %d/%d 人，失败 %d 人", lottery_id, success, len(winners), len(failed))
        return success, len(winners), failed
    finally:
        store._sending.discard(lottery_id)
