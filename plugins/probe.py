# =============================================================================
# AWBotNest 插件：插件开发探针（probe）
#
# 给插件开发者用的「信息采集器」。在 getmsg 的原始结构之上，额外生成一份
# 带「访问路径」的速查，把开发时最常翻的字段全拆好：
#   - 会话 chat（id / type / title / username，做限群、判私聊群聊用）
#   - 发送者 from_user / sender_chat（id / username / is_bot，做白名单用）
#   - 文本与实体 entities（取链接 url、@提及、代码块，做格式解析用）
#   - 媒体 media（photo / document / video... 的 file_id / mime / 大小）
#   - 内联键盘 reply_markup（每个按钮的 text 与 callback_data / url，做点按钮用）
#   - 被回复消息 / 转发来源 / via_bot 等关系字段
#   - 建议使用的 ctx.filters（按本条消息特征推断）
#   - 末尾附完整 Pyrogram JSON 结构（等价 getmsg）
#
# 触发：
#   回复一条消息发 .probe   → 导出「那条消息」的完整开发信息
#   不回复直接发  .probe    → 导出「当前会话」的 chat 信息 + 命令消息自身
#   .cbprobe on / off       → 开/关「回调抓取」：开启后 Bot 收到的内联按钮点击
#                             （callback_query）会被导出，做 bot 端按钮插件时用
#
# 导出物经 Bot 发到「平台通知」（主人 Bot 私聊）；Bot 不可用时回退到收藏夹。
# =============================================================================

import asyncio
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

__plugin__ = {
    "name": "插件开发探针",
    "id": "probe",
    "version": "1.0.2",
    "author": "AWdress",
    "description": "开发插件时采集消息/会话/按钮/回调的完整信息：回复消息发 .probe 导出带访问路径的字段速查 + 原始结构；.cbprobe 抓 Bot 收到的回调。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png",
    "changelog": "v1.0.2 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "scope": "both",
    "default_enabled": False,
    "config_schema": {
        "command": {
            "type": "string", "default": ".probe", "label": "探测命令",
            "section": "命令", "help": "自己发出、以此开头的消息会触发。/probe 与 .probe 等价。",
        },
        "cb_command": {
            "type": "string", "default": ".cbprobe", "label": "回调抓取开关命令",
            "section": "命令", "help": "「命令 on」开启、「命令 off」关闭抓取 Bot 收到的内联按钮回调。仅 Bot 账号生效。",
        },
        "delete_command": {
            "type": "boolean", "default": True, "label": "删除命令消息",
            "section": "输出与清理", "help": "导出后是否删除你发出的命令本身。",
        },
        "max_value_len": {
            "type": "number", "default": 300, "label": "单字段截断长度",
            "section": "输出与清理", "help": "速查区里文本类字段超过该长度会截断（原始结构区不截断）。",
        },
    },
}

_CB_FLAG_KEY = "capture_cb"


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _bare(command: str, fallback: str) -> str:
    return (command or "").lstrip("/.").strip().lower() or fallback


def _matches(text: str, bare: str) -> bool:
    head = text.split(maxsplit=1)[0].lower() if text else ""
    return head in (f"/{bare}", f".{bare}")


def _enum_name(value) -> str:
    """枚举取可读名：ChatType.SUPERGROUP -> 'supergroup'；普通值原样 str。"""
    name = getattr(value, "name", None)
    return name.lower() if isinstance(name, str) else str(value)


def _clip(value, limit: int) -> str:
    s = "" if value is None else str(value)
    s = s.replace("\r", "")
    if len(s) > limit:
        return s[:limit] + f" …(+{len(s) - limit}字)"
    return s


def _safe_slug(text, fallback: str = "probe") -> str:
    import re
    slug = re.sub(r"[^\w一-鿿-]", "", (text or "").strip())[:12]
    return slug or fallback


def _line(lines: list, attr: str, value, limit: int, *, always: bool = False):
    """value 为空且非 always 时不输出，保持速查区干净。"""
    if value is None or (value == "" and not always):
        return
    lines.append(f"  {attr:<28}= {_clip(value, limit)}")


