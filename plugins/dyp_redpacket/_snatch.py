# =============================================================================
# 癫影积分红包插件 - 抢包核心逻辑
#
# 编号按钮红包（癫影积分红包）：逐个点击未抢的数字按钮，抢到一格即停。
# =============================================================================
from __future__ import annotations

import re


def extract_text(message) -> str:
    return (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()


def classify_packet(blob: str, mine_keywords: list[str], normal_keywords: list[str]) -> str:
    """根据文字判定红包类型。blob 可以是 caption、OCR 文字，或两者拼接。

    返回:
      "mine"   —— 命中雷包关键词（雷包优先，最高优先级）
      "normal" —— 未命中雷包词，且命中正常红包放行词
      "unknown"—— 都没命中（上层 fail-closed：当雷包跳过）

    注意雷包文案含「这不是红包」——内含「红包」二字，故必须雷包词优先，
    不能见到「红包」就放行。
    """
    text = blob or ""
    # 1) 雷包词优先
    for kw in mine_keywords:
        kw = (kw or "").strip()
        if kw and kw in text:
            return "mine"
    # 2) 正常红包放行词
    for kw in normal_keywords:
        kw = (kw or "").strip()
        if kw and kw in text:
            return "normal"
    return "unknown"



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
