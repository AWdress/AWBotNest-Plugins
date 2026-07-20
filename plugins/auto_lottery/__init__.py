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
    "version": "1.0.8",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
    "description": "自动识别小菜抽奖机器人的抽奖消息并参与，中奖记录与可选自动发奖。自带 Vue 配置界面 + 待发奖管理。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/auto_lottery.jpg",
    "changelog": "v1.0.8 更新插件 Logo\n- 使用小菜抽奖专属图片作为插件卡片与市场图标",
}

# vue 模式无 config_schema：配置默认值集中此处备查（后端各处 ctx.config.get(k, 默认) 已带默认，
# 前端 Config.vue 用同一套默认初始化表单）。
DEFAULTS = {
    "auto_lottery_enabled": False, "lottery_bot_id": "6461022460", "auto_lottery_username": "",
    "auto_lottery_time": "", "lottery_target_groups": [], "custom_lottery_groups": [],
    "lottery_forward_enabled": False, "lottery_forward_first_participant": False,
    "prize_list": "", "universal_prize_match": False, "prize_case_sensitive": False,
    "trap_enabled": True, "trap_case_sensitive": False, "trap_enable_prize_pattern_check": True,
    "trap_enable_creator_blacklist": True, "trap_enable_participant_check": True,
    "trap_max_participants": 1, "trap_blacklist_creator_ids": "", "trap_suspicious_keywords": "",
    "lottery_wait_enabled": False, "lottery_participate_wait_min": 25, "lottery_participate_wait_max": 65,
    "lottery_thank_wait_min": 10, "lottery_thank_wait_max": 45,
    "lottery_heimu_wait_min": 20, "lottery_heimu_wait_max": 40,
    "lottery_negative_wait_min": 10, "lottery_negative_wait_max": 60, "group_wait_overrides": "",
    "lottery_thank_message": False, "thank_texts": "", "username_reply_switch": False, "transfer_groups": [],
    "lottery_heimu_message": False, "heimu_texts": "",
    "lose_reply_switch": False, "negative_texts": "",
    "auto_prize_enabled": False, "manual_prize_mode": False, "prize_send_interval_enabled": True,
    "prize_send_interval_min": 2, "prize_send_interval_max": 5, "prize_send_blacklist": "",
    "notify_owner": True, "notify_skips": False,
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

    # ============================================================
    # 6. 前端(Config.vue)用的后端接口
    # ============================================================
    def _fmt_ts(ts):
        try:
            from datetime import datetime
            return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
        except Exception:  # noqa: BLE001
            return ""

    @ctx.on_api("/dialogs", methods=["GET"])
    async def _api_dialogs(req):
        """列出账号的群/超级群，供前端群组选择器用。"""
        items = []
        seen = set()
        apps = list(getattr(ctx, "user_apps", None) or [])
        for client in apps:
            try:
                async for d in client.get_dialogs():
                    chat = getattr(d, "chat", None)
                    if not chat:
                        continue
                    t = str(getattr(chat, "type", "")).upper()
                    if "GROUP" not in t:  # GROUP / SUPERGROUP
                        continue
                    if chat.id in seen:
                        continue
                    seen.add(chat.id)
                    items.append({"id": chat.id, "title": getattr(chat, "title", "") or str(chat.id)})
                    if len(items) >= 500:
                        break
            except Exception as e:  # noqa: BLE001
                ctx.log.debug("[小菜抽奖] 拉取对话列表失败: %r", e)
        items.sort(key=lambda x: x["title"])
        return {"items": items}

    @ctx.on_api("/pending", methods=["GET"])
    async def _api_pending(req):
        items = []
        for lid, r in (_store.all() or {}).items():
            items.append({
                "lottery_id": lid,
                "winners": len(r.get("winners", [])),
                "chat_title": r.get("chat_title", ""),
                "prize": (r.get("winners") or [{}])[0].get("prize_name", "") if r.get("winners") else "",
                "time": _fmt_ts(r.get("timestamp")),
            })
        items.sort(key=lambda x: x["time"], reverse=True)
        return {"items": items, "count": len(items)}

    @ctx.on_api("/history", methods=["GET"])
    async def _api_prize_history(req):
        import json as _json
        raw = ctx.kv.get("prize_history", None)
        if isinstance(raw, str):
            try:
                raw = _json.loads(raw)
            except Exception:  # noqa: BLE001
                raw = []
        items = []
        for h in (raw if isinstance(raw, list) else []):
            items.append({
                "lottery_id": h.get("lottery_id", ""),
                "total": h.get("total", 0), "success": h.get("success", 0),
                "failed": h.get("failed", 0), "time": _fmt_ts(h.get("ts")),
            })
        items.reverse()  # 最近的在前
        return {"items": items}

    @ctx.on_api("/send", methods=["POST"])
    async def _api_send(req):
        # 发奖含随机间隔(每人可等数秒)，人多/全部发奖时整体耗时可能超过前端 HTTP 超时，
        # 故改后台任务：立即返回，结果走 ctx.notify 回报，前端稍后刷新「待发奖」即可。
        data = req.json or {}
        apps = list(getattr(ctx, "user_apps", None) or [])
        if not apps:
            return {"ok": False, "message": "没有可用的用户账号"}
        client = apps[0]
        cfg = ctx.config
        pending = _store.all() or {}
        if data.get("all"):
            records = list(pending.values())
        else:
            lid = data.get("lottery_id")
            rec = pending.get(lid)
            records = [rec] if rec else []
        if not records:
            return {"ok": False, "message": "未找到待发奖记录"}

        async def _bg_send(records):
            total_success = total_winners = 0
            all_failed = []
            for record in records:
                try:
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
                except Exception as e:  # noqa: BLE001
                    ctx.log.error("[小菜抽奖] 前端发奖失败: %r", e)
            msg = f"发奖完成：成功 {total_success}/{total_winners}，剩余待发 {_store.count()} 个"
            if all_failed:
                msg += "\n失败:\n" + "\n".join(
                    f"  {f['user_name']}({f['user_id']}): {f['reason']}" for f in all_failed[:10])
            if ctx.config.get("notify_owner", True):
                try:
                    await ctx.notify(msg, level="success" if not all_failed else "warning",
                                     category="小菜抽奖", account=client)
                except Exception:  # noqa: BLE001
                    pass

        _spawn(_bg_send(records))
        return {"ok": True, "started": True,
                "message": f"已在后台给 {len(records)} 个抽奖发奖，完成后推送通知，稍后刷新查看剩余待发。"}

    @ctx.on_api("/clear", methods=["POST"])
    async def _api_clear(req):
        n = _store.clear()
        return {"ok": True, "cleared": n}

    ctx.log.info("小菜抽奖插件已启用")


async def teardown(ctx):
    # 取消所有后台 task
    for t in list(_tasks):
        t.cancel()
    _tasks.clear()
    # 清空进程内抽奖状态
    _state.clear()
    ctx.log.info("小菜抽奖插件已停用")