# --------------------------------------------------------------------------- #
# 各区块格式化
# --------------------------------------------------------------------------- #
def _fmt_chat(chat, limit: int) -> list:
    out = ["【会话 chat】 限群/判私聊群聊用"]
    if not chat:
        out.append("  (无)")
        return out
    _line(out, "message.chat.id", getattr(chat, "id", None), limit, always=True)
    _line(out, "message.chat.type", _enum_name(getattr(chat, "type", None)), limit, always=True)
    _line(out, "message.chat.title", getattr(chat, "title", None), limit)
    _line(out, "message.chat.username", getattr(chat, "username", None), limit)
    _line(out, "message.chat.first_name", getattr(chat, "first_name", None), limit)
    _line(out, "message.chat.is_verified", getattr(chat, "is_verified", None), limit)
    return out


def _fmt_user(prefix: str, user, limit: int) -> list:
    if not user:
        return []
    out = [f"  --- {prefix} ---"]
    _line(out, f"{prefix}.id", getattr(user, "id", None), limit, always=True)
    _line(out, f"{prefix}.is_bot", getattr(user, "is_bot", None), limit, always=True)
    _line(out, f"{prefix}.username", getattr(user, "username", None), limit)
    _line(out, f"{prefix}.first_name", getattr(user, "first_name", None), limit)
    _line(out, f"{prefix}.last_name", getattr(user, "last_name", None), limit)
    return out


def _fmt_sender(message, limit: int) -> list:
    out = ["", "【发送者】 做白名单/身份判断用"]
    out += _fmt_user("message.from_user", getattr(message, "from_user", None), limit)
    sc = getattr(message, "sender_chat", None)
    if sc:
        out.append("  --- message.sender_chat（以频道/群身份发言）---")
        _line(out, "message.sender_chat.id", getattr(sc, "id", None), limit, always=True)
        _line(out, "message.sender_chat.title", getattr(sc, "title", None), limit)
        _line(out, "message.sender_chat.username", getattr(sc, "username", None), limit)
    vb = getattr(message, "via_bot", None)
    if vb:
        out += _fmt_user("message.via_bot", vb, limit)
    if len(out) == 2:
        out.append("  (无 from_user，可能是频道消息)")
    return out


def _fmt_text(message, limit: int) -> list:
    out = ["", "【文本与实体】 取文本/链接/提及/代码用"]
    text = getattr(message, "text", None)
    caption = getattr(message, "caption", None)
    _line(out, "message.text", text, limit)
    _line(out, "message.caption", caption, limit)

    for field, ent_attr in (("text", "entities"), ("caption", "caption_entities")):
        entities = getattr(message, ent_attr, None)
        body = getattr(message, field, None) or ""
        if not entities:
            continue
        out.append(f"  {ent_attr}（offset/length 以 UTF-16 计）:")
        for i, e in enumerate(entities):
            etype = _enum_name(getattr(e, "type", None))
            off = getattr(e, "offset", 0)
            length = getattr(e, "length", 0)
            extra = []
            if getattr(e, "url", None):
                extra.append(f"url={e.url}")
            if getattr(e, "user", None):
                extra.append(f"user_id={getattr(e.user, 'id', None)}")
            if getattr(e, "language", None):
                extra.append(f"lang={e.language}")
            if getattr(e, "custom_emoji_id", None):
                extra.append(f"custom_emoji_id={e.custom_emoji_id}")
            # UTF-16 切片还原实体覆盖的文本片段
            try:
                u16 = body.encode("utf-16-le")
                frag = u16[off * 2:(off + length) * 2].decode("utf-16-le", "replace")
            except Exception:
                frag = ""
            line = f"    [{i}] type={etype} offset={off} length={length}"
            if extra:
                line += "  " + " ".join(extra)
            out.append(line)
            if frag:
                out.append(f"        覆盖文本: {_clip(frag, limit)}")
        out.append(f"    → 取实体文本: body[e.offset:e.offset+e.length]（注意按 UTF-16 还原，body={field}）")
    return out


_MEDIA_ATTRS = (
    "photo", "document", "video", "audio", "voice", "sticker", "animation",
    "video_note", "contact", "location", "venue", "poll", "dice", "game",
    "web_page", "story",
)


