# =============================================================================
# AWBotNest 插件：AI 助手（ai）
#
# 用你的用户账号提供两种 AI 能力：
#   1. 人形回复：私聊直接对话；群里 @你 或回复你的消息时对话（带上下文记忆）。
#   2. /ai 解释：回复一条消息（或图片）再发 /ai，让 AI 解释/解答（单次，无记忆）。
#
# 自洽实现：直接调用 OpenAI 兼容接口（openai 库），配置全在 config_schema，
# 对话历史存 ctx.kv，不依赖平台 DI 容器。
# =============================================================================

import asyncio
import os
import random
import re
import tempfile
import time
from collections import deque
from html import escape

from ._engine import generate, classify_error

__plugin__ = {
    "name": "AI 助手",
    "id": "ai",
    "version": "1.0.3",
    "author": "AWdress",
    "description": "私聊/群@你时 AI 人形对话（带记忆，群聊可指定群组）；可选随机主动搭话开启话题；回复消息发 /ai 让 AI 解释或解答（支持图片）。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        # —— 接口 ——
        "api_key": {
            "type": "password", "default": "", "label": "API Key",
            "section": "接口", "help": "OpenAI 兼容接口的密钥。",
        },
        "base_url": {
            "type": "string", "default": "", "label": "接口地址(Base URL)",
            "section": "接口", "help": "OpenAI 兼容接口地址，如 https://api.openai.com/v1。留空用官方默认。",
        },
        "model": {
            "type": "string", "default": "gpt-3.5-turbo", "label": "模型",
            "section": "接口", "help": "如 gpt-4o-mini、gpt-3.5-turbo 等。",
        },
        # —— 人形回复 ——
        "enable_private_chat": {
            "type": "boolean", "default": True, "label": "私聊回复",
            "section": "人形回复", "help": "私聊里直接对话。",
        },
        "enable_group_chat": {
            "type": "boolean", "default": True, "label": "群聊回复",
            "section": "人形回复", "help": "群里 @你 或回复你的消息时对话。",
        },
        "group_chat_ids": {
            "type": "string", "default": "", "label": "群聊生效群组(可选)",
            "section": "人形回复", "show_if": {"enable_group_chat": True},
            "help": "只在这些群里 @你/回复你 才对话，群ID用逗号分隔。留空 = 所有群。",
        },
        "system_prompt": {
            "type": "text",
            "default": (
                "# Role\n你是一个相处了很久的普通网友。\n\n"
                "# Rules\n"
                "1. 语气口语化、随性、接地气，就像在微信或QQ上聊天。\n"
                "2. 每次回复必须精简，严禁长篇大论。\n"
                "3. 绝对不能超过 20 个字。\n"
                "4. 绝对不要在回复中模仿、复述或带入用户的动作动作。\n"
                "5. 偶尔可以在句末加一个合适的 emoji（如 😂、🤷‍♂️、👀），不要过多。"
            ),
            "label": "人设(系统提示词)",
            "section": "人形回复",
        },
        "max_history": {
            "type": "slider", "default": 10, "label": "记忆轮数",
            "min": 0, "max": 40, "step": 1, "section": "人形回复",
            "help": "每个会话保留多少条历史消息（含系统提示）。0 = 不记忆。",
        },
        # —— 主动搭话 ——
        "enable_proactive": {
            "type": "boolean", "default": False, "label": "随机主动搭话",
            "section": "主动搭话",
            "help": "开启后在下方群组里，每隔随机时间挑一条群友近期消息主动回复、开启话题；群友回复你后走人形对话继续陪聊。需填「主动搭话群组」，且「群聊回复」要开着才能续聊。",
        },
        "proactive_chat_ids": {
            "type": "string", "default": "", "label": "主动搭话群组",
            "section": "主动搭话", "show_if": {"enable_proactive": True},
            "help": "在这些群里主动搭话，群ID用逗号分隔。必填，留空则不搭话。",
        },
        "proactive_min_minutes": {
            "type": "slider", "default": 60, "label": "间隔-最小(分钟)",
            "min": 5, "max": 720, "step": 5, "section": "主动搭话",
            "show_if": {"enable_proactive": True},
            "help": "两次主动搭话之间的最小间隔。",
        },
        "proactive_max_minutes": {
            "type": "slider", "default": 180, "label": "间隔-最大(分钟)",
            "min": 5, "max": 1440, "step": 5, "section": "主动搭话",
            "show_if": {"enable_proactive": True},
            "help": "两次主动搭话之间的最大间隔。大于最小值时在两者间取随机；否则退化为固定用最小值。",
        },
        # —— 解释命令 ——
        "enable_explain_command": {
            "type": "boolean", "default": True, "label": "启用 /ai 解释命令",
            "section": "解释命令",
        },
        "enable_explain_prompt": {
            "type": "boolean", "default": False, "label": "用解释模板",
            "section": "解释命令", "help": "开启后 /ai 用下方模板组织问题；关闭则直接把内容丢给 AI。",
            "show_if": {"enable_explain_command": True},
        },
        "explain_prompt": {
            "type": "text",
            "default": (
                "你是一个群聊消息解读助手。请根据用户【回复的消息内容】进行解释与答疑，简明清晰。\n"
                "输出结构：\n1) 这句话/这段话的主要意思\n2) 语气/态度\n3) 可能的隐含信息（没有就写'无'）\n\n"
                "需要解释的消息内容：{content}"
            ),
            "label": "解释模板", "section": "解释命令",
            "help": "用 {content} 占位被解释的内容。", "show_if": {"enable_explain_prompt": True},
        },
        # —— 范围 ——
        "white_list_chats": {
            "type": "string", "default": "", "label": "会话白名单(可选)",
            "section": "范围", "help": "只在这些会话ID生效，逗号分隔。留空 = 所有会话。",
        },
    },
}

