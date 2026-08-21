# =============================================================================
# AWBotNest 插件：关键词互动助手（keyword_auto_reply）
#
# 用户账号监听群消息，命中关键词就自动回复。
# 配置全是普通表单项：规则一行一条「关键词=回复内容」，无需懂 JSON。
# =============================================================================

import asyncio
import html
import random
import re
import time
from datetime import datetime, timedelta

__plugin__ = {
    "name": "关键词互动助手",
    "id": "keyword_auto_reply",
    "version": "2.1.0",
    "author": "AWdress",
    "description": "群消息命中关键词后自动回复，支持冷却、限群、自动删除及可选薅羊毛排行榜。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_reply.png",
    "changelog": "v2.1.0 新增逐规则榜单统计与趣味回复\n- 每条规则可独立选择是否计入薅羊毛排行榜\n- 支持设置趣味文字出现概率，并从多条文案中随机回复\n- 未命中趣味概率时继续发送原标准回复\n\nv2.0.2 恢复逐规则零点重置\n- 冷却计算方式移入每条规则，可选滚动小时或每日零点重置\n- 旧版全局零点重置设置自动迁移到已有规则\n\nv2.0.1 新增逐规则触发方式\n- 每条规则可选择普通关键词或仅在回复我的消息时触发\n- 旧规则默认保持普通关键词触发，不改变现有行为\n\nv2.0.0 Vue 规则编辑器与独立规则策略\n- 新增 Vue 配置页，规则支持展开编辑、排序和复制\n- 每条规则独立设置匹配方式、冷却时间和冷却提示\n- 旧版全局匹配与冷却配置自动迁移到已有规则\n- 完善空状态、保存校验、移动端布局与键盘焦点\n\nv1.1.1 调整插件定位与名称\n- 更名为‘关键词互动助手’，突出关键词自动回复核心能力\n- 薅羊毛排行榜保留为可选附加功能\n- 配置说明覆盖提示、互动和福利等用途\n\nv1.1.0 新增薅羊毛排行榜\n- 成功发放福利后按账号、群组和用户持久化累计次数\n- 群内发送可配置命令查看当前群薅羊毛排行榜\n\nv1.0.9 持久化关键词冷却\n- 冷却记录写入插件专属 ctx.kv，平台或容器重启后继续生效\n- 插件更新、停用重启后自动恢复有效记录，并清理过期数据\n\nv1.0.8 适配平台后台任务治理\n- 回复与冷却提示的延迟删除任务改由 ctx.create_task 托管\n- 插件停用或重载时不再遗留等待中的删除任务\n\nv1.0.6 优化配置界面布局\n- 开关字段统一置顶，采用推荐的栅格布局\n- 参数字段添加 order 排序，提升扫描性\n- 符合 AWBotNest 插件开发规范\n\nv1.0.5 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示\n\nv1.0.4 恢复冷却提示回复\n- 每条关键词规则重新提供“冷却时提示”开关，现有规则默认开启\n- 冷却命中时回复剩余小时、分钟或秒数，零点重置模式显示距零点时间\n- 冷却提示沿用回复自动删除时间\n\nv1.0.3 优化规则配置\n- 关键词规则改用列表控件，群组范围改用会话选择器",
    "scope": "user",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "default_enabled": False,
    "render_mode": "vue",
    "config_schema": {
        # —— 功能开关（最上方，cols:3, order:1-4）——
        "enabled": {
            "type": "boolean", "default": True, "label": "启用关键词互动",
            "cols": 3, "order": 1, "section": "功能开关",
        },
        "midnight_reset": {
            "type": "boolean", "default": False, "label": "冷却每天零点清零",
            "cols": 3, "order": 2, "section": "功能开关",
        },
        "leaderboard_enabled": {
            "type": "boolean", "default": True, "label": "启用薅羊毛排行榜",
            "cols": 3, "order": 3, "section": "功能开关",
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
            "help": "命中关键词自动回复，可用于提示、互动或发福利。回复里可用 {uname}（对方昵称）、{uid}（对方ID）、a-b（a到b的随机数）。",
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
            "help": "关键词回复和羊毛榜发出后多少秒自动撤回；0 = 不删除。",
        },
        "blacklist_ids": {
            "type": "text", "default": "", "label": "屏蔽用户ID",
            "order": 23, "section": "范围与冷却",
            "help": "这些用户的消息不触发回复。一行一个或逗号分隔的用户ID。",
        },
        "leaderboard_command": {
            "type": "string", "default": ".羊毛榜", "label": "排行榜命令",
            "order": 30, "section": "薅羊毛排行榜",
            "help": "群内发送该命令，查看当前群累计领取福利次数。",
        },
        "leaderboard_size": {
            "type": "slider", "default": 10, "label": "显示人数",
            "min": 3, "max": 30, "step": 1, "order": 31, "section": "薅羊毛排行榜",
        },
    },
}

