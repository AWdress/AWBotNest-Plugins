# =============================================================================
# 自动抢红包插件 - 抢包核心逻辑（验证码口令红包）
#
# 面向「把口令渲染成扭曲验证码图片、群友发送图中字符即参与」这类红包（如本仓库
# red_packet_send 发出的幸运红包）。两条拿到口令的路径：
#
#   1. OCR 模式：下载验证码图 → ddddocr 多策略识别 → 发送识别到的口令。
#   2. 复制兜底：此类红包所有人答案是同一个口令，发包方会 reply 确认中奖者
#      （「…抢到 N 魔力」/「+金额」）。中奖者那条消息的文本就是正确口令 ——
#      监听群内确认，复制该口令自己再发一次。无需任何依赖即可工作，OCR 关闭/
#      失败时的可靠兜底。
#
# 状态全内存维护，不依赖平台 service / DB。每个红包按 (群, 消息id) 去重一次。
# =============================================================================
from __future__ import annotations

import asyncio
import random
import re
import time as _time
from typing import Optional


def extract_text(message) -> str:
    return (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()


def acct_name(client) -> str:
    me = getattr(client, "me", None)
    if not me:
        return "未知账号"
    if getattr(me, "username", None):
        return f"{me.first_name}(@{me.username})"
    return f"{me.first_name}(ID:{me.id})"


class _Packet:
    """一个正在监听/参与中的红包。"""

    __slots__ = (
        "group_id", "packet_id", "sender_id", "sender_name",
        "answered", "our_sent_id", "our_code", "mode", "expires_at",
    )

    def __init__(self, group_id, packet_id, sender_id, sender_name, ttl_secs):
        self.group_id = group_id
        self.packet_id = packet_id
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.answered = False          # 是否已发出口令（避免重复参与）
        self.our_sent_id = 0           # 我们发出的口令消息 id（用于确认中奖）
        self.our_code = ""             # 我们发出的口令
        self.mode = ""                 # OCR / 复制
        self.expires_at = _time.monotonic() + ttl_secs


class Grabber:
    """验证码口令红包自动抢夺器。"""

    def __init__(self, ctx, records):
        self._ctx = ctx
        self._log = ctx.log
        self._records = records
        # key=(group_id, packet_msg_id)
        self._active: dict[tuple[int, int], _Packet] = {}
        # key=(group_id, msg_id) -> 候选口令文本（他人发的、可能是正确口令）
        self._candidates: dict[tuple[int, int], str] = {}

    # —— 主入口：收到疑似验证码口令红包 ——
    async def handle_new_packet(
        self, client, message, sender_name: str, join_delay: float,
        ocr_enabled: bool, copy_enabled: bool, notify: bool,
        min_len: int, max_len: int, ttl_secs: int,
    ) -> None:
        group_id = message.chat.id
        packet_id = message.id
        fu = message.from_user
        sender_id = fu.id if fu else 0

        # 去重（账号 + 群 + 消息）：同一红包只处理一次
        me = getattr(client, "me", None)
        acct_id = me.id if me else 0
        packet_key = f"{acct_id}:{group_id}:{packet_id}"
        if self._records.already_handled(packet_key):
            return
        self._records.mark_handled(packet_key)

        self._sweep_expired()
        pkt = _Packet(group_id, packet_id, sender_id, sender_name, ttl_secs)
        self._active[(group_id, packet_id)] = pkt

        # 路径 1：OCR 识别
        code = ""
        if ocr_enabled:
            from . import _ocr
            if _ocr.ocr_available():
                img = await self._download_image(client, message)
                if img:
                    raw = await _ocr.recognize(img, self._log)
                    cand = _ocr.clean_code(raw)
                    if min_len <= len(cand) <= max_len:
                        code = cand
                    elif cand:
                        self._log.info(
                            "[自动抢红包] OCR 结果长度不符(%s)，丢弃: %r", len(cand), cand)

        if code:
            pkt.mode = "OCR"
            await self._send_answer(client, pkt, code, join_delay, notify)
            return

        # OCR 未成功 —— 交给复制兜底（若开启）
        reason = "OCR 关闭" if not ocr_enabled else "OCR 不可用/识别失败"
        if copy_enabled:
            self._log.info(
                "[自动抢红包] chat=%s msg=%s %s，转复制兜底（等他人口令被确认）",
                group_id, packet_id, reason)
        else:
            self._log.info(
                "[自动抢红包] chat=%s msg=%s %s 且复制兜底关闭，放弃",
                group_id, packet_id, reason)
            self._active.pop((group_id, packet_id), None)

    # —— 群内普通文本：缓存他人可能的口令（复制兜底用）——
    async def handle_group_text(self, client, message, min_len: int, max_len: int) -> None:
        group_id = message.chat.id
        # 只缓存「非回复」的普通文本（参与用的口令是独立一条消息，不是回复）
        if getattr(message, "reply_to_message_id", None):
            return
        # 该群没有进行中的红包就不缓存
        if not any(g == group_id for (g, _p) in self._active):
            return
        me = getattr(client, "me", None)
        if me and message.from_user and message.from_user.id == me.id:
            return  # 不缓存自己发的
        text = (message.text or "").strip()
        if not (min_len <= len(text) <= max_len):
            return
        # 口令是字母+数字（去混淆字符集）；命令/含空格的不是口令
        if not re.fullmatch(r"[0-9A-Za-z]+", text):
            return
        self._candidates[(group_id, message.id)] = text
        # 控制缓存规模
        if len(self._candidates) > 500:
            for k in list(self._candidates)[:200]:
                self._candidates.pop(k, None)

    # —— 群内回复：确认中奖（我方中奖 / 复制他人正确口令）——
    async def handle_reply(
        self, client, message, success_markers: list[str], transfer_prefix: str,
        join_delay: float, copy_enabled: bool, notify: bool,
    ) -> None:
        group_id = message.chat.id
        reply_to_id = getattr(message, "reply_to_message_id", None)
        if not reply_to_id:
            return
        text = extract_text(message)
        if not self._is_success(text, success_markers, transfer_prefix):
            return

        self._sweep_expired()

        # 路径 A：回复的是「我们发出的口令」→ 确认我方中奖
        for key, pkt in list(self._active.items()):
            if pkt.our_sent_id and reply_to_id == pkt.our_sent_id:
                self._log.info("[自动抢红包] 口令确认中奖 chat=%s 口令=%r 模式=%s",
                               group_id, pkt.our_code, pkt.mode)
                self._records.add_history({
                    "group_id": group_id, "sender": pkt.sender_name,
                    "code": pkt.our_code, "mode": pkt.mode, "ok": True,
                })
                if notify:
                    await self._safe_notify(
                        f"自动抢红包-抢到了 🧧\n发包人: {pkt.sender_name}\n"
                        f"口令: {pkt.our_code}（{pkt.mode}）",
                        level="success", account=client)
                self._active.pop(key, None)
                return

        # 路径 B：复制兜底 —— 回复的是他人某条候选口令，说明那条是正确口令
        if not copy_enabled:
            return
        code = self._candidates.get((group_id, reply_to_id))
        if not code:
            return
        pkt = self._latest_unanswered(group_id)
        if pkt is None:
            return
        pkt.mode = "复制"
        await self._send_answer(client, pkt, code, join_delay, notify)

    # —— 发送口令参与 ——
    async def _send_answer(self, client, pkt: _Packet, code: str,
                           join_delay: float, notify: bool) -> None:
        if pkt.answered:
            return
        pkt.answered = True
        pkt.our_code = code

        delay = max(0.0, join_delay) + random.uniform(0.2, 1.0)  # 轻微抖动，别太机械
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            sent = await client.send_message(pkt.group_id, code)
            pkt.our_sent_id = sent.id if sent else 0
        except Exception as e:  # noqa: BLE001
            self._log.error("[自动抢红包] 发送口令失败: %r", e)
            pkt.answered = False  # 允许后续复制兜底再试
            return

        self._log.info("[自动抢红包] 已发口令 chat=%s packet=%s 口令=%r 模式=%s",
                       pkt.group_id, pkt.packet_id, code, pkt.mode)
        if notify:
            await self._safe_notify(
                f"自动抢红包-已发口令\n发包人: {pkt.sender_name}\n"
                f"口令: {code}（{pkt.mode}）",
                level="info", account=client)

    # —— 工具 ——
    def _is_success(self, text: str, markers: list[str], transfer_prefix: str) -> bool:
        if not text:
            return False
        for m in markers:
            if m and m in text:
                return True
        # 发放触发（如 `+100`）也是明确的中奖信号
        pfx = re.escape((transfer_prefix or "+").strip() or "+")
        return bool(re.fullmatch(rf"{pfx}\s*\d+", text.strip()))

    def _latest_unanswered(self, group_id: int) -> Optional[_Packet]:
        best = None
        for (g, _p), pkt in self._active.items():
            if g == group_id and not pkt.answered:
                if best is None or pkt.expires_at > best.expires_at:
                    best = pkt
        return best

    def _sweep_expired(self) -> None:
        now = _time.monotonic()
        for key in [k for k, p in self._active.items() if p.expires_at < now]:
            self._active.pop(key, None)
        # 候选缓存随红包过期一并收缩（无对应活跃红包的群，清掉其候选）
        if self._candidates:
            live_groups = {g for (g, _p) in self._active}
            for k in [k for k in self._candidates if k[0] not in live_groups]:
                self._candidates.pop(k, None)

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
            self._log.debug("[自动抢红包] 图片下载失败: %r", e)
        return b""

    async def _safe_notify(self, text, level="info", account=None) -> None:
        try:
            await self._ctx.notify(text, level=level, category="自动抢红包", account=account)
        except Exception:  # noqa: BLE001
            pass

    def clear(self) -> None:
        self._active.clear()
        self._candidates.clear()

    def active_count(self) -> int:
        self._sweep_expired()
        return len(self._active)
