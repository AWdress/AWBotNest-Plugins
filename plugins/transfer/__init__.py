# =============================================================================
# AWBotNest 插件：多站点转账（transfer）
#
# 监听多个 PT 站群里的「转账 bot」消息，记录每笔转入/转出，按用户累计生成排行榜。
# 站点全部可配置（一行一个），用一个通用 handler 监听所有配置的群，按 chat_id 分派。
#
# 迁移自 AWLottery 的多站点转账 + 排行榜。规范：禁止 import pyrogram/core/config/...，
# 一切走 ctx。私有辅助见 _sites.py / _records.py / _leaderboard.py（包内 from . 导入）。
#
# 迁移决策：
#   1. 不依赖平台 transfer_service/DB —— 转账记录存 ctx.kv，排行榜在 Python 里聚合。
#   2. 不用转账 hook（那是给炸弹用的）—— 本插件自己监听各站点转账 bot。
#   3. 多站点合一：原来每站点一个文件，现在配置驱动，一个 handler 统管。
#   4. 排行榜默认输出文本；装了 imgkit+wkhtmltoimage 时可选出图。
#   5. wait_time → 通知前的随机延迟（notify_delay_min/max）。
#   6. MY_TGID → ctx.owner_id；通知走 ctx.notify。
#
# 解析差异（读完原项目 transform_*.py 确认）：
#   - audiences/hddolby/azusa/zm：同一回复链形态，仅金额正则不同 → parser=reply。
#   - springsunday/mock：回复链相同，但金额取「+金额」消息 → parser=plus。
#   - hdsky：实体解析 + outgoing 缓存，形态特殊 → parser=hdsky（专用分支）。
#   - ptvicomo：站点已关停，去除（原为 parser=reply）。
#   - u2dmhy：不是监听器（是带 cookie 的 HTTP 送礼命令），与「监听转账记录排行榜」
#     无关，不迁入本插件。
# =============================================================================

import asyncio
import random
import re

from ._sites import (
    build_active_sites, detect_direction, counterparty_message,
    plus_amount_message, extract_amount_from_text, extract_plus_amount,
    user_identity,
)
from ._records import RecordStore
from . import _leaderboard as lb

# 站点（群组ID/转账bot/货币/解析方式）全部内置写死在 _sites.py 的 _BUILTIN_SITES，
# 用户只通过下面 config_schema 的每站点开关决定是否监听/致谢/上榜。


