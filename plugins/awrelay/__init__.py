"""AWRelay: Telegram 私聊与论坛话题之间的双向中转。"""

import asyncio
import html
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime

from pyrogram import raw
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyParameters

__plugin__ = {
    "name": "AWRelay",
    "id": "awrelay",
    "version": "1.1.11",
    "author": "AWdress",
    "description": "轻量自托管的 Telegram 私聊消息中转机器人。私聊转发到话题群组，管理员在话题内回复用户。内置人机验证、广告过滤、黑名单。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/awrelay/logo.png",
    "changelog": "v1.1.11 修复转发消息丢失与话题误判\n- 优先使用 GetForumTopicsByID 直接核验本地话题，避免数字搜索漏报\n- 旧 v3 映射强制重新核验，确认标题归属后才允许复用\n- 保留文本网页预览，补充动画和特殊转发消息兜底\n\nv1.1.10 修复话题列表拉黑操作\n- 按平台请求规范读取 req.json 属性，修复 /ban API 异常\n- 拉黑与解除统一写入持久化 KV，并返回实际状态\n- 前端校验后端确认结果并同步刷新黑名单计数\n\nv1.1.9 修复私聊投递到错误话题\n- 使用 Telegram 原始 GetForumTopics 按用户 ID 核验真实话题\n- 废弃旧 reconciled_v2 映射并重新校验标题与话题 ID\n- 查询失败时停止转发，避免盲用错误映射或创建重复话题\n\nv1.1.8 修复 Pyrogram 发送结果解析缺陷\n- 文本转发改走底层 Telegram RPC，绕过 Bot Updates 缺少 users 导致的空结果\n- 从原始响应提取已发送消息 ID，恢复消息映射并验证真实送达\n- 媒体空返回降为调试信息，不再产生误导性警告\n\nv1.1.7 修复发送成功误报失败\n- 避开 Message.copy 空返回，改为按内容类型显式发送一次\n- Telegram 不返回消息对象时不再误报失败或重复转发\n\nv1.1.6 修复 Bot 兼容性异常\n- 改从群历史服务消息识别旧话题，绕过 get_forum_topics 解析错误\n- 全部 HTML 消息改用平台当前 Pyrogram 支持的 ParseMode 枚举\n- 话题创建或消息复制返回空值时自动恢复并显式重发\n\nv1.1.5 修复消息落入全部并恢复启动通知\n- 话题发送同时携带 thread 与 top message 参数，确保消息进入对应话题\n- 插件启用时向中转群发送 AWRelay 已启动通知\n\nv1.1.4 修复话题复用与消息转发\n- 使用 message_thread_id 正确投递到论坛话题\n- 自动认领独立版已有话题，重复话题优先复用最早的有效话题\n- 收紧失效话题重建条件，避免转发异常时误建重复话题\n\nv1.1.3 改为按钮式人机验证\n- 随机生成四个答案选项，用户点击即可验证\n- 答错后自动更换题目，并阻止他人代点验证\n\nv1.1.2 补充插件 Logo\n- 迁移 AWRelay 原项目 Logo，并同步插件卡片与市场图标\n\nv1.1.1 修正定时任务显示\n- 旧消息映射清理改为每天凌晨 04:00 执行，避免状态页误显示每 0 秒\n\nv1.1.0 完成核心功能迁移并适配新版平台\n- 修复 Vue 配置保存时报 post 未定义的问题\n- 话题、消息映射、验证状态和黑名单改为持久化存储\n- 修复管理员消息监听与普通话题消息双向路由\n- 增加媒体组聚合、失效话题重建、转发失败提示及黑名单管理\n- 全部运行接口改用 ctx 平台能力\n\nv1.0.3 改为随机人机验证题\n- 每位待验证用户随机生成加减乘算术题\n- 配置页不再要求填写固定问题和答案\n\nv1.0.2 重新发布完整前端构建产物\n- 使用新版本号触发平台重新下载 frontend/dist\n\nv1.0.1 补充插件版本日志与前端构建产物\n- 确保配置界面可由平台正常加载\n\nv1.0.0 初始版本\n- 支持话题式私聊中转、人机验证、广告过滤、黑名单与限流",
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


def _set_banned(ctx, user_id, banned):
    users = _ids(ctx, "banned_users")
    users.add(int(user_id)) if banned else users.discard(int(user_id))
    ctx.kv.set("banned_users", sorted(users))
    return int(user_id) in users


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


def _captcha_markup(user_id, answer):
    correct = int(answer)
    options = {correct}
    while len(options) < 4:
        options.add(max(0, correct + secrets.randbelow(11) - 5))
    choices = list(options)
    secrets.SystemRandom().shuffle(choices)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(str(choice), callback_data=f"awrelay_captcha:{user_id}:{choice}")
        for choice in choices
    ]])


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


