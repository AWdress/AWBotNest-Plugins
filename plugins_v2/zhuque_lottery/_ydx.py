# =============================================================================
# 朱雀「鳄鱼丼 YDX」骰子投注（zhuque_lottery 私有辅助）
#
# 迁移自 AWLottery：libs/ydx_betmodel.py + ydx_zhuque.py + models/ydx_db_modle.py。
#
# 关键迁移决策：
#   1. 投注流水/历史不再走 SQLAlchemy（Zhuqueydx 表）+ ydx_service，改存 ctx.kv：
#        - 键 ydx_history → 最近 N 局 die_point 列表（供 S 模型与统计）
#        - 键 ydx_records → 最近若干局完整记录（审计）
#   2. 下注/开奖均靠 pyrogram 回调与消息解析，但所有 pyrogram 调用都通过
#      handler 传入的 client / message 完成（本文件不 import pyrogram）。
#   3. 下注模型 A/B/E/S 逻辑保持原样；S 模型依赖 numpy/pandas（平台 venv 已装），
#      若运行环境缺库则降级为「不下注」并 log.warning。
#
# 需实盘校验的点（原项目依赖站点 bot 的具体文案/回调格式）：
#   - 下注按钮 callback_data 格式 {"t":<side>,"b":<amount>,"action":"ydxxz"}
#   - 开奖文案 "已结算: 结果为 X 大/小"、开局文案含「创建时间」、历史 40 数据块
#   这些来自朱雀群里的 bot，站点改版可能变化。YDX 默认关闭，不阻塞其它功能。
# =============================================================================
from __future__ import annotations

import asyncio
import json
import random
from abc import ABC, abstractmethod
from typing import Optional, Tuple

# 下注按钮金额档位（从大到小），与原项目一致
BET_VALUES = [50_000_000, 5_000_000, 1_000_000, 250_000, 50_000, 20_000, 2_000, 500]
MAX_BET = 50_000_000

_HISTORY_KEY = "ydx_history"     # 最近 die_point 列表
_RECORDS_KEY = "ydx_records"     # 最近完整记录
_RECORDS_MAX = 300
_HISTORY_MAX = 400


# ─── KV 历史存储（替代 Zhuqueydx 表）─────────────────────────────────────────
class YdxStore:
    """YDX 投注历史/流水存取（基于 ctx.kv）。"""

    def __init__(self, ctx):
        self._kv = ctx.kv
        self._log = ctx.log

    def get_history(self, limit: int = 200) -> list[int]:
        """返回最近 limit 局的 die_point（最新在前，与原 get_data 一致）。"""
        raw = self._kv.get(_HISTORY_KEY) or []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                raw = []
        return list(raw[:limit])

    def add_record(self, rec: dict) -> None:
        """写入一局完整结果，并更新 die_point 历史（最新在前）。"""
        # die_point 历史
        hist = self.get_history(_HISTORY_MAX)
        hist.insert(0, int(rec.get("die_point", 0)))
        hist = hist[:_HISTORY_MAX]
        self._save(_HISTORY_KEY, hist)
        # 完整记录环形缓冲
        recs = self._kv.get(_RECORDS_KEY) or []
        if isinstance(recs, str):
            try:
                recs = json.loads(recs)
            except (TypeError, ValueError):
                recs = []
        recs.append(rec)
        if len(recs) > _RECORDS_MAX:
            recs = recs[-_RECORDS_MAX:]
        self._save(_RECORDS_KEY, recs)

    def _save(self, key, val):
        try:
            self._kv.set(key, val)
        except Exception:
            self._kv.set(key, json.dumps(val, ensure_ascii=False))


