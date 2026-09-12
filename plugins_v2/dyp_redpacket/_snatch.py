# =============================================================================
# 癫影积分红包插件 - 抢包核心逻辑
#
# 编号按钮红包（癫影积分红包）：现在是「混合红包」——一条消息 M 格，暗含 N 个雷包，
# 其余给分。逐个点击未抢的数字按钮，落地一格即停（抢到分/踩雷都算用掉唯一机会，
# 只有「手慢了/已被抢」才继续点下一格）。
# =============================================================================
from __future__ import annotations

import re
import unicodedata


_REGISTRATION_CHALLENGE_RE = re.compile(
    r"(?:^|\n)\s*(?:🔐\s*)?抽奖报名验证\s*\n+"
    r"\s*(?P<target>[^\n，,]+?)\s*[，,]\s*请在\s*\d+\s*分钟内回复本消息\s*[:：]\s*\n+"
    r"\s*(?P<left>-?\d{1,9})\s*(?P<operator>[+＋\-−×xX*÷/])\s*"
    r"(?P<right>-?\d{1,9})\s*=\s*[?？]",
    re.IGNORECASE,
)


def sanitize(text: str) -> str:
    """清除零宽/不可见格式字符。

    癫影把零宽字符（U+200B 等，Unicode 类别 Cf）塞进「红包」「雷包」等关键词里
    防自动抢包脚本匹配（如「红​包」中间有 U+200B，`"红包" in text` 会失败）。
    匹配前统一清掉，让门槛与判定恢复，且对其往任意词塞零宽字符免疫。
    """
    if not text:
        return text
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def extract_text(message) -> str:
    raw = (
        getattr(message, "raw_text", None)
        or getattr(message, "text", None)
        or getattr(message, "caption", None)
        or ""
    )
    return sanitize(raw).strip()


def parse_registration_challenge(text: str) -> tuple[str, str] | None:
    """解析癫影报名验证，返回（被点名对象，答案）。

    只接受固定的“抽奖报名验证 + 回复本消息 + 简单算式”结构，避免把普通聊天
    或其他机器人的算术题当作验证。除法仅在能够整除时作答。
    """
    matched = _REGISTRATION_CHALLENGE_RE.search(sanitize(text or ""))
    if not matched:
        return None
    left, right = int(matched["left"]), int(matched["right"])
    operator = matched["operator"]
    if operator in {"+", "＋"}:
        answer = left + right
    elif operator in {"-", "−"}:
        answer = left - right
    elif operator in {"×", "x", "X", "*"}:
        answer = left * right
    else:
        if right == 0 or left % right:
            return None
        answer = left // right
    return matched["target"].strip(), str(answer)


def registration_target_matches(target: str, me) -> bool:
    """验证文案点名对象是否为当前 Telegram 账号。"""
    def normalize(value: object) -> str:
        text = unicodedata.normalize("NFKC", sanitize(str(value or ""))).strip()
        return re.sub(r"\s+", " ", text).removeprefix("@").casefold()

    first_name = str(getattr(me, "first_name", "") or "").strip()
    last_name = str(getattr(me, "last_name", "") or "").strip()
    username = str(getattr(me, "username", "") or "").strip()
    aliases = {normalize(first_name), normalize(username)}
    if first_name and last_name:
        aliases.add(normalize(f"{first_name} {last_name}"))
    aliases.discard("")
    return normalize(target) in aliases


def parse_packet_meta(caption: str) -> dict:
    """从红包文案里抽出 分值/份数/暗含雷包数/余位，仅用于日志与记录，不影响是否开抢。

    例：「分值: 50 · 份数: 9 · 暗含 1 个雷包」「余位: 9/9」
    抽不到的字段为 None。
    """
    text = caption or ""
    meta: dict = {"value": None, "shares": None, "mines": None, "left": None, "total": None}
    m = re.search(r"分值[:：]?\s*(\d+)", text)
    if m:
        meta["value"] = int(m.group(1))
    m = re.search(r"份数[:：]?\s*(\d+)", text)
    if m:
        meta["shares"] = int(m.group(1))
    m = re.search(r"暗含\s*(\d+)\s*个雷包", text)
    if m:
        meta["mines"] = int(m.group(1))
    m = re.search(r"余位[:：]?\s*(\d+)\s*/\s*(\d+)", text)
    if m:
        meta["left"] = int(m.group(1))
        meta["total"] = int(m.group(2))
    return meta


def find_numbered_buttons(message) -> list[tuple[int, int]]:
    """返回所有未抢数字按钮的 (row, col) 列表（癫影积分红包）。"""
    result: list[tuple[int, int]] = []
    # Telethon 的便捷属性是 ``message.buttons``；底层 ReplyInlineMarkup 则是
    # ``reply_markup.rows[*].buttons``。V1/Pyrogram 的旧按钮集合在 V2 消息上
    # 不存在，因此必须同时兼容前两种 Telethon 结构。
    rows = getattr(message, "buttons", None)
    if not rows:
        markup = getattr(message, "reply_markup", None)
        rows = [getattr(row, "buttons", []) for row in (getattr(markup, "rows", None) or [])]
    for r, row in enumerate(rows or []):
        for c, btn in enumerate(row or []):
            text = (getattr(btn, "text", "") or "").strip()
            if re.search(r"[一-鿿]", text):  # 含中文 → 管理员按钮（如「终止(管理员)」），跳过
                continue
            if re.match(r"^[✅☑]", text):    # ✅/☑ 已抢，跳过
                continue
            if re.search(r"\d$", text):               # 末尾数字 → 未抢
                result.append((r, c))
    return result


def is_snatch_success(result_text: str) -> bool:
    """点击结果是否表示抢到（拿到积分）。"""
    if not result_text or result_text in ("None", ""):
        return False
    return any(k in result_text for k in ("抢到了", "抢到", "恭喜", "你获得", "领取成功", "积分已到账"))


def is_thunder_hit(result_text: str) -> bool:
    """点击结果是否表示踩到雷包（扣分）。踩雷也算用掉唯一一次机会 → 应停手。"""
    if not result_text:
        return False
    return any(k in result_text for k in ("踩雷", "中雷", "雷包", "炸弹", "扣除", "扣了"))
