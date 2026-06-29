# =============================================================================
# 自动抽奖插件 - 纯工具函数（解析 / 奖品匹配 / 陷阱检测 / 金额提取 / 配置解析）
#
# 迁移自 AWLottery: plugins/user/lottery/_lottery_helpers.py
#                  + plugins/user/_prize_sender_helpers.py 的解析部分。
# 这里只保留与平台无关的纯逻辑：不 import pyrogram / core / config / state_manager。
# 业务参数全部由调用方从 ctx.config 读出后以普通参数传入。
# =============================================================================
from __future__ import annotations

import re
from datetime import datetime, time


# ─── 配置解析工具 ────────────────────────────────────────────────────────────

def parse_groups(raw) -> list[int]:
    """解析群组ID列表（逗号或换行分隔）。空 = 空列表。"""
    groups: list[int] = []
    if not raw:
        return groups
    for chunk in str(raw).replace("\n", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            groups.append(int(chunk))
        except ValueError:
            pass
    return groups


def parse_keywords(raw) -> list[str]:
    """解析关键词列表（逗号或换行分隔）。"""
    if not raw:
        return []
    out: list[str] = []
    for chunk in str(raw).replace("\n", ",").split(","):
        k = chunk.strip()
        if k:
            out.append(k)
    return out


def parse_group_wait_overrides(raw) -> dict[int, tuple[int, int]]:
    """
    解析「按群组专属等待时间」配置。
    每行一条：`群组ID|最小秒|最大秒`，例如：
        -1001234567890|30|90
    返回 {group_id: (wait_min, wait_max)}。
    """
    out: dict[int, tuple[int, int]] = {}
    if not raw:
        return out
    for line in str(raw).splitlines():
        line = line.strip()
        if not line:
            continue
        # 兼容 `|` 分隔（首选）与空白分隔
        parts = line.split("|") if "|" in line else line.split()
        parts = [p.strip() for p in parts]
        if len(parts) < 3:
            continue
        try:
            gid = int(parts[0])
            wmin = int(parts[1])
            wmax = int(parts[2])
        except ValueError:
            continue
        if wmin > wmax:
            wmin, wmax = wmax, wmin
        out[gid] = (wmin, wmax)
    return out


def to_int(val, default: int = 0) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ─── 关键词格式检测 ──────────────────────────────────────────────────────────

_MARKDOWN_PATTERNS = [
    r'\*\*',                 # 粗体 **
    r'__',                   # 粗体 __
    r'(?<!\*)\*(?!\*)',      # 单个星号（斜体）
    r'(?<!_)_(?!_)',         # 单个下划线（斜体）
    r'`',                    # 代码
    r'~~',                   # 删除线
    r'^/',                   # 命令（行首斜杠）
    r'\s/',                  # 命令（空格后斜杠）
    r'^@',                   # 提及（行首@）
    r'\s@',                  # 提及（空格后@）
    r'^#',                   # 话题标签（行首#）
    r'\s#',                  # 话题标签（空格后#）
    r'\[.+\]\(.+\)',         # 链接
]


def has_markdown_format(text: str) -> bool:
    """检测文本是否包含 Markdown 或特殊格式（@ / 等），决定是否要转发原消息参与。"""
    if not text:
        return False
    for pattern in _MARKDOWN_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


# ─── 抽奖时间窗口 ────────────────────────────────────────────────────────────

def parse_time_ranges(raw) -> list[tuple[str, str]]:
    """
    解析抽奖时间窗口配置。支持两种写法：
      1. "08:00-11:00,13:00-17:00"（逗号分隔，破折号连接）
      2. "[('08:00','11:00'),('13:00','17:00')]"（旧 literal 写法，尽力解析）
    返回 [(start, end), ...]。解析失败返回空列表（视为全天）。
    """
    if not raw:
        return []
    raw = str(raw).strip()
    ranges: list[tuple[str, str]] = []
    # 旧 literal 写法
    if raw.startswith("["):
        try:
            import ast
            parsed = ast.literal_eval(raw)
            for item in parsed:
                if len(item) == 2:
                    ranges.append((str(item[0]), str(item[1])))
            return ranges
        except Exception:
            return []
    # 新写法 "08:00-11:00,13:00-17:00"
    for chunk in raw.replace("\n", ",").split(","):
        chunk = chunk.strip()
        if not chunk or "-" not in chunk:
            continue
        start, _, end = chunk.partition("-")
        start, end = start.strip(), end.strip()
        if start and end:
            ranges.append((start, end))
    return ranges


def is_within_time_ranges(ranges: list[tuple[str, str]], now: time | None = None) -> bool:
    """当前时间是否落在任一时间窗口内。空 ranges 视为全天允许。"""
    if not ranges:
        return True
    if now is None:
        now = datetime.now().time()
    for start_str, end_str in ranges:
        try:
            start = time.fromisoformat(start_str)
            end = time.fromisoformat(end_str)
        except ValueError:
            continue
        # 00:00-23:59 视为全天
        if start_str == "00:00" and end_str == "23:59":
            return True
        if start <= now:
            if now.hour < end.hour or (now.hour == end.hour and now.minute <= end.minute):
                return True
    return False


# ─── 抽奖消息解析 ────────────────────────────────────────────────────────────

_NEW_LOTTERY_PATTERNS = {
    "ID": r"抽奖 ID：(.+)",
    "boss_name": r"创建者：(.+?)\s+\(",
    "boss_ID": r"创建者：.+?\s+\((\d+)\)",
    "prize": r"奖品：\n      ▸ (.+)",
    "allowuser": r"允许普通用户参加：(.+)",
    "keyword": r"参与关键词：「(.+)」",
    "description": r"简介[：:]\s*(.+)",
}


def parse_new_lottery(text: str, entities=None) -> dict:
    """
    解析「新的抽奖已经创建」消息，返回结构化信息字典。
    entities: 可选的 pyrogram entities 列表，用于保留关键词中的粗体格式（** 包裹）。
    """
    info: dict = {}
    for key, pat in _NEW_LOTTERY_PATTERNS.items():
        match = re.search(pat, text)
        info[key] = match.group(1) if match else ""

    # 多奖品行
    all_prizes = re.findall(r'▸\s*(.+)', text)
    if all_prizes:
        info['all_prizes'] = all_prizes
        info['prize'] = '\n      ▸ '.join(all_prizes)
    else:
        info['all_prizes'] = [info['prize']] if info['prize'] else []

    # 保留关键词的粗体格式
    keyword_with_format = info['keyword']
    if entities and info['keyword']:
        keyword_start = text.find(info['keyword'])
        if keyword_start != -1:
            keyword_end = keyword_start + len(info['keyword'])
            for entity in entities:
                entity_start = entity.offset
                entity_end = entity.offset + entity.length
                if (keyword_start <= entity_start < keyword_end or
                        keyword_start < entity_end <= keyword_end):
                    entity_type = str(entity.type).split('.')[-1].lower()
                    if entity_type == 'bold':
                        bold_text = text[entity_start:entity_end]
                        keyword_with_format = keyword_with_format.replace(
                            bold_text, f'**{bold_text}**')
    info['keyword'] = keyword_with_format

    # 参与人数（陷阱检测用）
    max_participants_match = re.search(r'中奖概率[：:]\s*\d+/(\d+)', text)
    if max_participants_match:
        info["max_participants"] = int(max_participants_match.group(1))

    return info


# ─── 奖品匹配 ────────────────────────────────────────────────────────────────
# 对应原项目 config.config.PRIZE_LIST（每群组 → 奖品关键词列表）
# + LOTTERY_PRIZE.universal_prize_match（通用匹配开关）
# + PRIZE_MATCH_RULES.case_sensitive（区分大小写）。

def parse_prize_list(raw) -> dict[int, list[str]]:
    """
    解析「奖品列表」配置（对应 PRIZE_LIST）。
    每行 `群组ID|奖品1,奖品2,...`，例如：
        -1001234567890|魔力,积分
        -1001234567891|金币,💎币,GB,邀请
    返回 {group_id: [关键词...]}。
    """
    out: dict[int, list[str]] = {}
    if not raw:
        return out
    for line in str(raw).splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        gid_part, _, kw_part = line.partition("|")
        try:
            gid = int(gid_part.strip())
        except ValueError:
            continue
        kws = [k.strip() for k in kw_part.split(",") if k.strip()]
        if kws:
            out.setdefault(gid, [])
            out[gid].extend(kws)
    return out


def match_prize_group(prize_string: str, prize_list_map: dict[int, list[str]],
                      chat_id: int, universal: bool = False,
                      case_sensitive: bool = False):
    """
    奖品匹配（对应原 prize_check）。返回匹配到的群组ID，未匹配返回 None。
      - universal=True（通用模式）：在所有群组的关键词里匹配，返回第一个命中的群组ID。
      - universal=False（精确模式）：只用当前群组(chat_id)自己的关键词匹配。
    """
    if not prize_string or not prize_list_map:
        return None
    target = prize_string if case_sensitive else prize_string.lower()

    def _hit(kws: list[str]) -> bool:
        for kw in kws:
            k = kw if case_sensitive else kw.lower()
            if k and k in target:
                return True
        return False

    if universal:
        for gid, kws in prize_list_map.items():
            if _hit(kws):
                return gid
        return None
    kws = prize_list_map.get(chat_id)
    if kws and _hit(kws):
        return chat_id
    return None


# ─── 奖品金额提取 ────────────────────────────────────────────────────────────

_CN_MULTIPLIERS = {'万': 10000, '千': 1000, '百': 100, '十': 10,
                   'w': 10000, 'k': 1000, 'm': 1000000}


def parse_prize_amount(prize_str: str):
    """
    从单个奖品字符串解析金额（用于陷阱检测的金额阈值判断）。
    支持 "6666 * 1"→6666 / "2万电力 * 5"→20000 / "50w魔力 * 1"→500000 等。
    无法解析返回 None。
    """
    if not prize_str or '*' not in prize_str:
        return None
    before_star = prize_str.split('*')[0].strip()
    amount = None
    if before_star.isdigit():
        amount = int(before_star)
    else:
        match = re.match(r'^(\d+)([万千百十wWkKmM])', before_star)
        if match:
            amount = int(match.group(1))
            unit = match.group(2).lower()
            if unit in _CN_MULTIPLIERS:
                amount *= _CN_MULTIPLIERS[unit]
        else:
            match = re.match(r'^(\d+)\s', before_star)
            if match:
                amount = int(match.group(1))
            else:
                match = re.search(r'[一-鿿A-Za-z_](\d+)([万千百十wWkKmM])', before_star)
                if match:
                    amount = int(match.group(1))
                    unit = match.group(2).lower()
                    if unit in _CN_MULTIPLIERS:
                        amount *= _CN_MULTIPLIERS[unit]
                else:
                    match = re.search(r'[一-鿿A-Za-z_](\d+)$', before_star)
                    if match:
                        amount = int(match.group(1))
    return amount


def extract_prize_amount(prize_name: str) -> int:
    """
    从开奖中奖者奖品名称中提取数量（用于发奖 "+金额"）。
    支持 "6666*1"→6666 / "1234茉莉*1"→1234 / "1w"→10000 / "5000"→5000 等。
    无法解析返回 0。
    """
    try:
        prize_name = (prize_name or "").strip()
        if '*' in prize_name:
            before_star = prize_name.split('*')[0].strip()
            if before_star.isdigit():
                return int(before_star)
            match = re.match(r'^(\d+)\s', before_star)
            if match:
                return int(match.group(1))
            match = re.match(r'^(\d+)[一-鿿]', before_star)
            if match:
                return int(match.group(1))
            match = re.search(r'[一-鿿]+(\d+)$', before_star)
            if match:
                return int(match.group(1))
            match = re.search(r'[a-zA-Z]+\s+(\d+)$', before_star)
            if match:
                return int(match.group(1))
            match = re.search(r'[a-zA-Z]+(\d+)$', before_star)
            if match:
                return int(match.group(1))
            numbers = re.findall(r'\d+', before_star)
            if numbers:
                return int(numbers[-1])
        # 无 * 号
        match = re.match(r'(\d+(?:\.\d+)?)\s*[wW]', prize_name)
        if match:
            return int(float(match.group(1)) * 10000)
        match = re.match(r'(\d+(?:\.\d+)?)\s*[kK]', prize_name)
        if match:
            return int(float(match.group(1)) * 1000)
        numbers = re.findall(r'\d+', prize_name)
        if numbers:
            return int(numbers[-1])
        return 0
    except Exception:
        return 0


# ─── 陷阱抽奖检测 ────────────────────────────────────────────────────────────

def is_trap_lottery(message_text: str, lottery_info: dict, *,
                    suspicious_keywords: list[str] | None = None,
                    blacklist_creator_ids: list[str] | None = None,
                    enable_prize_pattern_check: bool = True,
                    enable_creator_blacklist: bool = True,
                    enable_participant_check: bool = True,
                    max_participants: int = 1,
                    case_sensitive: bool = False) -> tuple[bool, str]:
    """
    检测是否为陷阱抽奖。返回 (是否陷阱, 触发原因)。对应原 TRAP_LOTTERY_DETECTION。

    检测项（任一命中即判定为陷阱），各项受对应子开关控制：
      - 可疑关键词(enable_prize_pattern_check)：仅 奖品名称/参与关键词/简介 命中
        suspicious_keywords（不扫整条消息，避免昵称/群名/按钮文案误杀）。
      - 创建者黑名单(enable_creator_blacklist)：boss_ID 命中 blacklist_creator_ids。
      - 参与人数(enable_participant_check)：单人抽奖(max==1) 或 参与人数 <= max_participants
        (且 max_participants>1) 判为陷阱。
    """
    suspicious_keywords = suspicious_keywords or []
    blacklist_creator_ids = [str(b) for b in (blacklist_creator_ids or [])]
    reasons: list[str] = []

    # 1. 可疑关键词检测（只查 奖品名称 / 参与关键词 / 简介，不查整条消息，避免误杀）
    if enable_prize_pattern_check and suspicious_keywords:
        haystacks = [
            lottery_info.get("prize", ""),
            lottery_info.get("keyword", ""),
            lottery_info.get("description", ""),
        ]
        joined = "\n".join(haystacks)
        target = joined if case_sensitive else joined.lower()
        for kw in suspicious_keywords:
            k = kw if case_sensitive else kw.lower()
            if k and k in target:
                reasons.append(f"命中可疑关键词: {kw}")
                break

    # 2. 创建者黑名单
    if enable_creator_blacklist:
        boss_id = str(lottery_info.get("boss_ID", "") or "")
        if boss_id and boss_id in blacklist_creator_ids:
            reasons.append(f"创建者在黑名单: {boss_id}")

    # 3. 参与人数检测
    if enable_participant_check:
        max_p = lottery_info.get("max_participants")
        if max_p is None:
            m = re.search(r'中奖概率[：:]\s*\d+/(\d+)', message_text or "")
            if m:
                max_p = int(m.group(1))
        if max_p is not None:
            if max_p == 1:
                reasons.append("单人抽奖（中奖概率 x/1）")
            elif max_participants > 1 and max_p <= max_participants:
                reasons.append(f"参与人数过少: {max_p} (阈值 {max_participants})")

    if reasons:
        return True, "; ".join(reasons)
    return False, ""


# ─── 中奖者解析（开奖消息）──────────────────────────────────────────────────

def extract_participation_target(draw_text: str, entities, user_name: str, user_id: str):
    """
    从开奖消息的 entities 中找到某中奖者的「参与消息」链接，解析出 (reply_chat_id, message_id)。
    找不到返回 None。
    """
    if not entities or not draw_text:
        return None
    user_text_pattern = rf"▸\s*{re.escape(user_name)}\s*\({user_id}\)"
    user_match = re.search(user_text_pattern, draw_text)
    if not user_match:
        return None
    user_end_pos = user_match.end()
    participation_link = None
    for entity in entities:
        entity_start = entity.offset
        entity_text = draw_text[entity_start:entity_start + entity.length]
        if user_end_pos <= entity_start <= user_end_pos + 30:
            entity_type_str = str(entity.type).split('.')[-1].lower()
            if entity_type_str == "text_link":
                if getattr(entity, "url", None):
                    if "参与消息" in entity_text or "/c/" in entity.url:
                        participation_link = entity.url
                        break
            elif entity_type_str == "url":
                if "/c/" in entity_text and "t.me/" in entity_text:
                    participation_link = entity_text
                    break
    if not participation_link:
        return None
    link_match = re.search(r'/c/(\d+)/(\d+)', participation_link)
    if link_match:
        chat_id_str = link_match.group(1)
        message_id = int(link_match.group(2))
        return int(f"-100{chat_id_str}"), message_id
    public_match = re.search(r't\.me/([^/]+)/(\d+)', participation_link)
    if public_match:
        return public_match.group(1), int(public_match.group(2))
    return None


def parse_winners(draw_text: str, entities, lottery_type: str, my_id: str,
                  stored_prize_name: str = "") -> list[dict]:
    """
    解析开奖消息的中奖者列表（排除自己）。
    返回 [{prize_name, prize_amount, user_name, user_id, reply_chat_id, message_id}, ...]。
    reply_chat_id/message_id 在找不到参与链接时为 None。
    """
    winner_section_match = re.search(r'中奖信息\n([\s\S]+)', draw_text)
    if not winner_section_match:
        return []
    winner_section = winner_section_match.group(1)

    if lottery_type == "手动开奖":
        prize_pattern = r'(\d+)\s*\*\s*(\d+)[：:]\s*\n?((?:\s*▸.+?(?:\n|$))+)'
    else:
        prize_pattern = r'(.+?)\s*\*\s*(\d+)[：:]\s*\n?((?:\s*▸.+?(?:\n|$))+)'

    winners: list[dict] = []
    for prize_match in re.finditer(prize_pattern, winner_section):
        if lottery_type == "手动开奖":
            prize_name = stored_prize_name or "未知奖品"
        else:
            prize_name = prize_match.group(1).strip()
        prize_amount = extract_prize_amount(prize_name)
        winners_text = prize_match.group(3)
        for winner_match in re.finditer(r'▸\s*(.+?)\s+\((-?\d+)\)', winners_text):
            user_name = winner_match.group(1).strip()
            user_id = winner_match.group(2)
            if str(user_id) == str(my_id):
                continue
            target = extract_participation_target(draw_text, entities, user_name, user_id)
            winners.append({
                'prize_name': prize_name,
                'prize_amount': prize_amount,
                'user_name': user_name,
                'user_id': user_id,
                'reply_chat_id': target[0] if target else None,
                'message_id': target[1] if target else None,
            })
    return winners
