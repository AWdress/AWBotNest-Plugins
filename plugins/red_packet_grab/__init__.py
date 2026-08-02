# =============================================================================
# AWBotNest 插件：自动抢红包（red_packet_grab）· Vue 模式
#
# 以用户账号自动参与验证码口令红包：OCR 识别图片，或在他人中奖后复制正确口令兜底。
# 原有抢包核心保持在 _grab.py；本文件负责配置、消息监听和 Vue 管理接口。
# =============================================================================
from __future__ import annotations

from ._grab import (
    Grabber,
    extract_plaintext_command,
    extract_text,
    is_rotating_password_packet,
    packet_has_remaining,
)
from ._records import Records, parse_targets, parse_group_ids, parse_keywords, to_float
from . import _ocr

__plugin__ = {
    "name": "自动抢红包", "id": "red_packet_grab", "version": "1.2.2",
    "author": "AWdress", "scope": "user", "default_enabled": False,
    "description": "自动参与口令红包：支持正文直接口令、图片财富密码、OCR 验证码识别及中奖确认复制兜底。可按发包人/群组限制范围，自带 Vue 配置界面与抢包记录。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_redpacket.png",
    "changelog": "v1.2.2 修复复制兜底漏响应\n- 支持群友回复红包消息发送口令，不再仅缓存独立文本\n- 缓存漏记时直接读取中奖确认所回复的原消息，必要时从 Telegram 回查\n- 同时监听新发与编辑后的中奖确认，兼容机器人编辑原消息返回结果\n- 扩展领取成功、获得、到账及内嵌金额确认识别\n- 记录候选口令所属红包，多红包并存时优先精确匹配并增加诊断日志\n\nv1.2.1 支持图片财富密码红包\n- 自动识别“财富密码见图片、发送财富密码即可领取”的拼手气红包\n- 监听红包图片编辑，前一次 OCR 未参与成功时会识别更新后的动态口令\n- 剩余数量为 0 时停止识别，避免红包结束后发送无效口令\n\nv1.2.0 支持正文拼手气红包\n- 自动识别“发送下方口令领取”后的完整口令并立即参与\n- 同时监听新消息与编辑消息，避免后补口令时漏抢\n- 按账号、群组和红包消息去重，结束状态不会重复发送\n\nv1.1.2 修复复制兜底选包\n- 修复多红包并存时按过期时间选包导致口令记错包，改为按确认者匹配对应红包\n\nv1.1.1 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "render_mode": "vue",
}

DEFAULTS = {
    "enabled": False,
    "trigger_keywords": "验证码,发送图中字符,识别上方,幸运红包",
    "target_senders": "", "target_groups": [],
    "ocr_enabled": True, "copy_fallback": True,
    "code_min_len": 4, "code_max_len": 8, "join_delay": 2,
    "success_markers": "抢到,恭喜", "transfer_prefix": "+",
    "activity_ttl_minutes": 30, "notify_owner": True,
}

_grabber: Grabber | None = None
_records: Records | None = None


def _effective_cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}


def _to_int(val, default: int) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


