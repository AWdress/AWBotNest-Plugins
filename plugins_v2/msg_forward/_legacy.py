# =============================================================================
# AWBotNest 插件：消息转发（msg_forward）
#
# 把来源会话（群/频道/bot/私聊）的新消息转发到一个或多个目标会话。
# 支持多条规则，每条可按「消息类型 / 关键词 / 发送者」过滤，可选原生转发或复制搬运。
# 用你的用户账号监听——来源和目标都需要你账号已加入/订阅/接触过。
# =============================================================================

import re
import time

__plugin__ = {
    "name": "消息转发",
    "id": "msg_forward",
    "version": "1.0.3",
    "author": "AWdress",
    "description": "把来源会话的消息按规则转发到目标会话，支持多规则、类型/关键词/发送者过滤、原生转发或复制搬运。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_relay.png",
    "changelog": "v1.0.3 显示群组/频道名称\n- 转发日志同时显示来源和目标会话名称，保留 ID 便于排查\n- 配置保存后自动解析已填写的会话 ID，在设置页显示名称\n\nv1.0.2 优化配置界面布局\n- 开关字段统一置顶，采用推荐的栅格布局\n- 参数字段添加 order 排序，提升扫描性\n- 符合 AWBotNest 插件开发规范\nv1.0.1 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "enable": {
            "type": "boolean", "default": False, "label": "启用转发",
            "cols": 3, "order": 1, "section": "功能开关",
            "help": "总开关。关闭后不转发任何消息。",
        },
        "forward_album": {
            "type": "boolean", "default": True, "label": "整组转发相册",
            "cols": 3, "order": 2, "section": "功能开关",
            "help": "相册（多图/多视频）整组一起转；关闭则每个文件单独转。",
        },
        "resolved_chat_names": {
            "type": "info", "label": "已识别会话名称", "order": 9, "section": "规则",
            "help": "保存配置后自动从账号会话列表解析名称；解析失败时保留会话 ID。",
        },
        "rules": {
            "type": "list", "default": [], "label": "转发规则", "item_label": "规则",
            "order": 10, "section": "规则",
            "fields": {
                "source": {"type": "string", "label": "来源会话",
                           "help": "填 -100 开头的会话ID 或 @用户名"},
                "targets": {"type": "string", "label": "转发到",
                            "help": "目标会话ID / @用户名，逗号可填多个"},
                "types": {"type": "multiselect", "label": "消息类型", "default": [],
                          "options": [
                              {"value": "text", "label": "文本"},
                              {"value": "link", "label": "链接"},
                              {"value": "photo", "label": "图片"},
                              {"value": "video", "label": "视频"},
                              {"value": "document", "label": "文件"},
                              {"value": "audio", "label": "音频"},
                          ]},
                "kw": {"type": "string", "label": "关键词",
                       "help": "含任一才转，逗号分隔；留空=不限"},
                "nkw": {"type": "string", "label": "排除词",
                        "help": "含任一则不转，逗号分隔；留空=不排除"},
                "sender": {"type": "string", "label": "只转谁发的",
                           "help": "@用户名 / 数字ID / bot(只转机器人)，逗号多个；留空=所有人"},
                "copy": {"type": "boolean", "label": "复制搬运", "default": False,
                         "help": "关=原生转发（带「转发自」）；开=复制搬运（不带来源标记）"},
            },
        },
    },
}

_URL_RE = re.compile(r"https?://", re.IGNORECASE)


def _split(raw) -> list[str]:
    if isinstance(raw, (list, tuple, set)):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [x.strip() for x in str(raw or "").replace("，", ",").split(",") if x.strip()]


def _normalize(raw):
    """会话标识归一：@用户名→str，数字→int，其它→None。"""
    s = str(raw or "").strip()
    if not s:
        return None
    if s.startswith("@"):
        return s
    try:
        return int(s)
    except ValueError:
        return None


def _chat_label(chat_id, chat=None) -> str:
    """Return a readable Telegram chat name, falling back to the ID."""
    if chat is not None:
        title = getattr(chat, "title", None)
        if title:
            return str(title)
        first = getattr(chat, "first_name", None) or ""
        last = getattr(chat, "last_name", None) or ""
        name = " ".join(x for x in (first, last) if x).strip()
        if name:
            return name
        username = getattr(chat, "username", None)
        if username:
            return f"@{username}"
    return str(chat_id)


async def _resolve_chat_label(client, chat_id, cache: dict) -> str:
    key = str(chat_id)
    if key in cache:
        return cache[key]
    try:
        chat = await client.get_chat(chat_id)
        label = _chat_label(chat_id, chat)
    except Exception:  # noqa: BLE001
        label = str(chat_id)
    if label != str(chat_id):
        cache[key] = label
    return label


async def _refresh_config_names(ctx, cache: dict) -> None:
    """Resolve configured IDs once so the native settings form can show names."""
    values = []
    for rule in (ctx.config.get("rules") or []):
        if not isinstance(rule, dict):
            continue
        for key in ("source", "targets"):
            for raw in _split(rule.get(key)):
                value = _normalize(raw)
                if value is not None:
                    values.append(value)
    if not values:
        return
    apps = list(getattr(ctx, "user_apps", None) or [])
    if not apps:
        return
    labels = []
    seen = set()
    for value in values:
        if str(value) in seen:
            continue
        seen.add(str(value))
        label = str(value)
        for client in apps:
            label = await _resolve_chat_label(client, value, cache)
            if label != str(value):
                break
        labels.append(f"{label} ({value})")
    if labels:
        ctx.update_config({"resolved_chat_names": ", ".join(labels)})


