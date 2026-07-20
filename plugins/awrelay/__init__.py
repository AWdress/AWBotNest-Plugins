"""AWRelay: Telegram 私聊与论坛话题之间的双向中转。"""

import asyncio
import html
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime

__plugin__ = {
    "name": "AWRelay",
    "id": "awrelay",
    "version": "1.1.1",
    "author": "AWdress",
    "description": "轻量自托管的 Telegram 私聊消息中转机器人。私聊转发到话题群组，管理员在话题内回复用户。内置人机验证、广告过滤、黑名单。",
    "changelog": "v1.1.1 修正定时任务显示\n- 旧消息映射清理改为每天凌晨 04:00 执行，避免状态页误显示每 0 秒\n\nv1.1.0 完成核心功能迁移并适配新版平台\n- 修复 Vue 配置保存时报 post 未定义的问题\n- 话题、消息映射、验证状态和黑名单改为持久化存储\n- 修复管理员消息监听与普通话题消息双向路由\n- 增加媒体组聚合、失效话题重建、转发失败提示及黑名单管理\n- 全部运行接口改用 ctx 平台能力\n\nv1.0.3 改为随机人机验证题\n- 每位待验证用户随机生成加减乘算术题\n- 配置页不再要求填写固定问题和答案\n\nv1.0.2 重新发布完整前端构建产物\n- 使用新版本号触发平台重新下载 frontend/dist\n\nv1.0.1 补充插件版本日志与前端构建产物\n- 确保配置界面可由平台正常加载\n\nv1.0.0 初始版本\n- 支持话题式私聊中转、人机验证、广告过滤、黑名单与限流",
    "scope": "bot",
    "default_enabled": False,
    "render_mode": "vue",
    "requirements": [],
}

DEFAULTS = {
    "enabled": False,
    "group_id": "",
    "admin_ids": "",
    "captcha_enabled": True,
    "spam_enabled": True,
    "spam_keywords": "USDT,博彩,兼职,t.me/,http://,https://",
    "rate_limit_window": 10,
    "rate_limit_count": 5,
    "media_group_delay": 2.0,
}

_captcha_pending = {}
_user_msg_times = defaultdict(deque)
_media_groups = {}
_media_tasks = set()


def _cfg(ctx):
    return {**DEFAULTS, **dict(ctx.config or {})}


def _dict(ctx, key):
    value = ctx.kv.get(key, {}) or {}
    return value if isinstance(value, dict) else {}


def _set_dict(ctx, key, value):
    ctx.kv.set(key, value)


def _topics(ctx):
    return _dict(ctx, "topics")


def _mappings(ctx):
    return _dict(ctx, "message_mappings")


def _ids(ctx, key):
    return {int(x) for x in (ctx.kv.get(key, []) or [])}


def _generate_captcha():
    operation = secrets.randbelow(3)
    if operation == 0:
        left, right = secrets.randbelow(20) + 1, secrets.randbelow(20) + 1
        return f"{left} + {right} = ?", str(left + right)
    if operation == 1:
        left = secrets.randbelow(20) + 1
        right = secrets.randbelow(left) + 1
        return f"{left} - {right} = ?", str(left - right)
    left, right = secrets.randbelow(8) + 2, secrets.randbelow(8) + 2
    return f"{left} × {right} = ?", str(left * right)


def _is_spam(text, cfg):
    words = [x.strip().lower() for x in str(cfg.get("spam_keywords", "")).replace("，", ",").split(",") if x.strip()]
    return bool(cfg.get("spam_enabled", True) and text and any(x in text.lower() for x in words))


def _configured_admins(cfg):
    raw = str(cfg.get("admin_ids", "")).replace("，", ",")
    return {int(item.strip()) for item in raw.split(",") if item.strip().lstrip("-").isdigit()}


def _command(message):
    parts = (getattr(message, "text", None) or "").split()
    return parts[0].split("@")[0].lower() if parts else ""


def _rate_limited(user_id, cfg):
    now = time.time()
    window = max(1, float(cfg.get("rate_limit_window", 10)))
    count = max(1, int(cfg.get("rate_limit_count", 5)))
    queue = _user_msg_times[user_id]
    while queue and now - queue[0] > window:
        queue.popleft()
    if len(queue) >= count:
        return True
    queue.append(now)
    return False


def _thread_id(message):
    return getattr(message, "message_thread_id", None) or (
        getattr(getattr(message, "reply_to_message", None), "id", None)
        if getattr(getattr(message, "reply_to_message", None), "forum_topic_created", None) else None
    )