__plugin__ = {
    "name": "多站点转账",
    "id": "transfer",
    "version": "1.0.10",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "监听多个PT站群的转账bot，记录转入/转出并生成排行榜。站点可配置。",
    "config_schema": {
        # —— 站点开关（群组ID/转账bot 全部内置写死，用户只开关功能）——
        # 每个站点 4 个开关：启用监听 / 群内致谢 / 致谢附转入榜 / 致谢附转出榜
        "site_audiences_enabled":   {"type": "boolean", "default": True,  "label": "Audiences 启用", "section": "Audiences"},
        "site_audiences_notify":    {"type": "boolean", "default": False, "label": "Audiences 群内致谢", "section": "Audiences", "show_if": {"site_audiences_enabled": True}},
        "site_audiences_lb_in":     {"type": "boolean", "default": False, "label": "Audiences 致谢附打赏榜(转入)", "section": "Audiences", "show_if": {"site_audiences_notify": True}},
        "site_audiences_lb_out":    {"type": "boolean", "default": False, "label": "Audiences 致谢附赏赐榜(转出)", "section": "Audiences", "show_if": {"site_audiences_notify": True}},

        "site_hddolby_enabled":     {"type": "boolean", "default": True,  "label": "HDDolby 启用", "section": "HDDolby"},
        "site_hddolby_notify":      {"type": "boolean", "default": False, "label": "HDDolby 群内致谢", "section": "HDDolby", "show_if": {"site_hddolby_enabled": True}},
        "site_hddolby_lb_in":       {"type": "boolean", "default": False, "label": "HDDolby 致谢附打赏榜(转入)", "section": "HDDolby", "show_if": {"site_hddolby_notify": True}},
        "site_hddolby_lb_out":      {"type": "boolean", "default": False, "label": "HDDolby 致谢附赏赐榜(转出)", "section": "HDDolby", "show_if": {"site_hddolby_notify": True}},

        "site_azusa_enabled":       {"type": "boolean", "default": True,  "label": "Azusa 启用", "section": "Azusa"},
        "site_azusa_notify":        {"type": "boolean", "default": False, "label": "Azusa 群内致谢", "section": "Azusa", "show_if": {"site_azusa_enabled": True}},
        "site_azusa_lb_in":         {"type": "boolean", "default": False, "label": "Azusa 致谢附打赏榜(转入)", "section": "Azusa", "show_if": {"site_azusa_notify": True}},
        "site_azusa_lb_out":        {"type": "boolean", "default": False, "label": "Azusa 致谢附赏赐榜(转出)", "section": "Azusa", "show_if": {"site_azusa_notify": True}},

        "site_zm_enabled":          {"type": "boolean", "default": True,  "label": "ZmPT 启用", "section": "ZmPT"},
        "site_zm_notify":           {"type": "boolean", "default": False, "label": "ZmPT 群内致谢", "section": "ZmPT", "show_if": {"site_zm_enabled": True}},
        "site_zm_lb_in":            {"type": "boolean", "default": False, "label": "ZmPT 致谢附打赏榜(转入)", "section": "ZmPT", "show_if": {"site_zm_notify": True}},
        "site_zm_lb_out":           {"type": "boolean", "default": False, "label": "ZmPT 致谢附赏赐榜(转出)", "section": "ZmPT", "show_if": {"site_zm_notify": True}},

        "site_springsunday_enabled":{"type": "boolean", "default": True,  "label": "SpringSunday 启用(含两个群)", "section": "SpringSunday"},
        "site_springsunday_notify": {"type": "boolean", "default": False, "label": "SpringSunday 群内致谢", "section": "SpringSunday", "show_if": {"site_springsunday_enabled": True}},
        "site_springsunday_lb_in":  {"type": "boolean", "default": False, "label": "SpringSunday 致谢附打赏榜(转入)", "section": "SpringSunday", "show_if": {"site_springsunday_notify": True}},
        "site_springsunday_lb_out": {"type": "boolean", "default": False, "label": "SpringSunday 致谢附赏赐榜(转出)", "section": "SpringSunday", "show_if": {"site_springsunday_notify": True}},

        "site_hdsky_enabled":       {"type": "boolean", "default": True,  "label": "HDSky 启用", "section": "HDSky"},
        "site_hdsky_notify":        {"type": "boolean", "default": False, "label": "HDSky 群内致谢", "section": "HDSky", "show_if": {"site_hdsky_enabled": True}},
        "site_hdsky_lb_in":         {"type": "boolean", "default": False, "label": "HDSky 致谢附打赏榜(转入)", "section": "HDSky", "show_if": {"site_hdsky_notify": True}},
        "site_hdsky_lb_out":        {"type": "boolean", "default": False, "label": "HDSky 致谢附赏赐榜(转出)", "section": "HDSky", "show_if": {"site_hdsky_notify": True}},

        "site_mocktest_enabled":    {"type": "boolean", "default": False, "label": "MockTest(测试) 启用", "section": "MockTest", "help": "测试站点，默认关闭。"},
        "site_mocktest_notify":     {"type": "boolean", "default": False, "label": "MockTest 群内致谢", "section": "MockTest", "show_if": {"site_mocktest_enabled": True}},
        "site_mocktest_lb_in":      {"type": "boolean", "default": False, "label": "MockTest 致谢附转入榜", "section": "MockTest", "show_if": {"site_mocktest_notify": True}},
        "site_mocktest_lb_out":     {"type": "boolean", "default": False, "label": "MockTest 致谢附转出榜", "section": "MockTest", "show_if": {"site_mocktest_notify": True}},

        # —— 致谢延迟 ——
        "notify_delay_min": {
            "type": "number", "default": 0, "label": "致谢延迟最小(秒)",
            "min": 0, "max": 300, "section": "致谢延迟",
            "help": "记录到转账后等待若干秒再发致谢，模拟人工。",
        },
        "notify_delay_max": {
            "type": "number", "default": 0, "label": "致谢延迟最大(秒)",
            "min": 0, "max": 300, "section": "致谢延迟",
        },
        # —— 排行榜 ——
        "rank_command": {
            "type": "string", "default": "转账排行", "label": "排行榜命令词",
            "section": "排行榜",
            "help": "自己在任意聊天发「.<命令词> [站点key] [in/out]」即可拉取排行榜。"
                    "如 .转账排行 audiences in。不带站点=逐站点输出。",
        },
        "rank_size": {
            "type": "slider", "default": 10, "label": "排行榜人数", "min": 3, "max": 30,
            "step": 1, "section": "排行榜",
        },
        "rank_output": {
            "type": "select", "default": "text", "label": "排行榜输出形式",
            "options": [
                {"value": "text", "label": "文本（始终可用）"},
                {"value": "image", "label": "图片（自带 PIL 即可出图，失败自动回退文本）"},
            ],
            "section": "排行榜",
            "help": "图片模式优先用 wkhtmltoimage（若系统装了），否则用 Pillow 纯 Python 绘制，无需额外装系统依赖。",
        },
        # —— 通知中心 ——
        "owner_notify": {
            "type": "boolean", "default": False, "label": "转账推送给平台主人",
            "section": "通知中心",
            "help": "每笔记录到的转账，额外用平台通知中心推一条给主人（ctx.notify）。",
        },
        # —— SpringSunday 大额确认 ——
        "ssd_click_mode": {
            "type": "select", "default": "off", "label": "SSD大额转账自动确认",
            "options": [
                {"value": "off", "label": "关闭（不自动点）"},
                {"value": "once", "label": "单次确认（点第一行按钮）"},
                {"value": "5min", "label": "5分钟确认（点第二行按钮）"},
            ],
            "section": "SSD大额确认",
            "help": "springsunday 转账金额过大时，转账bot会回复你一条「请确认你的转账」并附确认按钮。"
                    "开启后自动点对应按钮。对应原项目 SPRINGSUNDAY.ssd_click（off/once/5min）。",
        },
    },
}