def _fmt_media(message, limit: int) -> list:
    out = ["", "【媒体 media】 取 file_id/类型/大小用"]
    media_type = _enum_name(getattr(message, "media", None)) if getattr(message, "media", None) else None
    _line(out, "message.media", media_type, limit)
    mgid = getattr(message, "media_group_id", None)
    if mgid:
        _line(out, "message.media_group_id", mgid, limit)

    found = False
    for attr in _MEDIA_ATTRS:
        obj = getattr(message, attr, None)
        if not obj:
            continue
        found = True
        out.append(f"  --- message.{attr} ---")
        for f in ("file_id", "file_unique_id", "file_name", "mime_type",
                  "file_size", "duration", "width", "height", "emoji",
                  "phone_number", "latitude", "longitude", "question"):
            if hasattr(obj, f):
                _line(out, f"message.{attr}.{f}", getattr(obj, f, None), limit)
        # 图片缩略图列表（photo 取最后一档是原图）
        if attr in ("photo",) and hasattr(obj, "thumbs"):
            thumbs = getattr(obj, "thumbs", None) or []
            if thumbs:
                out.append(f"    thumbs: {len(thumbs)} 档（小→大）")
    if not found and not media_type:
        out.append("  (纯文本，无媒体)")
    return out


def _fmt_markup(message, limit: int) -> list:
    out = ["", "【内联键盘 reply_markup】 做点按钮/取 callback_data 用"]
    markup = getattr(message, "reply_markup", None)
    if not markup:
        out.append("  (无按钮)")
        return out

    inline = getattr(markup, "inline_keyboard", None)
    keyboard = getattr(markup, "keyboard", None)
    if inline:
        out.append("  inline_keyboard（InlineKeyboardMarkup）:")
        for r, row in enumerate(inline):
            for c, btn in enumerate(row):
                bits = [f'text="{getattr(btn, "text", "")}"']
                data = getattr(btn, "callback_data", None)
                if data is not None:
                    if isinstance(data, (bytes, bytearray)):
                        data = bytes(data).decode("utf-8", "replace")
                    bits.append(f'callback_data="{data}"')
                for f in ("url", "switch_inline_query", "switch_inline_query_current_chat", "user_id"):
                    v = getattr(btn, f, None)
                    if v:
                        bits.append(f"{f}={v}")
                if getattr(btn, "web_app", None):
                    bits.append(f"web_app={getattr(btn.web_app, 'url', '?')}")
                out.append(f"    [行{r}列{c}] " + "  ".join(bits))
        out.append('    → 点按钮: await message.click("按钮文字")  或  message.click(row, col)')
        out.append('    → 匹配回调: @ctx.on_callback(ctx.filters.regex(r"^前缀"))（bot scope）')
    elif keyboard:
        out.append("  keyboard（ReplyKeyboardMarkup，普通回复键盘）:")
        for r, row in enumerate(keyboard):
            texts = [getattr(b, "text", str(b)) for b in row]
            out.append(f"    行{r}: {texts}")
    else:
        out.append(f"  其它类型: {type(markup).__name__}")
    return out


def _fmt_relations(message, limit: int) -> list:
    out = ["", "【关系/其它字段】"]
    _line(out, "message.id", getattr(message, "id", None), limit, always=True)
    _line(out, "message.date", getattr(message, "date", None), limit)
    _line(out, "message.outgoing", getattr(message, "outgoing", None), limit)
    _line(out, "message.edit_date", getattr(message, "edit_date", None), limit)
    _line(out, "message.views", getattr(message, "views", None), limit)
    _line(out, "message.author_signature", getattr(message, "author_signature", None), limit)

    reply = getattr(message, "reply_to_message", None)
    _line(out, "message.reply_to_message_id", getattr(message, "reply_to_message_id", None), limit)
    if reply:
        snippet = getattr(reply, "text", None) or getattr(reply, "caption", None) or _enum_name(getattr(reply, "media", None))
        out.append(f"  message.reply_to_message → id={getattr(reply, 'id', None)} 内容: {_clip(snippet, limit)}")

    for f in ("forward_from", "forward_from_chat", "forward_sender_name", "forward_date"):
        v = getattr(message, f, None)
        if v:
            if hasattr(v, "id"):
                v = f"id={v.id} {getattr(v, 'username', None) or getattr(v, 'title', None) or ''}".strip()
            _line(out, f"message.{f}", v, limit)

    svc = getattr(message, "service", None)
    if svc:
        _line(out, "message.service", _enum_name(svc), limit, always=True)
    return out


