# =============================================================================
# AWBotNest 插件：自动抢红包（red_packet_grab）
#
# 用你的「用户账号」自动参与他人发的「验证码口令红包」——即把口令渲染成扭曲验证码
# 图片、要求群友发送图中字符才算参与的那种红包（如本仓库 red_packet_send 发出的
# 幸运红包）。拿到口令有两条路径：
#
#   1. OCR 模式（需 ddddocr，可选）：下载验证码图片，多策略识别口令后自动发送。
#      这类验证码专为「防脚本」设计（旋转/重叠/干扰线），OCR 命中率有限。
#   2. 复制兜底（无需任何依赖，默认开启）：此类红包所有人的口令是同一个，发包方会
#      reply 确认中奖者（「…抢到 N 魔力」/「+金额」）。监听到确认后，把那位中奖者
#      发的口令复制过来自己再发一次。OCR 关闭/不可用/识别失败时的可靠兜底。
#
# scope=user：以你的账号监听并参与。只抢「别人发的」红包（incoming），不会误触自己
# 用 red_packet_send 发出的红包。可选按发包人 / 群组白名单限制范围。
# =============================================================================
from __future__ import annotations

from ._grab import Grabber, extract_text
from ._records import (
    Records, parse_targets, parse_group_ids, parse_keywords, to_float,
)
from . import _ocr

__plugin__ = {
    "name": "自动抢红包",
    "id": "red_packet_grab",
    "version": "1.0.1",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "用你的账号自动参与他人发的「验证码口令红包」（把口令渲染成扭曲验证码图片、要求发送图中字符参与的红包，如本仓库发红包插件发出的幸运红包）。OCR 识别验证码（需 ddddocr，可选）或监听中奖确认后复制正确口令兜底参与。可按发包人/群组限制范围，只抢别人发的红包。",
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": False, "label": "启用自动抢红包",
            "section": "总开关",
            "help": "关闭后不再监听、不参与任何红包。",
        },

        # ───────── 识别范围 ─────────
        "trigger_keywords": {
            "type": "text",
            "default": "验证码,发送图中字符,识别上方,幸运红包",
            "label": "触发关键词", "section": "识别范围",
            "help": "红包图片的说明文字（caption）含其中任一关键词才判定为「验证码口令红包」并尝试参与。逗号或换行分隔。",
        },
        "target_senders": {
            "type": "text", "default": "", "label": "发包人白名单",
            "section": "识别范围",
            "help": "只抢这些人发的红包。一行一个，格式 `用户ID 备注` 或 `用户ID`。留空=不限发包人（任何人发的都抢）。",
        },
        "target_groups": {
            "type": "chat", "default": [], "label": "群组白名单", "multi": True,
            "chat_types": ["group"], "section": "识别范围",
            "help": "只在勾选的群里抢。留空=不限群组。",
        },

        # ───────── 口令识别 ─────────
        "ocr_enabled": {
            "type": "boolean", "default": True, "label": "启用 OCR 识别验证码",
            "section": "口令识别",
            "help": "用 ddddocr 识别验证码图片里的口令自动参与。这类验证码专为防脚本设计，识别率有限，失败时自动交给「复制兜底」。需安装 ddddocr（未安装则本项自动失效，仅靠复制兜底）。",
        },
        "copy_fallback": {
            "type": "boolean", "default": True, "label": "复制兜底",
            "section": "口令识别",
            "help": "OCR 关闭/不可用/识别失败时，监听群内中奖确认——把已被确认中奖的那位群友发的口令复制过来自己再发一次。此类红包人人口令相同，复制兜底通常比 OCR 更可靠。",
        },
        "code_min_len": {
            "type": "number", "default": 4, "label": "口令最短位数",
            "min": 1, "max": 12, "step": 1, "section": "口令识别",
            "help": "OCR 结果 / 候选口令长度低于此值视为无效。发红包插件默认验证码为 4 位。",
        },
        "code_max_len": {
            "type": "number", "default": 8, "label": "口令最长位数",
            "min": 1, "max": 30, "step": 1, "section": "口令识别",
            "help": "OCR 结果 / 候选口令长度超过此值视为无效。自定义中文口令场景可适当调大（但中文口令 OCR 基本靠复制兜底）。",
        },

        # ───────── 参与行为 ─────────
        "join_delay": {
            "type": "slider", "default": 2, "label": "参与延迟(秒)",
            "min": 0, "max": 60, "step": 1, "section": "参与行为",
            "help": "拿到口令后等待多少秒再发送（另加 0.2~1 秒随机抖动，别太机械）。0=尽快。",
        },
        "success_markers": {
            "type": "text", "default": "抢到,恭喜",
            "label": "中奖确认关键词", "section": "参与行为",
            "help": "发包方 reply 中含其中任一关键词即视为「有人中奖确认」，用于确认我方中奖 / 触发复制兜底。逗号或换行分隔。",
        },
        "transfer_prefix": {
            "type": "string", "default": "+", "label": "发放金额前缀",
            "section": "参与行为",
            "help": "发包方打款时的金额前缀（如 `+100`），也作为中奖确认信号。需与对方发红包插件的设置一致。",
        },

        # ───────── 通用 ─────────
        "activity_ttl_minutes": {
            "type": "slider", "default": 30, "label": "红包监听时长(分钟)",
            "min": 1, "max": 240, "step": 1, "section": "通用",
            "help": "一个红包出现后监听多久（用于复制兜底的等待窗口）。超时后不再对该红包参与。建议与对方红包超时时间接近。",
        },
        "notify_owner": {
            "type": "boolean", "default": True, "label": "抢包结果通知我",
            "section": "通用",
            "help": "发出口令 / 确认中奖时用机器人通知平台主人。",
        },
    },
}