# .ai 解释用的中性系统提示（不套人设）
_EXPLAIN_SYSTEM = (
    "你是一个中立、专业的助手，负责解答问题、解释内容和编写代码。"
    "直接给出准确、清晰的答案，不要扮演任何角色。就事论事，只回答被问到的内容；"
    "写代码时给出完整可用的代码；回答完就结束，不要画蛇添足、不要主动追问或推销后续服务。"
)


# 主动搭话用的追加系统提示（叠加在人设之后）
_PROACTIVE_SYSTEM = (
    "现在你要在群里主动搭话：下面是一条群友刚发的消息，请你像群里熟人一样自然接话，"
    "开启一段轻松的闲聊。只输出一句简短、口语化的话，别太长、别客套、别像客服，"
    "不要加引号、不要复述对方原话、不要@任何人。"
)

# 主动搭话候选消息缓冲：chat_id -> deque[{msg_id,user_id,name,text,ts}]
_recent: dict[int, deque] = {}
_RECENT_MAX = 50          # 每群最多缓存多少条
_RECENT_TTL = 3600        # 只从最近 1 小时内的消息里挑，避免回复陈旧消息


def _whitelist_ok(chat_id: int, raw: str) -> bool:
    if not raw:
        return True
    try:
        allowed = [int(c.strip()) for c in str(raw).split(",") if c.strip()]
        return chat_id in allowed
    except ValueError:
        return True


def _parse_ids(raw) -> list[int]:
    out = []
    for c in str(raw or "").replace("\n", ",").split(","):
        c = c.strip()
        if not c:
            continue
        try:
            out.append(int(c))
        except ValueError:
            pass
    return out


def _to_int(v, default: int) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _rand_gap_seconds(cfg) -> float:
    """按配置的最小/最大分钟数取一个随机间隔（秒）。"""
    lo = max(1, _to_int(cfg.get("proactive_min_minutes", 60), 60))
    hi = _to_int(cfg.get("proactive_max_minutes", 180), 180)
    if hi > lo:
        return random.uniform(lo, hi) * 60
    return lo * 60


def _hist_key(chat_id: int) -> str:
    return f"hist:{chat_id}"