async def setup(ctx):
    cfg = ctx.config
    store = RecordStore(ctx)

    # hdsky 专用：缓存自己发出的回复消息（"+金额"），key=chat_id → 被回复消息id
    hdsky_pay_cache: dict[int, int] = {}

    def _sites():
        """根据每站点开关构建 {chat_id: [SiteConfig]}（群组/bot 内置写死）。"""
        return build_active_sites(ctx.config)

    def _rank_size() -> int:
        try:
            return int(ctx.config.get("rank_size", 10) or 10)
        except (ValueError, TypeError):
            return 10

    def _ssd_groups() -> set[int]:
        """SpringSunday 大额确认监听的群（内置写死的两个 ssd 群）。"""
        return {-1002014253433, -1001173590111}

    ctx.log.info("多站点转账插件已启用，配置站点群数=%s", len(_sites()))

    # ── handler 1：hdsky 缓存自己发出的回复（先于 bot 确认到达）─────────────────
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.reply, group=-5, target="user")
    async def cache_outgoing_reply(client, message):
        try:
            sites = _sites().get(message.chat.id)
            if not sites or not any(s.parser == "hdsky" for s in sites):
                return
            rid = getattr(message, "reply_to_message_id", None)
            if rid:
                hdsky_pay_cache[message.chat.id] = rid
        except Exception as e:
            ctx.log.debug("hdsky 缓存失败: %s", e)

    # ── handler 2：通用转账监听（所有配置群的 bot 消息）──────────────────────────
    @ctx.on_message(ctx.filters.incoming & ctx.filters.group, group=-4, target="user")
    async def on_transfer_bot(client, message):
        try:
            sites = _sites().get(message.chat.id)
            if not sites:
                return
            fu = message.from_user
            if not fu:
                return
            # 找到匹配的站点配置（按发送者 id；bot_id=0 不校验）。
            # 注意：不额外要求 is_bot —— 原项目 azusa/zm 的转账通知账号按 id 直接匹配、
            # 并未要求是 bot（其它站点用 create_bot_filter 才带 is_bot）。TG 用户 id 唯一，
            # 仅按 id 匹配既能命中所有站点，又不会误配，还修好了 azusa/zm 不触发的问题。
            site = None
            for s in sites:
                if s.bot_id == 0 or fu.id == s.bot_id:
                    site = s
                    break
            if site is None:
                return

            if site.parser == "hdsky":
                await _handle_hdsky(ctx, store, client, message, site,
                                    hdsky_pay_cache, _rank_size)
                return

            await _handle_generic(ctx, store, client, message, site, _rank_size)
        except Exception as e:
            ctx.log.error("处理转账消息出错: %s", e)

    # 同一分派逻辑再挂一份「编辑消息」监听：springsunday 大额转账需确认，确认后 bot
    # 会「编辑」之前那条提示消息来送达成功结果，ctx.on_message 收不到编辑，故补挂
    # on_edited_message（平台标准能力，见 SPEC）。去重按 message.id 防同条多次编辑重复记。
    # hasattr 兜底：平台实例未升级到含该能力的版本时静默降级（不崩、不刷警告），
    # 升级平台后编辑监听自动生效。
    if hasattr(ctx, "on_edited_message"):
        ctx.on_edited_message(ctx.filters.incoming & ctx.filters.group, group=-4,
                              target="user")(on_transfer_bot)
    else:
        ctx.log.debug("当前平台实例无 on_edited_message，SSD 大额确认后的编辑消息暂不记录（升级平台后自动生效）")

    # ── handler 3：排行榜命令（自己发出的 .<命令词>）────────────────────────────
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-3, target="user")
    async def rank_command(client, message):
        try:
            text = (message.text or "").strip()
            cmd_word = (ctx.config.get("rank_command") or "转账排行").strip()
            if not text.startswith(".") and not text.startswith("/"):
                return
            body = text[1:].strip()
            parts = body.split()
            if not parts or parts[0] != cmd_word:
                return
            await _do_rank_command(ctx, store, message, parts[1:], _rank_size)
        except Exception as e:
            ctx.log.error("处理排行榜命令出错: %s", e)

    # ── handler 4：springsunday 大额转账自动点确认按钮（ssd_click）────────────────
    # 原项目 transform_ssd.py：转账金额过大时转账bot 回复「请确认你的转账」并附确认按钮，
    # 按 SPRINGSUNDAY.ssd_click（off/once/5min）自动点。这里复刻该逻辑。
    # 确认提示是 bot 新发的消息（带按钮），用 on_message 即可点中；点确认后 bot 会「编辑」
    # 该消息送达成功结果，那条编辑由上面的 on_edited_message 分派记账（本插件 1.0.9+）。
    @ctx.on_message(ctx.filters.incoming & ctx.filters.group & ctx.filters.reply,
                    group=-3, target="user")
    async def ssd_confirm_click(client, message):
        try:
            mode = (ctx.config.get("ssd_click_mode") or "off").strip().lower()
            if mode not in ("once", "5min"):
                return
            if message.chat.id not in _ssd_groups():
                return
            # 必须是转账bot 回复「我」发出的消息
            rtm = getattr(message, "reply_to_message", None)
            if not (rtm and rtm.from_user and getattr(rtm.from_user, "is_self", False)):
                return
            text = message.text or getattr(message, "caption", "") or ""
            if "转账金额过大" not in text and "请确认你的转账" not in text:
                return
            row, col = (0, 0) if mode == "once" else (1, 0)
            markup = getattr(message, "reply_markup", None)
            kb = getattr(markup, "inline_keyboard", None) if markup else None
            try:
                callback_data = kb[row][col].callback_data
            except (TypeError, AttributeError, IndexError):
                return
            await asyncio.sleep(0.5)
            try:
                await client.request_callback_answer(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    callback_data=callback_data,
                    timeout=10,
                )
                ctx.log.info("SSD大额转账确认成功，点击了 %s 按钮", mode)
            except TimeoutError:
                ctx.log.warning("SSD转账确认超时")
            except Exception as e:
                ctx.log.error("SSD转账确认失败: %s", e)
        except Exception as e:
            ctx.log.error("处理SSD大额确认出错: %s", e)


