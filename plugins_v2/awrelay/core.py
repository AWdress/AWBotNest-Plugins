"""AWRelay: Telegram 私聊与群组/Bot 话题之间的双向中转。"""

import asyncio
import html
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime
from types import SimpleNamespace
from telethon import Button, functions, utils

__plugin__ = {
    "name": "AWRelay",
    "id": "awrelay",
    "version": "1.2.12",
    "author": "AWdress",
    "description": "轻量自托管的 Telegram 私聊消息中转机器人。访客私聊转发到群组论坛话题，管理员在对应话题内回复用户。内置人机验证、广告过滤、黑名单。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/awrelay/logo.png",
    "changelog": "v1.2.8 修复话题匹配\n- 修复 General 话题（thread_id=0）误命中无 topic_id 的待处理记录\n\nv1.2.7 新增启动通知开关\n- 配置页新增「启动时在中转群发通知」开关，可关闭插件启用时向中转群发送的 AWRelay 已启动通知\n- 默认开启，保持原有行为\n\nv1.2.6 移除 Bot 私聊话题模式\n- 移除不稳定的 Bot 私聊话题创建、核验和消息路由功能\n- 配置界面恢复为仅支持群组论坛话题\n- 已保存的 topic_mode 配置将被忽略，群组转发继续使用话题群组 ID\n\nv1.2.5 修复 Bot 私聊消息未进入对应话题\n- Bot 模式改用 message.copy 并传入 message_thread_id，由 Pyrogram 正确构造私聊话题路由\n- 文本、图片、文件及其他媒体统一投递到用户对应话题\n- 群组模式继续使用原有服务端无署名复制，不改变现有行为\n\nv1.2.4 恢复 Bot 私聊话题删除检测\n- 每次转发前按用户标题查询并核验已保存的私聊话题 ID\n- 话题被删除或关闭后清除旧映射并自动新建，与群组模式一致\n- 存在同用户有效话题时优先复用，查询失败时停止操作以避免重复创建\n\nv1.2.3 修复 Bot 私聊话题投递协议\n- 私聊话题改用 InputReplyToMessage 路由，不再使用群组专用 top_msg_id\n- Bot 模式不再用群组标题结构误判话题已删除\n- 私聊响应缺少 reply_to_top_id 或消息 ID 时按成功处理，避免误报和反复重建\n\nv1.2.2 修复 Bot 私聊重复创建话题\n- 使用 Pyrogram 官方话题创建接口直接解析私聊话题 ID\n- 创建响应异常时先回查实际话题，不再立即重复创建\n- 无法确认话题 ID 时停止转发并给出明确错误，防止连续生成重复话题\n\nv1.2.1 复用管理员 ID 作为私聊目标\n- Bot 私聊话题模式直接使用管理员用户 ID 中的第一个 ID\n- 私聊模式不再显示重复的管理员私聊 ID 输入框\n- 群组模式继续独立保留话题群组 ID 配置\n\nv1.2.0 支持 Bot 私聊话题模式\n- 新增群组论坛话题与 Bot 私聊话题两种中转模式\n- Bot 模式使用 Telegram 私聊话题接口创建、核验和投递用户消息\n- 保留原有群组配置兼容性，并避免管理员私聊消息被当成访客消息转发\n\nv1.1.16 修复并发消息重复创建话题\n- 为每个私聊用户增加独立异步锁，串行执行话题核验、创建和消息发送\n- 同一用户短时间连续发送只会创建一个话题，不同用户仍可并发\n- 媒体组复用相同串行转发路径，避免与普通消息并发重复建话题\n\nv1.1.15 校验实际投递话题并自动纠正\n- 检查 Telegram 发送响应中的真实话题 ID，不再只相信发送参数\n- 发现消息降级到全部时立即撤回误投消息、清除映射并新建话题\n- 强制重建时跳过旧话题扫描缓存，确保不会再次复用已删除话题\n\nv1.1.14 修复已删除话题仍投递到全部\n- 每次转发前向 Telegram 核验本地话题 ID，不再永久信任已校验标记\n- 发现话题已删除、关闭或标题不匹配时立即清除映射并新建话题\n- 消息只在取得有效话题后发送，避免失效 ID 降级进入全部\n\nv1.1.13 对齐 AWRelay 原项目消息复制逻辑\n- 所有消息统一逐条执行 Telegram 服务端 copy，不再区分文本和媒体发送\n- 相册恢复原项目的逐条复制方式，避免批量 RPC 对转发媒体的兼容问题\n- 保留原消息实体、网页预览、说明文字和媒体属性\n\nv1.1.12 修复图片和文件无法转发\n- 非文本消息改由 Telegram 服务器端无署名复制，不再依赖 file_id 二次发送\n- 支持别人转发来的图片、文件、视频、贴纸及其他媒体\n- 媒体组按原顺序批量复制到对应话题并保存回复映射\n\nv1.1.11 修复转发消息丢失与话题误判\n- 优先使用 GetForumTopicsByID 直接核验本地话题，避免数字搜索漏报\n- 旧 v3 映射强制重新核验，确认标题归属后才允许复用\n- 保留文本网页预览，补充动画和特殊转发消息兜底\n\nv1.1.10 修复话题列表拉黑操作\n- 按平台请求规范读取 req.json 属性，修复 /ban API 异常\n- 拉黑与解除统一写入持久化 KV，并返回实际状态\n- 前端校验后端确认结果并同步刷新黑名单计数\n\nv1.1.9 修复私聊投递到错误话题\n- 使用 Telegram 原始 GetForumTopics 按用户 ID 核验真实话题\n- 废弃旧 reconciled_v2 映射并重新校验标题与话题 ID\n- 查询失败时停止转发，避免盲用错误映射或创建重复话题\n\nv1.1.8 修复 Pyrogram 发送结果解析缺陷\n- 文本转发改走底层 Telegram RPC，绕过 Bot Updates 缺少 users 导致的空结果\n- 从原始响应提取已发送消息 ID，恢复消息映射并验证真实送达\n- 媒体空返回降为调试信息，不再产生误导性警告\n\nv1.1.7 修复发送成功误报失败\n- 避开 Message.copy 空返回，改为按内容类型显式发送一次\n- Telegram 不返回消息对象时不再误报失败或重复转发\n\nv1.1.6 修复 Bot 兼容性异常\n- 改从群历史服务消息识别旧话题，绕过 get_forum_topics 解析错误\n- 全部 HTML 消息改用平台当前 Pyrogram 支持的 ParseMode 枚举\n- 话题创建或消息复制返回空值时自动恢复并显式重发\n\nv1.1.5 修复消息落入全部并恢复启动通知\n- 话题发送同时携带 thread 与 top message 参数，确保消息进入对应话题\n- 插件启用时向中转群发送 AWRelay 已启动通知\n\nv1.1.4 修复话题复用与消息转发\n- 使用 message_thread_id 正确投递到论坛话题\n- 自动认领独立版已有话题，重复话题优先复用最早的有效话题\n- 收紧失效话题重建条件，避免转发异常时误建重复话题\n\nv1.1.3 改为按钮式人机验证\n- 随机生成四个答案选项，用户点击即可验证\n- 答错后自动更换题目，并阻止他人代点验证\n\nv1.1.2 补充插件 Logo\n- 迁移 AWRelay 原项目 Logo，并同步插件卡片与市场图标\n\nv1.1.1 修正定时任务显示\n- 旧消息映射清理改为每天凌晨 04:00 执行，避免状态页误显示每 0 秒\n\nv1.1.0 完成核心功能迁移并适配新版平台\n- 修复 Vue 配置保存时报 post 未定义的问题\n- 话题、消息映射、验证状态和黑名单改为持久化存储\n- 修复管理员消息监听与普通话题消息双向路由\n- 增加媒体组聚合、失效话题重建、转发失败提示及黑名单管理\n- 全部运行接口改用 ctx 平台能力\n\nv1.0.3 改为随机人机验证题\n- 每位待验证用户随机生成加减乘算术题\n- 配置页不再要求填写固定问题和答案\n\nv1.0.2 重新发布完整前端构建产物\n- 使用新版本号触发平台重新下载 frontend/dist\n\nv1.0.1 补充插件版本日志与前端构建产物\n- 确保配置界面可由平台正常加载\n\nv1.0.0 初始版本\n- 支持话题式私聊中转、人机验证、广告过滤、黑名单与限流",
    "scope": "bot",
    "default_enabled": False,
    "render_mode": "vue",
    "requirements": [],
}

