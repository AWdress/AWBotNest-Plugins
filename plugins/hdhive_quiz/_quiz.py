# =============================================================================
# 影巢答题红包插件 - 题面解析 / 答案匹配（私有辅助，_ 开头不被识别为插件）
#
# 影巢机器人发的「答题红包」：消息里带一道题（单选 4 项 或 判断 对/错），
# 答对（回复正确答案文本）即可参与。本模块负责：
#   1. sanitize：剔除零宽/格式字符（影巢 bot 惯用零宽字符防脚本，见项目记忆）。
#   2. parse_quiz：从消息文本里解析出「题干 + 选项 + 题型」。
#   3. resolve/match：把题库或大模型给出的答案映射到本条消息实际选项，
#      生成要回复的文本。
#
# 消息格式无法从代码/网络推定，故解析尽量鲁棒、多格式兼容，并在 __init__ 里
# 对解析失败/命中情况打日志，便于对着真实红包（getmsg）微调。
# =============================================================================
from __future__ import annotations

import re
import unicodedata

# 判断题的「对 / 错」两侧同义词（归一到 对 / 错）
_TRUE_WORDS = {"对", "正确", "是", "true", "yes", "√", "✓", "t"}
_FALSE_WORDS = {"错", "错误", "否", "不对", "false", "no", "×", "✗", "f"}

# 疑似「答题红包」的题面标记（命中任一才当作答题红包处理）
QUIZ_MARKERS = ("答题", "答对", "题目", "问题", "回答", "答案")

# 行首选项：A. / A、/ A) / (A) / A: / 1. 等；label 捕获 A-D 或 1-4，content 捕获正文
_OPTION_LINE = re.compile(
    r"^\s*[（(【\[]?\s*([A-Da-d1-4１-４])\s*[)）】\]]?\s*[\.、。::，,\)、]?\s*(.+?)\s*$"
)
# 题干显式标记
_Q_MARKER = re.compile(r"(?:题目|问题|题干|问)\s*[:：]\s*(.*)")


def sanitize(text: str) -> str:
    """剔除 Unicode Cf（零宽/格式）字符——影巢 bot 惯用它们防自动答题脚本。"""
    if not text:
        return ""
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def _fullwidth_digit_to_letter(ch: str) -> str:
    """全角/半角数字 1-4 → A-D；A-D 原样大写返回。"""
    mapping = {"1": "A", "2": "B", "3": "C", "4": "D",
               "１": "A", "２": "B", "３": "C", "４": "D"}
    return mapping.get(ch, ch.upper())


def normalize(text: str) -> str:
    """匹配用归一化：去零宽、去空白、去标点、小写。用于题干/选项内容比对。"""
    text = sanitize(text or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))
    return text


def normalize_judge(word: str) -> str:
    """把「对/错」类答案归一到 '对' 或 '错'，无法判定返回 ''。"""
    w = normalize(word)
    if not w:
        return ""
    if w in {normalize(x) for x in _TRUE_WORDS}:
        return "对"
    if w in {normalize(x) for x in _FALSE_WORDS}:
        return "错"
    return ""


