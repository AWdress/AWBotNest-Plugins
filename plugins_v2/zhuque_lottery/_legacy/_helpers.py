# =============================================================================
# 朱雀插件 - 通用工具（zhuque_lottery 私有辅助）
#
# 包含：
#   - calc_starting_bet：倍投起手金额表（/betbonus）
#   - extract_lingshi_amount：从打劫结果文本里抽取灵石数额
#   - build_reply_messages：根据配置的「名字」生成打劫反击文案字典
#
# 纯 Python，无任何平台/pyrogram 依赖。
# =============================================================================
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional


def calc_starting_bet(c: float = 50_000_000, max_n: int = 20) -> str:
    """
    倍投起手金额表：给定本金上限 c 与最大连输次数 max_n，
    计算每个连输档位的起手金额、最后一注、总投入。
    （迁移自 calc_starting_bet.py，逻辑不变。）
    """
    lines = []
    header = f"{'连输次数':<6} | {'起手金额':>10} | {'最后一注':>10} | {'总投入':>15}"
    separator = "-" * len(header)
    lines.append(header)
    lines.append(separator)

    for n in range(1, int(max_n) + 1):
        power = 2 ** (n - 1)
        x = abs((c - (power - 1)) // power)
        x = int(x)
        last_bet = power * x + (power - 1)
        total = sum(2 ** i * x + (2 ** i - 1) for i in range(n))
        line = f"{n:<6} | {x:>10,} | {last_bet:>10,} | {total:>15,}"
        lines.append(line)

    return "\n".join(lines)


def extract_lingshi_amount(text: str, pattern: str) -> Optional[Decimal]:
    """按正则从文本里取第 2 个分组作为灵石金额。"""
    if not text:
        return None
    match = re.search(pattern, text)
    if match:
        try:
            return Decimal(match.group(2))
        except Exception:
            return None
    return None


def build_reply_messages(name: str) -> dict:
    """
    根据主人昵称生成朱雀打劫/查询反击文案。
    迁移自 config/reply_message.py 的 ZQ_REPLY_MESSAGE（把 MY_NAME 改为配置项）。
    """
    n = name or "我"
    return {
        "infoBy": "别翻了，口袋比你的脸还干净呢！！",
        "dajieInfoLose": f"抢你{n}哥这么多钱，等我打劫回来！！！？",
        "dajieInfoWin": f"{n}哥觉得你是个好人！祝你好运！！",
        "dajieCoolingDown": f"就这么急不可耐得想给你{n}哥送钱？？！",
        "meInsufficient": f"你{n}哥也难免有资金周转不开的时候，支援点吧！",
        "othersInsufficient": f"哇嘎嘎嘎嘎，学人打劫，输完了吧，{n}哥送1块打车费，回去猥琐发育吧，",
        "robbedByWin": f"感谢大佬给你{n}哥送钱，继续保持",
        "robbedByLose": f"{n}哥你也敢抢?看我打劫回来?",
        "robbedByLoseCD": f"{n}哥还在CD，养精蓄锐，这次算你走运放过你了",
        "robbedlosfandaoff": f"{n}哥你也敢抢？嗯,算了算了，今天心情好下次再反打了",
        "robbedwinfandaoff": f"感谢大佬给你{n}哥送钱，看在灵石的份上放过你不反打了",
        "robbedBynosidepot": "输赢这么少，估计没进加倍区，我都懒得去看我打劫CD好了没有",
        "autoRobbingHint": f"{n}的枪已经瞄准你了！！",
    }


def parse_groups(text: str) -> list[int]:
    """把「逗号/换行分隔的群组ID」解析为 int 列表。"""
    if not text:
        return []
    out = []
    for part in re.split(r"[,\s]+", str(text).strip()):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out


def safe_int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def parse_blacklist(text: str) -> set[int]:
    """返现黑名单：逗号分隔的 TGID。"""
    return set(parse_groups(text))