async def teardown(ctx):
    ctx.log.info("多站点转账插件已停用")


# 转账失败/确认类提示词：命中则不是一笔成功转账，跳过。
# 对齐原项目 cmct_pay_keyword（排除 转账金额过大/余额不足/转账失败）+ ssd「请确认你的转账」。
# 对 reply 解析的站点，其金额正则本身要求「成功/转账成功」等字样，天然不会命中失败消息；
# 但 plus 解析（springsunday/mock）金额取自「+金额」消息、不校验 bot 文本，
# 若不排除，bot 回复的「请确认你的转账 / 转账失败」会被误记成一笔转账。
_TRANSFER_SKIP_KEYWORDS = (
    "转账金额过大", "余额不足", "转账失败", "请确认你的转账", "确认你的转账",
    "请输入正确数量", "限额", "失败", "不足", "错误",
)


# ─── 通用站点处理（reply / plus）──────────────────────────────────────────────
async def _handle_generic(ctx, store, client, message, site, rank_size_fn):
    direction = detect_direction(message)
    if direction is None:
        return

    # 金额提取（严格对齐原项目：reply 站只从 bot 文本取，plus 站只从「+金额」取）
    bot_text = message.text or getattr(message, "caption", None) or ""
    # 失败/确认提示 → 不是成功转账，跳过
    if any(k in bot_text for k in _TRANSFER_SKIP_KEYWORDS):
        return
    if site.parser == "plus":
        # springsunday/mock：金额取回复链里的「+金额」消息
        plus_msg = plus_amount_message(message, direction)
        amount_str = extract_plus_amount(getattr(plus_msg, "text", None))
    else:  # reply：audiences/hddolby/azusa/zm，金额取自 bot 文本，不回退「+金额」
        amount_str = extract_amount_from_text(bot_text, site.amount_re)
    if amount_str is None:
        return
    try:
        amount = float(amount_str)
    except ValueError:
        return
    if amount <= 0:
        return

    cp_msg = counterparty_message(message, direction)
    user_id, user_name = user_identity(cp_msg)
    # 回复目标 = 对手方消息（原项目 transform_message）；拿不到则回复 bot 确认消息
    target = cp_msg or message

    await _record_and_notify(ctx, store, client, message, target, site, direction,
                             user_id, user_name, amount, rank_size_fn)