def parse_quiz(text: str) -> dict | None:
    """
    解析答题红包文本。返回 {question, options:[(label, content)], qtype} 或 None。
      qtype: 'single'（单选）| 'judge'（判断）
    尽量鲁棒：识别 A./A、/(A)/1. 等多种选项格式；判断题识别 对/错 选项。
    """
    clean = sanitize(text or "")
    if not clean.strip():
        return None

    lines = [ln for ln in (l.strip() for l in clean.splitlines()) if ln]
    options: list[tuple[str, str]] = []
    q_marker_line = ""
    non_option_lines: list[str] = []

    for ln in lines:
        m = _OPTION_LINE.match(ln)
        if m and len(m.group(2).strip()) >= 1:
            label = _fullwidth_digit_to_letter(m.group(1))
            content = m.group(2).strip()
            # 排除误伤：内容不能又是另一条选项前缀且过短的噪声
            options.append((label, content))
            continue
        qm = _Q_MARKER.search(ln)
        if qm and qm.group(1).strip():
            q_marker_line = qm.group(1).strip()
        non_option_lines.append(ln)

    # 判断题：题面出现 对/错 选项，或显式「判断」字样
    judge = False
    if options:
        labels_content = [normalize_judge(c) for _, c in options]
        if all(labels_content) and len(options) <= 3:
            judge = True

    # 题干：优先显式标记行；否则取非选项行里最长的一条（红包头尾多为短提示）
    if q_marker_line:
        question = q_marker_line
    else:
        cand = [ln for ln in non_option_lines if len(ln) >= 4]
        question = max(cand, key=len) if cand else (non_option_lines[0] if non_option_lines else "")

    if not question:
        return None

    # 无标注选项，但题面像判断题 → 造 对/错 两项
    if not options and ("判断" in clean or "对还是错" in clean or "对或错" in clean):
        options = [("A", "对"), ("B", "错")]
        judge = True

    if not options:
        return None

    return {
        "question": question,
        "options": options,
        "qtype": "judge" if judge else "single",
    }


def resolve_bank_answer(bank_rec: dict) -> str:
    """
    把题库记录的 answer 解析成「正确选项的内容文本」（判断题为 '对'/'错'）。
    bank_rec: {answer, options:[...], question_type}
    """
    ans = str(bank_rec.get("answer", "")).strip()
    if not ans:
        return ""
    bank_opts = bank_rec.get("options") or []

    # 字母 A-D → 对应选项内容
    if re.fullmatch(r"[A-Da-d]", ans) and bank_opts:
        idx = ord(ans.upper()) - 65
        if 0 <= idx < len(bank_opts):
            return str(bank_opts[idx]).strip()

    # 判断题
    jt = normalize_judge(ans)
    if jt and (bank_rec.get("question_type") == "true_false" or not bank_opts):
        return jt

    # answer 本身就是选项原文
    return ans


def match_live_option(correct_content: str, live_options: list[tuple[str, str]],
                      qtype: str) -> tuple[str, str] | None:
    """在本条消息的实际选项里找到与 correct_content 对应的 (label, content)。"""
    if not correct_content:
        return None
    nc = normalize(correct_content)

    # 判断题：按 对/错 归一后比对
    if qtype == "judge":
        want = normalize_judge(correct_content) or nc
        for label, content in live_options:
            if (normalize_judge(content) or normalize(content)) == want:
                return (label, content)

    # 内容全等
    for label, content in live_options:
        if normalize(content) == nc:
            return (label, content)
    # 内容包含（题库选项可能带多余修饰）
    for label, content in live_options:
        ncont = normalize(content)
        if ncont and (ncont in nc or nc in ncont):
            return (label, content)
    return None


def option_by_letter(letter: str, live_options: list[tuple[str, str]]) -> tuple[str, str] | None:
    """按字母 A-D 直接取本条消息的选项（大模型/题库给字母时用）。"""
    letter = _fullwidth_digit_to_letter((letter or "").strip()[:1]) if letter else ""
    if not re.fullmatch(r"[A-D]", letter):
        return None
    # 先按 label 精确匹配，再退回按顺序索引
    for label, content in live_options:
        if label == letter:
            return (label, content)
    idx = ord(letter) - 65
    if 0 <= idx < len(live_options):
        return live_options[idx]
    return None


def build_reply(matched: tuple[str, str] | None, correct_content: str,
                qtype: str, reply_format: str) -> str:
    """
    生成要回复的文本。
      reply_format: 'content'(选项原文, 默认) | 'letter'(字母A-D) | 'full'(字母+原文)
    判断题固定回复归一后的 对/错（若匹配到实际选项则回其原文）。
    matched 为 None 时退回直接回复 correct_content。
    """
    if qtype == "judge":
        if matched:
            return matched[1]
        return normalize_judge(correct_content) or correct_content

    if not matched:
        return correct_content

    label, content = matched
    if reply_format == "letter":
        return label
    if reply_format == "full":
        return f"{label}. {content}"
    return content  # 'content' 默认
