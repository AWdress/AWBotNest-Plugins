# =============================================================================
# 多站点转账 - 站点配置解析 + 消息解析 + 金额提取
#
# 这里只放无副作用的纯工具：站点列表解析、转账方向判定、金额提取、对手方解析。
# 不 import pyrogram / core / config —— 运行期 Message 对象由调用方（__init__.py）传入，
# 我们只读它的属性（pyrogram Message 的标准字段）。
#
# 各站点的共性（已确认）：群里的「转账 bot」发一条确认消息，消息处在一条回复链上：
#   GET（别人转给我）：bot确认 → 回复 → 对方的「+金额」消息 → 回复 → 我的原始消息
#       → message.reply_to_message.reply_to_message.from_user.is_self 为真
#       → 对手方（转入方）= message.reply_to_message.from_user
#   PAY（我转给别人）：bot确认 → 回复 → 我的「+金额」消息 → 回复 → 对方的原始消息
#       → message.reply_to_message.from_user.is_self 为真
#       → 对手方（收款方）= message.reply_to_message.reply_to_message.from_user
# 金额来源两种：① 对 bot 文本跑正则（默认）；② 取回复链里的「+金额」消息（parser=plus）。
# hdsky 形态特殊，由 __init__.py 里的专用解析处理，本模块只负责识别它的 parser 标记。
# =============================================================================

import re
from typing import Optional, NamedTuple

# 金额默认正则：抓文本里第一个数字（含小数）
_DEFAULT_AMOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)")
# 「+金额」格式
_PLUS_RE = re.compile(r"^\s*\+?\s*(\d+(?:\.\d+)?)\s*$")


class SiteConfig(NamedTuple):
    """单个站点的配置。"""
    chat_id: int          # 群组 ID
    site_name: str        # 站点标识（聚合排行榜按此分组）
    bot_id: int           # 该群转账 bot 的数字 ID（0 = 不校验发送者）
    bonus_name: str       # 货币单位（爆米花/魔力值/茉莉…）
    amount_re: re.Pattern # 金额正则（parser=reply 时用）
    parser: str           # "reply"（默认，只从 bot 文本正则抓金额，对齐原项目 audiences/hddolby/azusa/zm）
                          # | "plus"（只取回复链里的 +金额 消息，对齐原项目 springsunday/mock）
                          # | "hdsky"（实体解析，专用分支）
    # ── per-site 开关（对应原项目 state.toml 里 [站点名大写] 段的三项）──
    # 三者均为 Optional[bool]：None = 继承对应全局开关；True/False = 本站点显式覆盖。
    notification: Optional[bool]    # 群内致谢（继承全局 notification）
    leaderboard: Optional[bool]     # 转入(打赏)榜（继承全局 leaderboard_in）
    payleaderboard: Optional[bool]  # 转出(赏赐)榜（继承全局 leaderboard_out）


# =============================================================================
# 内置站点（群组ID / 转账bot ID / 货币 / 解析方式 全部写死）。
# 这些是 PT 站固定信息，普通用户改不了也不该改 —— 用户只通过 config_schema
# 的每站点开关决定「是否监听该站、是否致谢、是否上榜」。
# 字段：key(配置用) | 显示名 | 群组ID列表 | botID | 货币 | parser | 金额正则 | 默认启用
# =============================================================================
_BUILTIN_SITES = [
    # key,         display,        chat_ids,                          bot_id,     bonus,   parser,  amount_re,                       default_on
    ("audiences",   "Audiences",   [-1002372175195],                  2053736484, "爆米花", "reply", r"送给.+?(\d+)\s*粒?爆米花", True),
    ("hddolby",     "HDDolby",     [-1002131053667],                  6474948384, "鲸币",   "reply", r"成功转账(\d+)",                True),
    ("azusa",       "Azusa",       [-1002132909147],                  6696869468, "魔力值", "reply", r"成功赠送\s*(\d+)\s*魔力值",     True),
    ("zm",          "ZmPT",        [-1001664998164],                  7192791419, "电力",   "reply", r"转账成功！已转账\s*(\d+)\s*电力", True),
    ("springsunday","SpringSunday",[-1002014253433, -1001173590111],  752250569,  "茉莉",   "plus",  "",                              True),
    ("hdsky",       "HDSky",       [-1001326208894],                  8907007783, "银元",   "hdsky", r"转赠\s*(\d+)\s*银元",          True),
    ("mocktest",    "MockTest(测试)",[-1003280466424],                7550375221, "测试币", "plus",  "",                              False),
]


def builtin_site_keys() -> list[tuple[str, str, str, bool]]:
    """返回 [(key, 显示名, 货币, 默认启用), ...]，供 __init__.py 动态生成 config_schema。"""
    return [(k, disp, bonus, default_on)
            for (k, disp, _ids, _bid, bonus, _p, _re, default_on) in _BUILTIN_SITES]


def build_active_sites(config) -> dict[int, list["SiteConfig"]]:
    """根据 config 里每站点的开关，构建 {chat_id: [SiteConfig]}。

    每站点读三个开关键：
      site_<key>_enabled   是否监听该站（关=完全不处理该群）
      site_<key>_notify    群内致谢开关
      site_<key>_lb_in     致谢附转入(打赏)榜
      site_<key>_lb_out    致谢附转出(赏赐)榜
    群组ID / botID / 货币 / 解析方式全部取内置写死值。
    """
    result: dict[int, list[SiteConfig]] = {}
    for (key, _disp, chat_ids, bot_id, bonus, parser, amount_pat, default_on) in _BUILTIN_SITES:
        if not config.get(f"site_{key}_enabled", default_on):
            continue
        try:
            amount_re = re.compile(amount_pat) if amount_pat else _DEFAULT_AMOUNT_RE
        except re.error:
            amount_re = _DEFAULT_AMOUNT_RE
        notify = bool(config.get(f"site_{key}_notify", False))
        lb_in = bool(config.get(f"site_{key}_lb_in", False))
        lb_out = bool(config.get(f"site_{key}_lb_out", False))
        for chat_id in chat_ids:
            cfg = SiteConfig(chat_id, key, bot_id, bonus, amount_re, parser,
                             notify, lb_in, lb_out)
            result.setdefault(chat_id, []).append(cfg)
    return result


