# =============================================================================
# AWBotNest 插件：定时自动回复（custom_auto_reply）
#
# 用户账号按设定的时间，自动向指定会话发送消息。
# 每行一条规则「会话 | 时间 | 内容」，各自独立定时；不写时间则用「默认时间」。
# 平台 config_schema 无「可重复字段组」类型，故用多行文本承载多条规则。
# =============================================================================

__plugin__ = {
    "name": "定时自动回复",
    "id": "custom_auto_reply",
    "version": "1.0.7",
    "author": "AWdress",
    "description": "到点自动用你的账号往指定群/会话发消息。支持多个会话，每个会话可单独设时间和内容。时间支持每天定点、每隔几小时/几分钟、或 cron 表达式。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        # —— 必填：发给谁、发什么 ——
        "target_chat_id": {
            "type": "text", "default": "", "label": "会话 · 时间 · 内容",
            "section": "发送内容",
            "help": (
                "每行一条规则，各自独立定时。三种写法（用竖线 | 分隔，半角全角都行）：\n"
                "  会话\n"
                "  会话 | 内容\n"
                "  会话 | 时间 | 内容\n"
                "• 会话：群组/频道ID（形如 -1001234567890）或 @用户名，不知道可用「查ID」插件。\n"
                "• 时间（第2段）可写：`09:30`=每天9点半；`3h`=每隔3小时；`30m`=每隔30分钟；"
                "`0 9 * * 1-5`=cron(工作日9点)。不写时间这段就用下方「默认时间」。\n"
                "• 内容里想换行用 \\n。只填会话不带内容时用下方「默认消息」。\n"
                "例：\n"
                "  -1001111111111 | 09:00 | 早安\n"
                "  @mychannel | 30m | 每半小时刷一条\n"
                "  -1002222222222 | 晚安（用默认时间发）"
            ),
        },
        "message": {
            "type": "text", "default": "", "label": "默认消息（可选）",
            "section": "发送内容",
            "help": "对没单独写内容的会话使用这条。所有会话都各自写了内容时可留空。",
        },

        # —— 默认时间（对没单独写时间的行生效）——
        "frequency": {
            "type": "select", "default": "daily", "label": "默认发送频率",
            "section": "默认时间",
            "options": [
                {"value": "daily", "label": "每天定点（每天一次）"},
                {"value": "hours", "label": "每隔几小时循环发"},
                {"value": "minutes", "label": "每隔几分钟循环发"},
                {"value": "cron", "label": "自定义 cron 表达式（高级）"},
            ],
            "help": "仅对没在行内单独写时间的会话生效。注册后按规则反复发送。",
        },
        "daily_hour": {
            "type": "slider", "default": 9, "label": "每天几点", "min": 0, "max": 23, "step": 1,
            "section": "默认时间", "help": "24 小时制，0~23 点。", "show_if": {"frequency": "daily"},
        },
        "daily_minute": {
            "type": "slider", "default": 0, "label": "几分", "min": 0, "max": 59, "step": 1,
            "section": "默认时间", "show_if": {"frequency": "daily"},
        },
        "every_hours": {
            "type": "slider", "default": 3, "label": "每隔几小时", "min": 1, "max": 24, "step": 1,
            "section": "默认时间", "show_if": {"frequency": "hours"},
        },
        "every_minutes": {
            "type": "slider", "default": 30, "label": "每隔几分钟", "min": 1, "max": 180, "step": 1,
            "section": "默认时间", "show_if": {"frequency": "minutes"},
        },
        "cron_expr": {
            "type": "string", "default": "0 9 * * 1-5", "label": "cron 表达式",
            "section": "默认时间", "show_if": {"frequency": "cron"},
            "help": (
                "标准 5 段格式：分 时 日 月 周。星期 0/7=周日，1=周一。\n"
                "例：`0 9 * * 1-5` 工作日每天 9:00；`*/15 9-18 * * *` 9~18 点每 15 分钟一次；"
                "`30 8 1 * *` 每月 1 号 8:30。"
            ),
        },

        # —— 可选 ——
        "notify_owner": {
            "type": "boolean", "default": False, "label": "把结果通知给我",
            "section": "高级（可选）",
            "help": "每次发送成功/失败后，平台用机器人私聊你（或发到你账号的收藏夹）报一条。无需填ID。",
        },
    },
}


def _normalize_chat_id(raw):
    """目标会话：@用户名 原样返回，纯数字转 int，非法返回 None。"""
    s = str(raw or "").strip()
    if not s:
        return None
    if s.startswith("@"):
        return s
    try:
        return int(s)
    except ValueError:
        return None


