# =============================================================================
# AWBotNest 插件：关键词自动回复（keyword_auto_reply）
#
# 用户账号监听群消息，命中关键词就自动回复。
# 配置全是普通表单项：规则一行一条「关键词=回复内容」，无需懂 JSON。
# =============================================================================

import asyncio
import random
import re
import time
from datetime import datetime, timedelta

__plugin__ = {
    "name": "关键词自动回复",
    "id": "keyword_auto_reply",
    "version": "2.0.0",
    "author": "AW",
    "description": "群里有人说到关键词，自动回复一句。规则一行一条「关键词=回复」，支持冷却、限群、自动删除。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": True, "label": "启用关键词回复",
            "section": "总开关",
        },

        # —— 规则：一行一条 ——
        "rules_text": {
            "type": "text", "default": "", "label": "关键词规则",
            "section": "规则",
            "help": (
                "一行一条规则，格式：关键词=回复内容\n"
                "例如：\n"
                "你好=你好呀 {uname}~\n"
                "签到=签到成功，获得 1-100 积分\n"
                "回复里可用 {uname}（对方昵称）、{uid}（对方ID）、a-b（a到b的随机数）。"
            ),
        },
        "match_type": {
            "type": "select", "default": "contains", "label": "匹配方式",
            "section": "规则",
            "options": [
                {"value": "contains", "label": "包含关键词即触发"},
                {"value": "exact", "label": "消息完全等于关键词才触发"},
            ],
        },

        # —— 范围与冷却 ——
        "chat_ids": {
            "type": "string", "default": "", "label": "只在这些群生效（可选）",
            "section": "范围与冷却",
            "help": "群组ID，多个用英文逗号隔开。留空 = 所有群都生效。",
        },
        "cooldown_hours": {
            "type": "slider", "default": 24, "label": "同一个人冷却(小时)",
            "min": 0, "max": 72, "step": 1, "section": "范围与冷却",
            "help": "同一个人触发后多久内不再回复他。0 = 不限制。",
        },
        "midnight_reset": {
            "type": "boolean", "default": False, "label": "冷却每天零点清零",
            "section": "范围与冷却",
        },
        "delete_after": {
            "type": "slider", "default": 0, "label": "回复自动删除(秒)",
            "min": 0, "max": 600, "step": 10, "section": "范围与冷却",
            "help": "回复发出后多少秒自动撤回；0 = 不删除。",
        },
    },
}

# 冷却记录：{(账号id, 用户id, 关键词): (最后触发时间戳, 触发日序号)}
_user_cooldowns: dict[tuple, tuple[float, int]] = {}
# 自动删除后台任务，停用时统一取消
_pending_tasks: set = set()


def _parse_rules(text: str) -> list[tuple[str, str]]:
    """把多行「关键词=回复」解析成 [(关键词, 回复), ...]。"""
    rules: list[tuple[str, str]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keyword, reply = line.split("=", 1)
        keyword, reply = keyword.strip(), reply.strip()
        if keyword and reply:
            rules.append((keyword, reply))
    return rules


def _match(text: str, keyword: str, match_type: str) -> bool:
    if match_type == "exact":
        return text.strip() == keyword
    return keyword in text  # contains


def _check_chat_id(chat_id: int, chat_ids_str: str) -> bool:
    if not chat_ids_str:
        return True
    try:
        allowed = [int(c.strip()) for c in str(chat_ids_str).split(",") if c.strip()]
        return chat_id in allowed
    except ValueError:
        return True


def _render(reply: str, message=None) -> str:
    """渲染回复：a-b 随机数、{uid}/{uname}（昵称做 Markdown 转义）。"""
    pattern = re.compile(r"(?<!\d)(\+?)(\d+)-(\d+)(?!\d)")

    def _repl(m: re.Match) -> str:
        sign, start, end = m.group(1), int(m.group(2)), int(m.group(3))
        if start > end:
            start, end = end, start
        v = random.randint(start, end)
        return f"{sign}{v}" if sign else str(v)

    out = pattern.sub(_repl, reply)
    if message and message.from_user:
        uid = message.from_user.id
        uname = message.from_user.first_name or message.from_user.username or str(uid)
        for ch in ("\\", "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
            uname = uname.replace(ch, f"\\{ch}")
        out = out.replace("{uid}", str(uid)).replace("{uname}", uname)
    return out


def _schedule_delete(message, delay: int):
    if delay <= 0:
        return

    async def _runner():
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except Exception:
            pass

    task = asyncio.create_task(_runner())
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


async def setup(ctx):
    @ctx.on_message(
        ctx.filters.group & (ctx.filters.text | ctx.filters.caption),
        group=5,
    )
    async def keyword_listener(client, message):
        cfg = ctx.config
        if not cfg.get("enabled", True):
            return
        text = message.text or message.caption or ""
        if not text:
            return

        rules = _parse_rules(cfg.get("rules_text", ""))
        if not rules:
            return

        match_type = cfg.get("match_type", "contains")
        chat_ids_str = cfg.get("chat_ids", "")
        chat_id = message.chat.id
        if not _check_chat_id(chat_id, chat_ids_str):
            return

        me = getattr(client, "me", None)
        account_id = me.id if me else id(client)
        midnight_reset = bool(cfg.get("midnight_reset", False))
        try:
            cooldown_secs = max(0.0, float(cfg.get("cooldown_hours", 24))) * 3600
        except (ValueError, TypeError):
            cooldown_secs = 86400
        try:
            delete_after = int(cfg.get("delete_after", 0) or 0)
        except (ValueError, TypeError):
            delete_after = 0

        try:
            for keyword, reply in rules:
                if not _match(text, keyword, match_type):
                    continue

                user_id = message.from_user.id if message.from_user else None
                # 冷却（按 账号+用户+关键词）
                if user_id is not None and cooldown_secs > 0:
                    key = (account_id, user_id, keyword)
                    record = _user_cooldowns.get(key)
                    today = datetime.now().date().toordinal()
                    if isinstance(record, tuple):
                        last_time, last_day = record
                    else:
                        last_time, last_day = float(record or 0.0), today
                    if midnight_reset and last_time > 0 and last_day != today:
                        last_time = 0.0
                    if time.time() - last_time < cooldown_secs:
                        continue
                    _user_cooldowns[key] = (time.time(), today)

                sent = await client.send_message(
                    chat_id, _render(reply, message), reply_to_message_id=message.id
                )
                _schedule_delete(sent, delete_after)
                ctx.log.info("[关键词回复] 命中 '%s' | 群组 %s", keyword, chat_id)
                break  # 一条消息只回第一个命中的规则
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[关键词回复] 处理消息出错: %r", e)


async def teardown(ctx):
    for task in list(_pending_tasks):
        task.cancel()
    _pending_tasks.clear()
