# =============================================================================
# auto_subscribe 私有辅助：落地流水线（同步，跑在 asyncio.to_thread 里）
#
# 每条 RankMediaItem：pre 过滤 -> NextFind /search 解析取最佳匹配 -> 库/订阅/评分/
# 类型判定 -> /subscriptions/add -> 记历史。因 /search 已含 is_subscribed（去重）、
# is_in_library（库查重）、_vote_average（评分），原 MoviePilot 版的 recognize->exists->
# media-exists->vote 四步合并为一次搜索。
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Dict, List, Optional

from ._base import get_provider
# 导入各来源模块以触发 @register 自注册。
from . import _douban, _maoyan, _mikan, _netflix  # noqa: F401
from ._models import (
    STATUS_ALREADY, STATUS_ERROR, STATUS_FILTERED, STATUS_IN_LIBRARY,
    STATUS_LABELS, STATUS_SUBSCRIBED, STATUS_SUBSCRIBED_EXISTS, STATUS_UNRECOGNIZED,
    TERMINAL_STATUSES, make_history_key,
)
from ._nextfind import NextFindAuthError, NextFindClient

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class Filters:
    """全局过滤阈值（0 = 不启用）。"""

    min_year: int = 0
    min_vote: float = 0.0
    min_popularity: int = 0
    media_type: str = "all"   # all | movie | tv


@dataclass
class RunResult:
    """一轮运行的汇总结果。"""

    stats: Dict[str, Dict[str, int]] = field(default_factory=dict)   # source -> {status: count}
    errors: Dict[str, str] = field(default_factory=dict)             # source -> error
    added: List[str] = field(default_factory=list)                  # 新增订阅的标题列表
    handled: Dict[str, dict] = field(default_factory=dict)          # 历史（写回 kv）
    nf_cache: dict = field(default_factory=dict)                    # netflix 周更缓存（写回 kv）
    auth_error: str = ""                                            # NextFind 鉴权失败则中止整轮并记此


# 各来源的 options 构建器：从扁平 cfg 取出该来源需要的字段。
def _source_options(cfg: dict, nf_cache: dict) -> List:
    """返回启用的 [(source_id, options), ...]。"""
    out = []
    if cfg.get("douban_enabled"):
        out.append(("douban", {
            "ranks": cfg.get("douban_ranks"),
            "rsshub_base": cfg.get("douban_rsshub"),
            "rss_addrs": cfg.get("douban_rss_custom"),
        }))
    if cfg.get("mikan_enabled"):
        out.append(("mikan", {
            "year": cfg.get("mikan_year"),
            "season": cfg.get("mikan_season"),
            "resolve_bangumi_id": cfg.get("mikan_resolve_detail", True),
        }))
    if cfg.get("netflix_enabled"):
        out.append(("netflix", {
            "global": cfg.get("netflix_global", True),
            "global_dataset": cfg.get("netflix_dataset"),
            "global_media_types": cfg.get("netflix_media_types"),
            "countries": cfg.get("netflix_countries"),
            "country_types": cfg.get("netflix_country_types"),
            "limit": cfg.get("netflix_limit", 10),
            "rich_metadata": cfg.get("netflix_rich", False),
            "use_cache": True,
            "_cache": nf_cache,
        }))
    if cfg.get("maoyan_enabled"):
        out.append(("maoyan", {
            "movie_box": cfg.get("maoyan_movie_box", True),
            "web_platforms": cfg.get("maoyan_web_platforms"),
            "web_types": cfg.get("maoyan_web_types"),
            "num": cfg.get("maoyan_num", 10),
            # Cookie 由 __init__ 经 ctx.browser 预取后放进 cfg["maoyan_cookies"]。
            "cookies": cfg.get("maoyan_cookies"),
        }))
    return out


def _f_int(v) -> int:
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def _f_float(v) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _read_filters(cfg: dict) -> Filters:
    """全局过滤（默认，未开独立过滤的来源都用它）。"""
    return Filters(
        min_year=_f_int(cfg.get("min_year")),
        min_vote=_f_float(cfg.get("min_vote")),
        min_popularity=_f_int(cfg.get("min_popularity")),
        media_type=str(cfg.get("media_type") or "all").strip().lower(),
    )


