# =============================================================================
# AWBotNest 插件：小菜抽奖（auto_lottery）
#
# 自动识别小菜抽奖机器人发起的抽奖消息，按配置（监听群 / 时间窗 / 奖品关键词 /
# 陷阱检测）自动参与；开奖时检测中奖、记录中奖者并可自动或手动发奖。
#
# 迁移自 AWLottery（配置项严格对照原项目真实键，不臆造、不漏项）：
#   - plugins/user/auto_lottery_for_xiaocai.py（自动抽奖主逻辑 + 全局 lottery_list）
#   - plugins/user/lottery/_lottery_helpers.py（解析 / 匹配 / 陷阱检测 / 时间段）
#   - plugins/user/auto_prize_sender.py（中奖记录 / 发奖）
#   - bot 配置 UI：auto_lottery_set(AUTO_LOTTERY) / lottery_wait_time_set
#     (LOTTERY_WAIT_TIME) / lottery_prize_set(LOTTERY_PRIZE) /
#     lottery_group_wait_time（按群等待）
#   - config.config 常量：LOTTERY_TARGET_GROUP / PRIZE_LIST / PRIZE_MATCH_RULES /
#     TRAP_LOTTERY_DETECTION
#
# 平台适配决策：
#   1. 三个用户插件 + helpers 合并为本文件夹插件，全局 lottery_list 收敛到 _state.py。
#   2. 不依赖 PrizeService / DB：待发奖记录走 ctx.kv（_prize.py）。
#   3. 原 get_transform_groups() 跨插件 import transfer 站点 TARGET 来决定中奖后是否
#      回复用户名 —— 本平台禁止跨插件 import，改为自带 config 字段 `transfer_groups`。
#   4. 原通知发到 PT_GROUP_ID['BOT_MESSAGE_CHAT'] → 改用 ctx.notify（notify_owner 开关）。
#   5. 原贴纸 LOTTERY_Sticker_REPLY_MESSAGE（thank1-5/heimu1-2）平台无此配置，改为
#      thank_texts / heimu_texts 多行文字随机选一条。
#   6. MY_TGID→ctx.owner_id；后台 task 登记并在 teardown cancel。
#
# scope=user：用你的用户账号监听群消息并参与抽奖、发关键词 / 发奖，请仅监听可信抽奖群。
# =============================================================================
from __future__ import annotations

import asyncio
import re
from random import randint, random

from ._helpers import (
    parse_groups, parse_keywords, parse_group_wait_overrides, to_int,
    parse_time_ranges, is_within_time_ranges, has_markdown_format,
    parse_new_lottery, parse_prize_list, match_prize_group, is_trap_lottery,
)
from . import _state
from ._prize import PrizeStore, record_draw_result, send_prizes