__plugin__.update(
    version="1.2.13",
    changelog=(
        "v1.2.13 修复 V2 Bot 路由未应用\n"
        "- 启动时主动读取平台给 AWRelay 分配的 Bot，避免错误使用默认 Bot\n"
        "- 群组校验、私聊监听、话题创建与消息复制统一使用同一个路由 Bot\n\n"
        "v1.2.12 增加私有论坛 Bot API 回退\n"
        "- Telethon 无法取得频道 access_hash 时改用当前平台 Bot 的官方 Bot API\n"
        "- 支持数字群 ID 校验、创建话题、启动通知和消息复制，不再依赖实体缓存\n"
        "- 回退失败时明确提示 Bot 未入群、群 ID 错误或目标未开启论坛\n\n"
        "v1.2.11 修复 Bot 会话首次启动无法解析话题群\n"
        "- 数字 ID 未命中 Telethon 实体缓存时自动遍历对话并缓存目标群\n"
        "- 论坛查询、创建和消息复制统一复用已解析的 InputPeer\n\n"
        "v1.2.10 修复 V2 群组识别与相册转发\n"
        "- 仅把真实私聊识别为访客消息，避免广播频道误入私聊流程\n"
        "- 使用 Telethon grouped_id 恢复相册聚合，并补充目标论坛与双向转发日志\n\n"
        + __plugin__["changelog"]
    ),
)

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
    "startup_notify": True,
}

_captcha_pending = {}
_user_msg_times = defaultdict(deque)
_media_groups = {}
_media_tasks = set()
_topic_locks = defaultdict(asyncio.Lock)
_storage_state = {}
_storage_tasks = set()
_target_entities = {}
_bot_api_targets = set()


def _cfg(ctx):
    return {**DEFAULTS, **dict(ctx.config or {})}


def _dict(ctx, key):
    value = _storage_state.get(key, {}) or {}
    return value if isinstance(value, dict) else {}


def _set_dict(ctx, key, value):
    _persist(ctx, key, value)


def _persist(ctx, key, value):
    _storage_state[key] = value
    task = ctx.create_task(ctx.storage.set(key, value), name=f"awrelay-storage:{key}")
    _storage_tasks.add(task)
    task.add_done_callback(_storage_tasks.discard)


def _topics(ctx):
    return _dict(ctx, "topics")


