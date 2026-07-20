# =============================================================================
# AWBotNest 插件：AI 助手（ai）
#
# 用你的用户账号提供两种 AI 能力：
#   1. 人形回复：私聊直接对话；群里 @你 或回复你的消息时对话（带上下文记忆）。
#   2. /ai 解释：回复一条消息（或图片）再发 /ai，让 AI 解释/解答（单次，无记忆）。
#
# 自洽实现：直接调用 OpenAI 兼容接口（openai 库），对话历史存 ctx.kv，不依赖平台 DI 容器。
# Vue 模式：配置/对话记忆管理界面由自带 Vue 组件渲染（frontend/src/Config.vue），
# 配置默认值集中在 DEFAULTS，后端接口见 setup 里的 ctx.on_api。
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
    "version": "1.0.6",
    "author": "AWdress",
    "description": "私聊/群@你时 AI 人形对话（带记忆，群聊可指定群组）；可选随机主动搭话开启话题；回复消息发 /ai 让 AI 解释或解答（支持图片）。自带 Vue 配置界面 + 对话记忆管理。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/ai.png",
    "changelog": "v1.0.6 更新插件 Logo\n- 使用 AI 助手专属图片作为插件卡片与市场图标\n\nv1.0.5 修复主动搭话定时任务\n- 未启用主动搭话时不再注册每分钟检查任务",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
}

# vue 模式无 config_schema：配置默认值集中在此，供后端读取（前端 Config.vue 用同一套默认
# 初始化表单）。后端各处 ctx.config.get(key, 默认) 已带默认值，此处仅作文档/单点参考。
DEFAULTS = {
    "api_key": "", "base_url": "", "model": "gpt-3.5-turbo",
    "enable_private_chat": True, "enable_group_chat": True, "group_chat_ids": "",
    "system_prompt": (
        "# Role\n你是一个相处了很久的普通网友。\n\n"
        "# Rules\n"
        "1. 语气口语化、随性、接地气，就像在微信或QQ上聊天。\n"
        "2. 每次回复必须精简，严禁长篇大论。\n"
        "3. 绝对不能超过 20 个字。\n"
        "4. 绝对不要在回复中模仿、复述或带入用户的动作动作。\n"
        "5. 偶尔可以在句末加一个合适的 emoji（如 😂、🤷‍♂️、👀），不要过多。"
    ),
    "max_history": 10,
    "enable_proactive": False, "proactive_chat_ids": "",
    "proactive_min_minutes": 60, "proactive_max_minutes": 180,
    "enable_explain_command": True, "enable_explain_prompt": False,
    "explain_prompt": (
        "你是一个群聊消息解读助手。请根据用户【回复的消息内容】进行解释与答疑，简明清晰。\n"
        "输出结构：\n1) 这句话/这段话的主要意思\n2) 语气/态度\n3) 可能的隐含信息（没有就写'无'）\n\n"
        "需要解释的消息内容：{content}"
    ),
    "white_list_chats": "",
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

    # 关闭主动搭话时不要注册空跑任务，也避免系统状态页显示未启用的功能。
    # Vue 配置保存不会动态增删 scheduler；开启后重载/重新启用插件即可注册。
    if ctx.config.get("enable_proactive", False):
        ctx.schedule(proactive_tick, "interval", minutes=1, id="AI主动搭话")

    # ── 前端(Config.vue)用的后端接口 ──
    @ctx.on_api("/test", methods=["POST"])
    async def _api_test(req):
        cfg = ctx.config
        if not cfg.get("api_key"):
            return {"ok": False, "message": "未配置 API Key"}
        try:
            reply = await generate(
                cfg.get("api_key", ""), cfg.get("base_url", ""),
                cfg.get("model", "gpt-3.5-turbo"),
                [{"role": "user", "content": "ping"}],
            )
            return {"ok": True, "model": cfg.get("model", ""),
                    "message": "连接正常" + (f"（回复：{reply[:30]}）" if reply else "")}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": classify_error(e)}

    @ctx.on_api("/histories", methods=["GET"])
    async def _api_histories(req):
        items = []
        try:
            keys = [k for k in ctx.kv.keys() if str(k).startswith("hist:")]
        except Exception:  # noqa: BLE001
            keys = []
        for k in keys:
            try:
                chat_id = int(str(k)[len("hist:"):])
            except (ValueError, TypeError):
                continue
            hist = ctx.kv.get(k, []) or []
            if not isinstance(hist, list) or not hist:
                continue
            last = ""
            for m in reversed(hist):
                if isinstance(m, dict) and m.get("content"):
                    last = str(m["content"])
                    break
            items.append({
                "chat_id": chat_id, "is_private": chat_id > 0,
                "count": len(hist), "last": last[:60],
            })
        items.sort(key=lambda x: x["count"], reverse=True)
        # 下次主动搭话时刻（epoch → 本地时间字符串）
        proactive_next = ""
        nxt = ctx.kv.get("proactive_next_ts", None)
        if nxt:
            try:
                from datetime import datetime
                proactive_next = datetime.fromtimestamp(float(nxt)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:  # noqa: BLE001
                proactive_next = ""
        return {"items": items, "proactive_next": proactive_next}

    @ctx.on_api("/history", methods=["GET"])
    async def _api_history(req):
        raw = (req.query.get("chat_id") if hasattr(req, "query") else None) or ""
        try:
            chat_id = int(raw)
        except (ValueError, TypeError):
            return {"chat_id": raw, "messages": []}
        hist = ctx.kv.get(_hist_key(chat_id), []) or []
        msgs = [{"role": m.get("role", ""), "content": m.get("content", "")}
                for m in hist if isinstance(m, dict)]
        return {"chat_id": chat_id, "messages": msgs}

    @ctx.on_api("/history/clear", methods=["POST"])
    async def _api_history_clear(req):
        data = req.json or {}
        if data.get("all"):
            try:
                keys = [k for k in ctx.kv.keys() if str(k).startswith("hist:")]
            except Exception:  # noqa: BLE001
                keys = []
            for k in keys:
                try:
                    ctx.kv.delete(k)
                except Exception:  # noqa: BLE001
                    pass
            return {"ok": True, "cleared": len(keys)}
        chat_id = data.get("chat_id")
        if chat_id is None:
            return {"ok": False, "message": "缺少 chat_id"}
        try:
            ctx.kv.delete(_hist_key(int(chat_id)))
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True}


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
