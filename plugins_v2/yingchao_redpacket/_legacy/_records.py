# =============================================================================
# 影巢口令红包插件 - 配置解析 + 记录（ctx.kv）
#
# 配置走 ctx.config（前端 config_schema 表单），运行记录走 ctx.kv。
# 每插件独立 kv（data/kv/<id>.sqlite），与抢红包插件互不干扰。
# =============================================================================
from __future__ import annotations

import json
import time as _time


# ─── 配置解析工具 ──────────────────────────────────────────────────────────

def parse_targets(raw: str) -> dict[int, str]:
    """解析「监控发包人」配置（多行 `uid 备注` 或 `uid`），返回 {uid: 备注}。"""
    targets: dict[int, str] = {}
    if not raw:
        return targets
    for line in str(raw).splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        try:
            uid = int(parts[0])
        except (ValueError, IndexError):
            continue
        remark = parts[1].strip() if len(parts) > 1 else str(uid)
        targets[uid] = remark
    return targets


def parse_keywords(raw: str) -> list[str]:
    """解析陷阱关键词（逗号或换行分隔）。"""
    if not raw:
        return []
    out = []
    for chunk in str(raw).replace("\n", ",").split(","):
        k = chunk.strip()
        if k:
            out.append(k)
    return out


def to_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ─── 抢包记录（ctx.kv 持久化）─────────────────────────────────────────────

_SNATCHED_KEY = "snatched_packets"   # 已抢/已处理红包去重表 {packet_key: ts}
_HISTORY_KEY = "snatch_history"      # 最近抢包历史（环形，最多 N 条）
_HISTORY_MAX = 100
_DEDUP_TTL = 6 * 3600                # 去重记录存活 6 小时


class Records:
    """基于 ctx.kv 的抢包记录器：去重 + 历史。"""

    def __init__(self, kv, log=None):
        self._kv = kv
        self._log = log

    # —— 去重 ——
    def _load_dedup(self) -> dict:
        data = self._kv.get(_SNATCHED_KEY, None)
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        return data if isinstance(data, dict) else {}

    def _save_dedup(self, data: dict) -> None:
        self._kv.set(_SNATCHED_KEY, json.dumps(data, ensure_ascii=False))

    def already_handled(self, packet_key: str) -> bool:
        """该红包是否已处理过（自动清理过期记录）。"""
        data = self._load_dedup()
        now = _time.time()
        # 清理过期
        stale = [k for k, ts in data.items() if now - float(ts or 0) > _DEDUP_TTL]
        changed = False
        for k in stale:
            data.pop(k, None)
            changed = True
        hit = packet_key in data
        if changed:
            self._save_dedup(data)
        return hit

    def mark_handled(self, packet_key: str) -> None:
        data = self._load_dedup()
        data[packet_key] = _time.time()
        self._save_dedup(data)

    # —— 历史 ——
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