def _has_media(message) -> bool:
    return any(getattr(message, a, None) for a in
               ("photo", "video", "document", "audio", "voice", "animation", "sticker", "video_note"))


def _chat_match(message, src) -> bool:
    if isinstance(src, int):
        return message.chat.id == src
    if isinstance(src, str) and src.startswith("@"):
        return (getattr(message.chat, "username", "") or "").lower() == src[1:].lower()
    return False


def _type_ok(msgs, text, types) -> bool:
    """types 为空=不限；否则组内任一消息命中任一类型即通过（相册按整组判）。"""
    if not types:
        return True
    if "text" in types and any(m.text and not _has_media(m) for m in msgs):
        return True
    if "link" in types and _URL_RE.search(text):
        return True
    for m in msgs:
        if "photo" in types and m.photo:
            return True
        if "video" in types and (m.video or m.animation):
            return True
        if "document" in types and m.document:
            return True
        if "audio" in types and (m.audio or m.voice):
            return True
    return False


def _sender_ok(message, senders) -> bool:
    if not senders:
        return True
    u = message.from_user
    for s in senders:
        sl = s.lower()
        if sl == "bot":
            if u and u.is_bot:
                return True
        elif s.startswith("@"):
            if u and (u.username or "").lower() == sl[1:]:
                return True
        else:
            try:
                if u and u.id == int(s):
                    return True
            except ValueError:
                pass
    return False


def _pass_filters(rule, msgs, text) -> bool:
    if not _type_ok(msgs, text, rule.get("types") or []):
        return False
    kw = _split(rule.get("kw"))
    if kw and not any(w in text for w in kw):
        return False
    nkw = _split(rule.get("nkw"))
    if nkw and any(w in text for w in nkw):
        return False
    if not _sender_ok(msgs[0], _split(rule.get("sender"))):
        return False
    return True


async def _forward(client, message, tgt, copy, album, album_ids):
    src_id = message.chat.id
    if album:
        if copy:
            await client.copy_media_group(tgt, src_id, message.id)
        else:
            await client.forward_messages(tgt, src_id, album_ids)
    else:
        if copy:
            await client.copy_message(tgt, src_id, message.id)
        else:
            await client.forward_messages(tgt, src_id, message.id)


async def _process(client, cfg, rules, message, seen, ctx, name_cache):
    gid = getattr(message, "media_group_id", None)
    album = bool(gid) and cfg.get("forward_album", True)

    album_msgs = None
    if album:
        now = time.time()
        for k in [k for k, t in seen.items() if now - t > 60]:
            seen.pop(k, None)
        if gid in seen:
            return  # 该相册已处理，跳过组内后续消息
        seen[gid] = now
        # 提前取整组：相册 caption 常只在一条上，需聚合后再过滤；同时备好转发用的 ids
        try:
            album_msgs = await client.get_media_group(message.chat.id, message.id)
        except Exception as e:  # noqa: BLE001
            ctx.log.warning("[消息转发] 取相册失败: %r", e)
            album_msgs = [message]

    msgs = album_msgs or [message]
    album_ids = [m.id for m in album_msgs] if album_msgs else None
    text = next((m.caption or m.text or "" for m in msgs if (m.caption or m.text)), "")

    for rule in rules:
        src = _normalize(rule.get("source"))
        if src is None or not _chat_match(message, src):
            continue
        if not _pass_filters(rule, msgs, text):
            continue
        targets = [t for t in (_normalize(x) for x in _split(rule.get("targets"))) if t is not None]
        if not targets:
            continue
        copy = bool(rule.get("copy"))
        for tgt in targets:
            try:
                await _forward(client, message, tgt, copy, album, album_ids)
                source_name = _chat_label(message.chat.id, message.chat)
                target_name = await _resolve_chat_label(client, tgt, name_cache)
                ctx.log.info("[消息转发] %s (%s) -> %s (%s) (%s)",
                             source_name, message.chat.id, target_name, tgt,
                             "copy" if copy else "fwd")
            except Exception as e:  # noqa: BLE001
                source_name = _chat_label(message.chat.id, message.chat)
                target_name = name_cache.get(str(tgt), str(tgt))
                ctx.log.warning("[消息转发] 转发失败 %s (%s)->%s (%s): %r",
                                source_name, message.chat.id, target_name, tgt, e)


async def setup(ctx):
    seen: dict = {}  # media_group_id -> ts，防相册重复转
    name_cache: dict = {}

    try:
        await _refresh_config_names(ctx, name_cache)
    except Exception as e:  # noqa: BLE001
        ctx.log.debug("[消息转发] 读取会话名称失败: %r", e)

    @ctx.on_message(ctx.filters.incoming, group=5)
    async def relay(client, message):
        cfg = ctx.config
        if not cfg.get("enable", False):
            return
        rules = cfg.get("rules") or []
        if not rules:
            return
        try:
            await _process(client, cfg, rules, message, seen, ctx, name_cache)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[消息转发] 处理异常: %r", e)


async def teardown(ctx):
    pass