# 冷却记录：{(稳定账号标识, 用户id, 关键词): (最后触发时间戳, 触发日序号)}
_user_cooldowns: dict[tuple[str, int, str], tuple[float, int]] = {}
_COOLDOWNS_KV_KEY = "user_cooldowns_v1"
_LEADERBOARD_KV_KEY = "welfare_leaderboard_v1"
# 自动删除后台任务，停用时统一取消
_pending_tasks: set = set()


def _parse_rules(raw, *, default_match: str = "contains", default_cooldown: float = 24, default_midnight: bool = False) -> list[tuple[str, str, bool, str, float, str, bool, bool, float, list[str]]]:
    """解析规则；旧配置自动继承原来的全局匹配方式与冷却时间。"""
    rules: list[tuple[str, str, bool, str, float, str, bool, bool, float, list[str]]] = []
    if isinstance(raw, list):
        for d in raw:
            if isinstance(d, dict):
                keyword, reply = str(d.get("keyword", "")).strip(), str(d.get("reply", "")).strip()
                if keyword and reply:
                    match_type = str(d.get("match_type", default_match) or default_match)
                    if match_type not in {"contains", "exact"}:
                        match_type = default_match
                    try:
                        cooldown = max(0.0, min(720.0, float(d.get("cooldown_hours", default_cooldown))))
                    except (TypeError, ValueError):
                        cooldown = default_cooldown
                    trigger_mode = str(d.get("trigger_mode", "any") or "any")
                    if trigger_mode not in {"any", "reply_to_me"}:
                        trigger_mode = "any"
                    reset_at_midnight = bool(d.get("reset_at_midnight", default_midnight))
                    count_for_leaderboard = bool(d.get("count_for_leaderboard", True))
                    try:
                        fun_reply_chance = max(0.0, min(100.0, float(d.get("fun_reply_chance", 0) or 0)))
                    except (TypeError, ValueError):
                        fun_reply_chance = 0.0
                    raw_fun_replies = d.get("fun_replies", "")
                    if isinstance(raw_fun_replies, list):
                        fun_replies = [str(item).strip() for item in raw_fun_replies if str(item).strip()]
                    else:
                        fun_replies = [line.strip() for line in str(raw_fun_replies or "").splitlines() if line.strip()]
                    rules.append((keyword, reply, bool(d.get("cooldown_notify", True)), match_type, cooldown, trigger_mode, reset_at_midnight, count_for_leaderboard, fun_reply_chance, fun_replies))
        return rules
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keyword, reply = line.split("=", 1)
        keyword, reply = keyword.strip(), reply.strip()
        if keyword and reply:
            rules.append((keyword, reply, True, default_match, default_cooldown, "any", default_midnight, True, 0.0, []))
    return rules


def _match(text: str, keyword: str, match_type: str) -> bool:
    if match_type == "exact":
        return text.strip() == keyword
    return keyword in text  # contains


def _is_reply_to_me(message) -> bool:
    """当前消息是否回复了本账号发出的消息。"""
    replied = getattr(message, "reply_to_message", None)
    sender = getattr(replied, "from_user", None) if replied else None
    return bool(sender and getattr(sender, "is_self", False))


def _save_cooldowns(ctx) -> None:
    """将内存冷却记录保存为 JSON 友好的列表。"""
    rows = [
        {
            "account": account,
            "user_id": user_id,
            "keyword": keyword,
            "last_time": last_time,
            "last_day": last_day,
        }
        for (account, user_id, keyword), (last_time, last_day) in _user_cooldowns.items()
    ]
    ctx.kv.set(_COOLDOWNS_KV_KEY, rows)