def _parse_timespec(raw):
    """把行内时间段解析成触发规格 dict；无法识别返回 None。

    支持：`09:30`(每天定点) / `3h`(每N小时) / `45m`(每N分钟) / `0 9 * * 1-5`(cron5段)。
    返回形如 {"kind":"daily","hour":9,"minute":30} / {"kind":"interval","hours":3}
            / {"kind":"interval","minutes":45} / {"kind":"cron","expr":"..."}。
    """
    s = str(raw or "").strip()
    if not s:
        return None
    # cron：含空格且恰好 5 段
    if len(s.split()) == 5:
        return {"kind": "cron", "expr": s}
    low = s.lower()
    # HH:MM 每天定点
    if ":" in low or "：" in low:
        hh, _, mm = low.replace("：", ":").partition(":")
        try:
            h, m = int(hh), int(mm)
        except ValueError:
            return None
        if 0 <= h <= 23 and 0 <= m <= 59:
            return {"kind": "daily", "hour": h, "minute": m}
        return None
    # Nh / Nm 间隔
    if low.endswith("h"):
        try:
            n = int(low[:-1])
        except ValueError:
            return None
        return {"kind": "interval", "hours": n} if n >= 1 else None
    if low.endswith("m"):
        try:
            n = int(low[:-1])
        except ValueError:
            return None
        return {"kind": "interval", "minutes": n} if n >= 1 else None
    return None