async def setup(ctx):
    global _grabber, _records
    _records = Records(ctx.kv, ctx.log)
    _grabber = Grabber(ctx, _records)

    if not _ocr.ocr_available():
        ctx.log.info("[自动抢红包] ddddocr 不可用，OCR 模式将失效，仅靠「复制兜底」参与")

    def _matched(caption: str) -> bool:
        kws = parse_keywords(_effective_cfg(ctx).get("trigger_keywords", "")) or ["验证码"]
        return any(k in caption for k in kws)

    def _sender_allowed(message, cfg):
        targets = parse_targets(cfg.get("target_senders", ""))
        fu = message.from_user
        if targets:
            if not fu or fu.id not in targets:
                return None
            sender_name = targets.get(fu.id, str(fu.id))
        else:
            sender_name = (fu.username or fu.first_name) if fu else "未知"
        groups = parse_group_ids(cfg.get("target_groups", ""))
        if groups and message.chat.id not in groups:
            return None
        return sender_name

    @ctx.on_api("/history", methods=["GET"])
    async def _api_history(req):
        return {"items": _records.history() if _records else []}

    @ctx.on_api("/history/clear", methods=["POST"])
    async def _api_history_clear(req):
        if _records:
            _records.clear_history()
        return {"ok": True}

    @ctx.on_api("/status", methods=["GET"])
    async def _api_status(req):
        return {"ocr_available": _ocr.ocr_available(),
                "active_count": _grabber.active_count() if _grabber else 0}

    @ctx.on_message(
        ctx.filters.incoming & ctx.filters.group
        & (ctx.filters.photo | ctx.filters.document), group=-10,
    )
    async def on_packet(client, message):
        cfg = _effective_cfg(ctx)
        if not cfg.get("enabled", False):
            return
        caption = extract_text(message)
        rotating_password = is_rotating_password_packet(caption)
        if not caption or (not rotating_password and not _matched(caption)):
            return
        if rotating_password and not packet_has_remaining(caption):
            ctx.log.info(
                "[自动抢红包] 图片财富密码红包已领完，跳过 chat=%s msg=%s",
                message.chat.id, message.id,
            )
            return

        sender_name = _sender_allowed(message, cfg)
        if sender_name is None:
            return
        try:
            await _grabber.handle_new_packet(
                client, message, sender_name=sender_name,
                join_delay=to_float(cfg.get("join_delay", 2)),
                ocr_enabled=cfg.get("ocr_enabled", True),
                copy_enabled=cfg.get("copy_fallback", True),
                notify=cfg.get("notify_owner", True),
                min_len=_to_int(cfg.get("code_min_len", 4), 4),
                max_len=_to_int(cfg.get("code_max_len", 8), 8),
                ttl_secs=max(1, _to_int(cfg.get("activity_ttl_minutes", 30), 30)) * 60,
                keep_for_retry=rotating_password,
            )
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动抢红包] 处理红包失败: %r", e)

    if hasattr(ctx, "on_edited_message"):
        ctx.on_edited_message(
            ctx.filters.incoming & ctx.filters.group
            & (ctx.filters.photo | ctx.filters.document), group=-10,
            target="user",
        )(on_packet)

    async def on_plaintext_packet(client, message):
        cfg = _effective_cfg(ctx)
        if not cfg.get("enabled", False):
            return
        command = extract_plaintext_command(extract_text(message))
        if not command:
            return
        sender_name = _sender_allowed(message, cfg)
        if sender_name is None:
            return
        try:
            await _grabber.handle_plaintext_packet(
                client, message, sender_name=sender_name, command=command,
                join_delay=to_float(cfg.get("join_delay", 2)),
                notify=cfg.get("notify_owner", True),
                ttl_secs=max(1, _to_int(cfg.get("activity_ttl_minutes", 30), 30)) * 60,
            )
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动抢红包] 处理正文拼手气红包失败: %r", e)

    ctx.on_message(
        ctx.filters.incoming & ctx.filters.group & ctx.filters.text, group=-10,
    )(on_plaintext_packet)
    if hasattr(ctx, "on_edited_message"):
        ctx.on_edited_message(
            ctx.filters.incoming & ctx.filters.group & ctx.filters.text, group=-10,
            target="user",
        )(on_plaintext_packet)

    @ctx.on_message(ctx.filters.incoming & ctx.filters.group & ctx.filters.reply, group=-9)
    async def on_reply(client, message):
        cfg = _effective_cfg(ctx)
        if not cfg.get("enabled", False):
            return
        try:
            await _grabber.handle_reply(
                client, message,
                success_markers=parse_keywords(cfg.get("success_markers", "抢到,恭喜")),
                transfer_prefix=str(cfg.get("transfer_prefix", "+") or "+"),
                join_delay=to_float(cfg.get("join_delay", 2)),
                copy_enabled=cfg.get("copy_fallback", True),
                notify=cfg.get("notify_owner", True),
                min_len=_to_int(cfg.get("code_min_len", 4), 4),
                max_len=_to_int(cfg.get("code_max_len", 8), 8),
            )
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动抢红包] 处理确认回复失败: %r", e)

    if hasattr(ctx, "on_edited_message"):
        ctx.on_edited_message(
            ctx.filters.incoming & ctx.filters.group & ctx.filters.reply, group=-9,
            target="user",
        )(on_reply)

    @ctx.on_message(ctx.filters.incoming & ctx.filters.group & ctx.filters.text, group=5)
    async def on_group_text(client, message):
        cfg = _effective_cfg(ctx)
        if not cfg.get("enabled", False) or not cfg.get("copy_fallback", True):
            return
        try:
            await _grabber.handle_group_text(
                client, message,
                min_len=_to_int(cfg.get("code_min_len", 4), 4),
                max_len=_to_int(cfg.get("code_max_len", 8), 8),
            )
        except Exception as e:  # noqa: BLE001
            ctx.log.debug("[自动抢红包] 缓存候选口令异常: %r", e)

    ctx.log.info("[自动抢红包] 已加载（OCR可用=%s）", _ocr.ocr_available())


async def teardown(ctx):
    global _grabber, _records
    if _grabber is not None:
        _grabber.clear()
    _grabber = None
    _records = None