# ─── hdsky 专用处理（广播式转账，严格对齐原项目 self_received/self_mentioned）──
# HDSky 转账 bot 会「广播」群里的每一笔转账，是独立消息（不在回复链上）：
#   第1行：{转出方昵称} · 🥇 · 🥈 · 🥉        （昵称常是数学粗体等花体 unicode）
#   第2行：已向 {收款方} 转赠 {金额} 银元，...
# 方向判定完全复刻原项目 filters/custom_filters.py：
#   self_received：文本含「已向 {我} 转赠」            → 我是收款方（in/get）
#   self_mentioned：有指向我的实体，或（粗体还原后）文本以我的名字开头 → 我是转出方（out/pay）
#   两者都不满足 = 别人转给别人，直接忽略（旧逻辑误判为「我转出」，是排行榜误触发的根因）。
async def _handle_hdsky(ctx, store, client, message, site, pay_cache, rank_size_fn):
    text = message.text or ""
    # 失败/确认提示（限额、余额不足、请输入正确数量等）→ 不是成功转账，跳过
    if any(k in text for k in _TRANSFER_SKIP_KEYWORDS):
        return
    amount_str = extract_amount_from_text(text, site.amount_re)
    if amount_str is None:
        return
    try:
        amount = float(amount_str)
    except ValueError:
        return
    if amount <= 0:
        return

    me = client.me
    full_name = ""
    if me:
        full_name = " ".join(filter(None, [getattr(me, "first_name", None),
                                           getattr(me, "last_name", None)]))
    entities = getattr(message, "entities", None) or []
    entity_self = any(getattr(e, "user", None) and getattr(e.user, "is_self", False)
                      for e in entities)
    other_entity = next((e for e in entities
                         if getattr(e, "user", None) and not getattr(e.user, "is_self", False)),
                        None)

    self_received = bool(full_name and f"已向 {full_name} 转赠" in text)
    self_mentioned = entity_self or bool(
        full_name and _strip_math_bold(text).startswith(full_name))

    if self_received:
        direction = "in"
        # 对手方 = 转出方：第一个非自己的 text_mention，或取首行名字
        if other_entity:
            user_id, user_name = user_identity_from_user(other_entity.user)
        else:
            name = text.split("\n")[0].strip() or "未知用户"
            user_id, user_name = 0, name[:48]
        # 回复目标：bot 消息若在回复链上 → 回复源消息，否则回复 bot 广播消息本身
        target = getattr(message, "reply_to_message", None) or message
    elif self_mentioned:
        direction = "out"
        # 对手方 = 收款方：第一个非自己的 text_mention，或「已向 X 转赠」里的 X
        if other_entity:
            user_id, user_name = user_identity_from_user(other_entity.user)
        else:
            m = re.search(r"已向\s+(.+?)\s+转赠", text)
            name = (m.group(1) if m else "未知用户").strip()
            user_id, user_name = 0, name[:48]
        # 回复目标：我发起转账时回复的那条（收款人）消息（缓存的 id），拿不到则不指定回复
        target = None
        cached = pay_cache.pop(message.chat.id, 0)
        if cached:
            try:
                target = await client.get_messages(message.chat.id, cached)
            except Exception:
                target = None
    else:
        # 这笔转账与我无关（别人转给别人），忽略，不记账、不触发排行榜
        return

    await _record_and_notify(ctx, store, client, message, target, site, direction,
                             user_id, user_name, amount, rank_size_fn)


