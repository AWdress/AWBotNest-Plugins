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
    raw = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    return sanitize(raw).strip()


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
    markup = getattr(message, "reply_markup", None)
    if not markup or not getattr(markup, "inline_keyboard", None):
        return result
    for r, row in enumerate(markup.inline_keyboard):
        for c, btn in enumerate(row):
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