async def setup(ctx):
    # ── 功能 1：人形回复（监听收到的私聊/群消息）──
    @ctx.on_message((ctx.filters.private | ctx.filters.group) & ~ctx.filters.outgoing, group=6)
    async def human_reply(client, message):
        cfg = ctx.config
        if not message.text:
            return
        fu = message.from_user
        if not fu or fu.is_self or fu.is_bot:
            return
        if not cfg.get("api_key"):
            return

        chat_id = message.chat.id
        if not _whitelist_ok(chat_id, cfg.get("white_list_chats", "")):
            return

        is_private = chat_id > 0
        if is_private:
            if not cfg.get("enable_private_chat", True):
                return
            text = message.text.strip()
        else:
            if not cfg.get("enable_group_chat", True):
                return
            # 指定群组限制：留空=所有群；填了则只在这些群生效。
            # 主动搭话的群也一并放行，保证群友回复主动消息后能续聊。
            gids = _parse_ids(cfg.get("group_chat_ids", ""))
            if gids:
                allowed = set(gids)
                if cfg.get("enable_proactive", False):
                    allowed |= set(_parse_ids(cfg.get("proactive_chat_ids", "")))
                if chat_id not in allowed:
                    return
            # 群里仅 @我 或 回复我 时触发
            me = getattr(client, "me", None)
            me_id = getattr(me, "id", None)
            me_username = (getattr(me, "username", None) or "").lower()
            is_reply_to_me = bool(
                me_id and message.reply_to_message
                and message.reply_to_message.from_user
                and message.reply_to_message.from_user.id == me_id
            )
            text_l = (message.text or "").lower()
            mentioned = bool(me_username and f"@{me_username}" in text_l)
            if not (mentioned or is_reply_to_me):
                return
            text = message.text
            if me_username:
                text = re.sub(f"@{re.escape(me_username)}", "", text, flags=re.IGNORECASE).strip()
            if not text:
                return

        # 跳过命令
        if text.startswith("/") or text.startswith("."):
            return

        try:
            max_hist = int(cfg.get("max_history", 10) or 0)
            system_prompt = cfg.get("system_prompt") or "你是一个有用的助手。"
            # 取历史
            history = ctx.kv.get(_hist_key(chat_id), []) if max_hist > 0 else []
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": text})

            try:
                reply = await generate(
                    cfg.get("api_key", ""), cfg.get("base_url", ""),
                    cfg.get("model", "gpt-3.5-turbo"), messages,
                )
            except Exception as e:  # noqa: BLE001
                ctx.log.warning("[AI] 人形回复生成失败: %r", e)
                return  # 人形回复失败静默，不打扰群
            if not reply:
                return

            await client.send_message(chat_id, reply)

            # 更新历史（裁剪到 max_hist 条 user/assistant）
            if max_hist > 0:
                history.append({"role": "user", "content": text})
                history.append({"role": "assistant", "content": reply})
                if len(history) > max_hist:
                    history = history[-max_hist:]
                ctx.kv.set(_hist_key(chat_id), history)
        except Exception:  # noqa: BLE001
            ctx.log.exception("[AI] 人形回复处理异常")

    # ── 功能 2：/ai 解释命令（自己发出）──
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-13)
    async def ai_explain(client, message):
        cfg = ctx.config
        if not re.match(r"^[/\.]ai(?:\s|$)", message.text or "", re.IGNORECASE):
            return
        if not cfg.get("enable_explain_command", True):
            return await _edit_autodel(message, "/ai 解释命令未启用")
        if not cfg.get("api_key"):
            return await _edit_autodel(message, "未配置 API Key")

        command_text = (message.text or "").strip()
        extra_text = re.sub(r"^[/\.]ai\s*", "", command_text, flags=re.IGNORECASE).strip()

        # 取被回复消息的文本/图片
        target_text, image_bytes = "", None
        reply = message.reply_to_message
        if reply:
            target_text = (reply.text or reply.caption or "").strip()
            image_bytes = await _extract_image(client, reply, ctx)

        if not target_text and not extra_text and not image_bytes:
            return await _edit_autodel(message, "请回复要解释的消息/图片，或在 /ai 后直接带文本")

        content = target_text or extra_text or "请解释这张图片表达的内容。"
        if cfg.get("enable_explain_prompt", False):
            template = cfg.get("explain_prompt") or "{content}"
            try:
                prompt = template.format(content=content)
            except (KeyError, IndexError):
                prompt = content
        else:
            prompt = content

        try:
            code_msg = await message.edit("正在解释中...")
        except Exception:
            code_msg = message

        messages = [
            {"role": "system", "content": _EXPLAIN_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        try:
            response = await generate(
                cfg.get("api_key", ""), cfg.get("base_url", ""),
                cfg.get("model", "gpt-3.5-turbo"), messages, image_bytes=image_bytes,
            )
        except Exception as e:  # noqa: BLE001
            ctx.log.warning("[AI] /ai 解释失败: %r", e)
            return await _edit_autodel(code_msg, classify_error(e))

        if not response:
            return await _edit_autodel(code_msg, "AI 未返回内容（检查模型/密钥/接口）")

        try:
            # 不传 parse_mode：客户端默认模式会解析 HTML 标签
            await code_msg.edit_text(
                "<b>消息解释</b>\n"
                f"<blockquote><b>Q：</b> {escape(content)}</blockquote>\n"
                f"<blockquote><b>A：</b> {escape(response)}</blockquote>"
            )
        except Exception:
            # 兜底：纯文本输出
            try:
                await code_msg.edit_text(f"解释\nQ: {content}\n\nA: {response}")
            except Exception:
                pass
        asyncio.create_task(_auto_del(code_msg, 60))

    # ── 功能 3：随机主动搭话 ──
    # 3a. 记录「主动搭话群组」里群友的近期消息，作为搭话候选。
    @ctx.on_message((ctx.filters.group & ctx.filters.text) & ~ctx.filters.outgoing, group=7)
    async def record_recent(client, message):
        cfg = ctx.config
        if not cfg.get("enable_proactive", False):
            return
        pids = _parse_ids(cfg.get("proactive_chat_ids", ""))
        if not pids or message.chat.id not in pids:
            return
        fu = message.from_user
        if not fu or fu.is_self or fu.is_bot:
            return
        text = (message.text or "").strip()
        if not text or text.startswith("/") or text.startswith("."):
            return
        buf = _recent.setdefault(message.chat.id, deque(maxlen=_RECENT_MAX))
        buf.append({
            "msg_id": message.id, "user_id": fu.id,
            "name": getattr(fu, "first_name", "") or "", "text": text,
            "ts": time.time(),
        })

    # 3b. 定时器：每分钟检查一次，到了随机间隔就挑一条候选消息主动回复。
    async def proactive_tick():
        cfg = ctx.config
        if not cfg.get("enable_proactive", False) or not cfg.get("api_key"):
            return
        pids = _parse_ids(cfg.get("proactive_chat_ids", ""))
        if not pids:
            return
        now = time.time()
        next_ts = ctx.kv.get("proactive_next_ts", None)
        if next_ts is None:
            # 首次：排到未来某个随机时刻，不立即发
            ctx.kv.set("proactive_next_ts", now + _rand_gap_seconds(cfg))
            return
        if now < next_ts:
            return
        # 到点：先排下一次，再尝试搭话（失败也不赖着重试）
        ctx.kv.set("proactive_next_ts", now + _rand_gap_seconds(cfg))

        apps = list(ctx.user_apps or [])
        if not apps:
            return
        client = apps[0]

        random.shuffle(pids)
        for chat_id in pids:
            buf = _recent.get(chat_id)
            cands = [m for m in (buf or []) if now - m["ts"] <= _RECENT_TTL]
            if not cands:
                continue
            target = random.choice(cands)
            system_prompt = cfg.get("system_prompt") or "你是一个有用的助手。"
            messages = [
                {"role": "system", "content": f"{system_prompt}\n\n{_PROACTIVE_SYSTEM}"},
                {"role": "user", "content": target["text"]},
            ]
            try:
                opener = await generate(
                    cfg.get("api_key", ""), cfg.get("base_url", ""),
                    cfg.get("model", "gpt-3.5-turbo"), messages,
                )
            except Exception as e:  # noqa: BLE001
                ctx.log.warning("[AI] 主动搭话生成失败: %r", e)
                return
            if not opener:
                return
            try:
                await client.send_message(chat_id, opener, reply_to_message_id=target["msg_id"])
            except Exception as e:  # noqa: BLE001
                ctx.log.warning("[AI] 主动搭话发送失败 group=%s: %r", chat_id, e)
                return
            ctx.log.info("[AI] 主动搭话 group=%s 回复 msg=%s", chat_id, target["msg_id"])

            # 把这轮开场写进历史，群友回复后续聊时有上下文
            max_hist = int(cfg.get("max_history", 10) or 0)
            if max_hist > 0:
                history = ctx.kv.get(_hist_key(chat_id), [])
                history.append({"role": "user", "content": target["text"]})
                history.append({"role": "assistant", "content": opener})
                if len(history) > max_hist:
                    history = history[-max_hist:]
                ctx.kv.set(_hist_key(chat_id), history)

            # 用掉的候选移除，避免重复回同一条
            try:
                buf.remove(target)
            except ValueError:
                pass
            return

    ctx.schedule(proactive_tick, "interval", minutes=1, id="AI主动搭话")


async def _extract_image(client, reply, ctx):
    """下载被回复消息里的图片/文档为 bytes，失败返回 None。"""
    media = getattr(reply, "photo", None) or getattr(reply, "document", None)
    if not media:
        return None
    tmp_path = None
    downloaded = None
    try:
        suffix = ".jpg"
        doc = getattr(reply, "document", None)
        if doc and getattr(doc, "file_name", None) and "." in doc.file_name:
            suffix = "." + doc.file_name.rsplit(".", 1)[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
            tmp_path = t.name
        downloaded = await client.download_media(media, file_name=tmp_path)
        with open(downloaded or tmp_path, "rb") as f:
            return f.read()
    except Exception as e:  # noqa: BLE001
        ctx.log.debug("[AI] 下载图片失败: %r", e)
        return None
    finally:
        for p in (downloaded, tmp_path):
            if p and isinstance(p, str) and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


async def _auto_del(message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def _edit_autodel(message, text: str, delay: int = 30):
    try:
        m = await message.edit(text)
    except Exception:
        m = message
    asyncio.create_task(_auto_del(m, delay))


async def teardown(ctx):
    _recent.clear()
