# =============================================================================
# 多站点转账 - 转账记录存取 + 排行榜聚合（ctx.kv）
#
# 不依赖平台 service/DB：所有转账记录存 ctx.kv（每插件私有 sqlite 命名空间）。
# 设计：
#   - 聚合表（权威，供排行榜）：键 agg:<site> → JSON dict
#       { "in":  { "<user_id>": {"name":..,"total":float,"count":int} },
#         "out": { ... } }
#     方向 in=转入榜，out=转出榜。total 一律存正数，金额绝对值累加。
#   - 最近流水（审计/调试，环形截断）：键 recent → list（最多 200 条），
#       每条 {site,direction,user_id,user_name,amount,ts}
#   - 去重：内存 8 秒窗口，按 (site,direction,chat_id,msg_id,amount) 去重，
#     对应原项目 do_transfer 的 dedupe 逻辑（防 bot 消息+编辑双触发）。
#
# kv value 必须 JSON-able：金额用 float，时间用 ISO 字符串。
# =============================================================================

import json
import time
from datetime import datetime, timezone

_AGG_PREFIX = "agg:"
_RECENT_KEY = "recent"
_RECENT_MAX = 200
_DEDUPE_TTL = 8.0  # 秒


def _agg_key(user_id, user_name) -> str:
    """排行榜聚合键。

    有真实 uid → 用 uid 字符串；uid 缺失/为 0（如 hdsky 广播只给名字、无 text_mention）
    → 用 "name:<名字>"，避免不同的人都并进 uid=0 一条里（金额混算、名字互相覆盖）。
    """
    try:
        if user_id and int(user_id) != 0:
            return str(int(user_id))
    except (ValueError, TypeError):
        if user_id:
            return str(user_id)
    name = (user_name or "").strip()
    return f"name:{name}" if name else "0"



class RecordStore:
    """转账记录存取 + 排行榜聚合（基于 ctx.kv）。"""

    def __init__(self, ctx):
        self._kv = ctx.kv
        self._log = ctx.log
        self._recent_keys: dict[tuple, float] = {}

    # ── 去重 ──────────────────────────────────────────────────────────────
    def is_duplicate(self, site: str, direction: str, chat_id: int,
                     msg_id: int, amount: float) -> bool:
        """8 秒窗口内的重复转账确认返回 True（并刷新时间戳）。"""
        now = time.monotonic()
        # 清理过期键
        expired = [k for k, t in self._recent_keys.items() if now - t > _DEDUPE_TTL]
        for k in expired:
            self._recent_keys.pop(k, None)
        key = (site, direction, chat_id, msg_id, round(amount, 4))
        last = self._recent_keys.get(key)
        if last is not None and now - last <= _DEDUPE_TTL:
            return True
        self._recent_keys[key] = now
        return False

    # ── 写入 ──────────────────────────────────────────────────────────────
    def record(self, site: str, direction: str, user_id: int, user_name: str,
               amount: float) -> dict:
        """记录一笔转账，更新聚合表与流水。返回该用户在该方向的累计 {total,count,rank}。"""
        amount = abs(float(amount))
        agg = self._load_agg(site)
        side = agg.setdefault(direction, {})
        uid = _agg_key(user_id, user_name)
        entry = side.get(uid) or {"name": user_name, "total": 0.0, "count": 0}
        entry["name"] = user_name or entry.get("name") or f"用户{user_id}"
        entry["total"] = round(float(entry["total"]) + amount, 4)
        entry["count"] = int(entry["count"]) + 1
        side[uid] = entry
        self._save_agg(site, agg)

        self._append_recent({
            "site": site,
            "direction": direction,
            "user_id": user_id,
            "user_name": entry["name"],
            "amount": amount,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })

        rank = self._rank_of(side, uid)
        return {"total": entry["total"], "count": entry["count"], "rank": rank}

    # ── 排行榜 ────────────────────────────────────────────────────────────
    def leaderboard(self, site: str, direction: str, limit: int = 10) -> list[dict]:
        """返回某站点某方向的排行榜（按 total 降序）。

        每项：{rank,user_id,user_name,total,count}
        """
        agg = self._load_agg(site)
        side = agg.get(direction, {})
        rows = [
            {"user_id": int(uid) if uid.lstrip("-").isdigit() else 0,
             "user_name": e.get("name", f"用户{uid}"),
             "total": float(e.get("total", 0.0)),
             "count": int(e.get("count", 0))}
            for uid, e in side.items()
        ]
        rows.sort(key=lambda r: r["total"], reverse=True)
        out = []
        for i, r in enumerate(rows[:limit], start=1):
            r = dict(r)
            r["rank"] = i
            out.append(r)
        return out

    def sites_with_data(self) -> list[str]:
        """返回所有已有聚合数据的站点名。"""
        return [k[len(_AGG_PREFIX):] for k in self._kv.keys() if k.startswith(_AGG_PREFIX)]

    def reset_site(self, site: str) -> None:
        self._kv.delete(_AGG_PREFIX + site)

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _rank_of(self, side: dict, uid: str) -> int:
        ordered = sorted(side.items(), key=lambda kv: float(kv[1].get("total", 0.0)), reverse=True)
        for i, (k, _) in enumerate(ordered, start=1):
            if k == uid:
                return i
        return -1

    def _load_agg(self, site: str) -> dict:
        raw = self._kv.get(_AGG_PREFIX + site)
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return {}

    def _save_agg(self, site: str, agg: dict) -> None:
        # 直接存 dict（平台 kv 支持 JSON-able 值）；为稳妥也兼容字符串后端
        try:
            self._kv.set(_AGG_PREFIX + site, agg)
        except Exception:
            self._kv.set(_AGG_PREFIX + site, json.dumps(agg, ensure_ascii=False))

    def _append_recent(self, item: dict) -> None:
        raw = self._kv.get(_RECENT_KEY)
        if isinstance(raw, list):
            lst = raw
        elif raw:
            try:
                lst = json.loads(raw)
            except (TypeError, ValueError):
                lst = []
        else:
            lst = []
        lst.append(item)
        if len(lst) > _RECENT_MAX:
            lst = lst[-_RECENT_MAX:]
        try:
            self._kv.set(_RECENT_KEY, lst)
        except Exception:
            self._kv.set(_RECENT_KEY, json.dumps(lst, ensure_ascii=False))