# ─── 下注模型（迁移自 libs/ydx_betmodel.py）─────────────────────────────────
class BetModel(ABC):
    fail_count: int = 0
    guess_dx: int = -1

    @abstractmethod
    async def guess(self, data, store: "YdxStore | None" = None) -> int:
        """data 是最近 die_point 的 0/1 数组（最后一个最近，0小1大）。"""
        return 0

    def set_result(self, result: int):
        """更新连败次数（在监听开奖结果里调用）。"""
        if self.guess_dx != -1:
            if result == self.guess_dx:
                self.fail_count = 0
            else:
                self.fail_count += 1

    def get_consecutive_count(self, data: list[int]) -> int:
        """根据历史结果计算当前连大/连小次数。"""
        if not data:
            return 0
        last = data[-1]
        count = 0
        for v in reversed(data):
            if v == last:
                count += 1
            else:
                break
        return count

    def get_bet_count(self, data: list[int], start_count: int = 0, stop_count: int = 0) -> int:
        consecutive_count = self.get_consecutive_count(data)
        bet_count = consecutive_count - start_count
        if 0 <= bet_count < stop_count:
            return bet_count
        return -1

    def get_bet_bonus(self, start_bonus, bet_count) -> int:
        return int(start_bonus * (2 ** (bet_count + 1) - 1))


class A(BetModel):
    """打反：押与上一局相反方向。"""
    async def guess(self, data, store=None):
        self.guess_dx = 1 - data[-1]
        return self.guess_dx


class B(BetModel):
    """打顺：押与上一局相同方向，按连败追投。"""
    async def guess(self, data, store=None):
        self.guess_dx = data[-1]
        return self.guess_dx

    def get_bet_count(self, data, start_count=0, stop_count=0):
        bet_count = self.fail_count - start_count
        if 0 <= bet_count < stop_count:
            return bet_count
        return -1


class E(BetModel):
    """随机：每两次连败重新随机方向。"""
    async def guess(self, data, store=None):
        if self.guess_dx == -1:
            self.guess_dx = random.randint(0, 1)
        if self.fail_count % 2 == 0:
            self.guess_dx = random.randint(0, 1)
        return self.guess_dx

    def get_bet_count(self, data, start_count=0, stop_count=0):
        bet_count = self.fail_count - start_count
        if 0 <= bet_count < stop_count:
            return bet_count
        return -1


class S(BetModel):
    """KDJ 技术指标模型。依赖 numpy/pandas，从 kv 历史读取数据。"""
    async def guess(self, data, store=None):
        try:
            import numpy as np
            import pandas as pd
        except ImportError:
            # 环境缺少 numpy/pandas，降级为不下注
            return data[-1] if data else 0

        if store is None:
            return data[-1] if data else 0
        ydx_data = store.get_history(limit=200)
        if not ydx_data:
            return data[-1] if data else 0

        _data = [1 if i > 3 else -1 for i in ydx_data]
        _data = _data[::-1]
        n = 2
        base_value = 1000
        cumulative_data = np.zeros_like(_data, dtype=float)
        cumulative_data[0] = base_value + _data[0]
        for i in range(1, len(_data)):
            cumulative_data[i] = cumulative_data[i - 1] + _data[i]
        num_windows = len(_data) // n
        if num_windows < 2:
            return data[-1] if data else 0
        windows = cumulative_data[: num_windows * n].reshape(-1, n)
        window_data = pd.DataFrame({
            "close": windows[:, -1],
            "high": np.max(windows, axis=1),
            "low": np.min(windows, axis=1),
        })
        kdj = _make_KDJ(window_data, pd)
        last_j = kdj.iloc[-1, 2]
        last_k = kdj.iloc[-1, 0]
        return 1 if last_j >= last_k else 0

    def get_bet_count(self, data, start_count=0, stop_count=0):
        return 0


