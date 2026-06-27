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

from ._helpers import parse_winners

_PENDING_KEY = "pending_prizes"   # 待发奖记录 {lottery_id: record}
_HISTORY_KEY = "prize_history"    # 发奖历史（环形）
_HISTORY_MAX = 100


class PrizeStore:
    """基于 ctx.kv 的待发奖记录器（替代 PrizeService / pending_prizes 全局字典）。"""

    def __init__(self, kv):
        self._kv = kv

    def _load(self) -> dict:
        data = self._kv.get(_PENDING_KEY, None)
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict) -> None:
        self._kv.set(_PENDING_KEY, json.dumps(data, ensure_ascii=False))

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
        n = len(self._load())
        self._save({})
        return n

    def add_history(self, entry: dict) -> None:
        data = self._kv.get(_HISTORY_KEY, None)
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
        self._kv.set(_HISTORY_KEY, json.dumps(data, ensure_ascii=False))


def acct_name(client) -> str:
    me = getattr(client, "me", None)
    if not me:
        return "未知账号"
    return f"{me.first_name}(@{me.username})" if getattr(me, "username", None) \
        else f"{me.first_name}(ID:{me.id})"


async def record_draw_result(message, lottery_type: str, store: PrizeStore,
                             my_id: str, stored_prize_name: str = "") -> dict | None:
    """
    解析开奖消息并把待发奖记录写入 store。返回记录 dict（无其他中奖者时返回 None）。
    在此处即把每位中奖者的参与消息位置（reply_chat_id/message_id）解析出来落盘。
    """
    text = message.text or ""
    import re
    lottery_id_match = re.search(r'抽奖 ID[：:]\s*([a-f0-9\-]+)', text)
    creator_match = re.search(r'创建者[：:]\s*.+?\((\d+)\)', text)
    if not lottery_id_match or not creator_match:
        return None
    lottery_id = lottery_id_match.group(1)
    creator_id = creator_match.group(1)

    # 只记录自己发起的抽奖
    if str(creator_id) != str(my_id):
        return None

    winners = parse_winners(text, message.entities, lottery_type, my_id, stored_prize_name)
    if not winners:
        return None

    record = {
        'lottery_id': lottery_id,
        'creator_id': creator_id,
        'winners': winners,
        'chat_id': message.chat.id,
        'chat_title': getattr(message.chat, "title", "") or "",
        'timestamp': _time.time(),
    }
    store.add(lottery_id, record)
    return record


async def send_prizes(record: dict, user_app, *, store: PrizeStore, log,
                      interval_enabled: bool, interval_min: int, interval_max: int,
                      send_blacklist: set[str]) -> tuple[int, int, list[dict]]:
    """
    给一条记录里的所有中奖者发奖（回复参与消息 "+金额"）。
    返回 (成功数, 中奖总数, 失败明细列表)。完成后从 store 移除该记录。
    """
    lottery_id = record['lottery_id']
    winners = record['winners']
    success = 0
    failed: list[dict] = []

    await asyncio.sleep(randint(3, 8))  # 模拟人工

    for winner in winners:
        user_name = winner.get('user_name', '')
        user_id = str(winner.get('user_id', ''))
        prize_amount = winner.get('prize_amount')
        try:
            if user_id in send_blacklist:
                failed.append({'user_name': user_name, 'user_id': user_id,
                               'reason': '命中发送黑名单'})
                continue
            if not prize_amount:
                failed.append({'user_name': user_name, 'user_id': user_id,
                               'reason': '奖品数量为0或无法解析'})
                continue
            reply_chat_id = winner.get('reply_chat_id')
            message_id = winner.get('message_id')
            if reply_chat_id is None or message_id is None:
                failed.append({'user_name': user_name, 'user_id': user_id,
                               'reason': '未找到参与消息链接'})
                continue

            await user_app.send_message(
                chat_id=reply_chat_id,
                text=f"+{prize_amount}",
                reply_to_message_id=message_id,
            )
            success += 1
            if log:
                log.info("已发奖给 %s (%s): +%s", user_name, user_id, prize_amount)

            if interval_enabled:
                await asyncio.sleep(randint(interval_min, interval_max))
        except Exception as e:  # noqa: BLE001
            if log:
                log.error("发奖失败 - %s (%s): %r", user_name, user_id, e)
            failed.append({'user_name': user_name, 'user_id': user_id, 'reason': str(e)})

    store.remove(lottery_id)
    store.add_history({
        'lottery_id': lottery_id,
        'total': len(winners),
        'success': success,
        'failed': len(failed),
    })
    if log:
        log.info("抽奖 %s 发奖完成，成功 %d/%d 人", lottery_id, success, len(winners))
    return success, len(winners), failed