def _restore_cooldowns(ctx) -> None:
    """恢复仍在当前冷却窗口内的记录，并顺便清理过期或损坏数据。"""
    _user_cooldowns.clear()
    raw = ctx.kv.get(_COOLDOWNS_KV_KEY, []) or []
    if not isinstance(raw, list):
        ctx.kv.set(_COOLDOWNS_KV_KEY, [])
        return

    cfg = ctx.config
    midnight_reset = bool(cfg.get("midnight_reset", False))
    try:
        default_cooldown = float(cfg.get("cooldown_hours", 24) or 24)
    except (TypeError, ValueError):
        default_cooldown = 24
    rules = _parse_rules(
        cfg.get("rules_text", []),
        default_match=str(cfg.get("match_type", "contains")),
        default_cooldown=default_cooldown,
        default_midnight=midnight_reset,
    )
    cooldown_secs = max((rule[4] for rule in rules), default=0) * 3600
    has_midnight_rule = any(rule[6] and rule[4] > 0 for rule in rules)
    now = time.time()
    today = datetime.now().date().toordinal()

    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            account = str(item["account"])
            user_id = int(item["user_id"])
            keyword = str(item["keyword"])
            last_time = float(item["last_time"])
            last_day = int(item.get("last_day", today))
        except (KeyError, TypeError, ValueError):
            continue
        if not account or not keyword or last_time <= 0:
            continue
        valid = ((has_midnight_rule and last_day == today) or
                 (cooldown_secs > 0 and now - last_time < cooldown_secs))
        if valid:
            _user_cooldowns[(account, user_id, keyword)] = (last_time, last_day)

    _save_cooldowns(ctx)


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


def _display_name(user) -> str:
    if not user:
        return "未知用户"
    name = " ".join(filter(None, (
        str(getattr(user, "first_name", "") or "").strip(),
        str(getattr(user, "last_name", "") or "").strip(),
    )))
    if name:
        return name
    username = str(getattr(user, "username", "") or "").strip()
    return f"@{username}" if username else f"用户{getattr(user, 'id', '')}"


async def _refresh_leaderboard_names(ctx, client, account: str, chat_id: int) -> None:
    """查询榜单时刷新旧记录昵称，链接仍始终使用稳定用户 ID。"""
    rows = ctx.kv.get(_LEADERBOARD_KV_KEY, []) or []
    if not isinstance(rows, list):
        return
    targets = [item for item in rows if isinstance(item, dict)
               and str(item.get("account")) == account
               and int(item.get("chat_id", 0)) == chat_id
               and int(item.get("user_id", 0))]
    if not targets:
        return
    try:
        users = await client.get_users([int(item["user_id"]) for item in targets])
        if not isinstance(users, list):
            users = [users]
        by_id = {int(user.id): user for user in users if user}
        changed = False
        for item in targets:
            user = by_id.get(int(item["user_id"]))
            if user and item.get("name") != _display_name(user):
                item["name"] = _display_name(user)
                changed = True
        if changed:
            ctx.kv.set(_LEADERBOARD_KV_KEY, rows)
    except Exception as exc:  # noqa: BLE001 - 昵称刷新失败继续使用已保存名称
        ctx.log.debug("[羊毛榜] 刷新用户昵称失败：%r", exc)


def _record_welfare(ctx, account: str, chat_id: int, user, keyword: str) -> None:
    if not user:
        return
    rows = ctx.kv.get(_LEADERBOARD_KV_KEY, []) or []
    if not isinstance(rows, list):
        rows = []
    user_id = int(user.id)
    row = next((item for item in rows if isinstance(item, dict)
                and str(item.get("account")) == account
                and int(item.get("chat_id", 0)) == chat_id
                and int(item.get("user_id", 0)) == user_id), None)
    if row is None:
        row = {"account": account, "chat_id": chat_id, "user_id": user_id, "count": 0}
        rows.append(row)
    row.update({
        "name": _display_name(user),
        "count": int(row.get("count", 0) or 0) + 1,
        "last_keyword": keyword,
        "last_time": int(time.time()),
    })
    ctx.kv.set(_LEADERBOARD_KV_KEY, rows)


def _leaderboard_text(ctx, account: str, chat_id: int, limit: int) -> str:
    rows = ctx.kv.get(_LEADERBOARD_KV_KEY, []) or []
    selected = [item for item in rows if isinstance(item, dict)
                and str(item.get("account")) == account
                and int(item.get("chat_id", 0)) == chat_id]
    selected.sort(key=lambda item: (-int(item.get("count", 0) or 0), int(item.get("last_time", 0) or 0)))
    if not selected:
        return "🐑 薅羊毛排行榜\n\n还没有人领取过福利。"
    medals = ("🥇", "🥈", "🥉")
    lines = ["🐑 薅羊毛排行榜", ""]
    for index, item in enumerate(selected[:max(3, min(30, limit))]):
        rank = medals[index] if index < 3 else f"{index + 1}."
        lines.append(f"{rank} {item.get('name') or '未知用户'} — {int(item.get('count', 0) or 0)} 次")
    lines.extend(["", f"累计上榜 {len(selected)} 人"])
    return "\n".join(lines)