__plugin__ = {
    "name": "小菜抽奖",
    "id": "auto_lottery",
    "version": "1.0.5",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "自动识别小菜抽奖机器人的抽奖消息并参与，中奖记录与可选自动发奖。",
    "config_schema": {
        # ═══════════ 自动抽奖（AUTO_LOTTERY section）═══════════
        "auto_lottery_enabled": {
            "type": "boolean", "default": False, "label": "自动抽奖总开关",
            "section": "自动抽奖",
            "help": "控制是否自动参与符合条件的抽奖。关闭后不参与任何抽奖"
                    "（仍会按发奖开关记录开奖以便发奖）。",
        },
        "lottery_bot_id": {
            "type": "string", "default": "6461022460", "label": "小菜抽奖机器人ID",
            "section": "自动抽奖", "show_if": {"auto_lottery_enabled": True},
            "help": "发起抽奖的小菜抽奖机器人用户ID（原 choujiang_bot 过滤器固定为 6461022460）。",
        },
        "auto_lottery_username": {
            "type": "string", "default": "", "label": "PT用户名",
            "section": "自动抽奖", "show_if": {"auto_lottery_enabled": True},
            "help": "示例: AWdress。中奖后在无转账功能的群里回复用户名时使用"
                    "（需开启「中奖回复用户名开关」）。",
        },
        "auto_lottery_time": {
            "type": "string", "default": "", "label": "抽奖时间段",
            "section": "自动抽奖", "show_if": {"auto_lottery_enabled": True},
            "help": "格式 08:00-11:00,13:00-17:00,20:00-23:00（24小时制，多段逗号分隔）。"
                    "留空=全天。",
        },
        # 抽奖群组（LOTTERY_TARGET_GROUP 常量 + custom_lottery_groups 配置，合并去重）
        "lottery_target_groups": {
            "type": "text", "default": "", "label": "预定义抽奖群组",
            "section": "自动抽奖", "show_if": {"auto_lottery_enabled": True},
            "help": "逗号或换行分隔的群组ID（对应原 LOTTERY_TARGET_GROUP）。"
                    "只在这些群里参与抽奖。",
        },
        "custom_lottery_groups": {
            "type": "text", "default": "", "label": "自定义抽奖群组",
            "section": "自动抽奖", "show_if": {"auto_lottery_enabled": True},
            "help": "逗号或换行分隔的群组ID（对应原 custom_lottery_groups）。"
                    "与预定义抽奖群组合并去重后生效。两者都留空=不参与任何群。",
        },
        # ═══════════ 参与方式 ═══════════
        "lottery_forward_enabled": {
            "type": "boolean", "default": False, "label": "转发原始抽奖消息参与",
            "section": "参与方式", "show_if": {"auto_lottery_enabled": True},
            "help": "开启：转发原始抽奖消息参与；关闭：普通文本直接发送关键词。\n"
                    "含 @、/ 等特殊格式的关键词无论开关都会转发原消息。",
        },
        "lottery_forward_first_participant": {
            "type": "boolean", "default": False, "label": "转发第一个参与者",
            "section": "参与方式", "show_if": {"auto_lottery_enabled": True},
            "help": "开启：等待并转发第一个参与者的消息参与（最多等30秒，超时降级）。\n"
                    "优先级：特殊格式(@、/)→转发原消息 > 本开关 > 转发原消息开关 > 直接发文本。",
        },
        # ═══════════ 奖品匹配（LOTTERY_PRIZE section + PRIZE_LIST + PRIZE_MATCH_RULES）═══════════
        "prize_list": {
            "type": "text", "default": "", "label": "奖品列表",
            "section": "奖品匹配", "show_if": {"auto_lottery_enabled": True},
            "help": "每行 `群组ID|奖品1,奖品2,...`（对应原 PRIZE_LIST，每群组要参与的奖品名）。\n"
                    "例：\n-1001234567890|魔力,积分\n-1001234567891|金币,币,GB,邀请\n"
                    "抽奖奖品文本包含某群任一关键词即视为符合。",
        },
        "universal_prize_match": {
            "type": "boolean", "default": False, "label": "通用奖品匹配",
            "section": "奖品匹配", "show_if": {"auto_lottery_enabled": True},
            "help": "开启（通用模式）：所有群组共用全部奖品关键词，任一群的关键词都能匹配。\n"
                    "关闭（精确模式）：只匹配当前群组配置的奖品。建议关闭（精确模式）。",
        },
        "prize_case_sensitive": {
            "type": "boolean", "default": False, "label": "奖品关键词区分大小写",
            "section": "奖品匹配", "show_if": {"auto_lottery_enabled": True},
            "help": "对应 PRIZE_MATCH_RULES.case_sensitive。",
        },
        # ═══════════ 陷阱检测（TRAP_LOTTERY_DETECTION 常量展开）═══════════
        "trap_enabled": {
            "type": "boolean", "default": True, "label": "启用陷阱抽奖检测",
            "section": "陷阱检测", "show_if": {"auto_lottery_enabled": True},
            "help": "陷阱检测总开关。命中任一陷阱特征则跳过参与。",
        },
        "trap_case_sensitive": {
            "type": "boolean", "default": False, "label": "陷阱关键词区分大小写",
            "section": "陷阱检测", "show_if": {"trap_enabled": True},
            "help": "对应 TRAP_LOTTERY_DETECTION.case_sensitive。",
        },
        "trap_enable_prize_pattern_check": {
            "type": "boolean", "default": True, "label": "启用关键词检测",
            "section": "陷阱检测", "show_if": {"trap_enabled": True},
            "help": "检测奖品名/参与关键词/简介是否命中可疑关键词。",
        },
        "trap_enable_creator_blacklist": {
            "type": "boolean", "default": True, "label": "启用创建者黑名单",
            "section": "陷阱检测", "show_if": {"trap_enabled": True},
            "help": "命中黑名单创建者的抽奖一律跳过。",
        },
        "trap_enable_participant_check": {
            "type": "boolean", "default": True, "label": "启用参与人数检测",
            "section": "陷阱检测", "show_if": {"trap_enabled": True},
            "help": "单人抽奖(中奖概率 x/1) 或参与人数过少视为陷阱。",
        },
        "trap_max_participants": {
            "type": "number", "default": 1, "label": "最大参与人数阈值",
            "min": 1, "max": 1000, "section": "陷阱检测",
            "show_if": {"trap_enable_participant_check": True},
            "help": "对应 TRAP_LOTTERY_DETECTION.max_participants。参与人数 <= 此值视为陷阱"
                    "（=1 时即只拦截单人抽奖）。",
        },
        "trap_blacklist_creator_ids": {
            "type": "text", "default": "", "label": "创建者黑名单",
            "section": "陷阱检测", "show_if": {"trap_enable_creator_blacklist": True},
            "help": "逗号或换行分隔的创建者用户ID（对应 blacklist_creator_ids）。",
        },
        "trap_suspicious_keywords": {
            "type": "text",
            "default": "脚本,挂机,机器人,外挂,bot,自动,作弊,刷,假人,封禁,封,禁,ban,封号,"
                       "script,auto,cheat,hack,fake,test,腳本,掛機,機器人,外掛,自動,封號",
            "label": "可疑关键词", "section": "陷阱检测",
            "show_if": {"trap_enable_prize_pattern_check": True},
            "help": "逗号或换行分隔（对应 suspicious_keywords）。"
                    "仅 奖品名/参与词/简介 命中任一则判为陷阱。",
        },
        # ═══════════ 抽奖等待时间（LOTTERY_WAIT_TIME section）═══════════
        "lottery_wait_enabled": {
            "type": "boolean", "default": False, "label": "抽奖等待时间总开关",
            "section": "等待时间", "show_if": {"auto_lottery_enabled": True},
            "help": "启用/禁用抽奖相关的所有等待时间。关闭后参与抽奖立即执行。",
        },
        "lottery_participate_wait_min": {
            "type": "number", "default": 25, "label": "参与前等待(最小秒)",
            "min": 0, "max": 300, "section": "等待时间",
            "show_if": {"lottery_wait_enabled": True},
            "help": "参与抽奖前的最小等待时间（秒），范围 0-300。0=立即参与。",
        },
        "lottery_participate_wait_max": {
            "type": "number", "default": 65, "label": "参与前等待(最大秒)",
            "min": 0, "max": 300, "section": "等待时间",
            "show_if": {"lottery_wait_enabled": True},
            "help": "参与抽奖前的最大等待时间（秒），范围 0-300。",
        },
        "lottery_thank_wait_min": {
            "type": "number", "default": 10, "label": "感谢消息等待(最小秒)",
            "min": 0, "max": 120, "section": "等待时间",
            "show_if": {"lottery_wait_enabled": True},
            "help": "中奖后发感谢消息的最小等待时间（秒），范围 0-120。",
        },
        "lottery_thank_wait_max": {
            "type": "number", "default": 45, "label": "感谢消息等待(最大秒)",
            "min": 0, "max": 120, "section": "等待时间",
            "show_if": {"lottery_wait_enabled": True},
        },
        "lottery_heimu_wait_min": {
            "type": "number", "default": 20, "label": "黑幕消息等待(最小秒)",
            "min": 0, "max": 120, "section": "等待时间",
            "show_if": {"lottery_wait_enabled": True},
            "help": "未中奖发黑幕消息的最小等待时间（秒），范围 0-120。",
        },
        "lottery_heimu_wait_max": {
            "type": "number", "default": 40, "label": "黑幕消息等待(最大秒)",
            "min": 0, "max": 120, "section": "等待时间",
            "show_if": {"lottery_wait_enabled": True},
        },
        "lottery_negative_wait_min": {
            "type": "number", "default": 10, "label": "负面回复等待(最小秒)",
            "min": 0, "max": 120, "section": "等待时间",
            "show_if": {"lottery_wait_enabled": True},
            "help": "发送负面回复的最小等待时间（秒），范围 0-120。",
        },
        "lottery_negative_wait_max": {
            "type": "number", "default": 60, "label": "负面回复等待(最大秒)",
            "min": 0, "max": 120, "section": "等待时间",
            "show_if": {"lottery_wait_enabled": True},
        },
        "group_wait_overrides": {
            "type": "text", "default": "", "label": "按群组专属参与等待",
            "section": "等待时间", "show_if": {"lottery_wait_enabled": True},
            "help": "每行 `群组ID|最小秒|最大秒`，覆盖该群的全局参与前等待。\n"
                    "例：-1001234567890|30|90",
        },
        # ═══════════ 中奖回应（LOTTERY_WAIT_TIME 开关 + AUTO_LOTTERY.username_reply_switch）═══════════
        "lottery_thank_message": {
            "type": "boolean", "default": False, "label": "中奖后发感谢消息",
            "section": "中奖回应", "show_if": {"auto_lottery_enabled": True},
            "help": "中奖后随机发一句感谢创建者的话。",
        },
        "thank_texts": {
            "type": "text", "default": "感谢{boss}大佬\n{boss}爷，谢谢\n感谢老板，小弟在这",
            "label": "感谢文案", "section": "中奖回应",
            "show_if": {"lottery_thank_message": True},
            "help": "每行一条，随机选一条（替代原贴纸 thank1-5）。{boss} 替换为创建者名字。",
        },
        "username_reply_switch": {
            "type": "boolean", "default": False, "label": "中奖回复用户名开关",
            "section": "中奖回应", "show_if": {"auto_lottery_enabled": True},
            "help": "在无转账功能的群里中奖后回复自己的 PT 用户名（需填上方 PT用户名）。\n"
                    "有转账功能的群组（见下）会自动跳过。",
        },
        "transfer_groups": {
            "type": "text", "default": "", "label": "转账群组ID（免回用户名）",
            "section": "中奖回应", "show_if": {"username_reply_switch": True},
            "help": "逗号或换行分隔。这些群有转账功能、无需回复 PT 用户名"
                    "（替代原 get_transform_groups 的跨插件依赖）。",
        },
        "lottery_heimu_message": {
            "type": "boolean", "default": False, "label": "未中奖发黑幕消息",
            "section": "中奖回应", "show_if": {"auto_lottery_enabled": True},
            "help": "自己参与但没中奖时，随机发一句黑幕。",
        },
        "heimu_texts": {
            "type": "text", "default": "黑幕\n这也能不中\n下次一定",
            "label": "黑幕文案", "section": "中奖回应",
            "show_if": {"lottery_heimu_message": True},
            "help": "每行一条，随机选一条（替代原贴纸 heimu1-2 + LOTTERY_LOSE_REPLY_MESSAGE）。",
        },
        # ═══════════ 负面回复（被质疑是机器人）═══════════
        "lose_reply_switch": {
            "type": "boolean", "default": False, "label": "负面回复开关",
            "section": "负面回复", "show_if": {"auto_lottery_enabled": True},
            "help": "有人回复你的消息说「机器人/脚本/不是真人」等时，随机反驳一句"
                    "（对应原 lose_reply_switch + NO_AOUTOLOTTERY_REPLY_MESSAGE）。",
        },
        "negative_texts": {
            "type": "text", "default": "怎么可能啊\n别开玩笑啊\n啊绝对不是\n我是真的\n不要黑我\n？",
            "label": "反驳文案", "section": "负面回复",
            "show_if": {"lose_reply_switch": True},
            "help": "每行一条，随机选一条。",
        },
        # ═══════════ 自动发奖（AUTO_LOTTERY section）═══════════
        "auto_prize_enabled": {
            "type": "boolean", "default": False, "label": "自动发奖功能总开关",
            "section": "自动发奖",
            "help": "开启后才会记录自己发起的抽奖的中奖者并发奖。关闭后不记录任何中奖信息。",
        },
        "manual_prize_mode": {
            "type": "boolean", "default": False, "label": "手动发奖模式",
            "section": "自动发奖", "show_if": {"auto_prize_enabled": True},
            "help": "开启：只记录中奖者，等你用 .sendprize 命令发奖；关闭：开奖后立即自动发奖。\n"
                    "命令：.sendprize <ID> / .listprize / .clearprize。",
        },
        "prize_send_interval_enabled": {
            "type": "boolean", "default": True, "label": "发奖间隔开关",
            "section": "自动发奖", "show_if": {"auto_prize_enabled": True},
            "help": "开启：每次发奖后随机等待；关闭：秒发。建议开启避免被检测。",
        },
        "prize_send_interval_min": {
            "type": "number", "default": 2, "label": "发奖间隔(最小秒)",
            "min": 0, "max": 60, "section": "自动发奖",
            "show_if": {"prize_send_interval_enabled": True},
            "help": "每次发奖之间的最小等待时间（秒），范围 0-60。",
        },
        "prize_send_interval_max": {
            "type": "number", "default": 5, "label": "发奖间隔(最大秒)",
            "min": 0, "max": 60, "section": "自动发奖",
            "show_if": {"prize_send_interval_enabled": True},
            "help": "每次发奖之间的最大等待时间（秒），范围 0-60。",
        },
        "prize_send_blacklist": {
            "type": "text", "default": "", "label": "发奖黑名单",
            "section": "自动发奖", "show_if": {"auto_prize_enabled": True},
            "help": "逗号或换行分隔的用户ID（对应原发奖黑名单），这些中奖者不给发奖。",
        },
        # ═══════════ 通知 ═══════════
        "notify_owner": {
            "type": "boolean", "default": True, "label": "关键事件通知我",
            "section": "通知",
            "help": "参与成功/中奖/发奖完成时用机器人通知平台主人"
                    "（替代原发到 PT_GROUP_ID['BOT_MESSAGE_CHAT']）。",
        },
        "notify_skips": {
            "type": "boolean", "default": False, "label": "通知跳过原因",
            "section": "通知", "show_if": {"notify_owner": True},
            "help": "奖品不符/陷阱/不在时间段等跳过时也通知（较吵，默认关）。",
        },
    },
}

