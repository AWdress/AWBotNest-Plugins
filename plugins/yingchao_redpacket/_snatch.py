# =============================================================================
# 影巢口令红包插件 - 抢包核心逻辑（口令红包）
#
# 口令红包（图片/文档口令）：OCR 识别口令自动回复；OCR 失败/关闭 → 等待复制
# 他人被确认的口令再发。三层陷阱防护：命令前缀 / 注入字符 / 关键词库。
#
# 状态机（内存维护）：
#   pending_copy：OCR 失败/关闭，等待复制他人口令
#   ocr_sent    ：已发 OCR 口令，等待红包系统确认
#   reply_cache ：缓存他人对红包的回复，供复制模式使用
# =============================================================================
from __future__ import annotations

import asyncio
import re
import time as _time
from typing import Optional

from . import _ocr

# OCR 发口令后等待确认超时（秒）
_OCR_TIMEOUT = 30.0
# 状态条目存活上限（秒）
_PENDING_TTL = 24 * 3600

# 危险命令前缀/关键词（绝不发送）
_DANGEROUS_COMMANDS = [
    "创建红包", "结束红包", "红包状态",
    "开启数字炸弹", "结束数字炸弹", "持续数字炸弹",
]


# ─── 文本工具 ────────────────────────────────────────────────────────────

def extract_text(message) -> str:
    return (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()


def is_failure_reply(text: str) -> bool:
    if not text:
        return False
    return any(k in text for k in ("口令不对", "口令错误", "口令有误", "口令不正确"))


def is_success_reply(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"抢到了", text.strip()))


def acct_name(client) -> str:
    me = getattr(client, "me", None)
    if not me:
        return "未知账号"
    if getattr(me, "username", None):
        return f"{me.first_name}(@{me.username})"
    return f"{me.first_name}(ID:{me.id})"


# ─── 陷阱检测 ────────────────────────────────────────────────────────────

def is_trap_keyword(keyword: str, enabled: bool, custom_keywords: list[str], log=None) -> bool:
    """检测口令是否为陷阱关键词。返回 True 表示应拒绝发送。

    三层防护：
      1. 命令前缀（/ . 开头）或已知危险命令 —— 始终拦截，不受开关控制。
      2. 命令注入（含换行、; | & 等多语句符号）—— 始终拦截。
      3. 关键词库匹配 —— 受 enabled 开关控制。
    """
    kw = (keyword or "").strip()
    if not kw:
        return True

    # 1. 命令前缀 / 危险命令（始终拦截）
    if kw.startswith("/") or kw.startswith("."):
        if log:
            log.warning("[影巢口令陷阱] 口令以命令前缀开头，拒绝: %r", kw)
        return True
    for cmd in _DANGEROUS_COMMANDS:
        if cmd in kw:
            if log:
                log.warning("[影巢口令陷阱] 口令含危险命令 %r，拒绝: %r", cmd, kw)
            return True

    # 2. 命令注入（始终拦截）
    if re.search(r"[\n\r;|&]", kw):
        if log:
            log.warning("[影巢口令陷阱] 口令含注入字符，拒绝: %r", kw)
        return True

    # 3. 关键词库（受开关控制）
    if not enabled:
        return False
    kw_lower = kw.lower()
    for trap in custom_keywords:
        if trap and trap.lower() in kw_lower:
            if log:
                log.warning("[影巢口令陷阱] 口令命中陷阱关键词 %r，拒绝: %r", trap, kw)
            return True
    return False


# ─── 口令红包状态机 ────────────────────────────────────────────────────────

class _PendingCopy:
    __slots__ = ("packet_id", "group_id", "sender_name", "join_delay", "expires_at")

    def __init__(self, packet_id, group_id, sender_name, join_delay):
        self.packet_id = packet_id
        self.group_id = group_id
        self.sender_name = sender_name
        self.join_delay = join_delay
        self.expires_at = _time.monotonic() + _PENDING_TTL