async def _matching_topics(client, group_id, suffix):
    """直接读取 Telegram 原始话题响应，避开高层解析器的 users=None 缺陷。"""
    result = await client.invoke(
        raw.functions.messages.GetForumTopics(
            peer=await client.resolve_peer(group_id),
            offset_date=0, offset_id=0, offset_topic=0, limit=100,
            q=None,
        )
    )
    return [
        topic for topic in (getattr(result, "topics", None) or [])
        if (getattr(topic, "title", "") or "").endswith(suffix)
        and not getattr(topic, "deleted", False)
        and not getattr(topic, "closed", False)
    ]


async def _topics_by_id(client, group_id, topic_ids):
    result = await client.invoke(
        raw.functions.messages.GetForumTopicsByID(
            peer=await client.resolve_peer(group_id), topics=[int(item) for item in topic_ids],
        )
    )
    return getattr(result, "topics", None) or []


async def _topic_for(ctx, client, user, cfg, force=False):
    topics = _topics(ctx)
    key = str(user.id)
    group_id = int(cfg.get("group_id") or 0)
    if not group_id:
        raise ValueError("请先配置话题群组")
    base = (f"{user.first_name or ''} {user.last_name or ''}".strip() or f"用户{user.id}")
    suffix = f" · {user.id}"
    existing = topics.get(key)
    if not force and existing and existing.get("reconciled_v4"):
        return int(existing["topic_id"])

    # 优先按 ID 直接核验本地映射。Telegram 的 q 搜索不保证匹配标题末尾的数字 ID，
    # 不能因为搜索结果为空就判定现有话题失效。
    if not force and existing and existing.get("topic_id"):
        try:
            direct = await _topics_by_id(client, group_id, [existing["topic_id"]])
            if any((getattr(item, "title", "") or "").endswith(suffix) for item in direct):
                existing["reconciled_v4"] = True
                topics[key] = existing
                _set_dict(ctx, "topics", topics)
                return int(existing["topic_id"])
        except Exception as exc:
            raise RuntimeError(f"无法核验已有话题 {existing.get('topic_id')}：{exc}") from exc

    # 独立版数据库不会随插件迁移。首次遇到用户时扫描群组话题，通过标题末尾的
    # 用户 ID 认领旧话题；若曾误建重复话题，优先选择创建时间最早的有效话题。
    try:
        matches = await _matching_topics(client, group_id, suffix)
        if matches:
            chosen = min(matches, key=lambda item: getattr(item, "date", 0) or 0)
            chosen_id = int(chosen.id)
            topics[key] = {
                "topic_id": chosen_id, "name": base, "username": user.username or "",
                "last_active": (existing or {}).get("last_active", "-"), "reconciled_v4": True,
            }
            _set_dict(ctx, "topics", topics)
            ctx.log.info("复用用户 %s 的已有话题 %s", user.id, chosen_id)
            return chosen_id
    except Exception as exc:
        if existing:
            raise RuntimeError(f"无法核验已有话题 {existing.get('topic_id')}：{exc}") from exc
        ctx.log.warning("扫描用户 %s 的已有话题失败：%s", user.id, exc)
        raise

    if not force and existing:
        ctx.log.warning("未能核验用户 %s 的本地话题映射 %s，不再盲目复用", user.id, existing.get("topic_id"))

    topic = await client.create_forum_topic(group_id, base[:128 - len(suffix)] + suffix)
    topic_id = int(topic.id) if topic is not None and getattr(topic, "id", None) else 0
    if not topic_id:
        await asyncio.sleep(0.5)
        created_matches = await _matching_topics(client, group_id, suffix)
        if created_matches:
            topic_id = int(max(created_matches, key=lambda item: getattr(item, "date", 0) or 0).id)
    if not topic_id:
        raise RuntimeError("Telegram 已执行创建话题，但未返回话题 ID")
    topics[key] = {
        "topic_id": topic_id, "name": base, "username": user.username or "",
        "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "reconciled_v4": True,
    }
    _set_dict(ctx, "topics", topics)
    link = f'<a href="tg://user?id={user.id}">{html.escape(base)}</a>'
    username = f"  @{html.escape(user.username)}" if user.username else ""
    await client.send_message(
        group_id, f"{link}{username}\n🆔 <code>{user.id}</code>",
        message_thread_id=topic_id,
        reply_parameters=ReplyParameters(message_id=topic_id, chat_id=group_id), parse_mode=ParseMode.HTML,
    )
    return topic_id


