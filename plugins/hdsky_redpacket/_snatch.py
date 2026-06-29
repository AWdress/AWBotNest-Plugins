# =============================================================================
# 拼手气红包插件 - 抢包核心逻辑
#
# 按钮红包（HDSKY 拼手气红包）：检测「拼手气红包」消息并点击「抢红包」内联按钮。
# =============================================================================
from __future__ import annotations


def extract_text(message) -> str:
    return (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()


def find_snatch_button(message):
    """在内联键盘里找「抢红包」按钮，返回 (row, col) 或 None。"""
    markup = getattr(message, "reply_markup", None)
    if not markup or not getattr(markup, "inline_keyboard", None):
        return None
    for r, row in enumerate(markup.inline_keyboard):
        for c, btn in enumerate(row):
            text = (getattr(btn, "text", "") or "")
            if "抢红包" in text or "抢 红 包" in text or text.strip() in ("抢", "领取红包"):
                return (r, c)
    return None


def is_lucky_packet(message) -> bool:
    """判断是否为拼手气（按钮）红包消息。"""
    text = extract_text(message)
    if "拼手气红包" in text:
        return True
    if "红包" in text and ("份数" in text or "总银元" in text or "总金额" in text):
        return True
    return False