def _strip_math_bold(text: str) -> str:
    """将 Unicode 数学粗体字母(U+1D400–U+1D433)还原为普通 ASCII（复刻原项目）。"""
    out = []
    for c in text:
        cp = ord(c)
        if 0x1D400 <= cp <= 0x1D419:
            out.append(chr(cp - 0x1D400 + 0x41))   # 粗体 A-Z → A-Z
        elif 0x1D41A <= cp <= 0x1D433:
            out.append(chr(cp - 0x1D41A + 0x61))   # 粗体 a-z → a-z
        else:
            out.append(c)
    return "".join(out)


def user_identity_from_user(fu) -> tuple[int, str]:
    """从 pyrogram User 对象解析 (user_id, name)。"""
    uid = getattr(fu, "id", 0) or 0
    parts = []
    if getattr(fu, "first_name", None):
        parts.append(fu.first_name)
    if getattr(fu, "last_name", None):
        parts.append(fu.last_name)
    name = " ".join(parts).strip()
    if not name:
        uname = getattr(fu, "username", None)
        name = f"@{uname}" if uname else f"用户{uid}"
    return uid, name[:48]


# ─── 记录 + 通知 ───────────────────────────────────────────────────────────────
# 对齐原项目 core/services/transfer_service.py::_send_combined_notification：
#   - 记录 → 组合致谢；致谢/榜单回复「对手方消息」（target），而非 bot 确认消息。
#   - 图片模式：致谢正文 + <i>附注</i> 作为图片 caption；发图失败回退精修版文字榜。
#   - 文字模式/无图能力：致谢正文 + <blockquote>精修版文字榜</blockquote>。
async def _record_and_notify(ctx, store, client, message, target, site, direction,
                             user_id, user_name, amount, rank_size_fn):
    # 去重（防 bot 消息 + 编辑双触发）
    if store.is_duplicate(site.site_name, direction, message.chat.id, message.id, amount):
        return

    stat = store.record(site.site_name, direction, user_id, user_name, amount)
    ctx.log.info("[%s] 记录转账 dir=%s user=%s amount=%s", site.site_name,
                 direction, user_name, amount)

    # 推送给平台主人（可选）
    if ctx.config.get("owner_notify", False):
        word = "收到" if direction == "in" else "发出"
        try:
            await ctx.notify(
                f"{site.site_name} {word}转账：{user_name} {amount} {site.bonus_name}"
                f"（累计{stat['count']}次/{stat['total']}）",
                level="info", category="转账", account=client,
            )
        except Exception as e:
            ctx.log.debug("ctx.notify 失败: %s", e)

    # 群内致谢（可选）—— 按「该站点自己的开关」判断，缺省继承全局 notification
    notif_on = site.notification if site.notification is not None \
        else bool(ctx.config.get("notification", False))
    if not notif_on:
        return

    # 延迟（对应原项目 wait_time）
    dmin = _safe_int(ctx.config.get("notify_delay_min", 0), 0)
    dmax = _safe_int(ctx.config.get("notify_delay_max", 0), 0)
    if dmax > 0 and dmax >= dmin:
        await asyncio.sleep(random.uniform(dmin, dmax))

    text = lb.render_user_summary(stat, site.bonus_name, direction,
                                  user_name, amount, user_id)

    # 排行榜开关：转入看 leaderboard（缺省继承 leaderboard_in），
    #             转出看 payleaderboard（缺省继承 leaderboard_out）。
    if direction == "in":
        lb_on = site.leaderboard if site.leaderboard is not None \
            else bool(ctx.config.get("leaderboard_in", False))
    else:
        lb_on = site.payleaderboard if site.payleaderboard is not None \
            else bool(ctx.config.get("leaderboard_out", False))
    entries = []
    if lb_on:
        entries = store.leaderboard(site.site_name, direction, rank_size_fn())

    owner_name = client.me.first_name if client.me else ""
    chat_id = message.chat.id
    sent = None
    want_image = ctx.config.get("rank_output", "text") == "image"
    try:
        if entries and want_image:
            img = lb.render_image(entries, site.site_name, site.bonus_name,
                                  direction, owner_name, ctx.data_dir)
            if img:
                cap = text + lb.render_extra(owner_name, direction, len(entries))
                try:
                    sent = await _send_reply(client, chat_id, target, photo=img, caption=cap)
                except Exception as photo_err:  # noqa: BLE001 - 发图失败回退文本
                    ctx.log.warning("[排行榜] 发图失败，回退文本: %r", photo_err)
                finally:
                    try:
                        import os
                        if os.path.exists(img):
                            os.unlink(img)
                    except Exception:
                        pass
            else:
                ctx.log.warning("[排行榜] 出图未生成（imgkit=%s pil=%s），回退文本",
                                lb._imgkit_available(), lb._pil_available())
        if sent is None:
            if entries:
                table = lb.render_text_fallback(entries, owner_name, direction,
                                                site.bonus_name)
                text = f"{text}\n<blockquote>{table}</blockquote>"
            sent = await _send_reply(client, chat_id, target, text=text)
    except Exception as e:
        ctx.log.warning("发送致谢消息失败: %s", e)
        return

    # 15 秒后自删
    if sent is not None:
        asyncio.create_task(_auto_delete(sent, 15))


