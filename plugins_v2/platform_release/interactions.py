"""Bot-only developer support; persistent deletion applies only to our replies."""
from __future__ import annotations

import asyncio
import copy
import html
import re
import time

from .core import BotError, PublishError, _pieces, _selected_bot, parse_targets
from .wiki import WIKI, WikiLibrary


STATE_KEY = "developer_assistant_v1"
MAX_RECORDS = 3000
MAX_QUEUE = 2000
DELETE_WINDOW = 47 * 3600
FORMAT_HELP = ("<b>问题反馈格式</b>\n请以 <code>#bug反馈</code> 开头，再写清问题：\n\n"
               "<code>#bug反馈\n版本：你使用的版本\n问题：哪里不正常\n"
               "步骤：怎样操作会出现\n报错：提示内容（请勿附 Cookie、密码或密钥）</code>")


def _int(value, default, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(value)))
    except (ValueError, TypeError, OverflowError):
        return default


def redact(text):
    """Best-effort credential scrubbing before forwarding user-provided logs."""
    text = re.sub(r"(?im)(\b(?:cookie|set-cookie|authorization)\s*[:=]\s*)[^\r\n]+",
                  r"\1[已隐藏]", str(text))
    pattern = (r"(?i)((?:[\"']?)(?:x-api-key|api[_-]?key|access[_-]?token|refresh[_-]?token|"
               r"bot[_-]?token|aeskey|password|passwd|secret|密码|密钥)(?:[\"']?)\s*[:=]\s*)"
               r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s&,;\r\n]+)")
    text = re.sub(pattern, r"\1[已隐藏]", text)
    text = re.sub(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b", "[Bot Token 已隐藏]", text)
    return re.sub(r"(https?://)[^\s/@:]+:[^\s/@]+@", r"\1[已隐藏]@", text)


class DeveloperAssistant:
    def __init__(self, ctx, publisher):
        self.ctx, self.publisher = ctx, publisher
        self.wiki = WikiLibrary(ctx)
        self.state = None
        self.lock = asyncio.Lock()
        self.delete_lock = asyncio.Lock()
        self.reply_lock = asyncio.Lock()
        self.wakeup = asyncio.Event()
        self.task = None
        self.closed = False
        self.cooldown = {}
        self.clients = {}
        self.version_cache = None

    @property
    def enabled(self):
        return any(self.ctx.config.get(key, False) for key in
                   ("keyword_enabled", "wiki_enabled", "bug_feedback_enabled"))

    async def load(self):
        if self.state is not None:
            return
        value = await self.ctx.storage.get(STATE_KEY, None)
        if value is None:
            value = {"schema": 1, "replies": [], "recent": {}, "feedback": {}}
        if (not isinstance(value, dict) or value.get("schema") != 1
                or not isinstance(value.get("replies"), list) or len(value["replies"]) > MAX_QUEUE
                or not isinstance(value.get("recent"), dict) or not isinstance(value.get("feedback"), dict)):
            raise PublishError("回复记录格式异常，请保留插件数据并检查存储；未执行自动删除")
        for record in value["replies"]:
            if (not isinstance(record, dict) or record.get("kind") != "temporary_reply"
                    or not isinstance(record.get("bot_spec"), str)
                    or not all(type(record.get(key)) is int and record[key] > 0 for key in ("bot_id", "message_id"))
                    or type(record.get("chat_id")) is not int or record["chat_id"] == 0
                    or not all(type(record.get(key)) in (int, float) and 0 < record[key] < 1e12
                               for key in ("created_at", "due_at"))):
                raise PublishError("待删记录无效，已停止清理，避免删除无关消息")
        self.state = value
        self._prune()
        await self.wiki.load()
        if self.ctx.config.get("wiki_status") != self.wiki.status_text:
            self.ctx.update_config({"wiki_status": self.wiki.status_text})

    def _prune(self):
        now = time.time()
        self.state["recent"] = {key: stamp for key, stamp in self.state["recent"].items()
                                if isinstance(stamp, (int, float)) and now - stamp < 7 * 86400}
        self.state["feedback"] = {key: record for key, record in self.state["feedback"].items()
                                  if isinstance(record, dict) and isinstance(record.get("created_at"), (int, float))
                                  and now - record["created_at"] < 30 * 86400}
        for field, timestamp in (("recent", lambda v: v), ("feedback", lambda v: v["created_at"])):
            records = self.state[field]
            if len(records) > MAX_RECORDS:
                self.state[field] = dict(sorted(records.items(), key=lambda pair: timestamp(pair[1]))[-MAX_RECORDS:])

    async def _save(self):
        await self.ctx.storage.set(STATE_KEY, copy.deepcopy(self.state))

    def start(self):
        if self.task is None and not self.closed:
            self.task = self.ctx.create_task(self.worker(), name="开发者助手·临时回复清理")

    async def close(self):
        self.closed = True
        self.wakeup.set()
        if self.task is not None and self.task is not asyncio.current_task():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        self.task = None

    async def refresh_wiki(self):
        result = await self.wiki.refresh(force=True)
        self.ctx.update_config({"wiki_status": result["message"]})
        return result

    async def _allowed(self, event):
        chat_id = getattr(event, "chat_id", None)
        if type(chat_id) is not int or chat_id == 0:
            return False
        if chat_id > 0:
            return bool(getattr(event, "is_private", False))
        raw = self.ctx.config.get("reply_chats", "").strip() or self.ctx.config.get("targets", "").strip()
        if not raw:
            return False
        targets = parse_targets(raw)
        if str(chat_id) in targets:
            return True
        if not any(target.startswith("@") for target in targets):
            return False
        chat = await event.get_chat()
        username = str(getattr(chat, "username", "") or "").lower()
        return bool(username and "@" + username in targets)

    async def _identity(self, event):
        spec, token = _selected_bot(self.ctx)
        bot_id = await self.publisher._bot_id(token)
        client = getattr(event, "client", None)
        if client is None:
            raise PublishError("未能确认消息来自平台 Bot")
        cached = self.clients.get(id(client))
        if not cached or cached[0] != bot_id or time.monotonic() - cached[1] > 600:
            me = await client.get_me()
            if not getattr(me, "bot", False) or getattr(me, "id", None) != bot_id:
                raise PublishError("接收消息的 Bot 与平台指定 Bot 不一致，未作回复")
            self.clients[id(client)] = (bot_id, time.monotonic())
        return spec, token, bot_id

    async def _claim(self, key, sender_id, *, feedback=False):
        async with self.lock:
            now = time.time()
            cooldown = _int(self.ctx.config.get("reply_cooldown", 15), 15, 0, 300)
            lane = (sender_id, "feedback" if feedback else "reply")
            if key in self.state["recent"] or key in self.state["feedback"]:
                return False
            if now - self.cooldown.get(lane, 0) < cooldown:
                return False
            if len(self.state["replies"]) >= MAX_QUEUE:
                return False
            self.state["recent"][key] = now
            self._prune()
            # Persist before external writes; an ambiguous send must not replay on restart.
            await self._save()
            self.cooldown[lane] = now
            if len(self.cooldown) > MAX_RECORDS:
                self.cooldown = {user: stamp for user, stamp in self.cooldown.items() if now - stamp < 300}
            return True

    @staticmethod
    def _thread(event):
        reply = getattr(event.message, "reply_to", None)
        if not reply:
            return None
        forum = getattr(reply, "forum_topic", False) or getattr(getattr(event, "chat", None), "forum", False)
        if not forum:
            return None
        top = getattr(reply, "reply_to_top_id", None)
        if not top and getattr(reply, "forum_topic", False):
            top = getattr(reply, "reply_to_msg_id", None)
        # General topic uses the ordinary chat endpoint. ID 1 is not accepted
        # as a message_thread_id by Bot API in some Telegram deployments.
        return top if type(top) is int and top > 1 else None

    async def _reply(self, event, identity, markup):
        async with self.reply_lock:
            await self._reply_locked(event, identity, markup)

    async def _reply_locked(self, event, identity, markup):
        spec, token, bot_id = identity
        seconds = _int(self.ctx.config.get("reply_delete_seconds", 60), 60, 0, 86400)
        if seconds and len(self.state["replies"]) >= MAX_QUEUE:
            raise PublishError("临时回复待删队列已满，暂停新回复，等待清理完成")
        payload = {"chat_id": event.chat_id, "text": markup, "parse_mode": "HTML",
                   "link_preview_options": {"is_disabled": True},
                   "reply_parameters": {"message_id": event.id, "allow_sending_without_reply": False}}
        thread = self._thread(event)
        if thread:
            payload["message_thread_id"] = thread
        sent = await self.publisher._bot(token, "sendMessage", payload)
        if not isinstance(sent, dict) or type(sent.get("message_id")) is not int or sent["message_id"] <= 0:
            raise BotError("临时答复未返回有效消息 ID", uncertain=True)
        if seconds:
            async with self.lock:
                now = time.time()
                self.state["replies"].append({"kind": "temporary_reply", "bot_spec": spec, "bot_id": bot_id,
                                               "chat_id": event.chat_id, "message_id": sent["message_id"],
                                               "created_at": now, "due_at": now + seconds, "attempts": 0})
                try:
                    await self._save()
                except Exception:
                    # Keep the in-memory entry so the worker can retry persistence/cleanup.
                    self.ctx.log.warning("临时回复已发送，但清理记录未保存；重启后可能需要手动删除")
                self.wakeup.set()

    def _keyword(self, text):
        if not self.ctx.config.get("keyword_enabled", False):
            return None
        rules = self.ctx.config.get("keyword_rules", [])
        if not isinstance(rules, list) or len(rules) > 100:
            raise PublishError("关键词规则格式无效或超过 100 条，请检查配置")
        value = text.strip().casefold()
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            keywords = rule.get("keywords", "")
            reply = rule.get("reply", "")
            if not isinstance(keywords, str) or not isinstance(reply, str):
                continue
            words = [word.strip().casefold() for word in re.split(r"[,，\n]+", keywords) if word.strip()]
            mode = rule.get("match", "exact")
            if mode not in {"exact", "contains"} or not reply.strip():
                continue
            if any(value == word if mode == "exact" else word in value for word in words):
                if len(reply) > 12000:
                    raise PublishError("关键词回复超过 12000 字，请缩短回复内容")
                return reply
        return None

    async def _render_keyword(self, reply):
        if "{version}" in reply or "{release_url}" in reply:
            async with self.publisher.lock:
                await self.publisher.load()
                if not self.version_cache or time.time() - self.version_cache[0] > 300:
                    release = await self.publisher._fetch_latest()  # Read only; never check()/publish.
                    self.version_cache = (time.time(), bool(self.ctx.config.get("include_prereleases")), release)
                elif self.version_cache[1] != bool(self.ctx.config.get("include_prereleases")):
                    release = await self.publisher._fetch_latest()
                    self.version_cache = (time.time(), bool(self.ctx.config.get("include_prereleases")), release)
                release = self.version_cache[2]
            reply = reply.replace("{version}", release["tag"]).replace("{release_url}", release["url"])
        return reply.replace("{wiki_url}", WIKI)

    async def _owner(self):
        raw = str(getattr(self.ctx.settings, "default_bot_chat_id", "") or "").strip()
        if not raw:
            raw = str(await self.ctx.accounts.default_notification_target() or "").strip()
        if not re.fullmatch(r"[1-9]\d{0,18}", raw):
            raise PublishError("无法确认主人私聊接收人，请在平台填写正数用户 ID，并先私聊 Bot 发送 /start")
        return int(raw)

    async def _feedback(self, event, identity, key, sender, body):
        spec, token, bot_id = identity
        try:
            owner = await self._owner()
        except Exception:
            self.ctx.log.warning("问题反馈未投递：请检查平台主人私聊接收人，并先向 Bot 发送 /start")
            await self._reply(event, identity, "反馈未送达：管理员尚未配置可用的私聊接收人，请直接联系管理员。")
            return
        chat = await event.get_chat()
        name = " ".join(str(getattr(sender, field, "") or "").strip() for field in ("first_name", "last_name")).strip()
        name = name or str(event.sender_id)
        username = str(getattr(sender, "username", "") or "")
        title = str(getattr(chat, "title", "") or "Bot 私聊")
        link = ""
        group_username = str(getattr(chat, "username", "") or "")
        if event.chat_id < 0:
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", group_username):
                link = f"https://t.me/{group_username}/{event.id}"
            elif str(event.chat_id).startswith("-100") and (getattr(chat, "megagroup", False) or getattr(event, "is_channel", False)):
                link = f"https://t.me/c/{str(event.chat_id)[4:]}/{event.id}"
        header = ("<b>收到 Bug 反馈</b>\n\n提交者：" + html.escape(name)
                  + (" (@" + html.escape(username) + ")" if username else "")
                  + "\n用户 ID：<code>" + str(event.sender_id) + "</code>\n来源：" + html.escape(title)
                  + "\n会话 ID：<code>" + str(event.chat_id) + "</code>")
        if link:
            header += '\n<a href="' + link + '">查看原消息</a>'
        clean = redact(body)
        parts = list(_pieces(clean, 2400))
        async with self.lock:
            record = {"created_at": time.time(), "bot_spec": spec, "bot_id": bot_id,
                      "status": "sending", "sent": [], "parts": len(parts), "owner": owner}
            self.state["feedback"][key] = record
            await self._save()
        try:
            for index, part in enumerate(parts):
                prefix = header if index == 0 else "<b>Bug 反馈（续 " + str(index + 1) + "）</b>"
                result = await self.publisher._bot(token, "sendMessage", {
                    "chat_id": owner, "text": prefix + "\n\n" + html.escape(part),
                    "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}})
                if not isinstance(result, dict) or type(result.get("message_id")) is not int or result["message_id"] <= 0:
                    raise BotError("反馈未返回有效消息 ID", uncertain=True)
                async with self.lock:
                    record["sent"].append(result["message_id"])
                    await self._save()
            async with self.lock:
                record["status"] = "delivered"
                await self._save()
        except Exception as exc:
            async with self.lock:
                record["status"] = "uncertain" if not isinstance(exc, BotError) or exc.uncertain else "failed"
                try:
                    await self._save()
                except Exception:
                    pass
            self.ctx.log.warning("问题反馈投递未获完整确认（%s），未自动重发；请检查 Bot 主人私聊", type(exc).__name__)
            await self._reply(event, identity, "反馈未确认完整送达，请直接联系管理员；为避免重复，不会自动重发这条反馈。")
            return
        await self._reply(event, identity, "反馈已送达管理员，请等待处理。")

    async def handle(self, event):
        if not self.enabled or self.closed:
            return
        message = getattr(event, "message", None)
        text = getattr(event, "raw_text", "")
        sender_id = getattr(event, "sender_id", None)
        if (message is None or not isinstance(text, str) or not text.strip() or len(text) > 16000
                or type(sender_id) is not int or sender_id <= 0 or type(getattr(event, "id", None)) is not int
                or getattr(message, "out", False) or getattr(event, "out", False) or getattr(message, "post", False)
                or getattr(message, "action", None) or getattr(message, "edit_date", None)):
            return
        try:
            await self.load()
            if not await self._allowed(event):
                return
            sender = await event.get_sender()
            if sender is None or getattr(sender, "bot", False) or getattr(sender, "is_self", False):
                return
            identity = await self._identity(event)
            if sender_id == identity[2]:
                return
            text = text.strip()
            feedback = bool(self.ctx.config.get("bug_feedback_enabled", False))
            is_feedback = feedback and text.startswith("#bug反馈")
            custom = None if is_feedback else self._keyword(text)
            bug_help = feedback and bool(re.search(r"(?i)\bbug\b|反馈|报错|无法|没反应|出错|失败|故障", text))
            question = bool(getattr(event, "is_private", False) or re.search(
                r"[?？]|怎么|如何|为何|为什么|哪里|什么|能否|是否|能不能|求助|请问|安装|部署|配置|设置|报错|错误|失败", text))
            wiki = bool(self.ctx.config.get("wiki_enabled", False)) and question and not text.startswith("/")
            if not (is_feedback or custom is not None or bug_help or wiki):
                return
            key = f"{identity[2]}:{event.chat_id}:{event.id}"
            body = text[len("#bug反馈"):].strip(" \r\n:：") if is_feedback else ""
            if not await self._claim(key, sender_id, feedback=is_feedback and bool(body)):
                return
            if is_feedback:
                if not body:
                    await self._reply(event, identity, FORMAT_HELP)
                else:
                    await self._feedback(event, identity, key, sender, body)
            elif custom is not None:
                try:
                    reply = await self._render_keyword(custom)
                except PublishError:
                    await self._reply(event, identity, "暂时无法确认最新版本，请稍后再试；未使用旧版本作为答案。")
                    return
                for part in _pieces(reply, 3500):
                    await self._reply(event, identity, html.escape(part))
            elif bug_help and not wiki:
                await self._reply(event, identity, FORMAT_HELP)
            elif wiki:
                answer = await self.wiki.answer(text)
                status = self.wiki.status_text
                if self.ctx.config.get("wiki_status") != status:
                    self.ctx.update_config({"wiki_status": status})
                if bug_help:
                    answer += "\n\n提交问题请以 <code>#bug反馈</code> 开头，附版本、步骤和报错（请勿附密钥）。"
                await self._reply(event, identity, answer)
        except Exception as exc:
            # Never log user text, token-containing URLs, or raw transport errors.
            self.ctx.log.warning("开发者助手回复未完成（%s），请检查 Bot、网络与插件存储", type(exc).__name__)

    async def delete_due(self):
        await self.load()
        async with self.delete_lock:
            now = time.time()
            batch = [record for record in self.state["replies"] if record["due_at"] <= now][:50]
            specs = {str(spec.id): str(spec.token or "").strip() for spec in self.ctx.settings.bot_specs()}
            limited = set()
            for record in batch:
                if record["bot_id"] in limited:
                    continue
                done = now - record["created_at"] >= DELETE_WINDOW
                if done:
                    self.ctx.log.warning("临时回复已超出自动清理时限，请在原会话手动删除")
                else:
                    try:
                        token = specs.get(record["bot_spec"], "")
                        if not token or await self.publisher._bot_id(token) != record["bot_id"]:
                            raise PublishError("原 Bot 已移除或身份改变，保留记录，不使用其他 Bot 清理")
                        result = await self.publisher._bot(token, "deleteMessage", {
                            "chat_id": record["chat_id"], "message_id": record["message_id"]})
                        if result is not True:
                            raise PublishError("Telegram 未确认删除临时回复")
                        done = True
                    except Exception as exc:
                        if isinstance(exc, BotError) and "message to delete not found" in str(exc).lower():
                            done = True
                        else:
                            retry = max(30, min(3600, 30 * 2 ** min(7, record.get("attempts", 0))))
                            if isinstance(exc, BotError) and exc.retry_after:
                                retry = max(retry, exc.retry_after)
                                limited.add(record["bot_id"])
                                for pending in self.state["replies"]:
                                    if pending["bot_id"] == record["bot_id"]:
                                        pending["due_at"] = max(pending["due_at"], now + retry)
                            record["attempts"] = record.get("attempts", 0) + 1
                            record["due_at"] = now + retry
                            if record["attempts"] in {1, 4}:
                                self.ctx.log.warning("临时回复清理暂未完成（%s），稍后重试", type(exc).__name__)
                async with self.lock:
                    if done and record in self.state["replies"]:
                        self.state["replies"].remove(record)
                    await self._save()

    async def worker(self):
        while not self.closed:
            self.wakeup.clear()
            try:
                await self.delete_due()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.ctx.log.warning("临时回复清理记录暂不可用（%s），稍后重试", type(exc).__name__)
                try:
                    await asyncio.wait_for(self.wakeup.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass
                continue
            if self.closed:
                return
            next_due = min((record["due_at"] for record in self.state["replies"]), default=None)
            if next_due is None:
                await self.wakeup.wait()
            else:
                try:
                    await asyncio.wait_for(self.wakeup.wait(), timeout=max(0.05, next_due - time.time()))
                except asyncio.TimeoutError:
                    pass