def _effective_filters(cfg: dict, src: str, global_f: Filters) -> Filters:
    """某来源的生效过滤：开了 {src}_filter_custom 用该源自定义，否则用全局。

    热度（min_popularity）无独立项，恒沿用全局；媒体类型无 {src}_media_type 键
    （如 mikan tv-only）时默认 all（不额外限制）。
    """
    if not cfg.get(f"{src}_filter_custom"):
        return global_f
    return Filters(
        min_year=_f_int(cfg.get(f"{src}_min_year")),
        min_vote=_f_float(cfg.get(f"{src}_min_vote")),
        min_popularity=global_f.min_popularity,
        media_type=str(cfg.get(f"{src}_media_type") or "all").strip().lower(),
    )


def _year_int(value) -> Optional[int]:
    """把年份串解析成 int（取前 4 位数字）；解析不到返回 None。"""
    if value is None:
        return None
    m = re.search(r"(\d{4})", str(value))
    return int(m.group(1)) if m else None


_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_SEASON_RE = re.compile(
    r"\s*第\s*(?P<number>\d+|[零〇一二两三四五六七八九十百]+)\s*季(?:\s*.*)?$",
    re.IGNORECASE,
)


def _number_int(value: str) -> Optional[int]:
    """解析阿拉伯数字或常见中文数字（季号通常不超过百）。"""
    value = str(value or "").strip()
    if value.isdigit():
        return int(value)
    if not value or any(ch not in _CN_DIGITS and ch not in "十百" for ch in value):
        return None
    total, current = 0, 0
    for ch in value:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch == "百":
            total += (current or 1) * 100
            current = 0
    return total + current


def _title_queries(item) -> tuple[List[str], Optional[int]]:
    """生成保守的搜索回退：原题优先，带“第N季”时再搜基础剧名。"""
    title = re.sub(r"\s+", " ", str(item.title or "")).strip()
    queries = [title] if title else []
    season = item.season
    if item.type_hint == "tv":
        match = _SEASON_RE.search(title)
        if match:
            season = season if season is not None else _number_int(match.group("number"))
            base = title[:match.start()].strip(" -–—:：·～~")
            if base and base not in queries:
                queries.append(base)
    return queries, season


def _search_best(client: NextFindClient, item):
    """依次搜索原题和安全回退标题，返回候选、实际查询词和识别出的季号。"""
    queries, season = _title_queries(item)
    for query in queries:
        best = _pick_best(client.search(query, item.type_hint), item)
        if best:
            return best, query, season
    return None, "", season


def _pick_best(results: List[dict], item) -> Optional[dict]:
    """从 /search 候选里挑最佳匹配：优先类型一致，再按年份就近。"""
    if not results:
        return None
    # 类型过滤：type_hint 明确时优先同类型候选，无同类型再放开。
    candidates = results
    if item.type_hint in ("movie", "tv"):
        typed = [r for r in results if str(r.get("raw_type") or "").lower() == item.type_hint]
        candidates = typed or results
    want_year = _year_int(item.year)
    if want_year:
        exact = [r for r in candidates if _year_int(r.get("year")) == want_year]
        if exact:
            return exact[0]
        near = [r for r in candidates if (yr := _year_int(r.get("year"))) and abs(yr - want_year) <= 1]
        if near:
            return near[0]
        # 电影的发行年就是作品年份；明确年份却只搜到相隔多年的同名电影时，
        # 宁可判为未识别，也不能误订旧作。剧集年份通常是首播年，续季不适用此限制。
        if item.type_hint == "movie" and any(_year_int(r.get("year")) for r in candidates):
            return None
    return candidates[0]