def _mappings(ctx):
    return _dict(ctx, "message_mappings")


def _ids(ctx, key):
    return {int(x) for x in (_storage_state.get(key, []) or [])}


def _set_banned(ctx, user_id, banned):
    users = _ids(ctx, "banned_users")
    users.add(int(user_id)) if banned else users.discard(int(user_id))
    _persist(ctx, "banned_users", sorted(users))
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
    return [[
        Button.inline(str(choice), data=f"awrelay_captcha:{user_id}:{choice}".encode())
        for choice in choices
    ]]


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
    reply = getattr(message, "reply_to", None)
    return getattr(reply, "reply_to_top_id", None) or getattr(reply, "reply_to_msg_id", None)


def _target_id(cfg):
    try:
        return int(str(cfg.get("group_id") or "0").strip())
    except (TypeError, ValueError):
        return 0


def _target_key(client, target_id):
    return id(client), int(target_id)


def _apply_configured_bot_route(ctx):
    """Apply the V2 platform Bot route before handlers capture their clients.

    AWBotNest V1 resolves ``ctx.bot`` from the per-plugin Bot assignment.  Some
    V2 platform releases only pass the manifest's static ``bot`` field into the
    plugin context, so a routed plugin can otherwise be attached to the default
    Bot.  That looks exactly like a bad group ID: both MTProto and Bot API answer
    ``chat not found`` even though the Bot selected in the UI is in the forum.
    """
    settings = getattr(ctx, "settings", None)
    accounts = getattr(ctx, "accounts", None)
    routes = getattr(settings, "bot_routing", None)
    bots = getattr(accounts, "bots", None)
    if not isinstance(routes, dict) or not isinstance(bots, dict):
        return str(getattr(ctx, "bot_id", "") or "")

    route = str(routes.get(getattr(ctx, "plugin_id", "awrelay"), "") or "")
    for candidate in (item.strip() for item in route.split(",")):
        if candidate and candidate in bots:
            previous = str(getattr(ctx, "bot_id", "") or "")
            ctx.bot_id = candidate
            if candidate != previous:
                ctx.log.info("已应用平台 Bot 路由：%s", candidate)
            return candidate
    return str(getattr(ctx, "bot_id", "") or "")


def _bot_token(ctx):
    """Return the token belonging to the same platform Bot client used by this plugin."""
    selected_id = str(getattr(ctx, "bot_id", "") or "")
    accounts = getattr(ctx, "accounts", None)
    current_bot = getattr(ctx, "bot", None)
    if accounts is not None and current_bot is not None:
        selected_id = next(
            (str(bot_id) for bot_id, client in accounts.bots.items() if client is current_bot),
            selected_id,
        )
    settings = getattr(ctx, "settings", None)
    if settings is None:
        return ""
    selected_id = selected_id or str(getattr(settings, "default_bot_id", "default") or "default")
    for spec in settings.bot_specs():
        if str(getattr(spec, "id", "")) == selected_id:
            return str(getattr(spec, "token", "") or "").strip()
    return ""


async def _bot_api_call(ctx, method, payload):
    """Use Bot API for numeric chat IDs when MTProto lacks the channel access_hash."""
    token = _bot_token(ctx)
    if not token:
        raise RuntimeError("平台当前 Bot 缺少可用 Token，无法启用 Bot API 回退")
    try:
        response = await ctx.http.post(
            f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=30,
        )
    except Exception as exc:
        detail = str(exc).replace(token, "***")[:300]
        raise RuntimeError(f"Telegram Bot API {method} 请求失败：{type(exc).__name__}: {detail}") from exc
    status = int(getattr(response, "status_code", 0) or 0)
    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(f"Telegram Bot API {method} 返回非 JSON 响应（HTTP {status or '-'}）") from exc
    if not isinstance(data, dict) or not data.get("ok"):
        description = str(data.get("description") or "未知错误") if isinstance(data, dict) else "响应格式异常"
        raise RuntimeError(f"Telegram Bot API {method} 失败（HTTP {status or '-'}）：{description[:300]}")
    return data.get("result")


def _uses_bot_api(client, target_id):
    return _target_key(client, target_id) in _bot_api_targets


async def _resolve_target_entity(client, target_id):
    """Resolve a numeric chat ID even when this Telethon session has no entity cache."""
    cache_key = (id(client), int(target_id))
    cached = _target_entities.get(cache_key)
    if cached is not None:
        return cached
    first_error = None
    try:
        entity = await client.get_entity(target_id)
    except (ValueError, TypeError) as exc:
        first_error = exc
        entity = None
    if entity is None:
        try:
            async for dialog in client.iter_dialogs(limit=None):
                candidate = getattr(dialog, "entity", None)
                try:
                    candidate_id = int(utils.get_peer_id(candidate)) if candidate is not None else 0
                except (TypeError, ValueError):
                    continue
                if candidate_id == int(target_id):
                    entity = candidate
                    break
        except Exception as exc:
            if first_error is None:
                first_error = exc
    if entity is None:
        if first_error is not None:
            raise first_error
        raise ValueError(f"无法在 Bot 对话列表中找到会话 {target_id}")
    # Passing the full entity gives Telethon the access_hash and warms its session cache.
    await client.get_input_entity(entity)
    _target_entities[cache_key] = entity
    return entity


async def _target_peer(client, target_id):
    entity = await _resolve_target_entity(client, target_id)
    return await client.get_input_entity(entity)