def _fmt_suggested_filters(message) -> list:
    out = ["", "【建议的 ctx.filters】 按本条特征推断，组合用 & | ~"]
    fs = []
    if getattr(message, "outgoing", None):
        fs.append("ctx.filters.outgoing")
    else:
        fs.append("ctx.filters.incoming")

    chat_type = _enum_name(getattr(getattr(message, "chat", None), "type", None))
    if chat_type == "private":
        fs.append("ctx.filters.private")
    elif chat_type in ("group", "supergroup"):
        fs.append("ctx.filters.group")
    elif chat_type == "channel":
        fs.append("ctx.filters.channel")

    if getattr(message, "text", None):
        fs.append("ctx.filters.text")
    if getattr(message, "caption", None):
        fs.append("ctx.filters.caption")
    for attr in ("photo", "document", "video", "audio", "voice", "sticker",
                 "animation", "video_note", "location", "contact", "poll", "dice"):
        if getattr(message, attr, None):
            fs.append(f"ctx.filters.{attr}")
    if getattr(message, "via_bot", None):
        fs.append("ctx.filters.via_bot")
    if getattr(message, "reply_to_message", None):
        fs.append("ctx.filters.reply")
    if getattr(message, "forward_date", None) or getattr(message, "forward_from", None):
        fs.append("ctx.filters.forward")
    fu = getattr(message, "from_user", None)
    if fu and getattr(fu, "is_bot", None):
        fs.append("ctx.filters.bot")

    out.append("  " + " & ".join(fs) if fs else "  (无法推断)")
    out.append('  限定群/人: ctx.filters.chat(chat_id)  /  ctx.filters.user(user_id)')
    out.append('  命令触发: ctx.filters.command("xxx")')
    return out


def _build_report(message, source: str, limit: int) -> str:
    head = [
        "=" * 60,
        "AWBotNest 插件开发探针 · probe",
        f"生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"采集来源: {source}",
        "=" * 60,
        "",
    ]
    blocks = []
    blocks += _fmt_chat(getattr(message, "chat", None), limit)
    blocks += _fmt_sender(message, limit)
    blocks += _fmt_text(message, limit)
    blocks += _fmt_media(message, limit)
    blocks += _fmt_markup(message, limit)
    blocks += _fmt_relations(message, limit)
    blocks += _fmt_suggested_filters(message)
    blocks += [
        "",
        "=" * 60,
        "【完整原始结构】 Pyrogram JSON（等价 getmsg，字段最全）",
        "=" * 60,
        str(message),
    ]
    return "\n".join(head + blocks)


def _build_cb_report(cb, limit: int) -> str:
    data = getattr(cb, "data", None)
    if isinstance(data, (bytes, bytearray)):
        data = bytes(data).decode("utf-8", "replace")
    lines = [
        "=" * 60,
        "AWBotNest 插件开发探针 · 回调抓取（CallbackQuery）",
        f"生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "=" * 60,
        "",
        "【回调核心】 on_callback 要匹配的就是 data",
        f"  callback_query.id            = {getattr(cb, 'id', None)}",
        f"  callback_query.data          = {data!r}",
        f"  → 匹配: @ctx.on_callback(ctx.filters.regex(r\"^{(data or '').split(':')[0]}\"))",
    ]
    lines += _fmt_user("callback_query.from_user", getattr(cb, "from_user", None), limit)
    msg = getattr(cb, "message", None)
    if msg:
        lines.append(f"  callback_query.message.id       = {getattr(msg, 'id', None)}")
        lines.append(f"  callback_query.message.chat.id  = {getattr(getattr(msg, 'chat', None), 'id', None)}")
    if getattr(cb, "inline_message_id", None):
        lines.append(f"  callback_query.inline_message_id = {cb.inline_message_id}")
    lines += ["", "=" * 60, "【完整原始结构】", "=" * 60, str(cb)]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 导出投递
