# =============================================================================
# 拼手气红包插件 - 配置解析 + 记录（ctx.kv）
#
# 配置走 ctx.config，运行记录走 ctx.kv（每插件独立 sqlite）。
# =============================================================================
from __future__ import annotations

import json
import time as _time


def parse_groups(raw) -> list[int]:
    """解析群组ID列表（逗号或换行分隔）。空 = 不限制（所有群）。"""
    groups: list[int] = []
    if not raw:
        return groups
    for chunk in str(raw).replace("\n", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            groups.append(int(chunk))
        except ValueError:
            pass
    return groups


def to_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ─── 抢包记录（ctx.kv 持久化）─────────────────────────────────────────────

_HISTORY_KEY = "snatch_history"      # 最近抢包历史（环形，最多 N 条）
_HISTORY_MAX = 100


class Records:
    """基于 ctx.kv 的抢包历史记录器。"""

    def __init__(self, kv, log=None):
        self._kv = kv
        self._log = log

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
