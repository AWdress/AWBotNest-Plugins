# =============================================================================
# 数字炸弹游戏 - 纯辅助函数与文案
#
# 这里只放无副作用的工具：配置解析、消息形态判定、文案构建、难度生成。
# 不 import pyrogram / core / config，所有运行期能力由调用方（__init__.py / _game.py）经 ctx 提供。
# =============================================================================

import re
import random

# 命令关键词（保持与原项目一致，硬编码）
START_KEYWORDS = ["开启数字炸弹"]
CONTINUOUS_KEYWORDS = ["持续数字炸弹"]
END_KEYWORDS = ["结束数字炸弹"]

# 严格猜测格式："我猜是<数字>"
_GUESS_PATTERN = re.compile(r"^我猜是(\d+)$")
# 参与格式："+<数字>"
_PLUS_PATTERN = re.compile(r"^\+(\d+)$")
# 金额提取（转账 bot 确认消息里的金额）
_AMOUNT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")


# ─── 配置解析 ────────────────────────────────────────────────────────────────
def _to_int_set(raw) -> set:
    """兼容 chat 控件的 id 数组与旧多行文本，解析成 int 集合。"""
    items = raw if isinstance(raw, list) else str(raw or "").splitlines()
    out = set()
    for x in items:
        try:
            out.add(x if isinstance(x, int) else int(str(x).strip()))
        except (ValueError, TypeError):
            pass
    return out


def parse_groups(raw) -> set:
    """群组ID集合。空 = 不限制（返回空集合）。"""
    return _to_int_set(raw)


def group_allowed(groups: set, chat_id: int) -> bool:
    """群组是否允许。空集合表示不限制。"""
    return True if not groups else chat_id in groups


def parse_bot_ids(raw) -> set:
    """转账确认 bot 的 ID 集合。空 = 接受任意 bot。"""
    return _to_int_set(raw)


def build_shrink_config(cfg: dict) -> dict:
    """从 ctx.config 组装范围调整配置，等价于旧项目的 NUMBER_BOMB_CONFIG。"""
    return {
        "enable_range_shrink": bool(cfg.get("enable_range_shrink", False)),
        "shrink_mechanism": {
            "distance_1_5": int(cfg.get("shrink_1_5", 0) or 0),
            "distance_6_15": int(cfg.get("shrink_6_15", -4) or 0),
            "distance_16_30": int(cfg.get("shrink_16_30", -2) or 0),
            "distance_31_plus": int(cfg.get("shrink_31plus", 2) or 0),
        },
    }


def calc_shrink_amount(shrink_cfg: dict, distance: int) -> int:
    """根据距离炸弹的远近计算范围调整幅度。
    正数：奖励缩小范围（靠近炸弹）；负数：惩罚扩大范围（远离炸弹）。
    """
    if not shrink_cfg.get("enable_range_shrink", False):
        return 0
    sm = shrink_cfg.get("shrink_mechanism", {})
    if distance <= 5:
        return sm.get("distance_1_5", 0)
    elif distance <= 15:
        return sm.get("distance_6_15", -4)
    elif distance <= 30:
        return sm.get("distance_16_30", -2)
    else:
        return sm.get("distance_31_plus", 2)


def difficulty_description(shrink_cfg: dict) -> str:
    """难度机制文案（与原项目一致）。"""
    if not shrink_cfg.get("enable_range_shrink", False):
        return "• 范围调整机制已禁用\n• 所有猜测都不会调整范围"
    return (
        "• 靠近炸弹奖励缩小范围，远离炸弹惩罚扩大范围\n"
        "• 距离1-5（靠近）：不调整范围\n"
        "• 距离6-15（较近）：不调整范围\n"
        "• 距离16-30（较远）：惩罚扩大1个数字\n"
        "• 距离31+（很远）：惩罚扩大2个数字"
    )


# ─── 消息形态判定 ────────────────────────────────────────────────────────────
def text_of(message) -> str:
    return (message.text or "").strip() if getattr(message, "text", None) else ""


def is_start_command(text: str) -> bool:
    if not text:
        return False
    if any(k in text for k in END_KEYWORDS):
        return False
    if any(k in text for k in CONTINUOUS_KEYWORDS):
        return False
    return any(k in text for k in START_KEYWORDS)