def _parse_plan(raw, default_msg: str) -> list:
    """解析规则清单 → [(target, message, timespec)] 列表，去重、丢非法/空内容。

    每行三种写法（| 半角，｜全角）：
      `会话`               → default_msg + 默认时间(timespec=None)
      `会话 | 内容`         → 该内容 + 默认时间(timespec=None)
      `会话 | 时间 | 内容`  → 该内容 + 行内时间(timespec=dict)
    不带 | 的行可再按逗号/空格拆成多个会话，共用 default_msg + 默认时间。
    去重键为 (target, timespec)，允许同一会话不同时间多条规则。
    """
    plan, seen = [], set()
    for line in str(raw or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        norm = line.replace("｜", "|")
        if "|" in norm:
            parts = [p.strip() for p in norm.split("|")]
            if len(parts) >= 3:
                # 会话 | 时间 | 内容（内容里若还有 | 合并回去）
                chat_part = parts[0]
                time_part = parts[1]
                msg = "|".join(parts[2:]).strip().replace("\\n", "\n")
                timespec = _parse_timespec(time_part)
                if timespec is None:
                    # 第2段不是合法时间 → 整体当作内容（兼容 内容里带竖线）
                    msg = "|".join(parts[1:]).strip().replace("\\n", "\n")
            else:
                # 会话 | 内容
                chat_part = parts[0]
                msg = parts[1].strip().replace("\\n", "\n")
                timespec = None
            target = _normalize_chat_id(chat_part)
            if target is None or not msg:
                continue
            key = (target, _timespec_key(timespec))
            if key in seen:
                continue
            seen.add(key)
            plan.append((target, msg, timespec))
        else:
            # 无竖线：可能一行多个会话，共用默认消息 + 默认时间
            tokens = norm.replace(",", " ").replace("，", " ").split()
            for tok in tokens:
                target = _normalize_chat_id(tok)
                if target is None or not default_msg:
                    continue
                key = (target, None)
                if key in seen:
                    continue
                seen.add(key)
                plan.append((target, default_msg, None))
    return plan


def _timespec_key(timespec):
    """把 timespec dict 变成可哈希去重键。"""
    if timespec is None:
        return None
    return tuple(sorted(timespec.items()))


def _build_message_link(target_chat_id, msg_id) -> str:
    """尽力构建一条消息的可点击链接。"""
    if isinstance(target_chat_id, int) and target_chat_id < 0:
        gid = str(target_chat_id).replace("-100", "")
        return f"https://t.me/c/{gid}/{msg_id}"
    if isinstance(target_chat_id, str) and target_chat_id.startswith("@"):
        username = target_chat_id[1:]
        if username.lower().endswith("bot"):
            return f"目标: {target_chat_id}, 消息ID: {msg_id}"
        return f"https://t.me/{username}/{msg_id}"
    return f"消息ID: {msg_id}"


def _make_action(ctx, target, message_text):
    """生成单条规则的定时回调：用所有已连接用户账号发到指定会话。"""
    async def _action():
        user_apps = ctx.user_apps
        if not user_apps:
            ctx.log.error("[定时回复] 没有已连接的用户账号，跳过")
            return

        notify_owner = bool(ctx.config.get("notify_owner", False))

        for app in user_apps:
            me = getattr(app, "me", None)
            if me:
                acct = f"{me.first_name}(@{me.username})" if me.username else f"{me.first_name}(ID:{me.id})"
            else:
                acct = getattr(app, "name", "未知账号")

            try:
                sent = await app.send_message(target, message_text)
                ctx.log.info("[定时回复] [%s] → %s 发送成功 msg=%s", acct, target, sent.id)
            except Exception as send_err:  # noqa: BLE001
                ctx.log.error("[定时回复] [%s] → %s 发送失败: %r", acct, target, send_err)
                if notify_owner:
                    # 级别/插件名/账号名由平台统一格式化，这里只给业务内容
                    try:
                        await ctx.notify(
                            f"定时回复失败\n🎯 目标：{target}\n⚠️ 错误：{send_err}",
                            level="error", category="定时回复", account=app,
                        )
                    except Exception:
                        pass
                continue

            if notify_owner:
                link = _build_message_link(target, sent.id)
                preview = message_text[:100] + ("..." if len(message_text) > 100 else "")
                try:
                    await ctx.notify(
                        f"定时回复已发送\n🎯 目标：{target}\n📝 内容：\n{preview}\n🔗 {link}",
                        level="success", category="定时回复", account=app,
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass

    return _action


def _default_timespec(cfg):
    """把「默认时间」分区的表单值整理成一个 timespec dict。"""
    freq = cfg.get("frequency", "daily")
    if freq == "hours":
        return {"kind": "interval", "hours": int(cfg.get("every_hours", 3) or 3)}
    if freq == "minutes":
        return {"kind": "interval", "minutes": int(cfg.get("every_minutes", 30) or 30)}
    if freq == "cron":
        return {"kind": "cron", "expr": (cfg.get("cron_expr") or "").strip()}
    return {"kind": "daily",
            "hour": int(cfg.get("daily_hour", 9) or 0),
            "minute": int(cfg.get("daily_minute", 0) or 0)}


def _schedule_rule(ctx, action, timespec, job_id):
    """按 timespec 注册一个定时任务。成功返回触发描述字符串，失败返回 None。"""
    kind = timespec.get("kind")
    if kind == "interval":
        if "hours" in timespec:
            ctx.schedule(action, "interval", hours=timespec["hours"], id=job_id)
            return f"每 {timespec['hours']} 小时"
        ctx.schedule(action, "interval", minutes=timespec["minutes"], id=job_id)
        return f"每 {timespec['minutes']} 分钟"
    if kind == "cron":
        try:
            from apscheduler.triggers.cron import CronTrigger
            trigger = CronTrigger.from_crontab(timespec["expr"])
        except Exception as e:  # noqa: BLE001 - 表达式非法
            ctx.log.error("[定时回复] cron 表达式无效 %r：%r", timespec.get("expr"), e)
            return None
        ctx.schedule(action, trigger, id=job_id)
        return f"cron({timespec['expr']})"
    # daily
    ctx.schedule(action, "cron", hour=timespec["hour"], minute=timespec["minute"], id=job_id)
    return f"每天 {timespec['hour']:02d}:{timespec['minute']:02d}"


async def setup(ctx):
    cfg = ctx.config
    default_msg = (cfg.get("message") or "").strip()
    plan = _parse_plan(cfg.get("target_chat_id"), default_msg)
    if not plan:
        ctx.log.info("[定时回复] 尚未填写有效的会话/内容，未注册定时任务")
        return

    default_ts = _default_timespec(cfg)

    # 每条规则注册一个独立任务（改配置后需在平台「重载」本插件以重新注册）
    registered = 0
    for idx, (target, message_text, timespec) in enumerate(plan, start=1):
        ts = timespec or default_ts
        action = _make_action(ctx, target, message_text)
        desc = _schedule_rule(ctx, action, ts, job_id=f"定时回复#{idx}")
        if desc is None:
            ctx.log.error("[定时回复] 第 %d 条（→ %s）时间无效，已跳过", idx, target)
            continue
        registered += 1
        ctx.log.info("[定时回复] 已注册 #%d：%s → %s", idx, desc, target)

    ctx.log.info("[定时回复] 共注册 %d 条规则", registered)


async def teardown(ctx):
    # ctx.schedule 注册的任务由平台停用时自动移除
    pass
