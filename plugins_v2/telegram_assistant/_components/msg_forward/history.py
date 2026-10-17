"""可续传的全量历史转发；只处理启用规则冻结截止点之前的消息。"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time


_STORAGE_KEY = "forward_history_v1"


def _interval(rule):
    try:
        value = float(rule.get("history_interval_sec", 3))
        if not math.isfinite(value):
            return 3.0
        return max(1.0, min(value, 3600.0))
    except (TypeError, ValueError):
        return 3.0


def _identity(rule, source, target, forward_album):
    """速度/置顶变化不重跑旧消息，内容筛选变化则是一个新的搬运任务。"""
    from . import _split

    identity = {
        "source": str(source).lower(),
        "target": str(target).lower(),
        "copy": bool(rule.get("copy", False)),
        "types": sorted(set(str(value) for value in (rule.get("types") or []))),
        "kw": sorted(set(_split(rule.get("kw")))),
        "nkw": sorted(set(_split(rule.get("nkw")))),
        "sender": sorted(set(value.lower() for value in _split(rule.get("sender")))),
        "album": bool(forward_album),
    }
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _flood_seconds(error):
    if error.__class__.__name__ not in {"FloodWaitError", "FloodPremiumWaitError", "SlowModeWaitError"}:
        return None
    try:
        value = float(getattr(error, "seconds", getattr(error, "value", 0)))
        return max(1.0, value) if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _number(value, default=0):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


async def _groups(client, entity, cursor, cutoff, forward_album):
    """Telethon 负责分页；仅保留当前相册，不把整个来源读入内存。"""
    pending = []
    pending_gid = None
    async for message in client.iter_messages(
        entity, min_id=cursor, max_id=cutoff + 1, reverse=True,
    ):
        message_id = _number(getattr(message, "id", 0))
        if not cursor < message_id <= cutoff:
            continue
        grouped_id = getattr(message, "grouped_id", None) if forward_album else None
        if pending and (grouped_id is None or grouped_id != pending_gid):
            yield pending
            pending = []
        pending.append(message)
        pending_gid = grouped_id
        if grouped_id is None:
            yield pending
            pending = []
    if pending:
        yield pending


async def run_history(
    client, rules, storage, log, resolve, sent, persist_sent, delivery_lock,
    *, forward_album=True,
):
    """逐目标转发并持久化游标，返回 sent/skipped/failed/completed 统计。

    调用方须保证同一账号同一时间只有一个全量任务。实时、遗漏补全与本函数
    共用 delivery_lock 和 sent；统一投递器在锁内做去重、发送及 sent 持久化。
    """
    from . import _canonical_peer, _deliver_rule, _history_entity, _passes, _peer, _split

    stats = {"sent": 0, "skipped": 0, "failed": 0, "completed": 0}
    saved = await storage.get(_STORAGE_KEY, {})
    entries = dict(saved.get("entries") or {}) if isinstance(saved, dict) else {}
    next_send_at = 0.0

    async def checkpoint(key, state):
        updated = dict(entries)
        updated[key] = dict(state)
        await storage.set(_STORAGE_KEY, {"version": 1, "entries": updated})
        entries.clear()
        entries.update(updated)

    async def flood_wait(error, source, target):
        seconds = _flood_seconds(error)
        if seconds is None:
            return False
        log.warning("[消息转发助手] 历史转发 %s -> %s 触发 Telegram 限速，等待 %s 秒后继续", source, target, seconds)
        await asyncio.sleep(seconds)
        return True

    for index, rule in enumerate(rules or []):
        if not isinstance(rule, dict) or not rule.get("history_enabled", False):
            continue
        source = _peer(rule.get("source"))
        targets = list(dict.fromkeys(
            value for value in (_peer(item) for item in _split(rule.get("targets")))
            if value is not None and str(value).lower() != str(source).lower()
        ))
        if source is None or not targets:
            log.warning("[消息转发助手] 历史转发规则 %s 来源或目标无效，或目标与来源相同，已跳过", index + 1)
            stats["failed"] += 1
            continue
        try:
            while True:
                try:
                    entity = await _history_entity(client, source)
                    canonical_source = await _canonical_peer(client, source)
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    if not await flood_wait(error, source, "来源读取"):
                        raise
            # 这一轮所有新目标使用同一个来源快照。已有目标沿用最初截止点。
            cutoff = None
            for target in targets:
                canonical_target = await _canonical_peer(client, target)
                if str(canonical_target).lower() == str(canonical_source).lower():
                    log.warning("[消息转发助手] 历史转发规则 %s 来源与目标为同一会话，已跳过 %s", index + 1, target)
                    continue
                key = _identity(rule, canonical_source, canonical_target, forward_album)
                state = entries.get(key)
                if isinstance(state, dict) and state.get("completed") is True:
                    stats["completed"] += 1
                    continue
                if not isinstance(state, dict):
                    if cutoff is None:
                        while True:
                            try:
                                cutoff = 0
                                async for message in client.iter_messages(entity, limit=1):
                                    cutoff = _number(getattr(message, "id", 0))
                                    break
                                break
                            except asyncio.CancelledError:
                                raise
                            except Exception as error:
                                if not await flood_wait(error, source, target):
                                    raise
                    state = {"source": str(canonical_source), "target": str(canonical_target), "cursor": 0, "cutoff": cutoff, "completed": False}
                    # 在任何发送前保存截止点，重启不会把后来消息混进历史搬运。
                    await checkpoint(key, state)
                else:
                    state = dict(state)
                    state["cursor"] = _number(state.get("cursor"))
                    state["cutoff"] = _number(state.get("cutoff"))
                log.info("[消息转发助手] 历史转发 %s -> %s：从消息 %s 继续，截止消息 %s，间隔 %s 秒", source, target, state["cursor"], state["cutoff"], _interval(rule))
                try:
                    while True:
                        try:
                            async for messages in _groups(client, entity, state["cursor"], state["cutoff"], forward_album):
                                messages.sort(key=lambda message: getattr(message, "id", 0))
                                cursor = max(_number(getattr(message, "id", 0)) for message in messages)
                                text = next((getattr(message, "raw_text", "") for message in messages if getattr(message, "raw_text", "")), "")
                                service = any(getattr(message, "action", None) is not None for message in messages)
                                sender = None
                                if not service and _split(rule.get("sender")):
                                    get_sender = getattr(messages[0], "get_sender", None)
                                    if callable(get_sender):
                                        sender = await get_sender()
                                if service or not _passes(rule, messages, text, sender):
                                    stats["skipped"] += 1
                                else:
                                    while True:
                                        try:
                                            delay = next_send_at - time.monotonic()
                                            if delay > 0:
                                                await asyncio.sleep(delay)
                                            delivery = await _deliver_rule(
                                                client, target, messages, rule, sent, log,
                                                delivery_lock, persist_sent=persist_sent,
                                            )
                                            if delivery is None:
                                                stats["skipped"] += 1
                                            else:
                                                if not delivery.get("message_ids"):
                                                    raise RuntimeError("历史转发未返回目标消息 ID")
                                                stats["sent"] += 1
                                                next_send_at = time.monotonic() + _interval(rule)
                                            break
                                        except asyncio.CancelledError:
                                            raise
                                        except Exception as error:
                                            if not await flood_wait(error, source, target):
                                                raise
                                updated = dict(state, cursor=cursor)
                                await checkpoint(key, updated)
                                state = updated
                            await checkpoint(key, dict(state, cursor=state["cutoff"], completed=True))
                            stats["completed"] += 1
                            break
                        except asyncio.CancelledError:
                            raise
                        except Exception as error:
                            # 读取历史时也可能限速；从已落盘游标恢复，不丢当前相册。
                            if not await flood_wait(error, source, target):
                                raise
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    stats["failed"] += 1
                    log.warning("[消息转发助手] 历史转发 %s -> %s 已暂停于消息 %s，下次从此处继续：%r", source, target, state["cursor"], error)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            stats["failed"] += 1
            log.warning("[消息转发助手] 历史转发来源 %s 读取失败：%r", source, error)
    return stats
