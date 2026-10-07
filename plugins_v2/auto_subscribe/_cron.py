"""Translate the host's five/six-field cron weekdays for its APScheduler SDK.

The host editor uses Sunday=0/7, Monday=1, ... Saturday=6. APScheduler uses
Monday=0 and rejects 7. Expand only the weekday field to explicit English
names so numeric ranges and steps keep the editor's Sunday-first meaning.
The SDK remains responsible for validating every other field.
"""

from __future__ import annotations

import re


_DAY_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
_DAY_NUMBERS = {name: number for number, name in enumerate(_DAY_NAMES)}
_DAY_VALUE = r"(?:[0-9]+|sun|mon|tue|wed|thu|fri|sat)"
_DAY_PART = re.compile(rf"(?P<start>\*|{_DAY_VALUE})(?:-(?P<end>{_DAY_VALUE}))?(?:/(?P<step>[0-9]+))?", re.IGNORECASE)


def _day_number(value: str) -> int:
    if value in _DAY_NUMBERS:
        return _DAY_NUMBERS[value]
    number = int(value)
    if not 0 <= number <= 7:
        raise ValueError("Cron 星期必须为 0～7 或 sun～sat")
    return number


def _weekdays(expression: str) -> str:
    expression = expression.lower()
    if expression == "?":
        return "*"
    selected: set[int] = set()
    for part in expression.split(","):
        match = _DAY_PART.fullmatch(part)
        if match is None:
            raise ValueError("Cron 星期格式无效；仅支持星期值、列表、范围和步长")
        start, end, raw_step = match.group("start", "end", "step")
        if start == "*" and end is not None:
            raise ValueError("Cron 星期范围不能以 * 开始")
        # The host's real save validator bounds every weekday numeral to 7,
        # including a step. Zero is never a valid step.
        step = int(raw_step) if raw_step is not None else 1
        if not 1 <= step <= 7:
            raise ValueError("Cron 星期步长必须为 1～7")
        if start != "*" and end is None and raw_step is None:
            selected.add(_day_number(start) % 7)
            continue
        raw_low = 0 if start == "*" else _day_number(start)
        low = raw_low % 7
        high = _day_number(end) if end is not None else 6
        if end is not None and raw_low == high:
            # Equal endpoints name one day, matching the SDK's existing
            # sun-sun behavior. They must never expand to a whole week.
            values = [low]
        elif low <= high:
            # Retain an explicit numeric 7 at the end of a range so 1-7/2
            # includes Monday/Wednesday/Friday/Sunday before alias folding.
            values = list(range(low, high + 1))
        else:
            # A wrapped range follows the actual order of days. For example,
            # 6-1/2 visits [Saturday, Sunday, Monday] and selects Sat/Mon.
            values = list(range(low, 7)) + list(range(0, high + 1))
        selected.update(number % 7 for number in values[::step])
    if len(selected) == 7:
        return "*"
    return ",".join(_DAY_NAMES[number] for number in sorted(selected))


def parse_cron(expression: str) -> dict[str, str]:
    """Return schedule_cron keyword fields; invalid/unsupported weekdays raise.

    Six-field expressions start with seconds, as in the host editor. Empty
    schedules are handled by the caller before parsing. Monthly nth/last
    weekday modifiers cannot be represented by this SDK's weekday field and
    are rejected instead of being silently treated as a weekly subscription.
    """
    if not isinstance(expression, str) or len(expression) > 512:
        raise ValueError("Cron 表达式格式无效")
    parts = expression.split()
    if len(parts) not in (5, 6):
        raise ValueError("Cron 必须包含五个字段（分、时、日、月、星期）或六个字段（秒、分、时、日、月、星期）")
    second = parts.pop(0) if len(parts) == 6 else "0"
    minute, hour, day, month, day_of_week = parts
    return {"second": second, "minute": minute, "hour": hour,
            "day": day, "month": month, "day_of_week": _weekdays(day_of_week)}