async def _validate_target(ctx, cfg):
    """解析并记录目标实体，尽早暴露错误 ID、非群组和非论坛配置。"""
    target_id = _target_id(cfg)
    if not cfg.get("enabled"):
        ctx.log.info("插件当前未启用，等待配置后接收私聊消息")
        return None
    if not target_id:
        ctx.log.error("插件已启用，但未配置有效的话题群组 ID（应为完整 -100... ID）")
        return None
    if not ctx.bot or not ctx.bot.is_connected():
        ctx.log.warning("平台 Bot 尚未连接，暂时无法校验话题群组 %s", target_id)
        return None
    bot_label = "未知"
    try:
        bot_me = await ctx.bot.get_me()
        bot_name = f"@{bot_me.username}" if getattr(bot_me, "username", None) else (
            getattr(bot_me, "first_name", None) or "Bot"
        )
        bot_label = f"{bot_name} / {getattr(bot_me, 'id', '-')}"
        ctx.log.info("AWRelay 当前使用 Bot：%s", bot_label)
    except Exception as exc:  # noqa: BLE001 - identity logging must not block validation
        ctx.log.debug("读取 AWRelay Bot 身份失败：%r", exc)
    bot_api_resolved = False
    try:
        entity = await _resolve_target_entity(ctx.bot, target_id)
    except Exception as telethon_error:
        try:
            chat = await _bot_api_call(ctx, "getChat", {"chat_id": target_id})
            if not isinstance(chat, dict):
                raise RuntimeError("Telegram Bot API getChat 未返回会话信息")
            entity = SimpleNamespace(
                _awrelay_peer_id=int(chat.get("id") or target_id),
                title=str(chat.get("title") or chat.get("username") or target_id),
                first_name=str(chat.get("first_name") or ""),
                megagroup=chat.get("type") == "supergroup",
                forum=bool(chat.get("is_forum")),
            )
            bot_api_resolved = True
            ctx.log.warning(
                "Telethon 无法取得话题群 %s 的 access_hash，已切换 Telegram Bot API：%s",
                target_id, telethon_error,
            )
        except Exception as bot_api_error:
            ctx.log.error(
                "无法识别话题群组 %s：Telethon 实体解析失败（%s）；Bot API 回退失败（%s）。"
                "当前实际使用 Bot：%s。请确认该 Bot 已加入目标群、群 ID 正确且 Bot 未被移除",
                target_id, telethon_error, bot_api_error, bot_label,
            )
            return None
    resolved_id = int(getattr(entity, "_awrelay_peer_id", 0) or utils.get_peer_id(entity))
    title = getattr(entity, "title", None) or getattr(entity, "first_name", None) or "-"
    is_group = bool(getattr(entity, "megagroup", False))
    is_forum = bool(getattr(entity, "forum", False))
    ctx.log.info(
        "已识别话题群组：%s（配置 ID=%s，实际 ID=%s，超级群=%s，论坛=%s）",
        title, target_id, resolved_id, is_group, is_forum,
    )
    if resolved_id != target_id:
        ctx.log.error("话题群组 ID 不匹配：配置 %s，Telegram 返回 %s", target_id, resolved_id)
        return None
    if not is_group:
        ctx.log.error("目标 %s 不是超级群，AWRelay 无法创建论坛话题", target_id)
        return None
    if not is_forum:
        ctx.log.error("目标群组 %s 未开启话题模式，请先在 Telegram 中启用论坛话题", target_id)
        return None
    # Telegram 禁止 Bot 调用 GetForumTopicsRequest 等 MTProto 论坛方法。
    # 即使 Telethon 已经拿到群实体/access_hash，话题核验、创建和消息复制
    # 也必须统一走当前 Bot 的官方 Bot API。
    if not _bot_token(ctx):
        ctx.log.error(
            "当前实际 Bot 缺少可用 Token，无法执行话题创建和消息复制：%s",
            bot_label,
        )
        return None
    _bot_api_targets.add(_target_key(ctx.bot, target_id))
    if not bot_api_resolved:
        ctx.log.info(
            "话题操作已使用 Telegram Bot API，避免 Bot 调用受限的 MTProto 论坛接口"
        )
    return entity


async def _matching_topics(ctx, client, target_id, suffix):
    """直接读取 Telegram 原始话题响应，避开高层解析器的 users=None 缺陷。"""
    if _uses_bot_api(client, target_id):
        # Bot API can create/use a topic but cannot enumerate forum topics.
        return []
    result = await client(
        functions.messages.GetForumTopicsRequest(
            peer=await _target_peer(client, target_id),
            offset_date=0, offset_id=0, offset_topic=0, limit=100,
            q=suffix.rsplit(" ", 1)[-1],
        )
    )
    return [
        topic for topic in (getattr(result, "topics", None) or [])
        if (getattr(topic, "title", "") or "").endswith(suffix)
        and not getattr(topic, "deleted", False)
        and not getattr(topic, "closed", False)
    ]


async def _topics_by_id(ctx, client, target_id, topic_ids):
    if _uses_bot_api(client, target_id):
        return []
    result = await client(
        functions.messages.GetForumTopicsByIDRequest(
            peer=await _target_peer(client, target_id), topics=[int(item) for item in topic_ids],
        )
    )
    return getattr(result, "topics", None) or []