async def _send_reply(client, chat_id, target, text=None, photo=None, caption=None):
    """回复对手方消息（target 为 Message 对象）；target 为空则直接发到群（不指定回复）。"""
    if photo is not None:
        if target is not None:
            return await target.reply_photo(photo, caption=caption)
        return await client.send_photo(chat_id, photo, caption=caption)
    if target is not None:
        return await target.reply(text)
    return await client.send_message(chat_id, text)


# ─── 排行榜命令 ──────────────────────────────────────────────────────────────
async def _do_rank_command(ctx, store, message, args, rank_size_fn):
    """.<命令词> [站点名] [in/out]"""
    site_filter = None
    direction = None
    for a in args:
        al = a.lower()
        if al in ("in", "转入", "打赏"):
            direction = "in"
        elif al in ("out", "转出", "赏赐"):
            direction = "out"
        else:
            site_filter = a

    sites = store.sites_with_data()
    if site_filter:
        # 大小写不敏感匹配
        sites = [s for s in sites if s.lower() == site_filter.lower()]
        if not sites:
            await message.edit_text(f"没有站点「{site_filter}」的转账数据。")
            return
    if not sites:
        await message.edit_text("暂无任何转账数据。")
        return

    directions = [direction] if direction else ["in", "out"]
    size = rank_size_fn()
    # 站点的奖励名：从当前启用站点里找；找不到用空
    site_cfgs = build_active_sites(ctx.config)
    bonus_by_site = {}
    for lst in site_cfgs.values():
        for s in lst:
            bonus_by_site.setdefault(s.site_name, s.bonus_name)

    blocks = []
    for site_name in sites:
        bonus = bonus_by_site.get(site_name, "")
        for d in directions:
            entries = store.leaderboard(site_name, d, size)
            if not entries:
                continue
            blocks.append(lb.render_text(entries, site_name, bonus, d))
    if not blocks:
        await message.edit_text("暂无符合条件的排行榜数据。")
        return

    out = "\n\n".join(blocks)
    try:
        await message.edit_text(out)
    except Exception:
        await message.reply(out)


def _safe_int(v, default):
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


async def _auto_delete(message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass
