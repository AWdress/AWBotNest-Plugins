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
#   - 建议使用的 V2 on_message 参数（按本条消息特征推断）
#   - 末尾附完整 Telethon 原始结构（等价 getmsg）
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
    "version": "1.0.12",
    "author": "AWdress",
    "description": "开发插件时采集消息/会话/按钮/回调的完整信息：回复消息发 .probe 导出带访问路径的字段速查 + 原始结构；.cbprobe 抓 Bot 收到的回调。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png",
    "changelog": "v1.0.3 优化配置界面布局\n- 开关字段统一置顶，采用推荐的栅格布局\n- 参数字段添加 order 排序，提升扫描性\n- 符合 AWBotNest 插件开发规范\nv1.0.2 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "scope": "both",
    "default_enabled": False,
    "config_schema": {
        "delete_command": {
            "type": "boolean", "default": True, "label": "删除命令消息",
            "cols": 3, "order": 1, "section": "功能开关",
            "help": "导出后是否删除你发出的命令本身。",
        },
        "command": {
            "type": "string", "default": ".probe", "label": "探测命令",
            "order": 10, "section": "命令配置",
            "help": "自己发出、以此开头的消息会触发。/probe 与 .probe 等价。",
        },
        "cb_command": {
            "type": "string", "default": ".cbprobe", "label": "回调抓取开关命令",
            "order": 11, "section": "命令配置",
            "help": "「命令 on」开启、「命令 off」关闭抓取 Bot 收到的内联按钮回调。仅 Bot 账号生效。",
        },
        "max_value_len": {
            "type": "slider", "min": 50, "max": 1000, "default": 300, "label": "单字段截断长度",
            "order": 20, "section": "输出设置",
            "help": "速查区里文本类字段超过该长度会截断（原始结构区不截断）。",
        },
    },
}

__plugin__.update(
    version="1.0.12",
    changelog=(
        "v1.0.12 完成 Telethon 原生字段迁移\n"
        "- 修复回复、媒体组、按钮、回调与文件投递接口\n"
        "- 报告改为 AWBotNest V2 原生事件注册示例\n\n"
        + __plugin__["changelog"]
    ),
)

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
def _fmt_chat(chat, message, limit: int) -> list:
    out = ["【会话】 限群/判私聊群聊用"]
    _line(out, "event.chat_id / message.chat_id", getattr(message, "chat_id", None), limit, always=True)
    kind = "private" if getattr(message, "is_private", False) else "group" if getattr(message, "is_group", False) else "channel" if getattr(message, "is_channel", False) else type(chat).__name__
    _line(out, "会话类型", kind, limit, always=True)
    if not chat:
        out.append("  (会话实体未加载，ID 与类型仍可用)")
        return out
    _line(out, "chat.title", getattr(chat, "title", None), limit)
    _line(out, "chat.username", getattr(chat, "username", None), limit)
    _line(out, "chat.first_name", getattr(chat, "first_name", None), limit)
    _line(out, "chat.verified", getattr(chat, "verified", None), limit)
    return out


def _fmt_user(prefix: str, user, limit: int) -> list:
    if not user:
        return []
    out = [f"  --- {prefix} ---"]
    _line(out, f"{prefix}.id", getattr(user, "id", None), limit, always=True)
    _line(out, f"{prefix}.bot", getattr(user, "bot", False), limit, always=True)
    _line(out, f"{prefix}.username", getattr(user, "username", None), limit)
    _line(out, f"{prefix}.first_name", getattr(user, "first_name", None), limit)
    _line(out, f"{prefix}.last_name", getattr(user, "last_name", None), limit)
    return out


def _fmt_sender(message, sender, limit: int) -> list:
    out = ["", "【发送者】 做白名单/身份判断用"]
    out += _fmt_user("sender / await event.get_sender()", sender, limit)
    _line(out, "message.sender_id", getattr(message, "sender_id", None), limit, always=True)
    _line(out, "message.via_bot_id", getattr(message, "via_bot_id", None), limit)
    if len(out) == 2:
        out.append("  (无 sender 实体，可能是频道消息或实体未加载)")
    return out


def _fmt_text(message, limit: int) -> list:
    out = ["", "【文本与实体】 取文本/链接/提及/代码用"]
    body = getattr(message, "raw_text", None) or getattr(message, "message", None) or ""
    _line(out, "message.raw_text", body, limit)
    entities = getattr(message, "entities", None)
    if entities:
        out.append("  message.entities（offset/length 以 UTF-16 计）:")
        for i, e in enumerate(entities):
            etype = type(e).__name__
            off = getattr(e, "offset", 0)
            length = getattr(e, "length", 0)
            extra = []
            if getattr(e, "url", None):
                extra.append(f"url={e.url}")
            if getattr(e, "user_id", None):
                extra.append(f"user_id={e.user_id}")
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
        out.append("    → 实体偏移按 UTF-16 还原；正文统一读取 message.raw_text")
    return out


_MEDIA_ATTRS = (
    "photo", "document", "video", "audio", "voice", "sticker", "animation",
    "video_note", "contact", "location", "venue", "poll", "dice", "game",
    "web_page", "story",
)


def _fmt_media(message, limit: int) -> list:
    out = ["", "【媒体】 取类型/大小/文件名用"]
    media_type = type(message.media).__name__ if getattr(message, "media", None) else None
    _line(out, "message.media", media_type, limit)
    mgid = getattr(message, "grouped_id", None)
    if mgid:
        _line(out, "message.grouped_id", mgid, limit)
    file = getattr(message, "file", None)
    if file:
        for field in ("name", "mime_type", "size", "width", "height", "duration", "emoji", "ext"):
            _line(out, f"message.file.{field}", getattr(file, field, None), limit)
    if not media_type:
        out.append("  (纯文本，无媒体)")
    return out


def _fmt_markup(message, limit: int) -> list:
    out = ["", "【内联键盘 reply_markup】 做点按钮/取 callback_data 用"]
    try:
        rows = getattr(message, "buttons", None) or []
    except Exception:
        rows = []
    if not rows:
        out.append("  (无按钮)")
        return out
    for r, row in enumerate(rows):
        for c, btn in enumerate(row):
            data = getattr(btn, "data", None)
            if isinstance(data, (bytes, bytearray)):
                data = bytes(data).decode("utf-8", "replace")
            bits = [f'text="{getattr(btn, "text", "")}"']
            if data is not None:
                bits.append(f'data="{data}"')
            if getattr(btn, "url", None):
                bits.append(f"url={btn.url}")
            out.append(f"    [行{r}列{c}] " + "  ".join(bits))
    out.append('    → 点按钮: await message.click(text="按钮文字") 或 await message.click(row, col)')
    out.append('    → 匹配回调: @ctx.on_callback(pattern=rb"^前缀")（bot scope）')
    return out


def _fmt_relations(message, reply, limit: int) -> list:
    out = ["", "【关系/其它字段】"]
    _line(out, "message.id", getattr(message, "id", None), limit, always=True)
    _line(out, "message.date", getattr(message, "date", None), limit)
    _line(out, "message.outgoing", getattr(message, "outgoing", None), limit)
    _line(out, "message.edit_date", getattr(message, "edit_date", None), limit)
    _line(out, "message.views", getattr(message, "views", None), limit)
    _line(out, "message.author_signature", getattr(message, "author_signature", None), limit)

    _line(out, "message.reply_to_msg_id", getattr(message, "reply_to_msg_id", None), limit)
    if reply:
        snippet = getattr(reply, "raw_text", None) or type(getattr(reply, "media", None)).__name__
        out.append(f"  await message.get_reply_message() → id={getattr(reply, 'id', None)} 内容: {_clip(snippet, limit)}")
    _line(out, "message.forward", getattr(message, "forward", None), limit)
    _line(out, "message.action", type(message.action).__name__ if getattr(message, "action", None) else None, limit)
    return out


def _fmt_suggested_filters(message) -> list:
    incoming = not bool(getattr(message, "outgoing", False))
    out = ["", "【建议的 V2 事件注册】"]
    out.append(f"  @ctx.on_message(incoming={incoming}, outgoing={not incoming}, pattern=r\"^命令\", chats=[{getattr(message, 'chat_id', 0)}])")
    out.append("  回调按钮使用 @ctx.on_callback(pattern=rb\"^前缀\")")
    out.append("  私聊/群组/频道在回调内读取 event.is_private / is_group / is_channel")
    return out


