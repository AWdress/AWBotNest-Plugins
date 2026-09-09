# =============================================================================
# auto_subscribe 私有辅助：标准化中间条目模型
#
# 榜单抓取阶段各来源统一产出 RankMediaItem（可能尚未带 tmdb id）。相比原
# MoviePilot 版去掉了对 MediaType 枚举的依赖，type_hint 直接用字符串
# "movie" / "tv" / None，便于在无重依赖环境里被 import / 测试。
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RankMediaItem:
    """抓取阶段产出的标准化中间条目。"""

    title: str
    year: Optional[str] = None
    type_hint: Optional[str] = None          # "movie" | "tv" | None
    season: Optional[int] = None
    douban_id: Optional[str] = None
    bangumi_id: Optional[int] = None
    poster: Optional[str] = None
    source_meta: dict = field(default_factory=dict)
    unique_seed: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 安全 dict（供 netflix 周更缓存持久化到 ctx.kv）。"""
        return {
            "title": self.title,
            "year": self.year,
            "type_hint": self.type_hint,
            "season": self.season,
            "douban_id": self.douban_id,
            "bangumi_id": self.bangumi_id,
            "poster": self.poster,
            "source_meta": self.source_meta,
            "unique_seed": self.unique_seed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RankMediaItem":
        """从持久化 dict 还原；缺字段走 dataclass 安全默认。"""
        d = d or {}
        return cls(
            title=d.get("title", ""),
            year=d.get("year"),
            type_hint=d.get("type_hint"),
            season=d.get("season"),
            douban_id=d.get("douban_id"),
            bangumi_id=d.get("bangumi_id"),
            poster=d.get("poster"),
            source_meta=d.get("source_meta") or {},
            unique_seed=d.get("unique_seed", ""),
        )


# 落地处理的最终状态（供统计与历史）。
STATUS_SUBSCRIBED = "subscribed"            # 新增订阅成功
STATUS_SUBSCRIBED_EXISTS = "exists"         # 已订阅（跳过）
STATUS_IN_LIBRARY = "in_library"            # 媒体库已存在（跳过）
STATUS_UNRECOGNIZED = "unrecognized"        # NextFind 搜不到
STATUS_FILTERED = "filtered"                # 被过滤
STATUS_ALREADY = "already_handled"          # 本插件历史已处理（跳过）
STATUS_ERROR = "error"                      # 异常

# 状态中文标签（通知汇总用）。
STATUS_LABELS = {
    STATUS_SUBSCRIBED: "新增订阅",
    STATUS_SUBSCRIBED_EXISTS: "已订阅",
    STATUS_IN_LIBRARY: "库中已有",
    STATUS_UNRECOGNIZED: "未识别",
    STATUS_FILTERED: "已过滤",
    STATUS_ALREADY: "已处理",
    STATUS_ERROR: "失败",
}

# 视为「正向终态」——记入历史、后续跑不再重复处理。
TERMINAL_STATUSES = (STATUS_SUBSCRIBED, STATUS_SUBSCRIBED_EXISTS, STATUS_IN_LIBRARY)


def make_history_key(tmdb_id, media_type: str, season: Optional[int]) -> str:
    """生成跨轮去重的历史键：电影按 tmdb，剧集按 tmdb+季。"""
    if str(media_type).lower() == "tv":
        return f"tv:{tmdb_id}:s{season}" if season is not None else f"tv:{tmdb_id}"
    return f"movie:{tmdb_id}"