def _process_item(client: NextFindClient, item, filters: Filters, handled: dict):
    """处理单条，返回 (status, title, detail)。detail 为可读原因（供运行日志逐条展示）。
    终态写入 handled（跨轮去重）。"""
    title = item.title
    # pre 过滤：热度（豆瓣 source_meta.count，无则跳过该过滤）。
    if filters.min_popularity:
        count = item.source_meta.get("count")
        if count is not None:
            try:
                if int(float(count)) < filters.min_popularity:
                    return STATUS_FILTERED, title, f"热度 {int(float(count))} < {filters.min_popularity}"
            except (ValueError, TypeError):
                pass

    # 解析：NextFind /search。
    best, matched_query, detected_season = _search_best(client, item)
    if not best:
        return STATUS_UNRECOGNIZED, title, f"搜索无结果（{item.type_hint or '全部'}）"

    tmdb_id = best.get("id")
    raw_type = str(best.get("raw_type") or "").lower()
    if not tmdb_id or raw_type not in ("movie", "tv"):
        return STATUS_UNRECOGNIZED, title, "结果无有效 tmdb/类型"

    # post 过滤：年份、类型、评分。
    year = _year_int(item.year) or _year_int(best.get("year"))
    if filters.min_year and year and year < filters.min_year:
        return STATUS_FILTERED, title, f"年份 {year} < {filters.min_year}"
    if filters.media_type in ("movie", "tv") and raw_type != filters.media_type:
        return STATUS_FILTERED, title, f"类型 {raw_type} ≠ {filters.media_type}"
    if filters.min_vote:
        try:
            vote = float(best.get("_vote_average") or 0)
        except (ValueError, TypeError):
            vote = 0.0
        if vote < filters.min_vote:
            return STATUS_FILTERED, title, f"评分 {vote} < {filters.min_vote}"

    season = detected_season if raw_type == "tv" else None
    key = make_history_key(tmdb_id, raw_type, season)
    tag = f"tmdb {tmdb_id}" + (f" S{season}" if season is not None else "")
    if matched_query and matched_query != item.title:
        tag += f"，回退标题：{matched_query}"

    # 跨轮去重：历史里已是终态则跳过。
    prev = handled.get(key)
    if prev and prev.get("status") in TERMINAL_STATUSES:
        return STATUS_ALREADY, title, f"已处理过（{STATUS_LABELS.get(prev.get('status'), prev.get('status'))}）"

    # 库/订阅判定（来自 /search，无需额外请求）。
    if best.get("is_in_library"):
        _record(handled, key, title, STATUS_IN_LIBRARY, item, tmdb_id)
        return STATUS_IN_LIBRARY, title, tag
    if best.get("is_subscribed"):
        _record(handled, key, title, STATUS_SUBSCRIBED_EXISTS, item, tmdb_id)
        return STATUS_SUBSCRIBED_EXISTS, title, tag

    # 加订阅。
    ok, msg = client.add(tmdb_id, raw_type, season)
    if ok:
        _record(handled, key, title, STATUS_SUBSCRIBED, item, tmdb_id)
        return STATUS_SUBSCRIBED, title, tag
    return STATUS_ERROR, title, f"订阅失败：{msg or '未知'}"


def _record(handled: dict, key: str, title: str, status: str, item, tmdb_id) -> None:
    """写入一条历史（终态，供跨轮去重与展示）。"""
    handled[key] = {
        "title": title,
        "status": status,
        "tmdb_id": str(tmdb_id),
        "source": item.source_meta.get("source") or "",
        "time": datetime.now().strftime(TIME_FORMAT),
    }


def run(cfg: dict, handled: dict, nf_cache: dict, log=None) -> RunResult:
    """执行一轮：遍历启用来源，逐条落地。返回汇总（handled/nf_cache 已更新，供写回 kv）。"""
    result = RunResult(handled=dict(handled or {}), nf_cache=dict(nf_cache or {}))
    client = NextFindClient(cfg.get("api_url", ""), cfg.get("api_key", ""))
    global_filters = _read_filters(cfg)

    for source_id, options in _source_options(cfg, result.nf_cache):
        provider = get_provider(source_id)
        if provider is None:
            continue
        filters = _effective_filters(cfg, source_id, global_filters)
        src_stats: Dict[str, int] = {}
        try:
            for item in provider.fetch(options):
                if not item.title:
                    continue
                title, detail = item.title, ""
                try:
                    status, title, detail = _process_item(client, item, filters, result.handled)
                except NextFindAuthError as exc:
                    # 密钥无效/过期：继续跑只会每条都 401，立即中止整轮并明确报因。
                    result.auth_error = str(exc)
                    if log:
                        log.error("[自动订阅] %s，已中止本轮", exc)
                    break
                except Exception as exc:  # noqa: BLE001 - 单条兜底
                    status, detail = STATUS_ERROR, repr(exc)
                    if log:
                        log.error("[自动订阅] %s 处理条目失败: %r", source_id, exc)
                src_stats[status] = src_stats.get(status, 0) + 1
                # 逐条写运行日志，便于查「哪条被过滤/未识别/订阅了、原因是什么」。
                if log:
                    log.info("[自动订阅] %s · %s → %s%s", provider.provider_name, title,
                             STATUS_LABELS.get(status, status), f"（{detail}）" if detail else "")
                if status == STATUS_SUBSCRIBED:
                    result.added.append(f"{provider.provider_name}·{item.title}")
        except NextFindAuthError as exc:
            result.auth_error = str(exc)
        except Exception as exc:  # noqa: BLE001 - 整源抓取失败兜底
            result.errors[source_id] = str(exc)
            if log:
                log.error("[自动订阅] %s 抓取失败: %r", source_id, exc)
        result.stats[source_id] = src_stats
        if result.auth_error:
            break  # 中止后续来源
    return result
