# =============================================================================
# AWBotNest 插件：自动抢红包（red_packet_grab）· Vue 模式
#
# 以用户账号自动参与验证码口令红包：OCR 识别图片，或在他人中奖后复制正确口令兜底。
# 原有抢包核心保持在 _grab.py；本文件负责配置、消息监听和 Vue 管理接口。
# =============================================================================
from __future__ import annotations

from ._grab import Grabber, extract_text
from ._records import Records, parse_targets, parse_group_ids, parse_keywords, to_float
from . import _ocr

__plugin__ = {
    "name": "自动抢红包", "id": "red_packet_grab", "version": "1.1.1",
    "author": "AWdress", "scope": "user", "default_enabled": False,
    "description": "自动参与验证码口令红包：OCR 识别或监听中奖确认后复制正确口令兜底。可按发包人/群组限制范围，自带 Vue 配置界面与抢包记录。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_redpacket.png",
    "changelog": "v1.1.1 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
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
        if not caption or not _matched(caption):
            return

        targets = parse_targets(cfg.get("target_senders", ""))
        fu = message.from_user
        if targets:
            if not fu or fu.id not in targets:
                return
            sender_name = targets.get(fu.id, str(fu.id))
        else:
            sender_name = (fu.username or fu.first_name) if fu else "未知"

        groups = parse_group_ids(cfg.get("target_groups", ""))
        if groups and message.chat.id not in groups:
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
            )
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动抢红包] 处理红包失败: %r", e)

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
            )
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动抢红包] 处理确认回复失败: %r", e)

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