def _make_KDJ(datas, pd, days=9, kn=3, dn=3):
    lowest = datas["low"].rolling(days).min()
    lowest = lowest.fillna(datas["low"].expanding().min())
    highest = datas["high"].rolling(days).max()
    lowest = lowest.fillna(datas["high"].expanding().max())
    rsv = (datas["close"] - lowest) / (highest - lowest) * 100
    rsv = rsv.fillna(100)
    k = rsv.ewm(kn - 1, adjust=False).mean()
    d = k.ewm(dn - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    return pd.concat([k, d, j], axis=1)


def make_models() -> dict:
    """每个插件实例独立一套模型（保持各模型内部连败计数状态）。"""
    return {"a": A(), "b": B(), "e": E(), "s": S()}


# ─── 投注/解析逻辑（迁移自 ydx_zhuque.py，pyrogram 操作走传入的 client）──────
async def manual_bet(client, message, bet_amount: int, flag: str, log) -> int:
    """
    按金额从大到小依次点击下注按钮。返回成功下注的总额。
    flag 为 's'/'b'（小/大）。所有 pyrogram 调用走 client/message。
    """
    rele_betbouns = 0
    remaining = min(bet_amount, MAX_BET)
    log.info("YDX 可下注总额=%s", remaining)

    bet_counts = []
    for value in BET_VALUES:
        count = remaining // value
        bet_counts.append(count)
        remaining -= count * value

    for i, count in enumerate(bet_counts):
        bet_value = BET_VALUES[i]
        if count <= 0:
            continue
        for _ in range(count):
            callback_data = f'{{"t":"{flag}","b":{int(bet_value)},"action":"ydxxz"}}'
            try:
                result = await client.request_callback_answer(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    callback_data=callback_data,
                    timeout=5,
                )
                msg = getattr(result, "message", "") or ""
                if "零食不足" in msg:
                    log.warning("YDX 零食不足，停止下注")
                    return rele_betbouns
                rele_betbouns += bet_value
                await asyncio.sleep(1)
            except TimeoutError:
                log.warning("YDX 回调超时，等待重试")
                await asyncio.sleep(3)
                continue
            except Exception as e:
                log.warning("YDX 下注出错: %s", e)
                await asyncio.sleep(2)
                continue
    log.info("YDX 总下注成功金额=%s", rele_betbouns)
    return rele_betbouns


def listof_winners_check(message, target_tgid: int) -> Optional[str]:
    """检查消息实体中是否包含自己的 tgid，返回 first_name。"""
    entities = getattr(message, "entities", None)
    if not entities:
        return None
    for entity in entities:
        user = getattr(entity, "user", None)
        if user and user.id == target_tgid:
            return user.first_name or "unknown"
    return None


def extract_winner_amount(text: str, winner_name: str) -> Optional[int]:
    """从开奖文本里抽取某人中奖金额。"""
    for line in (text or "").splitlines():
        line = line.strip()
        if winner_name in line and ":" in line:
            parts = line.rsplit(":", 1)
            if len(parts) == 2:
                amount_str = parts[-1].strip().replace(",", "")
                if amount_str.isdigit():
                    return int(amount_str)
    return None


def extract_bet_info(text: str, target_name: str) -> Optional[Tuple[str, int]]:
    """从下注列表文本里抽取某人押注的方位(Big/Small)和金额。"""
    current_area = None
    area_map = {"押大": "Big", "押小": "Small"}
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("押大:"):
            current_area = "押大"
            continue
        elif line.startswith("押小:"):
            current_area = "押小"
            continue
        if current_area and ":" in line:
            parts = line.rsplit(":", 1)
            if len(parts) == 2:
                name, amount_str = parts
                name = name.strip()
                amount_str = amount_str.strip().replace(",", "")
                if target_name in name and amount_str.isdigit():
                    return area_map[current_area], int(amount_str)
    return None


def history_list(message) -> list[int]:
    """通过 bot 提供的 40 个历史数据生成预测列表（最新在后）。"""
    text = getattr(message, "text", "") or ""
    lines = text.strip().split("\n")
    single = []
    for line in lines[1:5]:
        line = line.strip("[]").split()
        try:
            single.extend(int(num) for num in line)
        except ValueError:
            continue
    single.reverse()
    return single