# 待发奖存储（setup 时用 ctx.kv 实例化）
_store: PrizeStore | None = None
# 后台 task 集合（teardown 时取消）
_tasks: set = set()


def _spawn(coro) -> None:
    """登记一个后台 task，完成后自动从集合移除；teardown 时统一 cancel。"""
    t = asyncio.ensure_future(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def _int_cfg(cfg, key, default):
    return to_int(cfg.get(key, default), default)


def _lines(raw) -> list[str]:
    """按行解析文案（只按换行分隔，保留行内逗号），空行忽略。"""
    if not raw:
        return []
    return [ln.strip() for ln in str(raw).splitlines() if ln.strip()]


def _all_lottery_groups(cfg) -> list[int]:
    """合并预定义抽奖群组 + 自定义抽奖群组，去重。"""
    groups = set(parse_groups(cfg.get("lottery_target_groups", "")))
    groups.update(parse_groups(cfg.get("custom_lottery_groups", "")))
    return list(groups)


async def setup(ctx):
    global _store
    _store = PrizeStore(ctx.kv)

    def _my_id(client):
        me = getattr(client, "me", None)
        return str(me.id) if me else ""

    async def _maybe_notify(text, level, client, *, skip=False):
        if not ctx.config.get("notify_owner", True):
            return
        if skip and not ctx.config.get("notify_skips", False):
            return
        try:
            await ctx.notify(text, level=level, category="小菜抽奖", account=client)
        except Exception:  # noqa: BLE001
            pass

    # ============================================================
    # 1. 新抽奖监听 → 参与
    # ============================================================
    @ctx.on_message(ctx.filters.text, group=6)
    async def on_new_lottery(client, message):
        cfg = ctx.config
        text = message.text or ""
        if "新的抽奖已经创建" not in text or "参与关键词" not in text:
            return
        # 来源机器人校验（小菜抽奖 bot）
        bot_id = _int_cfg(cfg, "lottery_bot_id", 6461022460)
        fu = message.from_user
        if not (fu and fu.is_bot and fu.id == bot_id):
            return
        # 群组校验（预定义 + 自定义，合并去重）
        groups = _all_lottery_groups(cfg)
        if message.chat.id not in groups:
            return

        _state.prune_stale(ctx.log)
        info = parse_new_lottery(text, message.entities)
        lottery_id = info.get("ID", "")
        if not lottery_id or not info.get("keyword"):
            return

        # ── 陷阱检测 ──
        if cfg.get("trap_enabled", True):
            is_trap, reason = is_trap_lottery(
                text, info,
                suspicious_keywords=parse_keywords(cfg.get("trap_suspicious_keywords", "")),
                blacklist_creator_ids=parse_keywords(cfg.get("trap_blacklist_creator_ids", "")),
                enable_prize_pattern_check=cfg.get("trap_enable_prize_pattern_check", True),
                enable_creator_blacklist=cfg.get("trap_enable_creator_blacklist", True),
                enable_participant_check=cfg.get("trap_enable_participant_check", True),
                max_participants=_int_cfg(cfg, "trap_max_participants", 1),
                case_sensitive=cfg.get("trap_case_sensitive", False),
            )
            if is_trap:
                ctx.log.warning("跳过陷阱抽奖 %s: %s", lottery_id, reason)
                await _maybe_notify(
                    f"跳过陷阱抽奖\n\n{lottery_id}\n\n{info.get('prize','')}\n\n"
                    f"{reason}\n\n{message.link}",
                    "warning", client, skip=True)
                return

        # ── 总开关 ──
        if not cfg.get("auto_lottery_enabled", False):
            await _maybe_notify(
                f"自动抽奖未开启，跳过\n\n{lottery_id}\n\n{message.link}",
                "info", client, skip=True)
            return

        # ── 时间窗 ──
        if not is_within_time_ranges(parse_time_ranges(cfg.get("auto_lottery_time", ""))):
            await _maybe_notify(
                f"不在抽奖时间段，跳过\n\n{lottery_id}\n\n{message.link}",
                "info", client, skip=True)
            return

        # ── 奖品匹配（PRIZE_LIST + 通用匹配开关）──
        prize_map = parse_prize_list(cfg.get("prize_list", ""))
        matched_group = match_prize_group(
            info.get("prize", ""), prize_map, message.chat.id,
            universal=cfg.get("universal_prize_match", False),
            case_sensitive=cfg.get("prize_case_sensitive", False))
        if matched_group is None:
            await _maybe_notify(
                f"奖品不符合，跳过\n\n{lottery_id}\n\n{info.get('prize','')}\n\n"
                f"{message.link}", "info", client, skip=True)
            return

        # ── 登记并参与 ──
        _state.register(lottery_id, {
            'keyword': info['keyword'],
            'boss_name': info['boss_name'],
            'boss_ID': info['boss_ID'],
            'prize': info.get('prize', ''),
            'ptsite': matched_group,
            'prizechat': message.chat.id,
            'flag': 0,
            'original_message': message,
        })
        ctx.log.info("符合条件，准备参与抽奖 %s", lottery_id)
        _spawn(_participate(client, message, lottery_id, info))

    async def _participate(client, message, lottery_id, info):
        cfg = ctx.config
        # 等待时间（总开关 + 群组专属覆盖全局）
        if cfg.get("lottery_wait_enabled", False):
            overrides = parse_group_wait_overrides(cfg.get("group_wait_overrides", ""))
            if message.chat.id in overrides:
                wmin, wmax = overrides[message.chat.id]
            else:
                wmin = _int_cfg(cfg, "lottery_participate_wait_min", 25)
                wmax = _int_cfg(cfg, "lottery_participate_wait_max", 65)
            if wmin > wmax:
                wmin, wmax = wmax, wmin
            wait_time = randint(wmin, wmax)
            ctx.log.debug("抽奖 %s 等待 %ss 后参与", lottery_id, wait_time)
            await asyncio.sleep(wait_time)
        else:
            ctx.log.debug("抽奖等待时间已关闭，立即参与 %s", lottery_id)

        if lottery_id not in _state.lottery_list:
            ctx.log.info("抽奖 %s 在等待期间已结束", lottery_id)
            await _maybe_notify(
                f"抽奖已结束（等待期内）\n\n{lottery_id}\n\n{message.link}",
                "info", client, skip=True)
            return

        entry = _state.lottery_list[lottery_id]
        keyword = entry['keyword']
        original_message = entry.get('original_message')
        forward_original = cfg.get("lottery_forward_enabled", False)
        forward_first = cfg.get("lottery_forward_first_participant", False)

        # 决定参与方式（优先级：特殊格式 > 转发第一参与者 > 转发原消息 > 直接发文本）
        try:
            if has_markdown_format(keyword):
                if original_message:
                    await original_message.forward(message.chat.id)
                else:
                    await client.send_message(message.chat.id, keyword, parse_mode=None)
            elif forward_first:
                await _participate_via_first(client, message, lottery_id, keyword, original_message)
            elif forward_original:
                if original_message:
                    await original_message.forward(message.chat.id)
                else:
                    await client.send_message(message.chat.id, keyword, parse_mode=None)
            else:
                await client.send_message(message.chat.id, keyword, parse_mode=None)

            if lottery_id in _state.lottery_list:
                _state.lottery_list[lottery_id]['flag'] = 1
            ctx.log.info("抽奖参与成功 %s", lottery_id)
            await _maybe_notify(
                f"抽奖参与成功\n\n{lottery_id}\n\n{message.chat.title}\n\n"
                f"{info.get('prize','')}\n\n{keyword}\n\n{message.link}",
                "success", client)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("发送抽奖消息失败 %s: %r", lottery_id, e)
            await _maybe_notify(
                f"抽奖参与失败\n\n{lottery_id}\n\n{keyword}\n\n{e}",
                "error", client)

    async def _participate_via_first(client, message, lottery_id, keyword, original_message):
        """转发第一个参与者：标记等待，最多等30秒，超时降级。"""
        entry = _state.lottery_list.get(lottery_id)
        if not entry:
            return
        existing = entry.get('first_participant_message')
        if existing:
            await existing.forward(message.chat.id)
            return
        entry['waiting_for_first_participant'] = True
        entry['target_chat_id'] = message.chat.id
        loop = asyncio.get_event_loop()
        start = loop.time()
        while loop.time() - start < 30:
            await asyncio.sleep(1)
            if lottery_id not in _state.lottery_list:
                return
            fpm = _state.lottery_list[lottery_id].get('first_participant_message')
            if fpm:
                await fpm.forward(message.chat.id)
                _state.lottery_list[lottery_id]['waiting_for_first_participant'] = False
                return
        # 超时降级
        if lottery_id in _state.lottery_list:
            _state.lottery_list[lottery_id]['waiting_for_first_participant'] = False
        if has_markdown_format(keyword) and original_message:
            await original_message.forward(message.chat.id)
        else:
            await client.send_message(message.chat.id, keyword, parse_mode=None)

    # ============================================================
    # 2. 捕获第一个参与者（仅当有抽奖在等待时才生效）
    # ============================================================
    @ctx.on_message(~ctx.filters.bot & ~ctx.filters.me & ctx.filters.text, group=7)
    async def on_capture_first(client, message):
        try:
            waiting = [(lid, d) for lid, d in _state.lottery_list.items()
                       if d.get('waiting_for_first_participant')
                       and not d.get('first_participant_message')]
            if not waiting:
                return
            for lottery_id, data in waiting:
                keyword = data.get('keyword', '')
                target_chat_id = data.get('target_chat_id')
                keyword_clean = keyword.replace('**', '').replace('__', '').replace('`', '')
                if not keyword or keyword_clean not in (message.text or ""):
                    continue
                if target_chat_id and message.chat.id != target_chat_id:
                    continue
                _state.lottery_list[lottery_id]['first_participant_message'] = message
                ctx.log.info("捕获第一个参与者: 抽奖 %s", lottery_id)
                break
        except Exception as e:  # noqa: BLE001
            ctx.log.error("捕获第一个参与者失败: %r", e)

    # ============================================================
    # 3. 开奖结果：中奖回应 + 发奖记录
    # ============================================================
    @ctx.on_message(ctx.filters.text, group=8)
    async def on_draw_result(client, message):
        cfg = ctx.config
        text = message.text or ""
        is_auto = text.startswith("参与人数够啦！！开奖")
        is_manual = text.startswith("手动开奖啦！！")
        if not (is_auto or is_manual):
            return
        bot_id = _int_cfg(cfg, "lottery_bot_id", 6461022460)
        fu = message.from_user
        if not (fu and fu.is_bot and fu.id == bot_id):
            return
        # 群组过滤只作用于「中奖社交回应」（感谢/黑幕/回用户名）——你只在自动参与的群里
        # 发这些社交消息，对齐原项目 lottery_draw_result 的 all_groups 过滤。
        # 发奖不受此限制：发奖是给「自己发起的抽奖」的中奖者发，与在哪些群自动参与无关，
        # 原项目 record_lottery_result 本就没有群组过滤。迁移时把两者合并到一个 handler
        # 并在开头统一过滤，导致没把开奖群配进「自动参与群组」时发奖完全不触发。
        in_lottery_group = message.chat.id in _all_lottery_groups(cfg)

        # ── 中奖社交回应（仅自动开奖消息含中奖信息块，且在自动参与群组内）──
        if is_auto and in_lottery_group:
            await _handle_win_reactions(client, message)

        # ── 发奖记录 / 发放（不限群组，对齐原项目 record_lottery_result）──
        if cfg.get("auto_prize_enabled", False):
            _spawn(_handle_prize(client, message, "手动开奖" if is_manual else "自动开奖"))

    async def _handle_win_reactions(client, message):
        cfg = ctx.config
        text = message.text or ""
        m = re.search(r"抽奖 ID：(.+)", text)
        finish_key = m.group(1) if m else ""
        winner_m = re.search(r"中奖信息\n([\s\S]+)", text)
        winner_block = winner_m.group(1) if winner_m else ""
        my_id = _my_id(client)
        wait_on = cfg.get("lottery_wait_enabled", False)

        entry = _state.lottery_list.get(finish_key)
        # 只对「不是自己发起」的抽奖发社交消息
        if entry and str(my_id) != str(entry.get('boss_ID')):
            boss_name = entry.get('boss_name', '')
            transfer_groups = parse_groups(cfg.get("transfer_groups", ""))
            if my_id and my_id in winner_block:
                # 自己中奖
                if wait_on:
                    await asyncio.sleep(randint(
                        _int_cfg(cfg, "lottery_thank_wait_min", 10),
                        _int_cfg(cfg, "lottery_thank_wait_max", 45)))
                # 感谢消息
                if cfg.get("lottery_thank_message", False):
                    texts = _lines(cfg.get("thank_texts", ""))
                    if texts:
                        line = texts[randint(0, len(texts) - 1)].replace("{boss}", boss_name)
                        try:
                            await client.send_message(message.chat.id, line)
                        except Exception:  # noqa: BLE001
                            pass
                # 回复用户名（有转账功能的群跳过）
                if cfg.get("username_reply_switch", False) and message.chat.id not in transfer_groups:
                    pt = cfg.get("auto_lottery_username", "")
                    if pt:
                        try:
                            await client.send_message(
                                message.chat.id, f"{boss_name}大佬，我的是: {pt}")
                        except Exception:  # noqa: BLE001
                            pass
            else:
                # 自己参与但没中奖 → 黑幕
                if entry.get('flag') == 1 and cfg.get("lottery_heimu_message", False):
                    if wait_on:
                        await asyncio.sleep(randint(
                            _int_cfg(cfg, "lottery_heimu_wait_min", 20),
                            _int_cfg(cfg, "lottery_heimu_wait_max", 40)))
                    if random() > 0.2:
                        texts = _lines(cfg.get("heimu_texts", ""))
                        if texts:
                            try:
                                await client.send_message(
                                    message.chat.id, texts[randint(0, len(texts) - 1)])
                            except Exception:  # noqa: BLE001
                                pass

        if finish_key:
            _state.remove(finish_key)

    async def _handle_prize(client, message, lottery_type):
        cfg = ctx.config
        my_id = _my_id(client)
        # 手动开奖时奖品名从 lottery_list 取
        stored_prize = ""
        m = re.search(r'抽奖 ID[：:]\s*([a-f0-9\-]+)', message.text or "")
        if m:
            entry = _state.lottery_list.get(m.group(1))
            if entry:
                stored_prize = entry.get('prize', '')
        try:
            record = await record_draw_result(message, lottery_type, _store, my_id, stored_prize)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("记录开奖信息失败: %r", e)
            return
        if not record:
            return
        lottery_id = record['lottery_id']
        winners = record['winners']
        ctx.log.info("记录待发奖 %s，%d 位中奖者", lottery_id, len(winners))

        if cfg.get("manual_prize_mode", False):
            await _maybe_notify(
                f"记录待发奖\n\n{lottery_id}\n\n{len(winners)} 人\n\n"
                f"{record['chat_title']}\n\n发奖: .sendprize {lottery_id[:8]}",
                "info", client)
            return

        # 自动发奖
        success, total, failed = await send_prizes(
            record, client, store=_store, log=ctx.log,
            interval_enabled=cfg.get("prize_send_interval_enabled", True),
            interval_min=_int_cfg(cfg, "prize_send_interval_min", 2),
            interval_max=_int_cfg(cfg, "prize_send_interval_max", 5),
            send_blacklist=set(parse_keywords(cfg.get("prize_send_blacklist", ""))),
        )
        if failed:
            detail = "\n".join(f"  {f['user_name']}({f['user_id']}): {f['reason']}" for f in failed)
            await _maybe_notify(
                f"发奖完成（部分失败）\n\n{lottery_id}\n\n成功 {success}/{total}\n\n"
                f"失败明细:\n\n{detail}", "warning", client)
        else:
            await _maybe_notify(
                f"发奖完成\n\n{lottery_id}\n\n成功 {success}/{total} 人",
                "success", client)

    # ============================================================
    # 4. 负面回复（被质疑是机器人）
    # ============================================================
    _negative_regex = ctx.filters.regex(
        r"机器人|真人？|脚本|自动抽奖|不是真人|脚本抽奖|机器人抽奖|这个也是")

    @ctx.on_message(ctx.filters.reply & ctx.filters.text & _negative_regex, group=9)
    async def on_negative_reply(client, message):
        cfg = ctx.config
        if not cfg.get("lose_reply_switch", False):
            return
        # 必须是回复自己的消息
        rtm = message.reply_to_message
        if not (rtm and rtm.from_user and rtm.from_user.is_self):
            return
        texts = _lines(cfg.get("negative_texts", ""))
        if not texts:
            return
        if cfg.get("lottery_wait_enabled", False):
            await asyncio.sleep(randint(
                _int_cfg(cfg, "lottery_negative_wait_min", 10),
                _int_cfg(cfg, "lottery_negative_wait_max", 60)))
        try:
            await message.reply(texts[randint(0, len(texts) - 1)])
        except Exception:  # noqa: BLE001
            pass

    # ============================================================
    # 5. 手动发奖命令（.sendprize / .listprize / .clearprize / .prizehelp）
    # ============================================================
    @ctx.on_message(
        ctx.filters.me & ctx.filters.text
        & (ctx.filters.command("sendprize") | ctx.filters.regex(r"^\.sendprize\b")),
        group=5)
    async def cmd_sendprize(client, message):
        cfg = ctx.config
        text = (message.text or "").strip()
        arg = ""
        for prefix in ("/sendprize", ".sendprize"):
            if text.startswith(prefix):
                arg = text[len(prefix):].strip()
                break
        if not arg:
            await message.reply("用法: .sendprize <抽奖ID前缀> 或 .sendprize all")
            return
        pending = _store.all()
        if arg.lower() == "all":
            matched = list(pending.values())
        else:
            matched = [r for lid, r in pending.items() if lid.startswith(arg)]
        if not matched:
            await message.reply(f"未找到匹配的待发奖（关键词 {arg}），当前待发奖 {len(pending)} 个")
            return
        total_success = total_winners = 0
        all_failed = []
        for record in matched:
            s, t, f = await send_prizes(
                record, client, store=_store, log=ctx.log,
                interval_enabled=cfg.get("prize_send_interval_enabled", True),
                interval_min=_int_cfg(cfg, "prize_send_interval_min", 2),
                interval_max=_int_cfg(cfg, "prize_send_interval_max", 5),
                send_blacklist=set(parse_keywords(cfg.get("prize_send_blacklist", ""))),
            )
            total_success += s
            total_winners += t
            all_failed.extend(f)
        msg = (f"发奖完成\n处理抽奖: {len(matched)} 个\n中奖: {total_winners} 人\n"
               f"成功: {total_success} 人\n剩余待发: {_store.count()} 个")
        if all_failed:
            msg += "\n失败:\n" + "\n".join(
                f"  {f['user_name']}({f['user_id']}): {f['reason']}" for f in all_failed)
        await message.reply(msg)

    @ctx.on_message(
        ctx.filters.me & ctx.filters.text
        & (ctx.filters.command("listprize") | ctx.filters.regex(r"^\.listprize\b")),
        group=5)
    async def cmd_listprize(client, message):
        pending = _store.all()
        if not pending:
            await message.reply("当前没有待发奖的抽奖")
            return
        lines = ["待发奖列表:"]
        for i, (lid, r) in enumerate(pending.items(), 1):
            lines.append(f"{i}. #{lid[:8]} | {len(r.get('winners', []))} 人 | "
                         f"{r.get('chat_title', '')}")
        lines.append(f"共 {len(pending)} 个。发奖: .sendprize <ID前缀> / .sendprize all")
        await message.reply("\n".join(lines))

    @ctx.on_message(
        ctx.filters.me & ctx.filters.text
        & (ctx.filters.command("clearprize") | ctx.filters.regex(r"^\.clearprize\b")),
        group=5)
    async def cmd_clearprize(client, message):
        n = _store.clear()
        await message.reply(f"已清空待发奖列表，共 {n} 个")

    @ctx.on_message(
        ctx.filters.me & ctx.filters.text
        & (ctx.filters.command("prizehelp") | ctx.filters.regex(r"^\.prizehelp\b")),
        group=5)
    async def cmd_prizehelp(client, message):
        await message.reply(
            "发奖命令:\n"
            ".sendprize <ID前缀>  发送指定抽奖的奖品\n"
            ".sendprize all       发送所有待发奖\n"
            ".listprize           查看待发奖列表\n"
            ".clearprize          清空待发奖列表\n"
            ".prizehelp           显示本帮助\n"
            f"当前待发奖: {_store.count()} 个")

    ctx.log.info("小菜抽奖插件已启用")


async def teardown(ctx):
    # 取消所有后台 task
    for t in list(_tasks):
        t.cancel()
    _tasks.clear()
    # 清空进程内抽奖状态
    _state.clear()
    ctx.log.info("小菜抽奖插件已停用")
