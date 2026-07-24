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
    "version": "1.0.6",
    "author": "AWdress",
    "description": "群里有人说到关键词，自动回复一句。规则用列表逐条配置，支持冷却、限群、自动删除。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_reply.png",
    "changelog": "v1.0.6 优化配置界面布局\n- 开关字段统一置顶，采用推荐的栅格布局\n- 参数字段添加 order 排序，提升扫描性\n- 符合 AWBotNest 插件开发规范\n\nv1.0.5 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示\n\nv1.0.4 恢复冷却提示回复\n- 每条关键词规则重新提供“冷却时提示”开关，现有规则默认开启\n- 冷却命中时回复剩余小时、分钟或秒数，零点重置模式显示距零点时间\n- 冷却提示沿用回复自动删除时间\n\nv1.0.3 优化规则配置\n- 关键词规则改用列表控件，群组范围改用会话选择器",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        # —— 功能开关（最上方，cols:3, order:1-4）——
        "enabled": {
            "type": "boolean", "default": True, "label": "启用关键词回复",
            "cols": 3, "order": 1, "section": "功能开关",
        },
        "midnight_reset": {
            "type": "boolean", "default": False, "label": "冷却每天零点清零",
            "cols": 3, "order": 2, "section": "功能开关",
        },

        # —— 规则：逐条添加（order:10+）——
        "rules_text": {
            "type": "list", "default": [], "label": "关键词规则", "item_label": "规则",
            "order": 10, "section": "规则",
            "fields": {
                "keyword": {"type": "string", "label": "关键词"},
                "reply": {"type": "string", "label": "回复内容"},
                "cooldown_notify": {
                    "type": "boolean", "label": "冷却时提示", "default": True,
                },
            },
            "help": "命中关键词自动回一句。回复里可用 {uname}（对方昵称）、{uid}（对方ID）、a-b（a到b的随机数）。",
        },
        "match_type": {
            "type": "select", "default": "contains", "label": "匹配方式",
            "order": 11, "section": "规则",
            "options": [
                {"value": "contains", "label": "包含关键词即触发"},
                {"value": "exact", "label": "消息完全等于关键词才触发"},
            ],
        },

        # —— 范围与冷却参数（order:20+）——
        "chat_ids": {
            "type": "chat", "default": [], "label": "只在这些群生效（可选）", "multi": True,
            "chat_types": ["group"], "order": 20, "section": "范围与冷却",
            "help": "勾选生效的群；留空 = 所有群都生效。",
        },
        "cooldown_hours": {
            "type": "slider", "default": 24, "label": "同一个人冷却(小时)",
            "min": 0, "max": 72, "step": 1, "order": 21, "section": "范围与冷却",
            "help": "同一个人触发后多久内不再回复他。0 = 不限制。",
        },
        "delete_after": {
            "type": "slider", "default": 0, "label": "回复自动删除(秒)",
            "min": 0, "max": 600, "step": 10, "order": 22, "section": "范围与冷却",
            "help": "回复发出后多少秒自动撤回；0 = 不删除。",
        },
        "blacklist_ids": {
            "type": "text", "default": "", "label": "屏蔽用户ID",
            "order": 23, "section": "范围与冷却",
            "help": "这些用户的消息不触发回复。一行一个或逗号分隔的用户ID。",
        },
    },
}

# 冷却记录：{(账号id, 用户id, 关键词): (最后触发时间戳, 触发日序号)}
_user_cooldowns: dict[tuple, tuple[float, int]] = {}
# 自动删除后台任务，停用时统一取消
_pending_tasks: set = set()


def _parse_rules(raw) -> list[tuple[str, str, bool]]:
    """解析为 (关键词, 回复, 冷却提示)；旧规则没有开关时默认开启。"""
    rules: list[tuple[str, str, bool]] = []
    if isinstance(raw, list):
        for d in raw:
            if isinstance(d, dict):
                keyword, reply = str(d.get("keyword", "")).strip(), str(d.get("reply", "")).strip()
                if keyword and reply:
                    rules.append((keyword, reply, bool(d.get("cooldown_notify", True))))
        return rules
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keyword, reply = line.split("=", 1)
        keyword, reply = keyword.strip(), reply.strip()
        if keyword and reply:
            rules.append((keyword, reply, True))
    return rules


def _match(text: str, keyword: str, match_type: str) -> bool:
    if match_type == "exact":
        return text.strip() == keyword
    return keyword in text  # contains


def _check_chat_id(chat_id: int, chat_ids) -> bool:
    """兼容 chat 控件的 id 数组与旧的逗号分隔字符串。空=不限。"""
    if not chat_ids:
        return True
    items = chat_ids if isinstance(chat_ids, list) else str(chat_ids).split(",")
    try:
        allowed = [int(str(c).strip()) for c in items if str(c).strip()]
        return chat_id in allowed
    except ValueError:
        return True


def _parse_blacklist(raw) -> set[int]:
    """解析屏蔽用户ID（支持换行或逗号分隔）。"""
    ids: set[int] = set()
    for part in re.split(r"[,\s]+", str(raw or "")):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            pass
    return ids


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


def _fmt_remaining(seconds: float) -> str:
    """把剩余冷却时间格式化为易读文本，向上取整避免显示 0 秒。"""
    seconds = max(1, int(seconds + 0.999))
    if seconds >= 3600:
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        return f"{hours} 小时 {minutes} 分钟" if minutes else f"{hours} 小时"
    if seconds >= 60:
        minutes, remain_seconds = divmod(seconds, 60)
        return f"{minutes} 分钟 {remain_seconds} 秒" if remain_seconds else f"{minutes} 分钟"
    return f"{seconds} 秒"


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
        blacklist = _parse_blacklist(cfg.get("blacklist_ids", ""))
        # 屏蔽名单用户的消息不触发
        if message.from_user and message.from_user.id in blacklist:
            return
        try:
            cooldown_secs = max(0.0, float(cfg.get("cooldown_hours", 24))) * 3600
        except (ValueError, TypeError):
            cooldown_secs = 86400
        try:
            delete_after = int(cfg.get("delete_after", 0) or 0)
        except (ValueError, TypeError):
            delete_after = 0

        try:
            for keyword, reply, cooldown_notify in rules:
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
                        if cooldown_notify:
                            if midnight_reset:
                                now_dt = datetime.now()
                                next_midnight = datetime.combine(
                                    now_dt.date() + timedelta(days=1), datetime.min.time()
                                )
                                remaining = max(0.0, (next_midnight - now_dt).total_seconds())
                                cd_text = f"⏳ 冷却中，距零点重置还剩 {_fmt_remaining(remaining)}"
                            else:
                                remaining = cooldown_secs - (time.time() - last_time)
                                cd_text = f"⏳ 冷却中，距下次还剩 {_fmt_remaining(remaining)}"
                            cd_msg = await client.send_message(
                                chat_id, cd_text, reply_to_message_id=message.id
                            )
                            _schedule_delete(cd_msg, delete_after)
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
