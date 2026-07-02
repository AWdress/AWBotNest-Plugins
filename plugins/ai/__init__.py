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
import re
import tempfile
from html import escape

from ._engine import generate, classify_error

__plugin__ = {
    "name": "AI 助手",
    "id": "ai",
    "version": "1.0.2",
    "author": "AWdress",
    "description": "私聊/群@你时 AI 人形对话（带记忆）；回复消息发 /ai 让 AI 解释或解答（支持图片）。",
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
        "system_prompt": {
            "type": "text", "default": "你是一个有用的助手。", "label": "人设(系统提示词)",
            "section": "人形回复",
        },
        "max_history": {
            "type": "slider", "default": 10, "label": "记忆轮数",
            "min": 0, "max": 40, "step": 1, "section": "人形回复",
            "help": "每个会话保留多少条历史消息（含系统提示）。0 = 不记忆。",
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


def _whitelist_ok(chat_id: int, raw: str) -> bool:
    if not raw:
        return True
    try:
        allowed = [int(c.strip()) for c in str(raw).split(",") if c.strip()]
        return chat_id in allowed
    except ValueError:
        return True


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
    pass