class _OcrSent:
    __slots__ = ("packet_id", "group_id", "keyword", "sent_id", "sender_name", "timeout_task")

    def __init__(self, packet_id, group_id, keyword, sent_id, sender_name):
        self.packet_id = packet_id
        self.group_id = group_id
        self.keyword = keyword
        self.sent_id = sent_id
        self.sender_name = sender_name
        self.timeout_task: Optional[asyncio.Task] = None


class TokenSnatcher:
    """口令红包抢夺状态机（不依赖平台 service / DB）。"""

    def __init__(self, ctx, records):
        self._ctx = ctx
        self._log = ctx.log
        self._records = records
        # key=(group_id, packet_msg_id)
        self._pending_copy: dict[tuple[int, int], _PendingCopy] = {}
        # key=(group_id, sent_msg_id)
        self._ocr_sent: dict[tuple[int, int], _OcrSent] = {}
        # key=(group_id, reply_msg_id) -> (keyword, orig_packet_id)
        self._reply_cache: dict[tuple[int, int], tuple[str, int]] = {}
        self._chat_names: dict[int, str] = {}

    def _remember_chat(self, chat) -> str:
        group_id = chat.id
        title = (
            getattr(chat, "title", None)
            or getattr(chat, "first_name", None)
            or str(group_id)
        )
        self._chat_names[group_id] = title
        return f"{title} ({group_id})"

    def _chat_label(self, group_id: int) -> str:
        return f"{self._chat_names.get(group_id, group_id)} ({group_id})"

    # —— 主入口：收到目标用户的口令红包 ——
    async def handle_new_packet(
        self, client, message, sender_name: str, join_delay: float,
        ocr_enabled: bool, trap_enabled: bool, custom_keywords: list[str],
        notify: bool,
    ) -> None:
        self._prune_expired()
        group_id = message.chat.id
        chat_label = self._remember_chat(message.chat)
        packet_id = message.id
        caption = extract_text(message)

        # 去重（账号 + 群 + 消息）
        me = getattr(client, "me", None)
        acct_id = me.id if me else 0
        packet_key = f"{acct_id}:{group_id}:{packet_id}"
        if self._records.already_handled(packet_key):
            return
        self._records.mark_handled(packet_key)

        # 陷阱检测（对 caption）
        if is_trap_keyword(caption, trap_enabled, custom_keywords, self._log) and caption:
            # caption 命中陷阱仅记录，不影响后续（口令在图里，caption 一般是说明）
            self._log.info("[影巢口令] caption 含可疑词，谨慎处理 %s msg=%s", chat_label, packet_id)

        # OCR 模式：尝试下载图片识别
        keyword = ""
        if ocr_enabled and _ocr.ocr_available():
            img = await self._download_image(client, message)
            if img:
                keyword = await _ocr.recognize(img, self._log)

        if not keyword:
            # OCR 关闭 / 不可用 / 识别失败 → 进入等待复制模式
            reason = "OCR 关闭" if not ocr_enabled else ("OCR 不可用" if not _ocr.ocr_available() else "OCR 识别失败")
            self._pending_copy[(group_id, packet_id)] = _PendingCopy(packet_id, group_id, sender_name, join_delay)
            self._log.info("[影巢口令] 进入等待复制 %s msg=%s 原因=%s", chat_label, packet_id, reason)
            return

        # OCR 识别成功 → 陷阱检测口令本身
        if is_trap_keyword(keyword, trap_enabled, custom_keywords, self._log):
            self._log.warning("[影巢口令] OCR口令命中陷阱，拦截: %r", keyword)
            if notify:
                await self._safe_notify(
                    f"影巢口令红包-已拦截陷阱口令\n发包人: {sender_name}\n口令: {keyword}\n{getattr(message,'link','')}",
                    level="warning", account=client,
                )
            return

        # 发送口令
        if join_delay > 0:
            await asyncio.sleep(join_delay)
        try:
            sent = await client.send_message(group_id, keyword, reply_to_message_id=packet_id)
            sent_id = sent.id if sent else 0
        except Exception as e:  # noqa: BLE001
            self._log.error("[影巢口令] OCR口令发送失败: %r", e)
            return

        if sent_id <= 0:
            return

        entry = _OcrSent(packet_id, group_id, keyword, sent_id, sender_name)
        self._ocr_sent[(group_id, sent_id)] = entry
        entry.timeout_task = asyncio.create_task(self._ocr_timeout(group_id, sent_id))
        self._log.info("[影巢口令] 已发OCR口令 %s msg=%s sent=%s 口令=%r", chat_label, packet_id, sent_id, keyword)
        if notify:
            await self._safe_notify(
                f"影巢口令红包-已发OCR口令\n发包人: {sender_name}\n口令: {keyword}\n{getattr(message,'link','')}",
                level="info", account=client,
            )

    # —— 处理群内回复（缓存口令 / 失败确认 / 成功确认，合一处理）——
    async def handle_reply(self, client, message, notify: bool) -> None:
        self._prune_expired()
        group_id = message.chat.id
        chat_label = self._remember_chat(message.chat)
        reply_to_id = getattr(message, "reply_to_message_id", None)
        if not reply_to_id:
            return

        text = extract_text(message)
        me = getattr(client, "me", None)
        from_self = bool(me and message.from_user and message.from_user.id == me.id)

        # 失败确认：「口令不对」
        if is_failure_reply(text):
            await self._handle_failure(group_id, reply_to_id, notify, client)
            return

        # 成功确认：「抢到了」
        if is_success_reply(text):
            await self._handle_success(client, message, group_id, reply_to_id, notify)
            return

        # 否则：若该 reply_to 指向 pending 红包，缓存他人口令（复制模式备用）
        if from_self:
            return
        if (group_id, reply_to_id) in self._pending_copy and text:
            self._reply_cache[(group_id, message.id)] = (text, reply_to_id)
            self._log.info("[影巢口令] 缓存口令 %s reply=%s packet=%s 口令=%r",
                           chat_label, message.id, reply_to_id, text)

    async def _handle_failure(self, group_id, reply_to_id, notify, client) -> None:
        entry = self._ocr_sent.pop((group_id, reply_to_id), None)
        if entry is None:
            return
        if entry.timeout_task:
            entry.timeout_task.cancel()
        self._log.info("[影巢口令] OCR口令被判错 %s 口令=%r", self._chat_label(group_id), entry.keyword)
        # 失败后退回等待复制模式
        self._pending_copy[(group_id, entry.packet_id)] = _PendingCopy(
            entry.packet_id, group_id, entry.sender_name, 0.0
        )
        if notify:
            await self._safe_notify(
                f"影巢口令红包-OCR口令识别有误，转等待复制\n发包人: {entry.sender_name}\n口令: {entry.keyword}",
                level="warning", account=client,
            )

    async def _handle_success(self, client, message, group_id, reply_to_id, notify) -> None:
        # 路径1：reply_to 是我们发的 OCR 口令 → 确认成功
        ocr_entry = self._ocr_sent.pop((group_id, reply_to_id), None)
        if ocr_entry is not None:
            if ocr_entry.timeout_task:
                ocr_entry.timeout_task.cancel()
            self._log.info("[影巢口令] OCR口令确认成功 %s 口令=%r", self._chat_label(group_id), ocr_entry.keyword)
            self._records.add_history({
                "type": "口令红包", "mode": "OCR", "group_id": group_id,
                "group_title": self._chat_names.get(group_id, str(group_id)),
                "sender": ocr_entry.sender_name, "keyword": ocr_entry.keyword, "ok": True,
            })
            if notify:
                await self._safe_notify(
                    f"影巢口令红包-OCR口令抢到了\n发包人: {ocr_entry.sender_name}\n口令: {ocr_entry.keyword}",
                    level="success", account=client,
                )
            return

        # 路径2：复制模式——他人口令被确认成功 → 复制口令参与
        cached = self._reply_cache.get((group_id, reply_to_id))
        if cached is None:
            # fallback：成功消息回复到红包主消息，或当前群仅有一个 pending
            cached = self._find_cached_for_packet(group_id, reply_to_id)
        if cached is None:
            only = self._only_pending(group_id)
            if only is not None:
                cached = self._find_cached_for_packet(group_id, only)
        if cached is None:
            return

        keyword, orig_packet_id = cached
        pending = self._pending_copy.pop((group_id, orig_packet_id), None)
        if pending is None:
            return

        # 发送前再做陷阱检测（复制来的口令同样要防陷阱）
        cfg = self._ctx.config
        from ._records import parse_keywords
        trap_enabled = cfg.get("token_trap_detection", True)
        custom = parse_keywords(cfg.get("token_trap_keywords", ""))
        if is_trap_keyword(keyword, trap_enabled, custom, self._log):
            self._log.warning("[影巢口令] 复制口令命中陷阱，拦截: %r", keyword)
            return

        if pending.join_delay > 0:
            await asyncio.sleep(pending.join_delay)
        try:
            sent = await client.send_message(group_id, keyword, reply_to_message_id=orig_packet_id)
            ok = bool(sent and sent.id)
        except Exception as e:  # noqa: BLE001
            self._log.error("[影巢口令] 复制口令发送失败: %r", e)
            ok = False

        self._log.info("[影巢口令] 复制模式发送 %s packet=%s 口令=%r ok=%s",
                       self._chat_label(group_id), orig_packet_id, keyword, ok)
        self._records.add_history({
            "type": "口令红包", "mode": "复制", "group_id": group_id,
            "group_title": self._chat_names.get(group_id, str(group_id)),
            "sender": pending.sender_name, "keyword": keyword, "ok": ok,
        })
        if notify and ok:
            await self._safe_notify(
                f"影巢口令红包-复制口令参与\n发包人: {pending.sender_name}\n口令: {keyword}",
                level="success", account=client,
            )

    def _prune_expired(self) -> None:
        """清掉过期的 pending 条目，并同步清失效的 reply_cache。"""
        now = _time.monotonic()
        for k in [k for k, p in self._pending_copy.items() if now > p.expires_at]:
            self._pending_copy.pop(k, None)
        valid = set(self._pending_copy)  # set of (group_id, packet_id)
        for rk in [rk for rk, (_kw, orig) in self._reply_cache.items()
                   if (rk[0], orig) not in valid]:
            self._reply_cache.pop(rk, None)

    def _find_cached_for_packet(self, group_id, packet_id):
        for (g, _r), (kw, orig) in reversed(list(self._reply_cache.items())):
            if g == group_id and orig == packet_id:
                return (kw, orig)
        return None

    def _only_pending(self, group_id):
        ids = [pid for (g, pid) in self._pending_copy if g == group_id]
        return ids[0] if len(ids) == 1 else None

    async def _ocr_timeout(self, group_id, sent_id) -> None:
        await asyncio.sleep(_OCR_TIMEOUT)
        removed = self._ocr_sent.pop((group_id, sent_id), None)
        if removed is not None:
            self._log.info("[影巢口令] OCR等待确认超时 %s sent=%s 口令=%r",
                           self._chat_label(group_id), sent_id, removed.keyword)

    async def _download_image(self, client, message) -> bytes:
        media = getattr(message, "photo", None)
        if not media:
            doc = getattr(message, "document", None)
            mt = getattr(doc, "mime_type", None) if doc else None
            if doc and mt and mt.startswith("image/"):
                media = doc
        if not media:
            return b""
        try:
            data = await client.download_media(message, in_memory=True)
            if data is None:
                return b""
            if hasattr(data, "getvalue"):
                return data.getvalue()
            if hasattr(data, "getbuffer"):
                return bytes(data.getbuffer())
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
        except Exception as e:  # noqa: BLE001
            self._log.debug("[影巢口令] 图片下载失败: %r", e)
        return b""

    async def _safe_notify(self, text, level="info", account=None) -> None:
        try:
            await self._ctx.notify(text, level=level, category="影巢口令红包", account=account)
        except Exception:  # noqa: BLE001
            pass
