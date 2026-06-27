# =============================================================================
# AWBotNest 插件：发红包（red_packet_send）
#
# 用你的「用户账号」在群里发拼手气红包：
#   1. 你发命令 `创建红包 总额 个数 口令`（或回复贴图 `创建红包 总额 个数`）创建活动；
#   2. 群友发送与口令一致的消息（或相同贴图）参与；
#   3. 按拼手气随机分配，用 `+金额` reply 给每个参与者（群转账bot实际打款）；
#   4. 抢完或超时后自动结算公布；创建者可发 `结束红包` 提前结束、`红包状态` 查看进度。
#
# 迁移自 AWLottery plugins/user/games/red_packet.py（InstantRedPacketMonitor）的
# 发包侧。抢别人红包的功能已单独迁为 red_packet 插件，本插件不涉及。
#
# 不依赖平台 service / DB / libs.others：
#   - build_user_markdown_link → _activity.build_user_link
#   - is_user_in_send_blacklist → config 字段「屏蔽用户ID」（blacklist_ids）
# 活动状态为短时进程内内存；后台任务（超时结算、延迟删消息）登记集合，teardown 全 cancel。
# MY_TGID→ctx.owner_id，通知→ctx.notify。
#
# scope=user：靠你的账号发命令 + 收参与 + 发钱。
# =============================================================================
from __future__ import annotations

from ._activity import ActivityManager, cancel_all_tasks, is_create_command, to_int

__plugin__ = {
    "name": "发红包",
    "id": "red_packet_send",
    "version": "1.0.0",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "用你的账号在群里发拼手气红包：群友回复参与，按拼手气随机分配并自动发放魔力。",
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": True, "label": "启用发红包",
            "section": "总开关",
            "help": "关闭后不再响应发红包命令。",
        },

        # ───────── 命令 ─────────
        "create_word": {
            "type": "string", "default": "创建红包", "label": "创建命令词",
            "section": "命令",
            "help": "命令格式：`创建命令词 总额 个数 口令`，或回复贴图发 `创建命令词 总额 个数`。",
        },
        "status_word": {
            "type": "string", "default": "红包状态", "label": "查看状态命令词",
            "section": "命令",
            "help": "发送该命令词查看当前群红包活动进度。",
        },
        "end_word": {
            "type": "string", "default": "结束红包", "label": "结束命令词",
            "section": "命令",
            "help": "创建者发送该命令词可提前结束活动。",
        },

        # ───────── 限制 ─────────
        "max_amount": {
            "type": "number", "default": 10000, "label": "单次总额上限(魔力)",
            "min": 0, "max": 1000000, "step": 100, "section": "限制",
            "help": "创建红包时总额超过此值则拒绝。0 = 不限制。",
        },
        "max_count": {
            "type": "number", "default": 100, "label": "单次红包个数上限",
            "min": 0, "max": 1000, "step": 1, "section": "限制",
            "help": "创建红包时个数超过此值则拒绝。0 = 不限制。",
        },
        "activity_timeout_minutes": {
            "type": "slider", "default": 30, "label": "活动超时(分钟)",
            "min": 1, "max": 240, "step": 1, "section": "限制",
            "help": "活动创建后多久无人抢完则自动结算公布。",
        },
        "end_delete_delay": {
            "type": "slider", "default": 0, "label": "结束后删消息(秒)",
            "min": 0, "max": 600, "step": 5, "section": "限制",
            "help": "活动结束后延迟多少秒批量撤回红包相关消息。0 = 不删除。",
        },

        # ───────── 发放与文案 ─────────
        "transfer_prefix": {
            "type": "string", "default": "+", "label": "转账金额前缀",
            "section": "发放与文案",
            "help": "发放时发送的金额格式前缀，群转账bot据此打款。默认 `+`，即发送 `+100`。",
        },
        "congrats_text": {
            "type": "string", "default": "恭喜 {name} 抢到 {amount} 魔力！",
            "label": "祝贺文案", "section": "发放与文案",
            "help": "发放后的祝贺消息，可用 {name}（昵称）、{amount}（金额）占位。",
        },

        # ───────── 屏蔽 ─────────
        "blacklist_ids": {
            "type": "text", "default": "", "label": "屏蔽用户ID",
            "section": "屏蔽",
            "help": "这些用户参与时不计入、不发放。一行一个或逗号分隔的用户ID。",
        },
    },
}

# 活动管理器（setup 时创建）
_manager: ActivityManager | None = None


async def setup(ctx):
    global _manager
    _manager = ActivityManager(ctx)

    # ───────── 创建红包：你的账号发出命令（outgoing）─────────
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text & ctx.filters.group, group=-10)
    async def on_create(client, message):
        if not ctx.config.get("enabled", True):
            return
        create_word = ctx.config.get("create_word", "创建红包") or "创建红包"
        params = is_create_command(
            message.text,
            message.reply_to_message,
            create_word,
            to_int(ctx.config.get("max_amount", 10000), 10000),
            to_int(ctx.config.get("max_count", 100), 100),
        )
        if not params:
            return
        try:
            await _manager.create_redpacket(client, message, params)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[发红包] 创建活动失败: %r", e)

    # ───────── 查看状态 / 结束：你的账号发出命令（outgoing）─────────
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text & ctx.filters.group, group=-9)
    async def on_status_or_end(client, message):
        if not ctx.config.get("enabled", True):
            return
        text = (message.text or "").strip()
        status_word = ctx.config.get("status_word", "红包状态") or "红包状态"
        end_word = ctx.config.get("end_word", "结束红包") or "结束红包"
        try:
            if text == status_word:
                await _manager.get_activity_status(client, message.chat.id)
            elif text == end_word:
                await _manager.end_activity_by_user(client, message)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[发红包] 状态/结束命令失败: %r", e)

    # ───────── 群友参与：群内进来的消息（incoming：文本或贴图）─────────
    @ctx.on_message(
        ctx.filters.incoming & ctx.filters.group & (ctx.filters.text | ctx.filters.sticker),
        group=5,
    )
    async def on_participation(client, message):
        if not ctx.config.get("enabled", True):
            return
        try:
            await _manager.handle_participation(client, message)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[发红包] 处理参与失败: %r", e)

    ctx.log.info("[发红包] 已加载")


async def teardown(ctx):
    global _manager
    cancel_all_tasks()
    if _manager is not None:
        _manager.clear()
    _manager = None
