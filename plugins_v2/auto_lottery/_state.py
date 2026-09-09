# =============================================================================
# 自动抽奖插件 - 进程内共享状态
#
# 原项目用「auto_lottery_for_xiaocai.py 定义全局 lottery_list + auto_prize_sender
# 双向 import」实现跨模块共享。合并成单插件后，把共享态收敛到本模块级单例，
# 同进程单实例，自然消除循环 import。
#
#   lottery_list  —— 进行中的抽奖（含重量级 pyrogram Message 对象，仅进程内，不落盘）
#   added_at      —— 每条抽奖的加入时间戳，用于 TTL 清理僵尸条目
#
# 注意：lottery_list 持有 Message 对象（转发原消息 / 转发首参与者用），无法序列化，
# 故只放内存。待发奖记录里**可序列化**的部分另由 _prize.py 落到 ctx.kv。
# =============================================================================
from __future__ import annotations

import time as _time

# 进行中的抽奖：key = 抽奖ID
lottery_list: dict[str, dict] = {}
# 抽奖加入时间戳：key = 抽奖ID -> ts(秒)
added_at: dict[str, float] = {}

# 僵尸条目存活上限：10 天（开奖周期差异极大，TTL 必须够长避免误删仍在等待的条目）
ENTRY_TTL = 10 * 24 * 3600


def prune_stale(log=None) -> int:
    """清理超过 TTL 的僵尸抽奖条目，防止 lottery_list 无限增长。返回清理数量。"""
    now = _time.time()
    stale = [lid for lid, ts in added_at.items() if now - ts > ENTRY_TTL]
    for lid in stale:
        lottery_list.pop(lid, None)
        added_at.pop(lid, None)
    if stale and log:
        log.info("清理 %d 个僵尸抽奖条目（超过 %d 天未开奖）", len(stale), ENTRY_TTL // 86400)
    # 兜底：清理孤儿时间戳
    for lid in [lid for lid in added_at if lid not in lottery_list]:
        added_at.pop(lid, None)
    return len(stale)


def register(lottery_id: str, data: dict) -> None:
    """登记一条进行中的抽奖。"""
    lottery_list[lottery_id] = data
    added_at[lottery_id] = _time.time()


def remove(lottery_id: str) -> None:
    """移除一条抽奖（开奖后）。"""
    lottery_list.pop(lottery_id, None)
    added_at.pop(lottery_id, None)


def clear() -> None:
    """teardown 时清空全部进程内状态。"""
    lottery_list.clear()
    added_at.clear()