def _save_mapping(ctx, sent_id, user_id, user_msg_id):
    mappings = _mappings(ctx)
    mappings[str(sent_id)] = {"user_id": user_id, "user_msg_id": user_msg_id, "created_at": time.time()}
    _set_dict(ctx, "message_mappings", mappings)


async def _send_content_to_topic(client, group_id, topic_id, message):
    """按内容类型显式发送，避开当前 Pyrogram 的 Message.copy 空返回问题。"""
    route = {
        "message_thread_id": topic_id,
        "reply_parameters": ReplyParameters(message_id=topic_id, chat_id=group_id),
    }
    caption = getattr(message, "caption", None)
    if message.text:
        # 当前 Pyrogram 对部分 Bot Updates 的 users=None 解析失败，发送成功却返回 None。
        # 文本直接走底层 RPC，并从原始 Updates 提取消息 ID，避免依赖 parse_messages。
        result = await client.invoke(
            raw.functions.messages.SendMessage(
                peer=await client.resolve_peer(group_id),
                message=message.text,
                random_id=client.rnd_id(),
                no_webpage=False,
                reply_to=raw.types.InputReplyToMessage(
                    reply_to_msg_id=topic_id, top_msg_id=topic_id,
                ),
            )
        )
        direct_id = getattr(result, "id", None)
        if direct_id:
            return int(direct_id)
        for update in getattr(result, "updates", None) or []:
            raw_message = getattr(update, "message", None)
            if raw_message is not None and getattr(raw_message, "id", None):
                return int(raw_message.id)
        raise RuntimeError("Telegram 已响应发送请求，但原始响应中没有消息 ID")
    if message.photo:
        sent = await client.send_photo(group_id, message.photo.file_id, caption=caption, **route)
        return getattr(sent, "id", None)
    if message.video:
        sent = await client.send_video(group_id, message.video.file_id, caption=caption, **route)
        return getattr(sent, "id", None)
    if getattr(message, "animation", None):
        sent = await client.send_animation(group_id, message.animation.file_id, caption=caption, **route)
        return getattr(sent, "id", None)
    if message.document:
        sent = await client.send_document(group_id, message.document.file_id, caption=caption, **route)
        return getattr(sent, "id", None)
    if message.audio:
        sent = await client.send_audio(group_id, message.audio.file_id, caption=caption, **route)
        return getattr(sent, "id", None)
    if message.voice:
        sent = await client.send_voice(group_id, message.voice.file_id, **route)
        return getattr(sent, "id", None)
    if message.sticker:
        sent = await client.send_sticker(group_id, message.sticker.file_id, **route)
        return getattr(sent, "id", None)
    if message.video_note:
        sent = await client.send_video_note(group_id, message.video_note.file_id, **route)
        return getattr(sent, "id", None)
    sent = await message.copy(
        group_id, message_thread_id=topic_id,
        reply_parameters=ReplyParameters(message_id=topic_id, chat_id=group_id),
    )
    if sent is not None:
        return getattr(sent, "id", None)
    return None


