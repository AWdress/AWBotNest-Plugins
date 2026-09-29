"""HHanClub 官方机器人红包与抽奖自动参与。"""

from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass

from . import _storage


_OFFICIAL_BOT_ID = 8780479105
_HANDLED_KEY = "hhan_activity_handled"
_pending: set[str] = set()
_COMMAND_RE = re.compile(
    r"(?:直接)?发送口令\s*[「『“\"]\s*([^\n「」『』“”\"]{1,100}?)\s*[」』”\"]\s*(参与|领取)"
)


@dataclass(frozen=True)
class Activity:
    kind: str
    command: str
    title: str


def parse_activity(text: str) -> Activity | None:
    """只解析官方仍可参与的口令红包或抽奖正文。"""
    body = str(text or "").strip()
    if not body:
        return None

    match = _COMMAND_RE.search(body)
    if not match:
        return None
    command = match.group(1).strip()
    action = match.group(2)
    if not command or any(ord(char) < 32 for char in command):
        return None

    if "发起了一场抽奖" in body and "抽奖" in body and action == "参与":
        if not re.search(r"状态\s*[:：]\s*进行中", body):
            return None
        title_match = re.search(r"(?:🎉\s*)?#\d+\s*[·・]\s*([^\n]+)", body)
        title = title_match.group(1).strip() if title_match else command
        return Activity(kind="lottery", command=command, title=title)

    if ("普通红包" in body or "随机红包" in body) and action == "领取":
        ended_markers = ("已领完", "已领取完", "已过期", "已失效", "红包结束", "状态：已结束", "状态:已结束")
        if any(marker in body for marker in ended_markers):
            return None
        if re.search(r"剩余(?:份数)?\s*[:：]?\s*0(?:\s|份|$)", body):
            return None
        title = "普通红包" if "普通红包" in body else "随机红包"
        return Activity(kind="redpacket", command=command, title=title)

    return None


def _peer_id(peer) -> int:
    if peer is None:
        return 0
    for attr in ("user_id", "channel_id", "chat_id", "id"):
        try:
            value = int(getattr(peer, attr, 0) or 0)
        except (TypeError, ValueError):
            value = 0
        if value:
            return abs(value)
    try:
        return abs(int(peer))
    except (TypeError, ValueError):
        return 0


async def _is_official_event(event) -> tuple[bool, str]:
    """校验直接发送者或 Telegram 原生转发来源，拒绝仅靠正文冒充。"""
    message = event.message
    try:
        sender = await event.get_sender()
    except Exception:  # noqa: BLE001
        sender = None
    if _peer_id(sender) == _OFFICIAL_BOT_ID or _peer_id(getattr(message, "sender_id", None)) == _OFFICIAL_BOT_ID:
        return True, "官方机器人"

    forwarded = getattr(message, "fwd_from", None)
    if forwarded:
        for attr in ("from_id", "saved_from_peer"):
            if _peer_id(getattr(forwarded, attr, None)) == _OFFICIAL_BOT_ID:
                return True, "官方转发"
    return False, ""


def _delay_range(cfg: dict) -> tuple[float, float]:
    try:
        delay_min = max(0.0, min(float(cfg.get("random_packet_delay_min", 1) or 0), 3600.0))
        delay_max = max(0.0, min(float(cfg.get("random_packet_delay_max", 5) or 0), 3600.0))
    except (TypeError, ValueError):
        return 1.0, 5.0
    return (delay_max, delay_min) if delay_min > delay_max else (delay_min, delay_max)


async def _account_id(client) -> int:
    account_id = _peer_id(getattr(client, "me", None))
    if account_id:
        return account_id
    try:
        return _peer_id(await client.get_me())
    except Exception:  # noqa: BLE001
        return 0


async def setup(ctx) -> None:
    async def on_activity(event):
        message = event.message
        if not event.is_group:
            return

        activity = parse_activity(str(getattr(message, "raw_text", "") or ""))
        if not activity:
            return

        cfg = {"auto_grab_random_packet": False, "auto_join_official_lottery": False, **dict(ctx.config or {})}
        enabled = (
            cfg.get("auto_grab_random_packet", False)
            if activity.kind == "redpacket"
            else cfg.get("auto_join_official_lottery", False)
        )
        if not enabled:
            return

        official, source = await _is_official_event(event)
        if not official:
            ctx.log.debug("[憨憨活动] 忽略来源未经验证的%s消息：msg=%s", activity.title, getattr(message, "id", 0))
            return

        chat_id = int(getattr(event, "chat_id", 0) or 0)
        message_id = int(getattr(message, "id", 0) or 0)
        if not chat_id or not message_id:
            return
        kind_name = "抽奖" if activity.kind == "lottery" else "红包"
        account_id = await _account_id(event.client)
        handled_key = f"{account_id}:{chat_id}:{message_id}:{activity.kind}"
        handled = _storage.get(ctx, _HANDLED_KEY, []) or []
        handled = [str(item) for item in handled] if isinstance(handled, list) else []
        legacy = _storage.get(ctx, "bonus_redpacket_handled", []) or []
        legacy = [str(item) for item in legacy] if isinstance(legacy, list) else []
        legacy_keys = {f"{account_id}:{chat_id}:{message_id}", f"0:{chat_id}:{message_id}"}
        if activity.kind == "redpacket" and legacy_keys.intersection(legacy):
            return
        if handled_key in handled or handled_key in _pending:
            return
        _pending.add(handled_key)

        delay_min, delay_max = _delay_range(cfg)
        delay = random.uniform(delay_min, delay_max)
        ctx.log.info(
            "[憨憨活动] 识别%s（%s）：%s，%.1f 秒后发送口令",
            kind_name, source, activity.title, delay,
        )

        async def send_command():
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                sent = await event.client.send_message(chat_id, activity.command)
                latest = _storage.get(ctx, _HANDLED_KEY, []) or []
                latest = [str(item) for item in latest] if isinstance(latest, list) else []
                _storage.set(ctx, _HANDLED_KEY, [handled_key, *[item for item in latest if item != handled_key]][:500])
                ctx.log.info(
                    "[憨憨活动] %s口令已发送：%s（消息 %s）",
                    kind_name, activity.title, getattr(sent, "id", 0),
                )
            except Exception as exc:  # noqa: BLE001
                ctx.log.warning("[憨憨活动] %s参与失败：%s", kind_name, exc)
            finally:
                _pending.discard(handled_key)

        ctx.create_task(send_command(), name=f"憨憨{kind_name}延迟参与")

    ctx.on_message()(on_activity)
    ctx.on_edited_message()(on_activity)


async def teardown(ctx) -> None:
    _pending.clear()