# --------------------------------------------------------------------------- #
async def _deliver(ctx, client, content: str, name_hint: str) -> str:
    """写 txt 并经 Bot 发到平台通知；Bot 不可用回退收藏夹。返回去向描述。"""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    tmp_dir = Path(tempfile.mkdtemp(prefix="probe_"))
    file_path = tmp_dir / f"{_safe_slug(name_hint)}_{ts}.txt"
    try:
        file_path.write_text(content, encoding="utf-8")
        bot = ctx.bot
        if bot.connected and ctx.owner_id:
            await bot.raw.send_document(
                ctx.owner_id, str(file_path),
                caption="【插件开发探针】采集结果",
            )
            return "Bot 通知"
        await client.send_document("me", str(file_path))
        return "收藏夹（Bot 不可用回退）"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# setup
# --------------------------------------------------------------------------- #
async def setup(ctx):

    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-16, target="user")
    async def on_probe(client, message):
        text = message.text or ""
        cfg = ctx.config
        probe_bare = _bare(cfg.get("command", ".probe"), "probe")
        cb_bare = _bare(cfg.get("cb_command", ".cbprobe"), "cbprobe")

        # --- 回调抓取开关 ---
        if _matches(text, cb_bare):
            arg = text.split(maxsplit=1)[1].strip().lower() if len(text.split(maxsplit=1)) > 1 else ""
            if arg in ("on", "1", "开"):
                ctx.kv.set(_CB_FLAG_KEY, "1")
                tip = "回调抓取已开启 ✓ 现在去点 Bot 的内联按钮，结构会被导出。再发「命令 off」关闭。"
            elif arg in ("off", "0", "关"):
                ctx.kv.delete(_CB_FLAG_KEY)
                tip = "回调抓取已关闭 ✓"
            else:
                state = "开启" if ctx.kv.get(_CB_FLAG_KEY) else "关闭"
                tip = f"当前回调抓取：{state}。用法：{cfg.get('cb_command', '.cbprobe')} on / off"
            try:
                await message.edit(tip)
            except Exception:
                pass
            return

        if not _matches(text, probe_bare):
            return

        # --- 消息/会话探测 ---
        try:
            limit = int(cfg.get("max_value_len", 300) or 300)
        except (TypeError, ValueError):
            limit = 300

        reply = message.reply_to_message
        if reply:
            target, source = reply, "回复的消息"
        else:
            target, source = message, "当前会话 + 命令消息自身（未回复任何消息）"

        try:
            report = _build_report(target, source, limit)
            hint = getattr(target, "text", None) or getattr(target, "caption", None) or "probe"
            sent_to = await _deliver(ctx, client, report, hint)

            chat = getattr(target, "chat", None)
            n_btn = 0
            mk = getattr(target, "reply_markup", None)
            if mk and getattr(mk, "inline_keyboard", None):
                n_btn = sum(len(r) for r in mk.inline_keyboard)
            summary = (
                f"已导出到{sent_to} ✓ chat.id={getattr(chat, 'id', '?')} "
                f"msg.id={getattr(target, 'id', '?')} 按钮={n_btn}"
            )
            try:
                await message.edit(summary)
            except Exception:
                pass

            if cfg.get("delete_command", True) and not reply:
                # 未回复时命令消息本身就是被探测对象，保留反馈不删
                pass
            elif cfg.get("delete_command", True):
                async def _cleanup(m=message):
                    await asyncio.sleep(4)
                    try:
                        await m.delete()
                    except Exception:
                        pass
                asyncio.create_task(_cleanup())
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[probe] 导出失败: %r", e)
            try:
                await message.edit(f"导出失败: {e.__class__.__name__}: {e}")
            except Exception:
                pass

    @ctx.on_callback(target="bot")
    async def on_cb(client, callback_query):
        if not ctx.kv.get(_CB_FLAG_KEY):
            return
        try:
            data = getattr(callback_query, "data", None)
            if isinstance(data, (bytes, bytearray)):
                data = bytes(data).decode("utf-8", "replace")
            report = _build_cb_report(callback_query, 300)
            await _deliver(ctx, client, report, f"cb_{data or 'x'}")
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[probe] 回调导出失败: %r", e)


async def teardown(ctx):
    pass
