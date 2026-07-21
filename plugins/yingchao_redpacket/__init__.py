# =============================================================================
# AWBotNest 插件：影巢口令红包（yingchao_redpacket）—— 测试功能
#
# 监控指定发包人发的「口令红包」（图片/文档口令）并自动参与：
#   - OCR 开启且 ddddocr 可用：识别图片口令自动回复。
#   - OCR 关闭/不可用/识别失败：退回「等待复制」——他人口令被红包系统确认后，
#     复制该口令参与（更稳）。三层陷阱防护：命令前缀 / 注入字符 / 关键词库。
#
# 这是影巢的口令红包玩法，属测试功能，从「抢红包(red_packet)」插件拆出独立维护。
# 按钮红包(HDSKY)、癫影积分红包仍在 red_packet 插件，两者互不影响。
#
# 注意：本插件用「用户账号」监听并参与红包（scope=user）。它会以你的账号在群里
# 发送口令，请仅监控可信发包人。
# =============================================================================
from __future__ import annotations

from . import _ocr
from ._records import Records, parse_targets, parse_keywords, to_float
from ._snatch import TokenSnatcher, extract_text

__plugin__ = {
    "name": "影巢口令红包（测试）",
    "id": "yingchao_redpacket",
    "version": "1.0.2",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "影巢口令红包（测试功能）：监控指定发包人发的口令红包，OCR识别图片口令或复制他人口令参与，含陷阱防护。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/hdhive_lottery.jpg",
    "changelog": "v1.0.2 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "config_schema": {
        "token_enabled": {
            "type": "boolean", "default": False, "label": "启用口令红包监控",
            "section": "口令红包",
            "help": "监控指定发包人发的「口令红包」（图片/文档口令），OCR识别或复制他人口令参与。属影巢测试功能。",
        },
        "token_targets": {
            "type": "text", "default": "", "label": "监控发包人",
            "section": "口令红包", "show_if": {"token_enabled": True},
            "help": "一行一个，格式 `用户ID 备注` 或 `用户ID`。只抢这些人发的口令红包。",
        },
        "token_join_delay": {
            "type": "slider", "default": 0, "label": "参与延迟(秒)",
            "min": 0, "max": 60, "step": 1, "section": "口令红包",
            "show_if": {"token_enabled": True},
            "help": "识别/复制到口令后等待多少秒再发送，0=立即。",
        },
        "token_ocr_enabled": {
            "type": "boolean", "default": False, "label": "启用OCR识别图片口令",
            "section": "口令红包", "show_if": {"token_enabled": True},
            "help": "开启则用 ddddocr 识别图片口令自动参与（识别率较低，失败自动退回复制模式）；关闭则只复制他人已确认的口令（更稳）。需安装 ddddocr，未安装时自动降级为复制模式。",
        },
        "token_trap_detection": {
            "type": "boolean", "default": True, "label": "口令陷阱检测",
            "section": "口令红包", "show_if": {"token_enabled": True},
            "help": "发送口令前检查危险/可疑关键词。命令前缀与注入字符始终拦截，不受此开关影响。",
        },
        "token_trap_keywords": {
            "type": "text",
            "default": "脚本,挂,机器人,外挂,bot,自动,作弊,封禁,封号,ban,banned,封,禁,script,auto,cheat,hack,fake,test,block",
            "label": "陷阱关键词", "section": "口令红包",
            "show_if": {"token_enabled": True},
            "help": "逗号或换行分隔。口令命中其中任一关键词则拒绝发送。",
        },
        "notify_owner": {
            "type": "boolean", "default": True, "label": "抢包结果通知我",
            "section": "通用", "help": "抢到/拦截/失败时用机器人通知平台主人。",
        },
    },
}

# 口令红包状态机（setup 时创建）
_snatcher: TokenSnatcher | None = None


async def setup(ctx):
    global _snatcher
    records = Records(ctx.kv, ctx.log)
    _snatcher = TokenSnatcher(ctx, records)

    if not _ocr.ocr_available():
        ctx.log.info("[影巢口令] ddddocr 不可用，图片口令OCR将降级为「等待复制」模式")

    # ───────── 口令红包：监控目标发包人的图片/文档红包 ─────────
    @ctx.on_message(ctx.filters.group & (ctx.filters.photo | ctx.filters.document), group=-10)
    async def on_token_packet(client, message):
        cfg = ctx.config
        if not cfg.get("token_enabled", False):
            return
        targets = parse_targets(cfg.get("token_targets", ""))
        fu = message.from_user
        if not fu or fu.id not in targets:
            return
        if "口令红包" not in extract_text(message):
            return
        await _snatcher.handle_new_packet(
            client, message,
            sender_name=targets.get(fu.id, str(fu.id)),
            join_delay=to_float(cfg.get("token_join_delay", 0)),
            ocr_enabled=cfg.get("token_ocr_enabled", False),
            trap_enabled=cfg.get("token_trap_detection", True),
            custom_keywords=parse_keywords(cfg.get("token_trap_keywords", "")),
            notify=cfg.get("notify_owner", True),
        )

    # ───────── 口令红包：监控群内回复（缓存口令 / 失败 / 成功确认）─────────
    @ctx.on_message(ctx.filters.group & ctx.filters.reply, group=-10)
    async def on_token_reply(client, message):
        if not ctx.config.get("token_enabled", False):
            return
        await _snatcher.handle_reply(client, message, notify=ctx.config.get("notify_owner", True))

    ctx.log.info("[影巢口令] 已加载（OCR可用=%s）", _ocr.ocr_available())


async def teardown(ctx):
    global _snatcher
    _snatcher = None