async def _topic_for(ctx, client, user, cfg, force=False):
    topics = _topics(ctx)
    key = str(user.id)
    if not force and key in topics:
        return int(topics[key]["topic_id"])
    group_id = int(cfg.get("group_id") or 0)
    if not group_id:
        raise ValueError("请先配置话题群组")
    base = (f"{user.first_name or ''} {user.last_name or ''}".strip() or f"用户{user.id}")
    suffix = f" · {user.id}"
    topic = await client.create_forum_topic(group_id, base[:128 - len(suffix)] + suffix)
    topic_id = int(topic.id)
    topics[key] = {
        "topic_id": topic_id, "name": base, "username": user.username or "",
        "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _set_dict(ctx, "topics", topics)
    link = f'<a href="tg://user?id={user.id}">{html.escape(base)}</a>'
    username = f"  @{html.escape(user.username)}" if user.username else ""
    await client.send_message(group_id, f"{link}{username}\n🆔 <code>{user.id}</code>", reply_to_message_id=topic_id, parse_mode="html")
    return topic_id


def _save_mapping(ctx, sent_id, user_id, user_msg_id):
    mappings = _mappings(ctx)
    mappings[str(sent_id)] = {"user_id": user_id, "user_msg_id": user_msg_id, "created_at": time.time()}
    _set_dict(ctx, "message_mappings", mappings)


async def _forward_one(ctx, client, message, cfg):
    user = message.from_user
    topic_id = await _topic_for(ctx, client, user, cfg)
    group_id = int(cfg.get("group_id") or 0)
    try:
        sent = await message.copy(group_id, reply_to_message_id=topic_id)
    except Exception as exc:
        lowered = str(exc).lower()
        if not any(x in lowered for x in ("thread", "topic_deleted", "topic_closed")):
            raise
        topics = _topics(ctx)
        topics.pop(str(user.id), None)
        _set_dict(ctx, "topics", topics)
        topic_id = await _topic_for(ctx, client, user, cfg, force=True)
        sent = await message.copy(group_id, reply_to_message_id=topic_id)
    _save_mapping(ctx, sent.id, user.id, message.id)
    topics = _topics(ctx)
    if str(user.id) in topics:
        topics[str(user.id)]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _set_dict(ctx, "topics", topics)


async def _flush_media(ctx, client, media_id, cfg):
    try:
        await asyncio.sleep(max(0.1, float(cfg.get("media_group_delay", 2))))
        messages = _media_groups.pop(media_id, [])
        for message in sorted(messages, key=lambda item: item.id):
            await _forward_one(ctx, client, message, cfg)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        ctx.log.error("媒体组转发失败：%s", exc)


async def _send_to_user(client, user_id, message):
    try:
        await message.copy(user_id)
        return
    except Exception as exc:
        if "copy" not in str(exc).lower() and "protected" not in str(exc).lower():
            raise
    caption = getattr(message, "caption", None)
    if message.text:
        await client.send_message(user_id, message.text)
    elif message.photo:
        await client.send_photo(user_id, message.photo.file_id, caption=caption)
    elif message.video:
        await client.send_video(user_id, message.video.file_id, caption=caption)
    elif message.document:
        await client.send_document(user_id, message.document.file_id, caption=caption)
    elif message.audio:
        await client.send_audio(user_id, message.audio.file_id, caption=caption)
    elif message.voice:
        await client.send_voice(user_id, message.voice.file_id)
    elif message.sticker:
        await client.send_sticker(user_id, message.sticker.file_id)
    elif message.video_note:
        await client.send_video_note(user_id, message.video_note.file_id)
    else:
        raise ValueError("不支持的消息类型")


async def setup(ctx):
    filters = ctx.filters

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(req):
        cfg = _cfg(ctx)
        topics = _topics(ctx)
        return {"bot_running": bool(cfg["enabled"]), "bot_status": "运行中" if cfg["enabled"] else "已停止",
                "group_title": str(cfg.get("group_id") or "-"), "active_users": len(topics),
                "total_topics": len(topics), "banned_users": len(_ids(ctx, "banned_users"))}

    @ctx.on_api("/topics", methods=["GET"])
    async def api_topics(req):
        banned = _ids(ctx, "banned_users")
        items = []
        for user_id, record in _topics(ctx).items():
            items.append({"name": record.get("name") or f"User {user_id}", "user_id": int(user_id),
                          "topic_id": record.get("topic_id"), "last_active": record.get("last_active", "-"),
                          "status": "已封禁" if int(user_id) in banned else "正常"})
        return {"topics": sorted(items, key=lambda item: item["last_active"], reverse=True)}

    @ctx.on_api("/ban", methods=["POST"])
    async def api_ban(req):
        data = await req.json()
        user_id = int(data.get("user_id"))
        banned = _ids(ctx, "banned_users")
        if data.get("banned", True): banned.add(user_id)
        else: banned.discard(user_id)
        ctx.kv.set("banned_users", sorted(banned))
        return {"ok": True}

    @ctx.on_message(filters.private & filters.incoming, group=10)
    async def private_message(client, message):
        cfg = _cfg(ctx)
        if not cfg["enabled"] or not message.from_user:
            return
        user = message.from_user
        if user.id in _ids(ctx, "banned_users"):
            return
        command = _command(message)
        if command in ("/start", "/help"):
            await message.reply("👋 直接给我发送消息即可转达给管理员，请耐心等待回复。")
            return
        verified = _ids(ctx, "verified_users")
        if cfg["captcha_enabled"] and user.id not in verified:
            pending = _captcha_pending.get(user.id)
            if pending:
                if (message.text or "").strip() == pending["answer"]:
                    verified.add(user.id)
                    ctx.kv.set("verified_users", sorted(verified))
                    _captcha_pending.pop(user.id, None)
                    await message.reply("✅ 验证成功！请重新发送需要转达的消息。")
                else:
                    question, answer = _generate_captcha()
                    _captcha_pending[user.id] = {"answer": answer}
                    await message.reply(f"❌ 答案不对，请再试一次：\n\n{question}")
                return
            question, answer = _generate_captcha()
            _captcha_pending[user.id] = {"answer": answer}
            await message.reply(f"🤖 人机验证\n\n{question}")
            return
        if _rate_limited(user.id, cfg):
            await message.reply("⏳ 您发送得太频繁了，请稍后再试。")
            return
        if _is_spam(message.text or message.caption or "", cfg):
            ctx.log.info("拦截疑似广告消息：用户 %s", user.id)
            return
        media_id = getattr(message, "media_group_id", None)
        if media_id:
            _media_groups.setdefault(str(media_id), []).append(message)
            if len(_media_groups[str(media_id)]) == 1:
                task = asyncio.create_task(_flush_media(ctx, client, str(media_id), cfg))
                _media_tasks.add(task)
                task.add_done_callback(_media_tasks.discard)
            return
        try:
            await _forward_one(ctx, client, message, cfg)
        except Exception as exc:
            ctx.log.error("消息转发失败（用户 %s）：%s", user.id, exc)
            await message.reply("❌ 消息转发失败，请确认话题群配置和 Bot 权限后重试。")

    @ctx.on_message(filters.incoming, group=20)
    async def admin_message(client, message):
        cfg = _cfg(ctx)
        if not cfg["enabled"] or not cfg.get("group_id") or message.chat.id != int(cfg["group_id"]):
            return
        if not message.from_user or message.from_user.is_bot:
            return
        admins = _configured_admins(cfg)
        if admins and message.from_user.id not in admins:
            return
        mappings = _mappings(ctx)
        reply_id = str(getattr(message, "reply_to_message_id", "") or "")
        mapping = mappings.get(reply_id)
        topic_id = _thread_id(message)
        topics = _topics(ctx)
        user_id = int(mapping["user_id"]) if mapping else next(
            (int(uid) for uid, item in topics.items() if int(item.get("topic_id", 0)) == int(topic_id or 0)), 0)
        command = _command(message)
        if command in ("/ban", "/unban"):
            if not user_id:
                await message.reply("⚠️ 请在用户话题内使用，或回复一条用户消息。")
                return
            banned = _ids(ctx, "banned_users")
            banned.add(user_id) if command == "/ban" else banned.discard(user_id)
            ctx.kv.set("banned_users", sorted(banned))
            await message.reply("🚫 已拉黑该用户。" if command == "/ban" else "✅ 已解除该用户黑名单。")
            return
        if command == "/help":
            await message.reply("在用户话题内直接发送或回复消息即可回传。回复用户消息后使用 /ban 或 /unban 管理黑名单。")
            return
        if not user_id or (message.text or "").startswith("/"):
            return
        try:
            await _send_to_user(client, user_id, message)
        except Exception as exc:
            ctx.log.error("回复用户 %s 失败：%s", user_id, exc)
            await message.reply(f"❌ 发送失败：<code>{html.escape(str(exc))}</code>", parse_mode="html")

    async def cleanup_mappings():
        cutoff = time.time() - 7 * 86400
        mappings = _mappings(ctx)
        kept = {key: value for key, value in mappings.items() if float(value.get("created_at", 0)) >= cutoff}
        if len(kept) != len(mappings):
            _set_dict(ctx, "message_mappings", kept)

    ctx.schedule(cleanup_mappings, "cron", hour=4, minute=0, id="清理旧消息映射")


async def teardown(ctx):
    for task in list(_media_tasks):
        task.cancel()
    if _media_tasks:
        await asyncio.gather(*_media_tasks, return_exceptions=True)
    _media_tasks.clear()
    _media_groups.clear()
    _captcha_pending.clear()
    _user_msg_times.clear()
