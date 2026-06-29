# =============================================================================
# 癫影积分红包插件 - 抢包核心逻辑
#
# 编号按钮红包（癫影积分红包）：逐个点击未抢的数字按钮，抢到一格即停。
# =============================================================================
from __future__ import annotations

import re


def extract_text(message) -> str:
    return (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()


def find_numbered_buttons(message) -> list[tuple[int, int]]:
    """返回所有未抢数字按钮的 (row, col) 列表（癫影积分红包）。"""
    result: list[tuple[int, int]] = []
    markup = getattr(message, "reply_markup", None)
    if not markup or not getattr(markup, "inline_keyboard", None):
        return result
    for r, row in enumerate(markup.inline_keyboard):
        for c, btn in enumerate(row):
            text = (getattr(btn, "text", "") or "").strip()
            if re.search(r"[一-鿿]", text):  # 含中文 → 管理员按钮，跳过
                continue
            if re.match(r"^[✅☑]", text):    # ✅/☑ 已抢，跳过
                continue
            if re.search(r"\d$", text):               # 末尾数字 → 未抢
                result.append((r, c))
    return result


def is_snatch_success(result_text: str) -> bool:
    """判断点击结果是否表示抢包成功。"""
    if not result_text or result_text in ("None", ""):
        return False
    return any(k in result_text for k in ("抢到了", "抢到", "恭喜", "你获得", "领取成功", "积分已到账"))