def _leaderboard_rich(ctx, account: str, chat_id: int, limit: int) -> str:
    rows = ctx.kv.get(_LEADERBOARD_KV_KEY, []) or []
    selected = [item for item in rows if isinstance(item, dict)
                and str(item.get("account")) == account
                and int(item.get("chat_id", 0)) == chat_id]
    selected.sort(key=lambda item: (-int(item.get("count", 0) or 0), int(item.get("last_time", 0) or 0)))
    selected = selected[:max(3, min(30, limit))]
    if not selected:
        return "<h2>🐑 薅羊毛排行榜</h2><p>还没有人领取过福利。</p>"
    medals = ("🥇", "🥈", "🥉")
    table_rows = ['<tr><th align="center">排名</th><th align="left">用户</th><th align="right">领取次数</th></tr>']
    for index, item in enumerate(selected):
        rank = medals[index] if index < 3 else str(index + 1)
        name = html.escape(str(item.get("name") or "未知用户"))
        user_id = int(item.get("user_id", 0) or 0)
        user = f'<a href="tg://user?id={user_id}">{name}</a>' if user_id else name
        if index < 3:
            user = f"<b>{user}</b>"
        table_rows.append(
            f'<tr><td align="center"><b>{rank}</b></td>'
            f'<td align="left">{user}</td>'
            f'<td align="right"><b>{int(item.get("count", 0) or 0)}</b></td></tr>'
        )
    return (
        f"<h2>🐑 薅羊毛排行榜 TOP{len(selected)}</h2>\n"
        f'<table bordered striped>{"".join(table_rows)}</table>\n'
        f"<p>累计上榜 {len([x for x in rows if isinstance(x, dict) and str(x.get('account')) == account and int(x.get('chat_id', 0)) == chat_id])} 人</p>"
    )


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


def _choose_reply(standard_reply: str, fun_reply_chance: float, fun_replies: list[str]) -> str:
    """按百分比选择趣味文案；未配置或未命中时返回标准回复。"""
    if fun_replies and fun_reply_chance > 0 and random.random() * 100 < fun_reply_chance:
        return random.choice(fun_replies)
    return standard_reply


def _schedule_delete(ctx, message, delay: int):
    if delay <= 0:
        return

    async def _runner():
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except Exception:
            pass

    task = ctx.create_task(_runner(), name="关键词回复自动删除", operation="auto_delete")
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