def _valid_topic(topic, expected_id, suffix):
    return bool(
        topic
        and topic.__class__.__name__ != "ForumTopicDeleted"
        and int(getattr(topic, "id", 0) or 0) == int(expected_id)
        and (getattr(topic, "title", "") or "").endswith(suffix)
        and not getattr(topic, "deleted", False)
        and not getattr(topic, "closed", False)
    )


def _missing_topic_error(exc):
    text = str(exc).lower().replace(" ", "_")
    return any(marker in text for marker in (
        "message_thread_not_found", "topic_deleted", "forum_topic_deleted",
        "topic_closed", "topic_id_invalid", "message_id_invalid",
        "awrelay_topic_route_mismatch",
    ))


def _public_forward_error(exc):
    """给访客显示可定位但不携带敏感数据的错误摘要。"""
    detail = " ".join(str(exc).split()) or type(exc).__name__
    # Telethon 错误常附带很长的文档 URL，用户端只需要 RPC 原因。
    detail = detail.split(". Please read https://docs.telethon.dev/", 1)[0]
    return detail[:350]


async def _topic_for(ctx, client, user, cfg, force=False):
    topics = _topics(ctx)
    key = str(user.id)
    target_id = _target_id(cfg)
    if not target_id:
        raise ValueError("请先配置话题目标会话")
    target_key = _target_key(client, target_id)
    if target_key not in _target_entities and target_key not in _bot_api_targets:
        if await _validate_target(ctx, cfg) is None:
            raise RuntimeError(f"无法使用话题群组 {target_id}，请检查本轮启动日志")
    base = (f"{user.first_name or ''} {user.last_name or ''}".strip() or f"用户{user.id}")
    suffix = f" · {user.id}"
    existing = topics.get(key)
    if existing and (
        existing.get("target_id") not in (None, target_id)
    ):
        topics.pop(key, None)
        _set_dict(ctx, "topics", topics)
        existing = None
    # 每次发送前都按 ID 核验。Telegram 对已删除的话题 ID 可能不报错而把消息投到
    # General（“全部”），因此 reconciled 标记不能作为永久有效的依据。
    if not force and existing and existing.get("topic_id"):
        if _uses_bot_api(client, target_id):
            # Bot API has no getForumTopic/listForumTopics method. Optimistically reuse
            # the persisted topic; copyMessage will report a deleted/closed topic and
            # the normal recovery path below will create a replacement.
            return int(existing["topic_id"])
        try:
            direct = await _topics_by_id(ctx, client, target_id, [existing["topic_id"]])
            if any(_valid_topic(item, existing["topic_id"], suffix) for item in direct):
                existing["reconciled_v4"] = True
                existing["target_id"] = target_id
                topics[key] = existing
                _set_dict(ctx, "topics", topics)
                return int(existing["topic_id"])
            ctx.log.warning(
                "用户 %s 的话题 %s 已删除、关闭或不再匹配，将重新创建",
                user.id, existing.get("topic_id"),
            )
            topics.pop(key, None)
            _set_dict(ctx, "topics", topics)
            existing = None
        except Exception as exc:
            if not _missing_topic_error(exc):
                raise RuntimeError(f"无法核验已有话题 {existing.get('topic_id')}：{exc}") from exc
            ctx.log.warning("用户 %s 的话题 %s 已失效，将重新创建：%s", user.id, existing.get("topic_id"), exc)
            topics.pop(key, None)
            _set_dict(ctx, "topics", topics)
            existing = None

    # 独立版数据库不会随插件迁移。首次遇到用户时扫描群组话题，通过标题末尾的
    # 用户 ID 认领旧话题；若曾误建重复话题，优先选择创建时间最早的有效话题。
    if not force:
        try:
            matches = await _matching_topics(ctx, client, target_id, suffix)
            if matches:
                chosen = min(matches, key=lambda item: getattr(item, "date", 0) or 0)
                chosen_id = int(chosen.id)
                topics[key] = {
                    "topic_id": chosen_id, "name": base, "username": user.username or "",
                    "last_active": (existing or {}).get("last_active", "-"), "reconciled_v4": True,
                    "target_id": target_id,
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

    pending_until = float((existing or {}).get("creation_pending_until", 0) or 0)
    if pending_until > time.time():
        raise RuntimeError("话题已提交创建，正在等待 Telegram 同步，请稍后重试")

    title = base[:128 - len(suffix)] + suffix
    try:
        if _uses_bot_api(client, target_id):
            topic = await _bot_api_call(ctx, "createForumTopic", {
                "chat_id": target_id, "name": title,
            })
            topic_id = int((topic or {}).get("message_thread_id") or 0)
        else:
            topic = await client(functions.messages.CreateForumTopicRequest(
                peer=await _target_peer(client, target_id), title=title,
            ))
            topic_id = next((int(getattr(getattr(u, "message", None), "id", 0) or 0)
                             for u in getattr(topic, "updates", [])
                             if getattr(getattr(u, "message", None), "id", 0)), 0)
    except Exception as exc:
        # Telegram 可能已创建成功，但客户端在解析 Updates 时抛错。先按标题回查，
        # 确认不存在后才报告失败；绝不在同一次请求里再次创建，避免重复话题。
        ctx.log.warning("创建话题响应解析失败，将回查实际结果：%s", exc)
        topic_id = 0
    if not topic_id:
        await asyncio.sleep(1.0)
        created_matches = await _matching_topics(ctx, client, target_id, suffix)
        if created_matches:
            topic_id = int(max(created_matches, key=lambda item: getattr(item, "date", 0) or 0).id)
    if not topic_id:
        topics[key] = {
            "name": base, "username": user.username or "",
            "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_id": target_id,
            "creation_pending_until": time.time() + 60,
        }
        _set_dict(ctx, "topics", topics)
        raise RuntimeError("无法确认新话题 ID，已停止转发以避免重复创建；请稍后重试")
    topics[key] = {
        "topic_id": topic_id, "name": base, "username": user.username or "",
        "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "reconciled_v4": True, "target_id": target_id,
    }
    _set_dict(ctx, "topics", topics)
    link = f'<a href="tg://user?id={user.id}">{html.escape(base)}</a>'
    username = f"  @{html.escape(user.username)}" if user.username else ""
    topic_intro = f"{link}{username}\n🆔 <code>{user.id}</code>"
    if _uses_bot_api(client, target_id):
        await _bot_api_call(ctx, "sendMessage", {
            "chat_id": target_id, "message_thread_id": topic_id,
            "text": topic_intro, "parse_mode": "HTML",
        })
    else:
        await client.send_message(
            target_id, topic_intro, reply_to=topic_id, parse_mode="html",
        )
    ctx.log.info("已为用户 %s 创建话题 %s（目标群 %s）", user.id, topic_id, target_id)
    return topic_id


def _save_mapping(ctx, sent_id, user_id, user_msg_id):
    mappings = _mappings(ctx)
    mappings[str(sent_id)] = {"user_id": user_id, "user_msg_id": user_msg_id, "created_at": time.time()}
    _set_dict(ctx, "message_mappings", mappings)


def _raw_message_ids(result):
    """从底层 Telegram RPC 响应中提取实际生成的消息 ID。"""
    direct_id = getattr(result, "id", None)
    if direct_id:
        return [int(direct_id)]
    message_ids = []
    fallback_ids = []
    for update in getattr(result, "updates", None) or []:
        raw_message = getattr(update, "message", None)
        if raw_message is not None and getattr(raw_message, "id", None):
            message_ids.append(int(raw_message.id))
        elif update.__class__.__name__ == "UpdateMessageID" and getattr(update, "id", None):
            fallback_ids.append(int(update.id))
    return message_ids or fallback_ids


async def _copy_messages_to_topic(ctx, client, target_id, topic_id, messages):
    """由 Telegram 服务端无署名复制媒体，避免转发来源的 file_id 不可复用。"""
    source_chat_id = messages[0].chat_id
    if _uses_bot_api(client, target_id):
        message_ids = [int(message.id) for message in messages]
        if len(message_ids) == 1:
            result = await _bot_api_call(ctx, "copyMessage", {
                "chat_id": target_id,
                "from_chat_id": source_chat_id,
                "message_id": message_ids[0],
                "message_thread_id": topic_id,
            })
            sent_id = int((result or {}).get("message_id") or 0)
            return [sent_id] if sent_id else []
        result = await _bot_api_call(ctx, "copyMessages", {
            "chat_id": target_id,
            "from_chat_id": source_chat_id,
            "message_ids": message_ids,
            "message_thread_id": topic_id,
        })
        return [
            int(item.get("message_id") or 0)
            for item in (result or [])
            if isinstance(item, dict) and item.get("message_id")
        ]
    result = await client(
        functions.messages.ForwardMessagesRequest(
            from_peer=await client.get_input_entity(source_chat_id),
            id=[int(message.id) for message in messages],
            random_id=[client.rnd_id() for _ in messages],
            to_peer=await _target_peer(client, target_id),
            drop_author=True,
            top_msg_id=topic_id,
        )
    )
    sent_ids = _raw_message_ids(result)
    raw_messages = [
        getattr(update, "message", None)
        for update in (getattr(result, "updates", None) or [])
        if getattr(update, "message", None) is not None
    ]
    routed_ids = []
    for raw_message in raw_messages:
        reply = getattr(raw_message, "reply_to", None)
        routed_ids.append(int(
            getattr(reply, "reply_to_top_id", None)
            or getattr(reply, "reply_to_msg_id", None)
            or 0
        ))
    if raw_messages and any(routed_id != int(topic_id) for routed_id in routed_ids):
        if sent_ids:
            try:
                await client.delete_messages(target_id, sent_ids)
            except Exception:
                pass
        raise RuntimeError(
            f"AWRELAY_TOPIC_ROUTE_MISMATCH: 目标话题 {topic_id}，实际话题 {routed_ids}"
        )
    return sent_ids


async def _send_content_to_topic(ctx, client, target_id, topic_id, message):
    """等价于原项目 copy_message：所有内容均由 Telegram 服务端无署名复制。"""
    sent_ids = await _copy_messages_to_topic(ctx, client, target_id, topic_id, [message])
    if sent_ids:
        return sent_ids[0]
    raise RuntimeError("Telegram 已响应媒体复制请求，但原始响应中没有消息 ID")


async def _forward_one_unlocked(ctx, client, message, user, cfg):
    target_id = _target_id(cfg)
    try:
        topic_id = await _topic_for(ctx, client, user, cfg)
    except Exception as exc:
        raise RuntimeError(f"话题准备失败：{exc}") from exc
    try:
        sent_id = await _send_content_to_topic(ctx, client, target_id, topic_id, message)
    except Exception as exc:
        if not _missing_topic_error(exc):
            raise RuntimeError(f"消息复制失败：{exc}") from exc
        topics = _topics(ctx)
        topics.pop(str(user.id), None)
        _set_dict(ctx, "topics", topics)
        try:
            topic_id = await _topic_for(ctx, client, user, cfg, force=True)
            sent_id = await _send_content_to_topic(ctx, client, target_id, topic_id, message)
        except Exception as retry_exc:
            raise RuntimeError(f"失效话题重建后转发仍失败：{retry_exc}") from retry_exc
    if sent_id:
        _save_mapping(ctx, sent_id, user.id, message.id)
        ctx.log.info(
            "访客消息已转发：用户 %s，原消息 %s，目标群 %s，话题 %s，消息 %s",
            user.id, message.id, target_id, topic_id, sent_id,
        )
    topics = _topics(ctx)
    if str(user.id) in topics:
        topics[str(user.id)]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _set_dict(ctx, "topics", topics)


async def _forward_one(ctx, client, message, user, cfg):
    """同一用户串行处理，避免并发消息重复创建话题。"""
    async with _topic_locks[int(user.id)]:
        await _forward_one_unlocked(ctx, client, message, user, cfg)


async def _flush_media(ctx, client, media_id, cfg):
    try:
        await asyncio.sleep(max(0.1, float(cfg.get("media_group_delay", 2))))
        messages = sorted(_media_groups.pop(media_id, []), key=lambda item: item.id)
        if not messages:
            return
        for message in messages:
            user = await message.get_sender()
            if user:
                await _forward_one(ctx, client, message, user, cfg)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        ctx.log.error("媒体组转发失败：%s", exc)


async def _send_to_user(client, user_id, message):
    try:
        sent = await client.forward_messages(user_id, message, drop_author=True)
        if sent is not None:
            return
    except Exception as exc:
        if "copy" not in str(exc).lower() and "protected" not in str(exc).lower():
            raise
    if message.raw_text and not message.media:
        await client.send_message(user_id, message.raw_text)
    elif message.media:
        await client.send_file(user_id, message.media, caption=message.raw_text or None)
    else:
        raise ValueError("不支持的消息类型")


async def setup(ctx):
    # Must happen before reading ctx.bot and before decorators register event
    # handlers, otherwise the default Bot is captured for the whole lifecycle.
    _apply_configured_bot_route(ctx)
    _storage_state.clear()
    _storage_state.update(dict(await ctx.storage.items()))
    async def _flush_storage():
        if _storage_tasks:
            await asyncio.gather(*list(_storage_tasks), return_exceptions=True)
        _storage_tasks.clear()
    ctx.add_cleanup(_flush_storage)

    cfg_at_start = _cfg(ctx)
    validated_target = await _validate_target(ctx, cfg_at_start)
    if cfg_at_start.get("enabled") and cfg_at_start.get("startup_notify", True) and validated_target is not None:
        try:
            me = await ctx.bot.get_me()
            started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            username = f"@{html.escape(me.username)}" if me.username else html.escape(me.first_name or "AWRelay")
            target_id = _target_id(cfg_at_start)
            notice = (
                "<b>AWRelay 已启动</b>\n\n"
                f"机器人：{username}\n"
                f"时间：{started_at}\n\n"
                "用户私聊消息将转发至对应话题，在话题内直接发送即可回复用户。"
            )
            if _uses_bot_api(ctx.bot, target_id):
                await _bot_api_call(ctx, "sendMessage", {
                    "chat_id": target_id, "text": notice, "parse_mode": "HTML",
                })
            else:
                await ctx.bot.send_message(target_id, notice, parse_mode="html")
        except Exception as exc:
            ctx.log.warning("发送启动通知失败：%s", exc)

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(req):
        cfg = _cfg(ctx)
        topics = _topics(ctx)
        target_id = _target_id(cfg)
        group_title = str(target_id or "-")
        if target_id and ctx.bot and ctx.bot.is_connected():
            try:
                if _uses_bot_api(ctx.bot, target_id):
                    chat = await _bot_api_call(ctx, "getChat", {"chat_id": target_id})
                    group_title = str((chat or {}).get("title") or (chat or {}).get("first_name") or group_title)
                else:
                    chat = await ctx.bot.get_entity(target_id)
                    group_title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or group_title
            except Exception:  # noqa: BLE001
                pass
        return {"bot_running": bool(cfg["enabled"]), "bot_status": "运行中" if cfg["enabled"] else "已停止",
                "group_title": group_title, "group_id": target_id,
                "active_users": len(topics),
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

    @ctx.on_message(incoming=True)
    async def private_message(event):
        # 广播频道同样 is_group=False，只有 is_private 才能代表真实访客私聊。
        if not getattr(event, "is_private", False):
            return
        client, message = event.client, event.message
        user = await event.get_sender()
        cfg = _cfg(ctx)
        if not cfg["enabled"] or not user:
            return
        if user.id in _ids(ctx, "banned_users"):
            ctx.log.info("忽略黑名单用户 %s 的私聊消息 %s", user.id, message.id)
            return
        command = _command(message)
        if command in ("/start", "/help"):
            await message.reply("👋 直接给我发送消息即可转达给管理员，请耐心等待回复。")
            return
        verified = _ids(ctx, "verified_users")
        if cfg["captcha_enabled"] and user.id not in verified:
            pending = _captcha_pending.get(user.id)
            if pending:
                ctx.log.info("用户 %s 尚未完成人机验证，消息 %s 未转发", user.id, message.id)
                await message.reply("🔐 请点击上方按钮完成验证，再发送消息。")
                return
            question, answer = _generate_captcha()
            _captcha_pending[user.id] = {"answer": answer}
            ctx.log.info("已向用户 %s 发送人机验证，消息 %s 暂不转发", user.id, message.id)
            await message.reply(
                f"🔐 <b>人机验证</b>\n━━━━━━━━━━━━━━\n为防止机器人骚扰，发送消息前请先完成验证：\n\n👉 <b>{question}</b>\n\n请点击下方正确答案。",
                buttons=_captcha_markup(user.id, answer), parse_mode="html",
            )
            return
        if _rate_limited(user.id, cfg):
            ctx.log.warning("用户 %s 触发发送频率限制，消息 %s 未转发", user.id, message.id)
            await message.reply("⏳ 您发送得太频繁了，请稍后再试。")
            return
        if _is_spam(message.raw_text or "", cfg):
            ctx.log.info("拦截疑似广告消息：用户 %s", user.id)
            return
        # Telethon 使用 grouped_id；media_group_id 是 Pyrogram 字段，始终为空。
        media_id = getattr(message, "grouped_id", None)
        if media_id:
            media_key = f"{message.chat_id}:{media_id}"
            _media_groups.setdefault(media_key, []).append(message)
            if len(_media_groups[media_key]) == 1:
                ctx.log.info("开始聚合用户 %s 的相册 %s", user.id, media_id)
                task = ctx.create_task(_flush_media(ctx, client, media_key, cfg), name=f"awrelay-media-{media_id}")
                _media_tasks.add(task)
                task.add_done_callback(_media_tasks.discard)
            return
        try:
            await _forward_one(ctx, client, message, user, cfg)
        except Exception as exc:
            media_type = type(getattr(message, "media", None)).__name__ if getattr(message, "media", None) else "text"
            ctx.log.exception(
                "消息转发失败：用户=%s，原会话=%s，原消息=%s，目标群=%s，类型=%s：%s",
                user.id, getattr(message, "chat_id", "-"), getattr(message, "id", "-"),
                _target_id(cfg), media_type, exc,
            )
            await message.reply(f"❌ 消息转发失败\n原因：{_public_forward_error(exc)}")

    @ctx.on_callback(pattern=rb"^awrelay_captcha:")
    async def captcha_click(query):
        try:
            data = query.data.decode() if isinstance(query.data, bytes) else query.data
            _, raw_user_id, raw_choice = data.split(":", 2)
            user_id, choice = int(raw_user_id), int(raw_choice)
        except (AttributeError, TypeError, ValueError):
            await query.answer("验证数据无效", alert=True)
            return
        query_sender = await query.get_sender()
        if not query_sender or query_sender.id != user_id:
            await query.answer("这不是你的验证题", alert=True)
            return
        pending = _captcha_pending.get(user_id)
        if not pending:
            await query.answer("验证题已失效，请重新发送消息", alert=True)
            return
        if choice == int(pending["answer"]):
            verified = _ids(ctx, "verified_users")
            verified.add(user_id)
            _persist(ctx, "verified_users", sorted(verified))
            _captcha_pending.pop(user_id, None)
            await query.answer("验证成功")
            await query.edit("✅ 验证成功！请重新发送需要转达的消息。")
            return
        question, answer = _generate_captcha()
        _captcha_pending[user_id] = {"answer": answer}
        await query.answer("答案不对，已更换题目", alert=True)
        await query.edit(
            f"🔐 <b>人机验证</b>\n━━━━━━━━━━━━━━\n答案不对，请重新选择：\n\n👉 <b>{question}</b>",
            buttons=_captcha_markup(user_id, answer), parse_mode="html",
        )

    @ctx.on_message(incoming=True)
    async def admin_message(event):
        client, message = event.client, event.message
        sender = await event.get_sender()
        cfg = _cfg(ctx)
        if not cfg["enabled"] or not _target_id(cfg) or event.chat_id != _target_id(cfg):
            return
        if not sender or getattr(sender, "bot", False):
            return
        admins = _configured_admins(cfg)
        if admins and sender.id not in admins:
            ctx.log.warning("忽略非管理员 %s 在中转群 %s 的消息 %s", sender.id, event.chat_id, message.id)
            return
        mappings = _mappings(ctx)
        reply_id = str(getattr(message, "reply_to_msg_id", "") or "")
        mapping = mappings.get(reply_id)
        topic_id = _thread_id(message)
        topics = _topics(ctx)
        user_id = int(mapping["user_id"]) if mapping else next(
            (int(uid) for uid, item in topics.items() if item.get("topic_id") and int(item["topic_id"]) == int(topic_id or 0)), 0)
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
        if not user_id or (message.raw_text or "").startswith("/"):
            if not user_id and not (message.raw_text or "").startswith("/"):
                ctx.log.warning(
                    "中转群消息 %s 未匹配用户：chat_id=%s，topic_id=%s，reply_id=%s",
                    message.id, event.chat_id, topic_id, reply_id or "-",
                )
            return
        try:
            await _send_to_user(client, user_id, message)
            ctx.log.info(
                "管理员回复已发送：管理员 %s，中转消息 %s，话题 %s，用户 %s",
                sender.id, message.id, topic_id or "-", user_id,
            )
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
    _topic_locks.clear()
    _target_entities.clear()
    _bot_api_targets.clear()
    _captcha_pending.clear()
    _user_msg_times.clear()
