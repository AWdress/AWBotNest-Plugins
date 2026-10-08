"""Subscription identity and ownership evidence shared by automatic workflows."""
from __future__ import annotations

import re

from ._nextfind import NextFindResponseError


class SubscriptionBusyError(NextFindResponseError):
    """Automatic and explicit subscription writes must not race."""


def identity(value, media_type):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise NextFindResponseError("订阅缺少有效 TMDB ID")
    value = str(value).strip()
    if not re.fullmatch(r"[0-9]{1,12}", value) or int(value) <= 0:
        raise NextFindResponseError("订阅缺少有效 TMDB ID")
    media_type = {"电影": "movie", "剧集": "tv", "电视剧": "tv", "series": "tv"}.get(media_type, media_type)
    if media_type not in ("movie", "tv"):
        raise NextFindResponseError("订阅缺少有效媒体类型")
    return media_type, str(int(value))


def row_identity(row, *, search=False):
    if not isinstance(row, dict):
        raise NextFindResponseError("订阅条目格式无效")
    ids = [row[key] for key in ("tmdb_id", "tmdbId", "tmdbid") if row.get(key) not in (None, "")]
    if search:
        ids.append(row.get("id"))
    if row.get("media_source") in ("tmdb", "themoviedb") and row.get("media_id") not in (None, ""):
        ids.append(row["media_id"])
    types = [str(row[key]).strip().lower() for key in ("media_type", "mediaType", "raw_type", "type")
             if row.get(key) not in (None, "")]
    if not ids or not types:
        raise NextFindResponseError("订阅列表缺少媒体类型或 TMDB ID")
    identities = {identity(value, kind) for value in ids for kind in types}
    if len(identities) != 1:
        raise NextFindResponseError("订阅身份字段冲突")
    return identities.pop()


def history_identity(key, record):
    match = re.fullmatch(r"(movie|tv):([0-9]{1,12})(?::s([0-9]{1,3}))?", str(key))
    if not match or not isinstance(record, dict) or (match[1] == "movie" and match[3]):
        raise NextFindResponseError("订阅历史身份无效")
    wanted = identity(match[2], match[1])
    if identity(record.get("tmdb_id"), record.get("media_type", match[1])) != wanted:
        raise NextFindResponseError("订阅历史身份不一致")
    return wanted


def owned(record):
    # Old versions recorded subscribed only after a confirmed successful add.
    return isinstance(record, dict) and (record.get("created_by_plugin") is True or record.get("status") == "subscribed")


def flag(value):
    """Unknown is not false: missing status must never authorize a mutation."""
    if type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ("true", "false", "1", "0"):
        return value.strip().lower() in ("true", "1")
    return None


def suppressed(cfg, wanted):
    wanted = identity(wanted[1], wanted[0])
    return f"{wanted[0]}:{wanted[1]}" in (cfg.get("_removed_subscriptions") or {})


def subscription_active(row):
    """The live /subscriptions response also contains cancelled/completed rows."""
    states = {str(row[key]).strip().lower() for key in ("status", "sub_status") if row.get(key) not in (None, "")}
    active, inactive = {"subscribing", "active"}, {"cancelled", "completed", "expired"}
    current = flag(row.get("is_subscribed"))
    if states and (states - active - inactive or states & active and states & inactive):
        raise NextFindResponseError("NextFind 订阅状态不明确，暂不恢复")
    if current is not None:
        if states & active and not current or states & inactive and current:
            raise NextFindResponseError("NextFind 订阅状态字段冲突，暂不恢复")
        return current
    return not states or bool(states & active)


def subscription_completed(row):
    return any(str(row.get(key) or "").strip().lower() == "completed" for key in ("status", "sub_status"))


def explicit_missing(row):
    """Only explicit missing progress; mere presence in a library is insufficient."""
    total = row.get("aired_episodes", row.get("total_episodes"))
    local = row.get("local_episodes", row.get("downloaded_episodes"))
    for key in ("aired_episodes", "total_episodes", "local_episodes", "downloaded_episodes"):
        if key in row and (isinstance(row[key], bool) or not re.fullmatch(r"[0-9]+", str(row[key]))):
            return False
    if (not isinstance(total, bool) and not isinstance(local, bool)
            and re.fullmatch(r"[0-9]+", str(total)) and re.fullmatch(r"[0-9]+", str(local))):
        # A contradictory missing flag cannot override confirmed complete counts.
        if int(total) <= 0 or int(local) >= int(total):
            return False
        if any(flag(row.get(key)) is False for key in ("has_missing", "has_missing_episodes", "is_missing")):
            return False
        return True
    if any(flag(row.get(key)) is True for key in ("has_missing", "has_missing_episodes", "is_missing")):
        return True
    for key in ("missing_count", "missing_episode_count"):
        value = row.get(key)
        if not isinstance(value, bool) and re.fullmatch(r"[0-9]+", str(value or "")) and int(value) > 0:
            return True
    missing = row.get("missing_episodes")
    if isinstance(missing, (list, dict)) and missing:
        return True
    return str(row.get("status") or row.get("library_status") or "").lower() == "missing"
