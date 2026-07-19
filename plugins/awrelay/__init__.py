# =============================================================================
# AWBotNest 插件：AWRelay（awrelay）
#
# 轻量自托管的 Telegram 私聊消息中转机器人。用户私聊 bot 的消息会被转发到
# 开启了「话题」功能的超级群组，每位用户对应一个独立话题。管理员在话题内
# 直接回复即可将内容回传给用户。
#
# 功能：话题式收件箱、人机验证、广告过滤、黑名单、限流、控制面板
# =============================================================================

import asyncio
import time
import html
from collections import defaultdict, deque
from datetime import datetime
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

__plugin__ = {
    "name": "AWRelay",
    "id": "awrelay",
    "version": "1.0.1",
    "author": "AWdress",
    "description": "轻量自托管的 Telegram 私聊消息中转机器人。私聊转发到话题群组，管理员在话题内回复用户。内置人机验证、广告过滤、黑名单。",
    "changelog": "v1.0.1 补充插件版本日志与前端构建产物\n- 确保配置界面可由平台正常加载\n\nv1.0.0 初始版本\n- 支持话题式私聊中转、人机验证、广告过滤、黑名单与限流",
    "scope": "bot",
    "default_enabled": False,
    "render_mode": "vue",
    "requirements": [],
}

# ── 配置默认值 ──
DEFAULTS = {
    "enabled": False,
    "bot_token": "",
    "group_id": "",
    "captcha_enabled": True,
    "captcha_question": "1+1等于几？",
    "captcha_answer": "2",
    "spam_enabled": True,
    "spam_keywords": "",
    "rate_limit_window": 10,
    "rate_limit_count": 5,
    "menu_auto_delete": 60,
    "media_group_delay": 2.0,
}

# ── 运行态 ──
_user_topics = {}  # user_id -> topic_id
_topic_users = {}  # topic_id -> user_id
_msg_mapping = {}  # group_msg_id -> (user_id, user_msg_id)
_banned_users = set()
_captcha_pending = {}  # user_id -> pending_messages
_user_msg_times = defaultdict(deque)
_media_groups = {}  # media_group_id -> (timestamp, [messages])


def _effective_cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}


def _is_spam(text: str, cfg: dict) -> bool:
    if not cfg.get("spam_enabled", True) or not text:
        return False
    keywords = [k.strip() for k in cfg.get("spam_keywords", "").split(",") if k.strip()]
    text_lower = text.lower()
    return any(k.lower() in text_lower for k in keywords)


def _is_rate_limited(user_id: int, cfg: dict) -> bool:
    now = time.time()
    window = cfg.get("rate_limit_window", 10)
    count = cfg.get("rate_limit_count", 5)
    dq = _user_msg_times[user_id]
    while dq and now - dq[0] > window:
        dq.popleft()
    if len(dq) >= count:
        return True
    dq.append(now)
    return False


async def _get_or_create_topic(client, user, cfg: dict):
    user_id = user.id
    if user_id in _user_topics:
        return _user_topics[user_id]

    group_id = int(cfg.get("group_id", 0))
    if not group_id:
        return None

    name = user.first_name or f"User_{user_id}"
    try:
        topic = await client.create_forum_topic(group_id, name)
        topic_id = topic.id
        _user_topics[user_id] = topic_id
        _topic_users[topic_id] = user_id

        name_link = f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>'
        username_part = f"  @{html.escape(user.username)}" if user.username else ""
        info = f"{name_link}{username_part}\n🆔 <code>{user_id}</code>"
        await client.send_message(group_id, info, reply_to_message_id=topic_id, parse_mode="html")
        return topic_id
    except Exception as e:  # noqa: BLE001
        return None


async def setup(ctx):
    # ───────── Vue 模式后端 API ─────────
    @ctx.on_api("/status", methods=["GET"])
    async def _api_status(req):
        cfg = _effective_cfg(ctx)
        group_id = int(cfg.get("group_id", 0)) if cfg.get("group_id") else 0
        return {
            "bot_running": cfg.get("enabled", False),
            "bot_status": "运行中" if cfg.get("enabled") else "已停止",
            "group_title": f"Group {group_id}" if group_id else "-",
            "active_users": len(_user_topics),
            "total_topics": len(_user_topics),
            "banned_users": len(_banned_users),
        }

    @ctx.on_api("/topics", methods=["GET"])
    async def _api_topics(req):
        topics = []
        for user_id, topic_id in _user_topics.items():
            topics.append({
                "name": f"User {user_id}",
                "user_id": user_id,
                "topic_id": topic_id,
                "last_active": "-",
                "status": "已封禁" if user_id in _banned_users else "正常",
            })
        return {"topics": topics}

    @ctx.on_api("/update_config", methods=["POST"])
    async def _api_update_config(req):
        body = await req.json()
        ctx.update_config(body)
        return {"ok": True}

    # ───────── Bot 消息处理 ─────────
    @ctx.on_message(filters.private & filters.incoming, group=10)
    async def on_private_message(client, message):
        cfg = _effective_cfg(ctx)
        if not cfg.get("enabled", False):
            return

        user = message.from_user
        if user.id in _banned_users:
            return

        # 人机验证
        if cfg.get("captcha_enabled", True) and user.id in _captcha_pending:
            answer = (message.text or "").strip()
            if answer == cfg.get("captcha_answer", "2"):
                await message.reply("✅ 验证成功！")
                for pending_msg in _captcha_pending.pop(user.id, []):
                    await _forward_to_topic(client, pending_msg, cfg)
            else:
                await message.reply("❌ 验证失败，请重试。")
            return

        if cfg.get("captcha_enabled", True) and user.id not in _user_topics:
            question = cfg.get("captcha_question", "1+1等于几？")
            await message.reply(f"🤖 人机验证\n\n{question}")
            _captcha_pending[user.id] = [message]
            return

        # 垃圾过滤
        if _is_spam(message.text or message.caption or "", cfg):
            return

        # 限流
        if _is_rate_limited(user.id, cfg):
            return

        # 转发到话题
        await _forward_to_topic(client, message, cfg)

    async def _forward_to_topic(client, message, cfg):
        user = message.from_user
        topic_id = await _get_or_create_topic(client, user, cfg)
        if not topic_id:
            return

        group_id = int(cfg.get("group_id", 0))
        try:
            sent = await message.copy(group_id, reply_to_message_id=topic_id)
            _msg_mapping[sent.id] = (user.id, message.id)
        except Exception:  # noqa: BLE001
            pass

    @ctx.on_message(filters.chat(lambda _, __, msg: _effective_cfg(ctx).get("group_id") and msg.chat.id == int(_effective_cfg(ctx).get("group_id", 0))) & filters.outgoing, group=10)
    async def on_admin_reply(client, message):
        cfg = _effective_cfg(ctx)
        if not cfg.get("enabled", False):
            return

        # 回复转发消息
        if message.reply_to_message_id and message.reply_to_message_id in _msg_mapping:
            user_id, _ = _msg_mapping[message.reply_to_message_id]
            try:
                await message.copy(user_id)
            except Exception:  # noqa: BLE001
                pass
            return

        # 话题内直接发送
        if message.reply_to_message and message.reply_to_message.forum_topic_created:
            topic_id = message.reply_to_message.id
            user_id = _topic_users.get(topic_id)
            if user_id:
                try:
                    await message.copy(user_id)
                except Exception:  # noqa: BLE001
                    pass


async def teardown(ctx):
    pass