# 抢包器（setup 时创建）
_grabber: Grabber | None = None


def _to_int(val, default: int) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


async def setup(ctx):
    global _grabber
    records = Records(ctx.kv, ctx.log)
    _grabber = Grabber(ctx, records)

    if not _ocr.ocr_available():
        ctx.log.info("[自动抢红包] ddddocr 不可用，OCR 模式将失效，仅靠「复制兜底」参与")

    def _matched(caption: str) -> bool:
        kws = parse_keywords(ctx.config.get("trigger_keywords", "")) or ["验证码"]
        return any(k in caption for k in kws)

    # ───────── 收到疑似验证码口令红包（图片/图片文档）─────────
    @ctx.on_message(
        ctx.filters.incoming & ctx.filters.group
        & (ctx.filters.photo | ctx.filters.document),
        group=-10,
    )
    async def on_packet(client, message):
        cfg = ctx.config
        if not cfg.get("enabled", False):
            return
        caption = extract_text(message)
        if not caption or not _matched(caption):
            return

        # 发包人白名单（留空=不限）
        targets = parse_targets(cfg.get("target_senders", ""))
        fu = message.from_user
        if targets:
            if not fu or fu.id not in targets:
                return
            sender_name = targets.get(fu.id, str(fu.id))
        else:
            sender_name = (
                (fu.username or fu.first_name) if fu else "未知"
            )

        # 群组白名单（留空=不限）
        groups = parse_group_ids(cfg.get("target_groups", ""))
        if groups and message.chat.id not in groups:
            return

        try:
            await _grabber.handle_new_packet(
                client, message,
                sender_name=sender_name,
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

    # ───────── 群内确认回复：确认我方中奖 / 触发复制兜底 ─────────
    @ctx.on_message(ctx.filters.incoming & ctx.filters.group & ctx.filters.reply, group=-9)
    async def on_reply(client, message):
        cfg = ctx.config
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

    # ───────── 群内普通文本：缓存他人口令（复制兜底用）─────────
    @ctx.on_message(ctx.filters.incoming & ctx.filters.group & ctx.filters.text, group=5)
    async def on_group_text(client, message):
        cfg = ctx.config
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
    global _grabber
    if _grabber is not None:
        _grabber.clear()
    _grabber = None