async def _forward_one(ctx, client, message, cfg):
    user = message.from_user
    topic_id = await _topic_for(ctx, client, user, cfg)
    group_id = int(cfg.get("group_id") or 0)
    try:
        sent_id = await _send_content_to_topic(client, group_id, topic_id, message)
    except Exception as exc:
        lowered = str(exc).lower()
        if not any(x in lowered for x in ("message thread not found", "topic_deleted", "topic_closed")):
            raise
        topics = _topics(ctx)
        topics.pop(str(user.id), None)
        _set_dict(ctx, "topics", topics)
        topic_id = await _topic_for(ctx, client, user, cfg, force=True)
        sent_id = await _send_content_to_topic(client, group_id, topic_id, message)
    if sent_id:
        _save_mapping(ctx, sent_id, user.id, message.id)
    else:
        ctx.log.debug("媒体已发送，但 Pyrogram 未解析出消息 ID（用户 %s，话题 %s）", user.id, topic_id)
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
        sent = await message.copy(user_id)
        if sent is not None:
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

    cfg_at_start = _cfg(ctx)
    if cfg_at_start.get("enabled") and cfg_at_start.get("group_id") and ctx.bot.connected:
        try:
            raw_bot = ctx.bot.raw
            me = await raw_bot.get_me()
            started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            username = f"@{html.escape(me.username)}" if me.username else html.escape(me.first_name or "AWRelay")
            await ctx.bot.send(
                int(cfg_at_start["group_id"]),
                "<b>AWRelay 已启动</b>\n\n"
                f"机器人：{username}\n"
                f"时间：{started_at}\n\n"
                "用户私聊消息将转发至对应话题，在话题内直接发送即可回复用户。",
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            ctx.log.warning("发送启动通知失败：%s", exc)

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
        data = req.json or {}
        if not isinstance(data, dict) or data.get("user_id") in (None, ""):
            return {"ok": False, "message": "缺少用户 ID"}
        user_id = int(data["user_id"])
        is_banned = _set_banned(ctx, user_id, bool(data.get("banned", True)))
        return {"ok": True, "user_id": user_id, "banned": is_banned}

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
                await message.reply("🔐 请点击上方按钮完成验证，再发送消息。")
                return
            question, answer = _generate_captcha()
            _captcha_pending[user.id] = {"answer": answer}
            await message.reply(
                f"🔐 <b>人机验证</b>\n━━━━━━━━━━━━━━\n为防止机器人骚扰，发送消息前请先完成验证：\n\n👉 <b>{question}</b>\n\n请点击下方正确答案。",
                reply_markup=_captcha_markup(user.id, answer), parse_mode=ParseMode.HTML,
            )
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

    @ctx.on_callback(filters.regex(r"^awrelay_captcha:"), group=15)
    async def captcha_click(client, query):
        try:
            _, raw_user_id, raw_choice = query.data.split(":", 2)
            user_id, choice = int(raw_user_id), int(raw_choice)
        except (AttributeError, TypeError, ValueError):
            await query.answer("验证数据无效", show_alert=True)
            return
        if not query.from_user or query.from_user.id != user_id:
            await query.answer("这不是你的验证题", show_alert=True)
            return
        pending = _captcha_pending.get(user_id)
        if not pending:
            await query.answer("验证题已失效，请重新发送消息", show_alert=True)
            return
        if choice == int(pending["answer"]):
            verified = _ids(ctx, "verified_users")
            verified.add(user_id)
            ctx.kv.set("verified_users", sorted(verified))
            _captcha_pending.pop(user_id, None)
            await query.answer("验证成功")
            await query.message.edit_text("✅ 验证成功！请重新发送需要转达的消息。")
            return
        question, answer = _generate_captcha()
        _captcha_pending[user_id] = {"answer": answer}
        await query.answer("答案不对，已更换题目", show_alert=True)
        await query.message.edit_text(
            f"🔐 <b>人机验证</b>\n━━━━━━━━━━━━━━\n答案不对，请重新选择：\n\n👉 <b>{question}</b>",
            reply_markup=_captcha_markup(user_id, answer), parse_mode=ParseMode.HTML,
        )

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
            _set_banned(ctx, user_id, command == "/ban")
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
            await message.reply(f"❌ 发送失败：<code>{html.escape(str(exc))}</code>", parse_mode=ParseMode.HTML)

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