def _schedule_delete_rich(ctx, client, chat_id: int, sent_at: float, delay: int):
    """原生 Rich Message 不返回消息对象时，按发送时间回查并撤回。"""
    if delay <= 0:
        return

    async def _runner():
        try:
            await asyncio.sleep(delay)
            async for item in client.get_chat_history(chat_id, limit=30):
                date = getattr(item, "date", None)
                timestamp = date.timestamp() if date else 0
                if timestamp < sent_at - 3:
                    break
                if abs(timestamp - sent_at) > 10 or not getattr(item, "outgoing", False):
                    continue
                content = str(getattr(item, "text", "") or getattr(item, "caption", "") or "")
                if content and "薅羊毛排行榜" not in content:
                    continue
                await item.delete()
                return
        except Exception as exc:  # noqa: BLE001 - 自动删除失败不影响主流程
            ctx.log.warning("[羊毛榜] 富文本自动删除失败：%r", exc)

    task = ctx.create_task(_runner(), name="羊毛榜富文本自动删除", operation="auto_delete")
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
    _restore_cooldowns(ctx)
    ctx.log.info("[关键词回复] 已恢复 %d 条有效冷却记录", len(_user_cooldowns))

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

        chat_ids_str = cfg.get("chat_ids", "")
        chat_id = message.chat.id
        if not _check_chat_id(chat_id, chat_ids_str):
            return

        me = getattr(client, "me", None)
        if me is None:
            try:
                me = await client.get_me()
            except Exception:
                me = None
        account_id = str(me.id) if me else str(getattr(ctx, "account_name", "") or "default")
        leaderboard_command = str(cfg.get("leaderboard_command", ".羊毛榜") or ".羊毛榜").strip()
        if leaderboard_command and text.strip() == leaderboard_command:
            sender_id = int(getattr(getattr(message, "from_user", None), "id", 0) or 0)
            own_id = int(getattr(me, "id", 0) or 0)
            if not cfg.get("leaderboard_enabled", True) or not own_id or sender_id != own_id:
                return
            await _refresh_leaderboard_names(ctx, client, account_id, chat_id)
            try:
                limit = int(cfg.get("leaderboard_size", 10) or 10)
            except (TypeError, ValueError):
                limit = 10
            try:
                leaderboard_delete_after = int(cfg.get("delete_after", 0) or 0)
            except (TypeError, ValueError):
                leaderboard_delete_after = 0
            sent = None
            rich_sent = False
            rich_sent_at = 0.0
            try:
                if ctx.user and await ctx.user.supports_native_rich():
                    rich_sent_at = time.time()
                    sent = await ctx.user.send_rich(
                        chat_id, _leaderboard_rich(ctx, account_id, chat_id, limit), format="html"
                    )
                    rich_sent = True
            except Exception as exc:  # noqa: BLE001 - Premium 不可用时回退普通文本
                ctx.log.warning("[羊毛榜] 富文本发送失败，回退普通文本：%r", exc)
            if not rich_sent:
                sent = await client.send_message(
                    chat_id, _leaderboard_text(ctx, account_id, chat_id, limit),
                    reply_to_message_id=message.id,
                )
            if rich_sent and sent is None:
                _schedule_delete_rich(ctx, client, chat_id, rich_sent_at, leaderboard_delete_after)
            else:
                _schedule_delete(ctx, sent, leaderboard_delete_after)
            try:
                await message.delete()
            except Exception as exc:  # noqa: BLE001 - 无删除权限不影响榜单发送
                ctx.log.warning("[羊毛榜] 查询命令删除失败：%r", exc)
            return

        try:
            default_cooldown = float(cfg.get("cooldown_hours", 24) or 24)
        except (TypeError, ValueError):
            default_cooldown = 24
        rules = _parse_rules(
            cfg.get("rules_text", []),
            default_match=str(cfg.get("match_type", "contains")),
            default_cooldown=default_cooldown,
            default_midnight=bool(cfg.get("midnight_reset", False)),
        )
        if not rules:
            return
        blacklist = _parse_blacklist(cfg.get("blacklist_ids", ""))
        # 屏蔽名单用户的消息不触发
        if message.from_user and message.from_user.id in blacklist:
            return
        try:
            delete_after = int(cfg.get("delete_after", 0) or 0)
        except (ValueError, TypeError):
            delete_after = 0

        try:
            for keyword, reply, cooldown_notify, match_type, cooldown_hours, trigger_mode, reset_at_midnight, count_for_leaderboard, fun_reply_chance, fun_replies in rules:
                if not _match(text, keyword, match_type):
                    continue
                if trigger_mode == "reply_to_me" and not _is_reply_to_me(message):
                    continue

                cooldown_secs = cooldown_hours * 3600

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
                    if reset_at_midnight and last_time > 0 and last_day != today:
                        last_time = 0.0
                    if time.time() - last_time < cooldown_secs:
                        if cooldown_notify:
                            if reset_at_midnight:
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
                            _schedule_delete(ctx, cd_msg, delete_after)
                        continue
                    _user_cooldowns[key] = (time.time(), today)
                    _save_cooldowns(ctx)

                selected_reply = _choose_reply(reply, fun_reply_chance, fun_replies)
                sent = await client.send_message(
                    chat_id, _render(selected_reply, message), reply_to_message_id=message.id
                )
                if count_for_leaderboard:
                    _record_welfare(ctx, account_id, chat_id, message.from_user, keyword)
                _schedule_delete(ctx, sent, delete_after)
                chat_name = getattr(message.chat, "title", None) or str(chat_id)
                ctx.log.info("[关键词回复] 命中 '%s' | 群组 %s (%s)",
                             keyword, chat_name, chat_id)
                break  # 一条消息只回第一个命中的规则
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[关键词回复] 处理消息出错: %r", e)


async def teardown(ctx):
    for task in list(_pending_tasks):
        task.cancel()
    _pending_tasks.clear()