def _build_report(message, source: str, limit: int, *, chat=None, sender=None, reply=None) -> str:
    head = [
        "=" * 60,
        "AWBotNest 插件开发探针 · probe",
        f"生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"采集来源: {source}",
        "=" * 60,
        "",
    ]
    blocks = []
    blocks += _fmt_chat(chat, message, limit)
    blocks += _fmt_sender(message, sender, limit)
    blocks += _fmt_text(message, limit)
    blocks += _fmt_media(message, limit)
    blocks += _fmt_markup(message, limit)
    blocks += _fmt_relations(message, reply, limit)
    blocks += _fmt_suggested_filters(message)
    blocks += [
        "",
        "=" * 60,
        "【完整原始结构】 Telethon repr（等价 getmsg）",
        "=" * 60,
        repr(message),
    ]
    return "\n".join(head + blocks)


def _build_cb_report(cb, limit: int, *, sender=None) -> str:
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
        f"  event.query.query_id          = {getattr(getattr(cb, 'query', None), 'query_id', None)}",
        f"  event.data                    = {data!r}",
        f"  event.chat_id                 = {getattr(cb, 'chat_id', None)}",
        f"  event.message_id              = {getattr(cb, 'message_id', None)}",
        f"  → 匹配: @ctx.on_callback(pattern=rb\"^{(data or '').split(':')[0]}\")",
    ]
    lines += _fmt_user("await event.get_sender()", sender, limit)
    lines += ["", "=" * 60, "【完整原始结构】 Telethon repr", "=" * 60, repr(cb)]
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
        bot = getattr(ctx, "bot", None)
        settings = getattr(ctx, "settings", None)
        owner_id = int(str(getattr(settings, "default_bot_chat_id", "") or 0))
        if bot is not None and bot.is_connected() and owner_id:
            await bot.send_file(owner_id, str(file_path), caption="【插件开发探针】采集结果")
            return "Bot 通知"
        await client.send_file("me", str(file_path), caption="【插件开发探针】采集结果")
        return "收藏夹（Bot 不可用回退）"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# setup
# --------------------------------------------------------------------------- #
async def setup(ctx):

    @ctx.on_message(outgoing=True, incoming=False)
    async def on_probe(event):
        client, message = event.client, event.message
        text = message.text or ""
        cfg = ctx.config
        probe_bare = _bare(cfg.get("command", ".probe"), "probe")
        cb_bare = _bare(cfg.get("cb_command", ".cbprobe"), "cbprobe")

        # --- 回调抓取开关 ---
        if _matches(text, cb_bare):
            arg = text.split(maxsplit=1)[1].strip().lower() if len(text.split(maxsplit=1)) > 1 else ""
            if arg in ("on", "1", "开"):
                await ctx.storage.set(_CB_FLAG_KEY, "1")
                tip = "回调抓取已开启 ✓ 现在去点 Bot 的内联按钮，结构会被导出。再发「命令 off」关闭。"
            elif arg in ("off", "0", "关"):
                await ctx.storage.delete(_CB_FLAG_KEY)
                tip = "回调抓取已关闭 ✓"
            else:
                state = "开启" if await ctx.storage.get(_CB_FLAG_KEY) else "关闭"
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

        reply = await event.get_reply_message()
        if reply:
            target, source = reply, "回复的消息"
        else:
            target, source = message, "当前会话 + 命令消息自身（未回复任何消息）"

        try:
            chat = await event.get_chat()
            sender = await target.get_sender() if hasattr(target, "get_sender") else await event.get_sender()
            target_reply = await target.get_reply_message() if hasattr(target, "get_reply_message") else None
            report = _build_report(
                target, source, limit, chat=chat, sender=sender, reply=target_reply,
            )
            hint = getattr(target, "raw_text", None) or "probe"
            sent_to = await _deliver(ctx, client, report, hint)

            try:
                n_btn = sum(len(row) for row in (target.buttons or []))
            except Exception:
                n_btn = 0
            summary = (
                f"已导出到{sent_to} ✓ chat.id={getattr(target, 'chat_id', '?')} "
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
                ctx.create_task(_cleanup(), name="probe-cleanup")
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[probe] 导出失败: %r", e)
            try:
                await message.edit(f"导出失败: {e.__class__.__name__}: {e}")
            except Exception:
                pass

    @ctx.on_callback()
    async def on_cb(callback_query):
        if not await ctx.storage.get(_CB_FLAG_KEY):
            return
        client = callback_query.client
        try:
            data = getattr(callback_query, "data", None)
            if isinstance(data, (bytes, bytearray)):
                data = bytes(data).decode("utf-8", "replace")
            sender = await callback_query.get_sender()
            report = _build_cb_report(callback_query, 300, sender=sender)
            await _deliver(ctx, client, report, f"cb_{data or 'x'}")
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[probe] 回调导出失败: %r", e)


async def teardown(ctx):
    pass