def _parse_switch(val: Optional[str]) -> Optional[bool]:
    """解析站点行里的 on/off 列。空/未知 → None（继承全局开关）。"""
    v = (val or "").strip().lower()
    if v in ("on", "true", "1", "yes", "y", "开"):
        return True
    if v in ("off", "false", "0", "no", "n", "关"):
        return False
    return None


def parse_sites(raw: str) -> dict[int, list[SiteConfig]]:
    """解析多行站点配置文本，返回 {chat_id: [SiteConfig, ...]}。

    每行格式（| 分隔，两端空白自动去除）：
        群ID | 站点名 | botID | 奖励名 [ | 金额正则 ] [ | parser ]
                       [ | notification ] [ | leaderboard ] [ | payleaderboard ]

    - 金额正则可留空（用默认）；parser 可留空（默认 reply）。
    - 末尾 3 个开关列（notification/leaderboard/payleaderboard）可选：on/off，
      留空 = 继承对应全局开关（notification / leaderboard_in / leaderboard_out）。
      这复刻原项目「每站点独立开关」（state.toml 里 [站点名大写] 段）的粒度。
    - 同一群可能配多个站点（少见），故 value 用 list。
    - `#` 开头或空行忽略。
    """
    result: dict[int, list[SiteConfig]] = {}
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        try:
            chat_id = int(parts[0])
            bot_id = int(parts[2]) if parts[2] else 0
        except ValueError:
            continue
        site_name = parts[1]
        bonus_name = parts[3]
        amount_pat = parts[4] if len(parts) >= 5 and parts[4] else ""
        parser = parts[5].lower() if len(parts) >= 6 and parts[5] else "reply"
        # per-site 开关列（缺省 None → 继承全局）
        notification = _parse_switch(parts[6]) if len(parts) >= 7 else None
        leaderboard = _parse_switch(parts[7]) if len(parts) >= 8 else None
        payleaderboard = _parse_switch(parts[8]) if len(parts) >= 9 else None
        try:
            amount_re = re.compile(amount_pat) if amount_pat else _DEFAULT_AMOUNT_RE
        except re.error:
            amount_re = _DEFAULT_AMOUNT_RE
        cfg = SiteConfig(chat_id, site_name, bot_id, bonus_name, amount_re, parser,
                         notification, leaderboard, payleaderboard)
        result.setdefault(chat_id, []).append(cfg)
    return result


def _from_user_is_self(msg) -> bool:
    return bool(msg and msg.from_user and getattr(msg.from_user, "is_self", False))


def detect_direction(message) -> Optional[str]:
    """根据回复链判定方向：'in'（转入）/ 'out'（转出）/ None（不是转账确认）。

    GET/in : message.reply_to_message.reply_to_message.from_user.is_self
    PAY/out: message.reply_to_message.from_user.is_self
    注意：先判 in（更深一层），避免 out 误判。
    """
    rtm = getattr(message, "reply_to_message", None)
    if not rtm:
        return None
    rtm2 = getattr(rtm, "reply_to_message", None)
    if _from_user_is_self(rtm2):
        return "in"
    if _from_user_is_self(rtm):
        return "out"
    return None


def counterparty_message(message, direction: str):
    """返回承载对手方信息的那条消息（其 from_user 即转入方/收款方）。"""
    rtm = getattr(message, "reply_to_message", None)
    if not rtm:
        return None
    if direction == "in":
        return rtm                                   # 对方的 +金额 消息
    return getattr(rtm, "reply_to_message", None)    # 对方的原始消息


def plus_amount_message(message, direction: str):
    """parser=plus 时，承载「+金额」文本的那条消息。

    GET：别人回复我发的 +金额 → message.reply_to_message
    PAY：我回复别人发的 +金额 → message.reply_to_message
    两种方向「+金额」都在 message.reply_to_message。
    """
    return getattr(message, "reply_to_message", None)


def extract_amount_from_text(text: Optional[str], pattern: re.Pattern) -> Optional[str]:
    """用站点正则从文本里抓金额；抓不到返回 None。"""
    if not text:
        return None
    m = pattern.search(text)
    if not m:
        return None
    # 优先取第一个捕获组，没有分组就取整体匹配
    return m.group(1) if m.groups() else m.group(0)


def extract_plus_amount(text: Optional[str]) -> Optional[str]:
    """从「+888 / 888」这类文本里抓金额。"""
    if not text:
        return None
    m = _PLUS_RE.match(text.strip())
    return m.group(1) if m else None


def user_identity(msg) -> tuple[int, str]:
    """从一条消息的 from_user 解析 (user_id, user_name)。

    user_id 取不到时为 0；user_name 优先 first+last，回退 username/用户ID。
    """
    fu = getattr(msg, "from_user", None) if msg else None
    if not fu:
        return 0, "未知用户"
    user_id = getattr(fu, "id", 0) or 0
    parts = []
    if getattr(fu, "first_name", None):
        parts.append(fu.first_name)
    if getattr(fu, "last_name", None):
        parts.append(fu.last_name)
    name = " ".join(parts).strip()
    if not name or name.lower() in ("untitled", "none", "null"):
        uname = getattr(fu, "username", None)
        name = f"@{uname}" if uname else f"用户{user_id}"
    return user_id, name[:48]