def is_continuous_command(text: str) -> bool:
    if not text:
        return False
    if any(k in text for k in END_KEYWORDS):
        return False
    return any(k in text for k in CONTINUOUS_KEYWORDS)


def is_end_command(text: str) -> bool:
    if not text:
        return False
    return any(k in text for k in END_KEYWORDS)


def parse_guess(text: str):
    """解析「我猜是N」，返回 1-100 的整数或 None。"""
    if not text:
        return None
    m = _GUESS_PATTERN.match(text)
    if m:
        try:
            g = int(m.group(1))
            if 1 <= g <= 100:
                return g
        except ValueError:
            pass
    return None


def parse_plus_amount(text: str):
    """解析「+N」参与金额，返回整数或 None。"""
    if not text:
        return None
    m = _PLUS_PATTERN.match(text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def extract_amount(text):
    """从任意文本里提取首个金额数字（转账 bot 确认消息用）。"""
    if not text:
        return None
    m = _AMOUNT_PATTERN.search(text)
    return m.group(1) if m else None


def is_start_message_text(text) -> bool:
    """判断某条文本是否游戏开始消息（参与阶段）。"""
    if not text:
        return False
    return (
        ("数字炸弹游戏准备中" in text or "数字炸弹游戏重新开始" in text)
        and "参与阶段" in text
    )


# ─── 难度：加权生成炸弹数字 ───────────────────────────────────────────────────
def generate_difficult_bomb_number() -> int:
    """生成困难的炸弹数字，降低居中二分法中奖率。"""
    weights = []
    numbers = []
    common_guesses = {50, 25, 75, 12, 87, 6, 93, 3, 97, 1, 99, 13, 37, 63}
    for i in range(1, 101):
        numbers.append(i)
        if i in common_guesses:
            weights.append(0.1)
        elif i <= 10 or i >= 90:
            weights.append(20)
        elif 40 <= i <= 60:
            weights.append(0.2)
        else:
            weights.append(8)
    return random.choices(numbers, weights=weights, k=1)[0]


def select_smart_bomb_position(available_numbers: list, guess_history: list) -> int:
    """智能选择炸弹新位置，避开常用猜测模式（动态移弹）。"""
    if not available_numbers:
        return 1
    common_guesses = {50, 25, 75, 12, 87, 6, 93, 3, 97, 1, 99, 13, 37, 63}
    weights = []
    recent_guesses = [g.get("guess") for g in guess_history[-5:]]
    for num in available_numbers:
        weight = 1.0
        if num in common_guesses:
            weight *= 10.0
        if num in recent_guesses:
            weight *= 5.0
        if num <= 10 or num >= 90:
            weight *= 0.5
        if 40 <= num <= 60:
            weight *= 2.0
        weights.append(weight)
    return random.choices(available_numbers, weights=weights, k=1)[0]


# ─── 文案构建 ────────────────────────────────────────────────────────────────
def build_start_message(wait_time: int, entry_fee: int, continuous: bool, restart: bool = False) -> str:
    """构建游戏准备/重新开始消息。"""
    title = "数字炸弹游戏重新开始！" if restart else "数字炸弹游戏准备中！"
    bomb_line = "新的炸弹数字已设置（1-100之间）" if restart else "炸弹数字已设置（1-100之间）"
    mode_text = "持续模式" if continuous else "单次模式"
    return (
        f"**{title}**\n\n"
        f"{bomb_line}\n"
        f"**奖池模式已启用**\n\n"
        f"**参与阶段（{wait_time}秒）**\n"
        f"参与费用：{entry_fee} 魔力\n"
        f"参与方式：**回复此消息** +{entry_fee}\n"
        f"注意：等待群组bot转账确认后即可参与\n"
        f"**重要**：只能回复此消息参与，其他消息参与无效且魔力不退还\n\n"
        f"**{wait_time}秒后游戏正式开始**\n"
        f"只有参与者才能猜数字\n"
        f"中奖者获得奖池奖励\n\n"
        f"游戏模式：{mode_text}"
    )
